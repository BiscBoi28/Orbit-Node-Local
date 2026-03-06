import json
import requests
from typing import List, Dict, Set

# ---------------- Configuration ----------------
PRESIDIO_URL = "http://localhost:5001/analyze"

INPUT_FILE = "data/request/scan_request_chunks.jsonl"
OUTPUT_FILE = "data/result/scan_result_chunks.jsonl"

# Explicit entities we want Presidio to detect
PII_ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "PERSON",
    "US_BANK_NUMBER",
    "US_SSN",
    "IBAN_CODE",
    "IP_ADDRESS",
    "LOCATION",
    "DATE_TIME"
]

# ---------------- PII Scoring Configuration ----------------
# Severity weights based on banking/financial data sensitivity
# Higher weight = more sensitive/risky PII type
ENTITY_SEVERITY_WEIGHTS = {
    "CREDIT_CARD": 10.0,        # Critical: Direct financial access
    "US_BANK_NUMBER": 10.0,     # Critical: Direct financial access
    "US_SSN": 10.0,             # Critical: Identity theft risk
    "IBAN_CODE": 9.0,           # Critical: International banking
    "EMAIL_ADDRESS": 5.0,       # High: Account access vector
    "PHONE_NUMBER": 5.0,        # High: Contact & verification
    "PERSON": 4.0,              # Medium-High: Personal identification
    "IP_ADDRESS": 3.0,          # Medium: Network identification
    "LOCATION": 3.0,            # Medium: Physical location
    "DATE_TIME": 2.0            # Low-Medium: Temporal information
}

# High-risk entity combinations (multiplicative risk)
HIGH_RISK_COMBINATIONS = [
    {"CREDIT_CARD", "PERSON"},           # Name + CC = impersonation risk
    {"CREDIT_CARD", "EMAIL_ADDRESS"},    # Email + CC = account takeover
    {"US_BANK_NUMBER", "PERSON"},        # Name + Bank = fraud risk
    {"US_SSN", "PERSON"},                # SSN + Name = identity theft
    {"EMAIL_ADDRESS", "PHONE_NUMBER"},   # Multi-factor contact info
]

# Risk level thresholds
RISK_THRESHOLDS = {
    "CRITICAL": 25.0,
    "HIGH": 15.0,
    "MEDIUM": 8.0,
    "LOW": 3.0
}

# ---------------- Presidio Call ----------------
def analyze_text(text: str) -> List[Dict]:
    payload = {
        "text": text,
        "language": "en",
        "entities": PII_ENTITIES
    }

    response = requests.post(PRESIDIO_URL, json=payload, timeout=10)

    # Helpful debug if Presidio fails
    if response.status_code != 200:
        raise RuntimeError(
            f"Presidio error {response.status_code}: {response.text}"
        )

    return response.json()


# ---------------- PII Scoring Strategy ----------------
def calculate_pii_risk_score(entities: List[Dict]) -> Dict:
    """
    Calculate comprehensive PII risk score based on:
    1. Entity severity weights
    2. Confidence scores from Presidio
    3. Entity count (volume multiplier)
    4. High-risk combinations
    
    Returns a dict with score, risk_level, and scoring breakdown
    """
    if not entities:
        return {
            "risk_score": 0.0,
            "risk_level": "NONE",
            "entity_count": 0,
            "unique_entity_types": 0,
            "has_high_risk_combination": False,
            "detected_entity_types": []
        }
    
    # Extract unique entity types
    entity_types = {entity["entity_type"] for entity in entities}
    
    # Base score: Sum of (severity_weight * confidence) for each entity
    base_score = 0.0
    for entity in entities:
        entity_type = entity["entity_type"]
        confidence = entity.get("score", 1.0)
        severity_weight = ENTITY_SEVERITY_WEIGHTS.get(entity_type, 1.0)
        
        # Score contribution = severity * confidence
        base_score += severity_weight * confidence
    
    # Volume multiplier: More entities = increased risk
    # Using logarithmic scale to avoid excessive penalties
    entity_count = len(entities)
    if entity_count > 1:
        volume_multiplier = 1 + (0.2 * (entity_count - 1))
    else:
        volume_multiplier = 1.0
    
    # Check for high-risk combinations
    has_high_risk_combo = False
    combination_multiplier = 1.0
    
    for combo in HIGH_RISK_COMBINATIONS:
        if combo.issubset(entity_types):
            has_high_risk_combo = True
            combination_multiplier = 1.5  # 50% increase for dangerous combinations
            break
    
    # Final risk score calculation
    risk_score = base_score * volume_multiplier * combination_multiplier
    
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
        "entity_count": entity_count,
        "unique_entity_types": len(entity_types),
        "has_high_risk_combination": has_high_risk_combo,
        "detected_entity_types": sorted(list(entity_types))
    }

# ---------------- Main Pipeline ----------------
def main():
    total_chunks = 0
    high_risk_chunks = 0
    critical_risk_chunks = 0
    
    with open(INPUT_FILE, "r") as infile, open(OUTPUT_FILE, "w") as outfile:
        for line in infile:
            chunk = json.loads(line)
            total_chunks += 1

            chunk_id = chunk.get("chunk_id")
            asset_id = chunk.get("asset_id")
            record_id = chunk.get("record_id", "unknown")

            # IMPORTANT: your chunks use "content_text", not "text"
            text = chunk.get("content_text")

            if not text or not isinstance(text, str) or not text.strip():
                presidio_results = []
            else:
                try:
                    presidio_results = analyze_text(text)
                except Exception as e:
                    presidio_results = []
                    print(f"[WARN] Presidio failed for chunk {chunk_id}: {e}")

            # Calculate PII risk score
            risk_analysis = calculate_pii_risk_score(presidio_results)
            
            # Track statistics
            if risk_analysis["risk_level"] == "CRITICAL":
                critical_risk_chunks += 1
            elif risk_analysis["risk_level"] == "HIGH":
                high_risk_chunks += 1

            output_record = {
                "chunk_id": chunk_id,
                "asset_id": asset_id,
                "record_id": record_id,
                "presidio_entities": presidio_results,
                "pii_risk_analysis": risk_analysis
            }

            outfile.write(json.dumps(output_record) + "\n")

    # Print summary statistics
    print(f"\n{'='*60}")
    print(f"PII SCAN COMPLETE")
    print(f"{'='*60}")
    print(f"Total chunks processed: {total_chunks}")
    print(f"Critical risk chunks:   {critical_risk_chunks}")
    print(f"High risk chunks:       {high_risk_chunks}")
    print(f"Results written to:     {OUTPUT_FILE}")
    print(f"{'='*60}\n")

# ---------------- Entry Point ----------------
if __name__ == "__main__":
    main()