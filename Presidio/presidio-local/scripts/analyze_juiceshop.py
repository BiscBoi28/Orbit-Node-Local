#!/usr/bin/env python3
"""
analyse_juicebox.py
===================

PII detection and risk scoring service using Presidio.
Designed to operate as the Presidio component in the ORBIT architecture.

Responsibilities:
- Detect PII using Presidio
- Detect password fields
- Compute PII exposure risk score
- Return structured results to the orchestrator

Presidio communicates ONLY with the orchestrator.

Author: Security Analysis Team
Date: March 2026
"""

import json
import requests
from typing import List, Dict
from datetime import datetime
from collections import defaultdict

# ============================================================================
# CONFIGURATION
# ============================================================================

PRESIDIO_URL = "http://localhost:5001/analyze"

MIN_CONFIDENCE = 0.3

INPUT_FILE = "data/request/juiceshop_seed_export.jsonl"
OUTPUT_DIR = "data/result"

# ============================================================================
# PII ENTITIES
# ============================================================================

PII_ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "PERSON",
    "LOCATION",
    "US_BANK_NUMBER",
    "US_SSN",
    "IP_ADDRESS",
    "IBAN_CODE"
]

# ============================================================================
# RISK SCORING
# ============================================================================

ENTITY_SEVERITY_WEIGHTS = {
    "CREDIT_CARD": 10.0,
    "US_BANK_NUMBER": 10.0,
    "US_SSN": 10.0,
    "IBAN_CODE": 9.0,
    "EMAIL_ADDRESS": 6.0,
    "PHONE_NUMBER": 5.0,
    "PERSON": 4.0,
    "LOCATION": 2.5,
    "IP_ADDRESS": 2.0,
    "PASSWORD": 8.0,
}

HIGH_RISK_COMBINATIONS = [
    {"EMAIL_ADDRESS", "CREDIT_CARD"},
    {"EMAIL_ADDRESS", "PASSWORD"},
    {"CREDIT_CARD", "PERSON"},
    {"CREDIT_CARD", "LOCATION"},
    {"PHONE_NUMBER", "EMAIL_ADDRESS"},
    {"PERSON", "LOCATION", "PHONE_NUMBER"},
]

RISK_THRESHOLDS = {
    "CRITICAL": 30.0,
    "HIGH": 18.0,
    "MEDIUM": 10.0,
    "LOW": 4.0,
}

# ============================================================================
# PRESIDIO INTERFACE
# ============================================================================

def analyze_text_presidio(text: str) -> List[Dict]:
    """Call Presidio API to detect PII."""

    payload = {
        "text": text,
        "language": "en",
        "entities": PII_ENTITIES
    }

    try:
        response = requests.post(PRESIDIO_URL, json=payload, timeout=10)

        if response.status_code != 200:
            print(f"[WARN] Presidio returned {response.status_code}")
            return []

        results = response.json()

        # Filter low confidence detections
        results = [e for e in results if e.get("score", 0) >= MIN_CONFIDENCE]

        return results

    except Exception as e:
        print(f"[ERROR] Presidio call failed: {e}")
        return []


# ============================================================================
# ADDITIONAL DETECTIONS
# ============================================================================

def detect_password_fields(content_text: str) -> List[Dict]:

    entities = []

    if "password:" in content_text.lower():

        start = content_text.lower().find("password:")
        end = start + 15

        entities.append({
            "entity_type": "PASSWORD",
            "score": 1.0,
            "start": start,
            "end": end
        })

    return entities


def extract_user_profile_risk(content_text: str) -> Dict:

    return {
        "has_email": "email:" in content_text.lower(),
        "has_password": "password:" in content_text.lower(),
        "has_credit_card": "cardnum:" in content_text.lower(),
        "has_phone": "mobilenum:" in content_text.lower(),
        "has_address": any(
            x in content_text.lower()
            for x in ["streetaddress:", "city:", "country:"]
        ),
        "has_security_qa": "securityQuestion" in content_text,
    }


# ============================================================================
# RISK SCORING ENGINE
# ============================================================================

