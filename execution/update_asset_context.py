"""
update_asset_context.py — Merge sensitivity / importance metadata onto an Asset node in Neo4j.

Directive: directives/neo4j_graph_management.md

Usage:
    python execution/update_asset_context.py --asset-id corebank-db-01 --payload '{
        "current_sensitivity_score": 0.89,
        "asset_importance_score": 0.95,
        "detected_pii_types": ["PERSON", "EMAIL_ADDRESS"],
        "pii_counts_summary": {"PERSON": 12, "EMAIL_ADDRESS": 9},
        "crown_jewel": true
    }'
"""

import os
import json
import argparse
import sys

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")


def update_asset(tx, asset_id: str, payload: dict):
    """Merge sensitivity/importance data onto an Asset node."""
    tx.run(
        """
        MERGE (a:Asset {asset_id: $asset_id})
        SET a.current_sensitivity_score = $sensitivity,
            a.asset_importance_score    = $importance,
            a.detected_pii_types        = $pii_types,
            a.pii_counts_summary        = $pii_counts,
            a.crown_jewel               = $crown_jewel,
            a.last_scanned_at           = datetime(),
            a.last_updated              = datetime()
        """,
        asset_id=asset_id,
        sensitivity=payload.get("current_sensitivity_score", 0.0),
        importance=payload.get("asset_importance_score", 0.0),
        pii_types=json.dumps(payload.get("detected_pii_types", [])),
        pii_counts=json.dumps(payload.get("pii_counts_summary", {})),
        crown_jewel=payload.get("crown_jewel", False),
    )


def main():
    parser = argparse.ArgumentParser(description="Update asset context in Neo4j")
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--payload", required=True, help="JSON payload string")
    args = parser.parse_args()

    payload = json.loads(args.payload)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        session.execute_write(update_asset, args.asset_id, payload)

    driver.close()
    print(f"Updated asset '{args.asset_id}' in Neo4j.")


if __name__ == "__main__":
    main()
