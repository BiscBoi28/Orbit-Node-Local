"""
seed_graph.py — Seed Neo4j with Asset and Technology nodes from the bank CSV.

Directive: directives/neo4j_graph_management.md

Usage:
    python execution/seed_graph.py [--csv PATH_TO_CSV]

Defaults to cloudFormationScripts-Bank-simulation/ORBIT_simulated_bank.csv
"""

import os
import csv
import argparse
import sys

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

DEFAULT_CSV = os.path.join(
    os.path.dirname(__file__),
    "..",
    "cloudFormationScripts-Bank-simulation",
    "ORBIT_simulated_bank.csv",
)


def seed(tx, row: dict):
    """Merge an Asset node and its Technology nodes from a CSV row."""
    # Merge Asset
    tx.run(
        """
        MERGE (a:Asset {asset_id: $asset_id})
        SET a.hostname       = $hostname,
            a.technical_roles = $technical_roles,
            a.operating_system = $operating_system,
            a.last_updated    = datetime()
        """,
        asset_id=row.get("Hostname", row.get("asset_id", "")),
        hostname=row.get("Hostname", ""),
        technical_roles=row.get("Technical_Roles", ""),
        operating_system=row.get("OS", ""),
    )
    # Merge Technologies (split on comma if multiple)
    techs_raw = row.get("Technologies", row.get("Software", ""))
    if techs_raw:
        for tech in [t.strip() for t in techs_raw.split(",") if t.strip()]:
            tx.run(
                """
                MERGE (t:Technology {name: $name})
                SET t.last_updated = datetime()
                WITH t
                MATCH (a:Asset {asset_id: $asset_id})
                MERGE (a)-[:RUNS]->(t)
                """,
                name=tech,
                asset_id=row.get("Hostname", row.get("asset_id", "")),
            )


def main():
    parser = argparse.ArgumentParser(description="Seed Neo4j graph from bank CSV")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Path to the CSV file")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"ERROR: CSV not found at {args.csv}", file=sys.stderr)
        sys.exit(1)

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with open(args.csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        with driver.session() as session:
            count = 0
            for row in reader:
                session.execute_write(seed, row)
                count += 1

    driver.close()
    print(f"Seeded {count} assets into Neo4j.")


if __name__ == "__main__":
    main()
