"""
orc_pipeline.py — Full ORC data-change pipeline.

Directive: directives/orc_pipeline.md

Workflow:
    1. Receive data-change event.
    2. Scan each content_item via Presidio.
    3. Compute current_sensitivity_score and asset_importance_score.
    4. Update the asset node in Neo4j.

Usage:
    python execution/orc_pipeline.py --event '{
        "event_type": "data_change",
        "asset_id": "corebank-db-01",
        "content_items": ["Jane Doe, jane@example.com, account 021000021"]
    }'
"""

import os
import json
import argparse
import sys

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Local imports — these scripts are co-located in execution/
from presidio_scan import scan as presidio_scan
from update_asset_context import update_asset

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# ------------------------------------------------------------------
# Sensitivity / importance formulas (from high_level_design.md)
# ------------------------------------------------------------------

# Configurable thresholds
CROWN_JEWEL_THRESHOLD = float(os.getenv("CROWN_JEWEL_THRESHOLD", "0.75"))
ROLE_BONUS_DB = 0.10
ROLE_BONUS_WEB = 0.05
BREADTH_BONUS_MAX = 0.10
HIGH_RISK_PII = {"US_BANK_NUMBER", "CREDIT_CARD", "US_SSN", "IBAN_CODE"}


def compute_sensitivity(chunk_scores: list[float]) -> float:
    """current_sensitivity_score = 0.6 * max_score + 0.4 * avg_top_scores"""
    if not chunk_scores:
        return 0.0
    max_score = max(chunk_scores)
    top_scores = sorted(chunk_scores, reverse=True)[:5]
    avg_top = sum(top_scores) / len(top_scores)
    return round(0.6 * max_score + 0.4 * avg_top, 4)


def compute_importance(
    sensitivity: float, pii_types: set[str], asset_role: str = ""
) -> float:
    """asset_importance_score = sensitivity + role_bonus + breadth_bonus  (clamped 0..1)"""
    role = asset_role.lower()
    role_bonus = ROLE_BONUS_DB if "db" in role or "database" in role else (
        ROLE_BONUS_WEB if "web" in role else 0.0
    )
    high_risk_count = len(pii_types & HIGH_RISK_PII)
    breadth_bonus = min(high_risk_count * 0.025, BREADTH_BONUS_MAX)
    return round(min(sensitivity + role_bonus + breadth_bonus, 1.0), 4)


def run_pipeline(event: dict) -> dict:
    """Execute the full data-change pipeline and return the result."""
    asset_id = event["asset_id"]
    content_items = event.get("content_items", [])

    # 1. Scan each content item with Presidio
    all_scores = []
    all_types: set[str] = set()
    all_counts: dict[str, int] = {}

    for item in content_items:
        result = presidio_scan(item)
        all_scores.extend(result["chunk_scores"])
        all_types.update(result["detected_pii_types"])
        for k, v in result["entity_counts"].items():
            all_counts[k] = all_counts.get(k, 0) + v

    # 2. Compute scores
    sensitivity = compute_sensitivity(all_scores)

    # Try to look up asset role from Neo4j for the role_bonus
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    asset_role = ""
    with driver.session() as session:
        rec = session.run(
            "MATCH (a:Asset {asset_id: $id}) RETURN a.technical_roles AS roles",
            id=asset_id,
        ).single()
        if rec:
            asset_role = rec["roles"] or ""

    importance = compute_importance(sensitivity, all_types, asset_role)
    crown_jewel = importance >= CROWN_JEWEL_THRESHOLD

    payload = {
        "current_sensitivity_score": sensitivity,
        "asset_importance_score": importance,
        "detected_pii_types": sorted(all_types),
        "pii_counts_summary": all_counts,
        "crown_jewel": crown_jewel,
    }

    # 3. Update Neo4j
    with driver.session() as session:
        session.execute_write(update_asset, asset_id, payload)

    driver.close()

    return {"asset_id": asset_id, **payload}


def main():
    parser = argparse.ArgumentParser(description="ORC data-change pipeline")
    parser.add_argument("--event", required=True, help="JSON event string")
    args = parser.parse_args()

    event = json.loads(args.event)
    if event.get("event_type") != "data_change":
        print(f"ERROR: unexpected event_type '{event.get('event_type')}'", file=sys.stderr)
        sys.exit(1)

    result = run_pipeline(event)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