def calculate_pii_risk_score(entities: List[Dict], profile_data: Dict) -> Dict:

    if not entities:
        return {
            "risk_score": 0,
            "risk_level": "NONE",
            "entity_types": []
        }

    entity_types = {e["entity_type"] for e in entities}

    base_score = 0

    for entity in entities:
        etype = entity["entity_type"]
        confidence = entity.get("score", 1)

        severity = ENTITY_SEVERITY_WEIGHTS.get(etype, 1)

        base_score += severity * confidence

    entity_count = len(entities)

    volume_multiplier = 1 + (0.15 * (entity_count - 1)) if entity_count > 1 else 1

    combo_multiplier = 1

    for combo in HIGH_RISK_COMBINATIONS:
        if combo.issubset(entity_types):
            combo_multiplier = 1.6

    completeness_score = sum([
        profile_data["has_email"] * 2,
        profile_data["has_password"] * 3,
        profile_data["has_credit_card"] * 4,
        profile_data["has_phone"] * 1,
        profile_data["has_address"] * 1
    ])

    completeness_multiplier = 1.2 if completeness_score >= 8 else 1.1 if completeness_score >= 5 else 1

    risk_score = base_score * volume_multiplier * combo_multiplier * completeness_multiplier

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
        "entity_types": sorted(list(entity_types)),
        "entity_count": entity_count
    }


# ============================================================================
# CORE PRESIDIO SCAN FUNCTION (FOR ORCHESTRATOR)
# ============================================================================

def presidio_scan_records(records: List[Dict]) -> Dict:

    results = []

    max_risk = 0

    for record in records:

        record_id = record["record_id"]
        text = record["content_text"]

        presidio_entities = analyze_text_presidio(text)

        password_entities = detect_password_fields(text)

        all_entities = presidio_entities + password_entities

        profile_data = extract_user_profile_risk(text)

        risk_analysis = calculate_pii_risk_score(all_entities, profile_data)

        max_risk = max(max_risk, risk_analysis["risk_score"])

        results.append({
            "record_id": record_id,
            "entities": all_entities,
            "risk_analysis": risk_analysis
        })

    return {
        "scan_timestamp": datetime.now().isoformat(),
        "records_scanned": len(records),
        "max_risk_score": max_risk,
        "results": results
    }


# ============================================================================
# ORCHESTRATOR API
# ============================================================================

def scan_asset(asset_id: str, dataset: str) -> Dict:
    """
    Orchestrator-callable scanner API.
    
    Args:
        asset_id: Identifier for the asset being scanned (e.g., "juiceshop_users")
        dataset: Path to the dataset file to scan
    
    Returns:
        dict: Simplified orchestrator-friendly summary:
            - asset_id: Asset identifier
            - records_scanned: Total number of records processed
            - high_risk_records: Count of CRITICAL + HIGH risk records
            - pii_entities: Dictionary of entity type counts
            - max_risk_score: Highest risk score found
    """
    # Load records from dataset
    records = []
    with open(dataset) as f:
        for line in f:
            r = json.loads(line)
            records.append({
                "record_id": r.get("record_id"),
                "content_text": r.get("content_text", "")
            })
    
    # Run Presidio scan
    detailed_results = presidio_scan_records(records)
    
    # Count high-risk records
    high_risk_count = sum(
        1 for result in detailed_results["results"]
        if result["risk_analysis"]["risk_level"] in ["CRITICAL", "HIGH"]
    )
    
    # Aggregate entity counts
    entity_counts = defaultdict(int)
    for result in detailed_results["results"]:
        for entity_type in result["risk_analysis"]["entity_types"]:
            entity_counts[entity_type] += 1
    
    # Return orchestrator-friendly summary
    return {
        "asset_id": asset_id,
        "records_scanned": detailed_results["records_scanned"],
        "high_risk_records": high_risk_count,
        "pii_entities": dict(entity_counts),
        "max_risk_score": detailed_results["max_risk_score"]
    }


# ============================================================================
# LOCAL TEST PIPELINE
# ============================================================================

def analyze_juiceshop_users(input_file=INPUT_FILE):
    """Local test function - not for orchestrator use."""

    records = []

    with open(input_file) as f:
        for line in f:
            r = json.loads(line)

            records.append({
                "record_id": r.get("record_id"),
                "content_text": r.get("content_text", "")
            })

    print(f"Loaded {len(records)} records")

    results = presidio_scan_records(records)

    print("Scan complete")

    print(json.dumps(results["results"][:3], indent=2))

    return results


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":

    try:

        analyze_juiceshop_users()

    except Exception as e:

        print("Scan failed")

        print(e)