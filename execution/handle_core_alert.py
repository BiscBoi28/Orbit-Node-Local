"""
handle_core_alert.py — Ingest a Core alert and generate a prioritised action card.

Directive: directives/core_alert_handling.md

Usage:
    python execution/handle_core_alert.py --alert '{
        "alert_id": "ALT-001",
        "asset_id": "corebank-db-01",
        "affected_technology": "PostgreSQL",
        "affected_version": "15.3",
        "base_severity": "HIGH",
        "title": "PostgreSQL version vulnerability"
    }'
"""

import os
import json
import uuid
import argparse
import sys

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

SEVERITY_MAP = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def lookup_asset(session, asset_id: str) -> dict | None:
    """Fetch current asset context from Neo4j."""
    rec = session.run(
        """
        MATCH (a:Asset {asset_id: $id})
        RETURN a.current_sensitivity_score AS sensitivity,
               a.asset_importance_score    AS importance,
               a.crown_jewel              AS crown_jewel,
               a.technical_roles          AS roles
        """,
        id=asset_id,
    ).single()
    return dict(rec) if rec else None


def compute_priority(base_severity: str, importance: float, crown_jewel: bool) -> str:
    """Combine technical severity with business importance."""
    sev_score = SEVERITY_MAP.get(base_severity.upper(), 2)
    combined = sev_score * 0.5 + importance * 4 * 0.5  # scale importance to 0-4 range
    if crown_jewel:
        combined += 0.5

    if combined >= 3.0:
        return "CRITICAL"
    elif combined >= 2.0:
        return "HIGH"
    elif combined >= 1.0:
        return "MEDIUM"
    return "LOW"


def create_action_card(session, alert: dict, asset_ctx: dict, priority: str) -> dict:
    """Create an ActionCard node in Neo4j and return the card dict."""
    action_id = f"AC-{uuid.uuid4().hex[:8].upper()}"

    reason = (
        f"{alert['base_severity']}-severity {alert['affected_technology']} vulnerability "
        f"on asset with importance {asset_ctx.get('importance', 'unknown')}"
    )
    if asset_ctx.get("crown_jewel"):
        reason += " (crown jewel)"

    card = {
        "action_id": action_id,
        "alert_id": alert["alert_id"],
        "asset_id": alert["asset_id"],
        "priority": priority,
        "summary": f"Patch {alert['affected_technology']} on {alert['asset_id']}",
        "reason": reason,
        "recommended_action": f"Patch {alert['affected_technology']} to latest stable version and verify access controls",
        "status": "OPEN",
    }

    session.run(
        """
        MERGE (ac:ActionCard {action_id: $action_id})
        SET ac += $props,
            ac.created_at   = datetime(),
            ac.last_updated = datetime()
        WITH ac
        MATCH (a:Asset {asset_id: $asset_id})
        MERGE (ac)-[:GENERATED_FOR]->(a)
        WITH ac
        MERGE (al:Alert {alert_id: $alert_id})
        SET al.title              = $title,
            al.base_severity      = $base_severity,
            al.affected_technology = $affected_technology,
            al.source             = 'Core',
            al.created_at         = datetime(),
            al.last_updated       = datetime()
        MERGE (ac)-[:BASED_ON]->(al)
        MERGE (al)-[:AFFECTS]->(a)
        """,
        action_id=action_id,
        props=card,
        asset_id=alert["asset_id"],
        alert_id=alert["alert_id"],
        title=alert.get("title", ""),
        base_severity=alert.get("base_severity", ""),
        affected_technology=alert.get("affected_technology", ""),
        a_id=alert["asset_id"],
    )

    return card


def main():
    parser = argparse.ArgumentParser(description="Handle Core alert → action card")
    parser.add_argument("--alert", required=True, help="JSON alert string")
    args = parser.parse_args()

    alert = json.loads(args.alert)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        asset_ctx = lookup_asset(session, alert["asset_id"])
        if not asset_ctx:
            print(f"WARNING: Asset '{alert['asset_id']}' not found in Neo4j. Creating stub.", file=sys.stderr)
            asset_ctx = {"sensitivity": 0.0, "importance": 0.0, "crown_jewel": False, "roles": ""}

        priority = compute_priority(
            alert.get("base_severity", "MEDIUM"),
            asset_ctx.get("importance", 0.0) or 0.0,
            asset_ctx.get("crown_jewel", False) or False,
        )

        card = create_action_card(session, alert, asset_ctx, priority)

    driver.close()
    print(json.dumps(card, indent=2))


if __name__ == "__main__":
    main()
