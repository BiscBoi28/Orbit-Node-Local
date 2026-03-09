#!/usr/bin/env python3
"""
Phase 1 — Apply Schema (D2)
=============================
Creates all uniqueness constraints, indexes, and the SchemaVersion node for
the ORBIT.CyberGraph-Node graph.  Every statement uses IF NOT EXISTS so
re-running is safe (idempotent).

Existence constraints are only applied on Neo4j Enterprise edition;
Community edition skips them silently with a warning.

Exit code 0 = all applied successfully.
Exit code 1 = one or more statements failed.
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

logger = logging.getLogger("apply_schema")
logger.setLevel(LOG_LEVEL)

fh = logging.FileHandler(os.path.join(LOG_DIR, "01_apply_schema.log"))
fh.setLevel(LOG_LEVEL)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(LOG_LEVEL)
fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s")
fh.setFormatter(fmt)
ch.setFormatter(fmt)
logger.addHandler(fh)
logger.addHandler(ch)


# ── Schema Definitions ──────────────────────────────────────────────────────

# Uniqueness constraints: (label, property, constraint_name)
UNIQUENESS_CONSTRAINTS = [
    ("Host",            "host_id",          "host_host_id_unique"),
    ("Vulnerability",   "cve_id",           "vulnerability_cve_id_unique"),
    ("DataAsset",       "asset_hash",       "dataasset_asset_hash_unique"),
    ("ActionCard",      "action_id",        "actioncard_action_id_unique"),
    ("Analyst",         "analyst_id",       "analyst_analyst_id_unique"),
    ("Threat",          "threat_id",        "threat_threat_id_unique"),
    ("Subscription",    "subscription_id",  "subscription_subscription_id_unique"),
    ("DeltaEvent",      "delta_id",         "deltaevent_delta_id_unique"),
    ("SchemaVersion",   "name",             "schemaversion_name_unique"),
    ("ExecutionEvent",  "exec_id",          "executionevent_exec_id_unique"),
]

# Existence constraints (Enterprise only): (label, property, constraint_name)
EXISTENCE_CONSTRAINTS = [
    ("Host",          "hostname", "host_hostname_exists"),
    ("Vulnerability", "cve_id",   "vulnerability_cve_id_exists"),
]

# Indexes: (label, property, index_name)
INDEXES = [
    ("Host",         "hostname",          "idx_host_hostname"),
    ("Host",         "ip",                "idx_host_ip"),
    ("Service",      "name",              "idx_service_name"),
    ("DataAsset",    "sensitivity_score", "idx_dataasset_sensitivity_score"),
    ("DataAsset",    "crown_jewel",       "idx_dataasset_crown_jewel"),
    ("ActionCard",   "status",            "idx_actioncard_status"),
    ("Threat",       "severity",          "idx_threat_severity"),
    ("Subscription", "status",            "idx_subscription_status"),
    ("DeltaEvent",   "sent_status",       "idx_deltaevent_sent_status"),
]

SCHEMA_VERSION_CYPHER = """
MERGE (s:SchemaVersion {name: 'orbit-node'})
SET s.version = '1.1.0',
    s.updated = datetime(),
    s.notes   = 'Initial implementation: Subscription, DeltaEvent, crown_jewel, scan_status, 6-state ActionCard lifecycle, standardised last_updated'
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_edition(session) -> str:
    """Return 'community' or 'enterprise' (lowercase)."""
    result = session.run(
        "CALL dbms.components() YIELD edition RETURN edition"
    )
    record = result.single()
    return record["edition"].lower() if record else "unknown"


def _run_statement(session, cypher: str, description: str) -> bool:
    """Run a single Cypher statement.  Returns True on success."""
    try:
        session.run(cypher).consume()
        logger.info("✓  %s", description)
        return True
    except Exception as exc:
        logger.error("✗  %s — %s", description, exc)
        return False


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")

    logger.info("=" * 60)
    logger.info("ORBIT.CyberGraph-Node — Apply Schema (Phase 1)")
    logger.info("=" * 60)

    driver = None
    failures = 0

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()

        with driver.session() as session:
            edition = _get_edition(session)
            logger.info("Neo4j edition: %s", edition)

            # ── Uniqueness constraints ───────────────────────────────────
            logger.info("--- Uniqueness Constraints ---")
            for label, prop, name in UNIQUENESS_CONSTRAINTS:
                cypher = (
                    f"CREATE CONSTRAINT {name} IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                )
                if not _run_statement(session, cypher, f"UNIQUE {label}.{prop}"):
                    failures += 1

            # ── Existence constraints (Enterprise only) ──────────────────
            logger.info("--- Existence Constraints ---")
            if edition == "enterprise":
                for label, prop, name in EXISTENCE_CONSTRAINTS:
                    cypher = (
                        f"CREATE CONSTRAINT {name} IF NOT EXISTS "
                        f"FOR (n:{label}) REQUIRE n.{prop} IS NOT NULL"
                    )
                    if not _run_statement(session, cypher, f"EXISTS {label}.{prop}"):
                        failures += 1
            else:
                logger.warning(
                    "⚠  Skipping existence constraints — "
                    "requires Enterprise edition (current: %s)",
                    edition,
                )

            # ── Indexes ──────────────────────────────────────────────────
            logger.info("--- Indexes ---")
            for label, prop, name in INDEXES:
                cypher = (
                    f"CREATE INDEX {name} IF NOT EXISTS "
                    f"FOR (n:{label}) ON (n.{prop})"
                )
                if not _run_statement(session, cypher, f"INDEX {label}({prop})"):
                    failures += 1

            # ── SchemaVersion ────────────────────────────────────────────
            logger.info("--- SchemaVersion ---")
            if not _run_statement(
                session, SCHEMA_VERSION_CYPHER, "SchemaVersion → 1.1.0"
            ):
                failures += 1

    except Exception as exc:
        logger.error("✗  Fatal error: %s", exc)
        return 1
    finally:
        if driver:
            driver.close()

    # ── Result ───────────────────────────────────────────────────────────
    if failures > 0:
        logger.error("Schema apply finished with %d failure(s).", failures)
        return 1

    logger.info("=" * 60)
    logger.info("✓  All schema statements applied successfully.")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
