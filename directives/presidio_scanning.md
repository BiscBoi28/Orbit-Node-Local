# Directive — Presidio Scanning

## Goal
Detect PII in bank-relevant text using Presidio Analyzer and return structured
risk scores suitable for the ORC priority formulas.

## Inputs
- List of text strings from a data-change event (customer names, account IDs,
  email addresses, alert descriptions, etc.)

## Execution
1. Call `app.presidio_client.scan_texts(texts)` — sends each text to Presidio
   REST API at `PRESIDIO_URL/analyze`
2. `app.presidio_bank.scan_bank_content(texts)` wraps the client with:
   - Banking-oriented severity weights (CREDIT_CARD=10, SSN=10, etc.)
   - Volume multiplier: `1 + 0.2*(count-1)` for multi-entity chunks
   - High-risk combination detection (CC+PERSON, SSN+PERSON, etc.)
   - Risk-to-sensitivity normalisation via sigmoid mapping

## Outputs
```json
{
  "detected_pii_types": ["CREDIT_CARD", "PERSON", "EMAIL_ADDRESS"],
  "entity_counts": {"CREDIT_CARD": 2, "PERSON": 3, "EMAIL_ADDRESS": 1},
  "chunk_scores": [0.72, 0.85, 0.91],
  "risk_analysis": {
    "risk_score": 32.7,
    "risk_level": "CRITICAL",
    "entity_count": 6,
    "has_high_risk_combination": true
  }
}
```

## Edge Cases
- Presidio unreachable: returns empty entities, all scores 0.0
- Empty text: returns NONE risk level
- Detected PII stored only as type names in Neo4j, never raw values (privacy)

## References
- `app/presidio_client.py` — low-level REST client
- `app/presidio_bank.py` — bank-oriented adapter with scoring
- `Presidio/presidio-local/PII_SCORING_STRATEGY.md` — scoring design rationale
