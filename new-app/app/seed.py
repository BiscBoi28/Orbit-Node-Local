"""
Seed Script — Populate Neo4j from bank CSV and Wazuh fixtures.

Usage:
    python -m app.seed

Steps:
  1. Apply Neo4j schema (idempotent)
  2. Ingest hosts from bank CSV (via Wazuh fixture format)
  3. Ingest services/applications from CSV software column
  4. Ingest sample vulnerabilities from fixtures
"""

import csv
import logging
import sys

from app.config import BANK_CSV_PATH, LOG_LEVEL
from app.graph import (
    get_driver,
    close_driver,
    apply_schema,
    ingest_host,
    ingest_service,
    ingest_application,
    ingest_vulnerability,
)
from app.stubs.wazuh_source import FixtureWazuhSource

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(name)s %(levelname)s  %(message)s",
)
logger = logging.getLogger(__name__)


def seed_from_csv(driver):
    """Ingest hosts and their technologies from ORBIT_simulated_bank.csv."""
    with open(BANK_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hostname = row.get("Hostname", "")
            if not hostname:
                continue

            # Ingest host
            host_payload = {
                "host_id": hostname,
                "hostname": hostname,
                "ip": "",
                "os": row.get("Operating_System", ""),
                "agent_version": "",
                "source": "bank-csv",
            }
            ingest_host(driver, host_payload)
            logger.info("Seeded host: %s", hostname)

            # Ingest services/applications from software column
            software = row.get("OpenSource_Software_To_Install", "")
            if software:
                for sw in [s.strip() for s in software.split(",") if s.strip()]:
                    # Guess port/protocol for known services
                    port_map = {
                        "nginx": ("443", "tcp"),
                        "postgresql15": ("5432", "tcp"),
                        "postgresql15-server": ("5432", "tcp"),
                        "tomcat": ("8080", "tcp"),
                        "nodejs": ("3000", "tcp"),
                        "php8.1": ("9000", "tcp"),
                    }
                    if sw.lower() in port_map:
                        port, proto = port_map[sw.lower()]
                        try:
                            ingest_service(driver, {
                                "host_id": hostname,
                                "name": sw,
                                "port": port,
                                "proto": proto,
                                "source": "bank-csv",
                            })
                        except Exception as e:
                            logger.warning("Service ingest skipped for %s: %s", sw, e)

                    # Always ingest as application
                    try:
                        ingest_application(driver, {
                            "host_id": hostname,
                            "name": sw,
                            "version": "",
                            "vendor": "",
                            "source": "bank-csv",
                        })
                    except Exception as e:
                        logger.warning("App ingest skipped for %s: %s", sw, e)


def seed_from_wazuh_fixtures(driver):
    """Ingest hosts and vulnerabilities from Wazuh fixture files."""
    wazuh = FixtureWazuhSource()

    # Hosts (updates existing with IP/agent_version from fixture)
    for host in wazuh.get_hosts():
        ingest_host(driver, host)
        logger.info("Updated host from Wazuh fixture: %s", host["host_id"])

    # Vulnerabilities
    for vuln in wazuh.get_vulnerabilities():
        try:
            ingest_vulnerability(driver, vuln)
            logger.info("Seeded vulnerability: %s on %s",
                         vuln["cve_id"], vuln["host_id"])
        except Exception as e:
            logger.warning("Vulnerability ingest failed: %s", e)


def main():
    """Run the full seed pipeline."""
    driver = get_driver()

    try:
        # 1. Apply schema
        logger.info("Applying Neo4j schema...")
        apply_schema(driver)
        logger.info("Schema applied.")

        # 2. Seed from bank CSV
        logger.info("Seeding from bank CSV...")
        seed_from_csv(driver)

        # 3. Augment with Wazuh fixture data
        logger.info("Seeding from Wazuh fixtures...")
        seed_from_wazuh_fixtures(driver)

        logger.info("✓ Seed complete.")

    except Exception as e:
        logger.error("Seed failed: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        close_driver()


if __name__ == "__main__":
    main()
