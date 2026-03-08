"""
Presidio Bank Adapter
======================
Adapts the Presidio scanning logic for bank simulation data.

This module adds banking-oriented risk scoring on top of the raw Presidio
entity detections from presidio_client, using the severity weights and
combination rules from PII_SCORING_STRATEGY.md.

The key function is scan_bank_content(), which takes a list of text items
(from a data-change event) and returns aggregate PII analysis suitable
for the sensitivity/importance formulas in priority.py.
"""

import logging
from typing import List, Dict, Set

from app.presidio_client import scan_texts

logger = logging.getLogger(__name__)

# ── Banking-oriented severity weights (from PII_SCORING_STRATEGY.md) ─────
ENTITY_SEVERITY_WEIGHTS: dict[str, float] = {
    "CREDIT_CARD": 10.0,
    "US_BANK_NUMBER": 10.0,
    "US_SSN": 10.0,
    "IBAN_CODE": 9.0,
    "EMAIL_ADDRESS": 5.0,
    "PHONE_NUMBER": 5.0,
    "PERSON": 4.0,
    "IP_ADDRESS": 3.0,
    "LOCATION": 3.0,
}

# High-risk combinations (multiplicative risk)
HIGH_RISK_COMBINATIONS: list[set[str]] = [
    {"CREDIT_CARD", "PERSON"},
    {"CREDIT_CARD", "EMAIL_ADDRESS"},
    {"US_BANK_NUMBER", "PERSON"},
    {"US_SSN", "PERSON"},
    {"EMAIL_ADDRESS", "PHONE_NUMBER"},
]

# Risk level thresholds
RISK_THRESHOLDS: dict[str, float] = {
    "CRITICAL": 25.0,
    "HIGH": 15.0,
    "MEDIUM": 8.0,
    "LOW": 3.0,
}


def _calculate_risk_score(entities: list[dict]) -> dict:
    """Calculate banking-oriented PII risk score for a set of entities.

    Uses severity weighting, volume multiplier, and high-risk combination
    detection to produce a final risk score and level.
    """
    if not entities:
        return {
            "risk_score": 0.0,
            "risk_level": "NONE",
            "entity_count": 0,
            "has_high_risk_combination": False,
        }

    entity_types = {e["entity_type"] for e in entities}

    # Base score: severity × confidence for each entity
    base_score = 0.0
    for entity in entities:
        etype = entity["entity_type"]
        confidence = entity.get("score", 1.0)
        severity = ENTITY_SEVERITY_WEIGHTS.get(etype, 1.0)
        base_score += severity * confidence

    # Volume multiplier
    count = len(entities)
    volume_mult = 1 + (0.2 * (count - 1)) if count > 1 else 1.0

    # High-risk combination multiplier
    has_combo = False
    combo_mult = 1.0
    for combo in HIGH_RISK_COMBINATIONS:
        if combo.issubset(entity_types):
            has_combo = True
            combo_mult = 1.5
            break

    risk_score = base_score * volume_mult * combo_mult

    # Determine risk level
    if risk_score >= RISK_THRESHOLDS["CRITICAL"]:
        risk_level = "CRITICAL"
    elif risk_score >= RISK_THRESHOLDS["HIGH"]:
        risk_level = "HIGH"
    elif risk_score >= RISK_THRESHOLDS["MEDIUM"]:
        risk_level = "MEDIUM"
    elif risk_score >= RISK_THRESHOLDS["LOW"]:
        risk_level = "LOW"
    else:
        risk_level = "MINIMAL"

    return {
        "risk_score": round(risk_score, 2),
        "risk_level": risk_level,
        "entity_count": count,
        "has_high_risk_combination": has_combo,
    }


def _normalize_risk_to_sensitivity(risk_score: float) -> float:
    """Map a raw risk score to 0.0–1.0 sensitivity range.

    Uses a sigmoid-style mapping:
      0   →  0.0
      15  →  0.5
      30+ →  ~0.95+
    """
    if risk_score <= 0:
        return 0.0
    # Simple logistic: 1 / (1 + e^(-k*(x - midpoint)))
    import math
    k = 0.15
    midpoint = 15.0
    return round(1.0 / (1.0 + math.exp(-k * (risk_score - midpoint))), 4)


def scan_bank_content(content_items: list[str]) -> dict:
    """Scan bank-relevant text items and return ORC-ready results.

    This is the main orchestrator-callable function.

    Args:
        content_items: list of text strings from a data-change event

    Returns:
        {
            "detected_pii_types": ["PERSON", "EMAIL_ADDRESS", ...],
            "entity_counts": {"PERSON": 5, ...},
            "chunk_scores": [0.72, 0.85, ...],  # per-item normalised sensitivity
            "pii_counts_summary": {"PERSON": 5, ...},
            "risk_analysis": {
                "risk_score": 32.7,
                "risk_level": "CRITICAL",
                ...
            }
        }
    """
    # 1. Call Presidio via the client
    scan_result = scan_texts(content_items)

    # 2. Compute banking-oriented risk score from all raw entities
    all_raw_entities = []
    for item_result in scan_result.get("per_item_results", []):
        all_raw_entities.extend(item_result.get("raw_entities", []))

    risk_analysis = _calculate_risk_score(all_raw_entities)

    # 3. Convert per-item risk scores to normalised sensitivity scores
    chunk_scores: list[float] = []
    for item_result in scan_result.get("per_item_results", []):
        item_entities = item_result.get("raw_entities", [])
        item_risk = _calculate_risk_score(item_entities)
        chunk_scores.append(
            _normalize_risk_to_sensitivity(item_risk["risk_score"])
        )

    return {
        "detected_pii_types": scan_result["detected_pii_types"],
        "entity_counts": scan_result["entity_counts"],
        "chunk_scores": chunk_scores,
        "pii_counts_summary": scan_result["entity_counts"],
        "risk_analysis": risk_analysis,
    }
