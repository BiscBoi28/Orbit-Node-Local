"""
Thin Presidio REST API client.

Calls the Presidio Analyzer at PRESIDIO_URL/analyze and returns
structured results.  This is the low-level HTTP layer; the higher-level
bank-oriented scanning logic lives in presidio_bank.py.
"""

import logging
from collections import Counter

import requests

from app.config import PRESIDIO_URL

logger = logging.getLogger(__name__)

# Entities we explicitly ask Presidio to detect (banking-oriented set)
PII_ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "PERSON",
    "LOCATION",
    "US_BANK_NUMBER",
    "US_SSN",
    "IP_ADDRESS",
    "IBAN_CODE",
]

MIN_CONFIDENCE = 0.3


def analyze_text(text: str) -> list[dict]:
    """Call Presidio Analyzer for a single text string.

    Returns a list of entity dicts, each with:
      entity_type, score, start, end
    Filters out detections below MIN_CONFIDENCE.
    """
    try:
        response = requests.post(
            f"{PRESIDIO_URL}/analyze",
            json={
                "text": text,
                "language": "en",
                "entities": PII_ENTITIES,
            },
            timeout=15,
        )
        response.raise_for_status()
        entities = response.json()
        return [e for e in entities if e.get("score", 0) >= MIN_CONFIDENCE]
    except requests.exceptions.ConnectionError:
        logger.warning("Presidio unreachable at %s", PRESIDIO_URL)
        return []
    except Exception as e:
        logger.error("Presidio call failed: %s", e)
        return []


def scan_text(text: str) -> dict:
    """Scan a single text and return a structured result dict.

    Returns:
        {
            "detected_pii_types": ["PERSON", "EMAIL_ADDRESS", ...],
            "entity_counts": {"PERSON": 5, ...},
            "chunk_scores": [0.9, 0.7, ...],
            "overall_sensitivity_input": 0.82,
            "raw_entities": [...]
        }
    """
    entities = analyze_text(text)

    types = [e["entity_type"] for e in entities]
    counts = dict(Counter(types))
    scores = [e["score"] for e in entities]

    overall = sum(scores) / len(scores) if scores else 0.0

    return {
        "detected_pii_types": sorted(set(types)),
        "entity_counts": counts,
        "chunk_scores": scores,
        "overall_sensitivity_input": round(overall, 4),
        "raw_entities": entities,
    }


def scan_texts(texts: list[str]) -> dict:
    """Scan multiple text items and return aggregated results.

    Returns:
        {
            "detected_pii_types": [...],
            "entity_counts": {...},
            "chunk_scores": [...],
            "per_item_results": [...]
        }
    """
    all_types: set[str] = set()
    all_counts: dict[str, int] = {}
    all_scores: list[float] = []
    per_item: list[dict] = []

    for text in texts:
        result = scan_text(text)
        all_types.update(result["detected_pii_types"])
        for k, v in result["entity_counts"].items():
            all_counts[k] = all_counts.get(k, 0) + v
        all_scores.extend(result["chunk_scores"])
        per_item.append(result)

    return {
        "detected_pii_types": sorted(all_types),
        "entity_counts": all_counts,
        "chunk_scores": all_scores,
        "per_item_results": per_item,
    }
