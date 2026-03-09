#!/usr/bin/env python3
"""
Phase 1 — Verify Schema (D2)
==============================
Queries Neo4j to confirm every expected constraint, index, and the
SchemaVersion node are present.  Prints ✓/✗ per item and exits with
code 1 if any assertion fails.

Exit code 0 = all checks passed.
Exit code 1 = one or more checks failed.
"""

import os
import sys
import logging

from dotenv import load_dotenv
from neo4j import GraphDatabase

# ── Env & Logging ────────────────────────────────────────────────────────────
load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("LOG_DIR", ".tmp/logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("verify_schema")
logger.setLevel(LOG_LEVEL)

fh = logging.FileHandler(os.path.join(LOG_DIR, "02_verify_schema.log"))
fh.setLevel(LOG_LEVEL)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(LOG_LEVEL)
fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s")
fh.setFormatter(fmt)
ch.setFormatter(fmt)
logger.addHandler(fh)
logger.addHandler(ch)


# ── Expected Items ───────────────────────────────────────────────────────────

# Uniqueness constraints we always expect
EXPECTED_UNIQUENESS = [
    ("host_host_id_unique",                     "Host",           "host_id"),
    ("vulnerability_cve_id_unique",             "Vulnerability",  "cve_id"),
    ("dataasset_asset_hash_unique",             "DataAsset",      "asset_hash"),
    ("actioncard_action_id_unique",             "ActionCard",     "action_id"),
    ("analyst_analyst_id_unique",               "Analyst",        "analyst_id"),
    ("threat_threat_id_unique",                 "Threat",         "threat_id"),
    ("subscription_subscription_id_unique",     "Subscription",   "subscription_id"),
    ("deltaevent_delta_id_unique",              "DeltaEvent",     "delta_id"),
    ("schemaversion_name_unique",               "SchemaVersion",  "name"),
    ("executionevent_exec_id_unique",           "ExecutionEvent", "exec_id"),
]

# Existence constraints (Enterprise only)
EXPECTED_EXISTENCE = [
    ("host_hostname_exists",          "Host",          "hostname"),
    ("vulnerability_cve_id_exists",   "Vulnerability", "cve_id"),
]

# Indexes
EXPECTED_INDEXES = [
    ("idx_host_hostname",                "Host",         "hostname"),
    ("idx_host_ip",                      "Host",         "ip"),
    ("idx_service_name",                 "Service",      "name"),
    ("idx_dataasset_sensitivity_score",  "DataAsset",    "sensitivity_score"),
    ("idx_dataasset_crown_jewel",        "DataAsset",    "crown_jewel"),
    ("idx_actioncard_status",            "ActionCard",   "status"),
    ("idx_threat_severity",              "Threat",       "severity"),
    ("idx_subscription_status",          "Subscription", "status"),
    ("idx_deltaevent_sent_status",       "DeltaEvent",   "sent_status"),
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_edition(session) -> str:
    result = session.run(
        "CALL dbms.components() YIELD edition RETURN edition"
    )
    record = result.single()
    return record["edition"].lower() if record else "unknown"


def _get_constraint_names(session) -> set:
    """Return set of all constraint names currently in the database."""
    result = session.run("SHOW CONSTRAINTS YIELD name RETURN name")
    return {record["name"] for record in result}


def _get_index_names(session) -> set:
    """Return set of all user-created index names currently in the database."""
    result = session.run("SHOW INDEXES YIELD name RETURN name")
    return {record["name"] for record in result}


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")

    logger.info("=" * 60)
    logger.info("ORBIT.CyberGraph-Node — Verify Schema (Phase 1)")
    logger.info("=" * 60)

    driver = None
    failures = 0

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()

        with driver.session() as session:
            edition = _get_edition(session)
            existing_constraints = _get_constraint_names(session)
            existing_indexes = _get_index_names(session)

            # ── Uniqueness Constraints ───────────────────────────────────
            logger.info("--- Uniqueness Constraints ---")
            for name, label, prop in EXPECTED_UNIQUENESS:
                if name in existing_constraints:
                    logger.info("✓  UNIQUE %s.%s  (%s)", label, prop, name)
                else:
                    logger.error("✗  UNIQUE %s.%s  (%s) — MISSING", label, prop, name)
                    failures += 1

            # ── Existence Constraints (Enterprise only) ──────────────────
            logger.info("--- Existence Constraints ---")
            if edition == "enterprise":
                for name, label, prop in EXPECTED_EXISTENCE:
                    if name in existing_constraints:
                        logger.info("✓  EXISTS %s.%s  (%s)", label, prop, name)
                    else:
                        logger.error(
                            "✗  EXISTS %s.%s  (%s) — MISSING", label, prop, name
                        )
                        failures += 1
            else:
                logger.warning(
                    "⚠  Skipping existence constraint checks — "
                    "Community edition (expected)"
                )

            # ── Indexes ──────────────────────────────────────────────────
            logger.info("--- Indexes ---")
            for name, label, prop in EXPECTED_INDEXES:
                if name in existing_indexes:
                    logger.info("✓  INDEX %s(%s)  (%s)", label, prop, name)
                else:
                    logger.error(
                        "✗  INDEX %s(%s)  (%s) — MISSING", label, prop, name
                    )
                    failures += 1

            # ── SchemaVersion ────────────────────────────────────────────
            logger.info("--- SchemaVersion ---")
            result = session.run(
                "MATCH (s:SchemaVersion {name: 'orbit-node'}) "
                "RETURN s.version AS version"
            )
            record = result.single()
            if record is None:
                logger.error("✗  SchemaVersion node 'orbit-node' — MISSING")
                failures += 1
            elif record["version"] != "1.1.0":
                logger.error(
                    "✗  SchemaVersion = '%s' — expected '1.1.0'",
                    record["version"],
                )
                failures += 1
            else:
                logger.info("✓  SchemaVersion = 1.1.0")

    except Exception as exc:
        logger.error("✗  Fatal error: %s", exc)
        return 1
    finally:
        if driver:
            driver.close()

    # ── Result ───────────────────────────────────────────────────────────
    logger.info("=" * 60)
    if failures > 0:
        logger.error(
            "Schema verification FAILED — %d issue(s) found.", failures
        )
        return 1

    logger.info("✓  All schema checks passed.")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
