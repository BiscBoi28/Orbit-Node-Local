"""
presidio_scan.py — Call Presidio Analyzer and return structured PII results.

Directive: directives/presidio_scanning.md

Usage:
    python execution/presidio_scan.py --text "Jane Doe, jane@example.com, account 021000021"
"""

import os
import json
import argparse
from collections import Counter

import requests
from dotenv import load_dotenv

load_dotenv()

PRESIDIO_URL = os.getenv("PRESIDIO_URL", "http://localhost:5001")


def scan(text: str) -> dict:
    """Send text to Presidio Analyzer and return structured results."""
    response = requests.post(
        f"{PRESIDIO_URL}/analyze",
        json={
            "text": text,
            "language": "en",
        },
        timeout=30,
    )
    response.raise_for_status()
    entities = response.json()

    # Aggregate
    types = [e["entity_type"] for e in entities]
    counts = dict(Counter(types))
    scores = [e["score"] for e in entities]

    # Compute per-text sensitivity input (simple: average confidence if entities found)
    overall = sum(scores) / len(scores) if scores else 0.0

    return {
        "detected_pii_types": sorted(set(types)),
        "entity_counts": counts,
        "chunk_scores": scores,
        "overall_sensitivity_input": round(overall, 4),
        "raw_entities": entities,
    }


def main():
    parser = argparse.ArgumentParser(description="Scan text for PII via Presidio")
    parser.add_argument("--text", required=True)
    args = parser.parse_args()

    result = scan(args.text)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
