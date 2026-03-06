#!/usr/bin/env python3
"""
Phase 0 — Environment Verification
====================================
Confirms Neo4j is reachable, APOC is loaded, and driver/server versions match
expectations before any schema or data work begins.

Exit code 0 = all checks passed.
Exit code 1 = one or more checks failed.
"""

import os
import sys
import logging

from dotenv import load_dotenv
from neo4j import GraphDatabase
import neo4j

# ── Logging setup ────────────────────────────────────────────────────────────
load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("LOG_DIR", ".tmp/logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("verify_environment")
logger.setLevel(LOG_LEVEL)

# File handler
fh = logging.FileHandler(os.path.join(LOG_DIR, "00_verify_environment.log"))
fh.setLevel(LOG_LEVEL)

# Console handler
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(LOG_LEVEL)

fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s")
fh.setFormatter(fmt)
ch.setFormatter(fmt)
logger.addHandler(fh)
logger.addHandler(ch)


# ── Main verification ────────────────────────────────────────────────────────
def main() -> int:
    """Run all environment checks.  Returns 0 on success, 1 on failure."""

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")

    logger.info("=" * 60)
    logger.info("ORBIT.CyberGraph-Node — Environment Verification (Phase 0)")
    logger.info("=" * 60)

    # ── 1. Driver version ────────────────────────────────────────────────
    driver_version = neo4j.__version__
    logger.info("Python neo4j driver version: %s", driver_version)

    # ── 2. Connect and verify connectivity ───────────────────────────────
    logger.info("Connecting to %s as user '%s' ...", uri, user)
    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        logger.info("✓  Neo4j connectivity verified.")
    except Exception as exc:
        logger.error("✗  Connectivity check FAILED: %s", exc)
        return 1

    try:
        # ── 3. Server version via dbms.components() ──────────────────────
        with driver.session() as session:
            result = session.run(
                "CALL dbms.components() YIELD name, versions, edition"
            )
            record = result.single()

            if record is None:
                logger.error("✗  dbms.components() returned no rows.")
                return 1

            server_name = record["name"]
            server_versions = record["versions"]   # list of version strings
            server_edition = record["edition"]
            server_version = server_versions[0] if server_versions else "unknown"

            logger.info(
                "Server: %s %s (%s)", server_name, server_version, server_edition
            )

            # Assert major version is 5
            major = server_version.split(".")[0]
            if major != "5":
                logger.error(
                    "✗  Expected Neo4j server major version 5, got %s", major
                )
                return 1
            logger.info("✓  Neo4j server major version is 5.")

        # ── 4. APOC availability ─────────────────────────────────────────
        with driver.session() as session:
            result = session.run("RETURN apoc.version() AS v")
            record = result.single()

            if record is None or record["v"] is None:
                logger.error("✗  APOC is NOT loaded (apoc.version() returned null).")
                return 1

            apoc_version = record["v"]
            logger.info("✓  APOC loaded — version: %s", apoc_version)

    except Exception as exc:
        logger.error("✗  Verification query failed: %s", exc)
        return 1
    finally:
        if driver:
            driver.close()

    # ── Summary ──────────────────────────────────────────────────────────
    logger.info("-" * 60)
    logger.info("SUMMARY")
    logger.info("  Neo4j server : %s %s (%s)", server_name, server_version, server_edition)
    logger.info("  Python driver: %s", driver_version)
    logger.info("  APOC         : %s", apoc_version)
    logger.info("-" * 60)
    logger.info("✓  All environment checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
