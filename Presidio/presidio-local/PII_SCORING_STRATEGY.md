# PII Risk Scoring Strategy

## Overview
This document describes the PII (Personally Identifiable Information) risk scoring strategy implemented for bank information dataset analysis using Presidio Analyzer.

## Why This Strategy?

### Context: Banking & Financial Data
When dealing with bank information datasets, not all PII carries the same risk level. A leaked phone number has different implications than a leaked credit card number. Our scoring strategy reflects real-world financial data security requirements.

### Key Principles

#### 1. **Severity-Based Weighting**
Different PII types pose different levels of threat in a banking context:

| Entity Type | Weight | Rationale |
|-------------|--------|-----------|
| `CREDIT_CARD` | 10.0 | Direct financial access; enables fraudulent transactions |
| `US_BANK_NUMBER` | 10.0 | Direct account access; fund transfer capability |
| `US_SSN` | 10.0 | Identity theft risk; opens multiple attack vectors |
| `IBAN_CODE` | 9.0 | International banking access; cross-border fraud |
| `EMAIL_ADDRESS` | 5.0 | Account takeover vector; password reset attacks |
| `PHONE_NUMBER` | 5.0 | 2FA bypass; social engineering target |
| `PERSON` | 4.0 | Identity correlation; impersonation risk |
| `IP_ADDRESS` | 3.0 | Network tracking; session hijacking |
| `LOCATION` | 3.0 | Physical security; social engineering |
| `DATE_TIME` | 2.0 | Transaction correlation; pattern analysis |

**Why this weighting?**
- **Financial instruments (CC, Bank Numbers)** get maximum weight because they enable direct monetary theft
- **Identity documents (SSN)** are critical because they can be used to open new accounts or commit identity fraud
- **Contact information (Email, Phone)** is important for account access but requires additional exploitation steps
- **Personal information (Name, Location)** increases risk when combined with other data

#### 2. **Confidence-Weighted Scoring**
Presidio provides confidence scores (0.0 - 1.0) for each detection. We multiply severity by confidence:

```
Entity Score = Severity Weight × Presidio Confidence
```

**Why?**
- A low-confidence detection (0.3) might be a false positive
- A high-confidence detection (1.0) is almost certainly real PII
- This prevents false positives from inflating risk scores

**Example:**
- Credit Card detected with 0.9 confidence → 10.0 × 0.9 = 9.0 points
- Person name detected with 0.5 confidence → 4.0 × 0.5 = 2.0 points

#### 3. **Volume Multiplier**
Multiple PII entities in a single chunk increase risk non-linearly:

```
Volume Multiplier = 1 + (0.2 × (entity_count - 1))
```

**Why?**
- A chunk with 1 PII entity: 1.0× (no increase)
- A chunk with 3 PII entities: 1.4× (40% increase)
- A chunk with 5 PII entities: 1.8× (80% increase)

**Rationale:**
- More PII = more complete profile = higher exploitation potential
- Logarithmic scaling prevents excessive penalties
- Reflects that attackers need multiple data points for effective attacks

#### 4. **High-Risk Combinations**
Certain PII combinations are particularly dangerous:

| Combination | Multiplier | Attack Vector |
|-------------|------------|---------------|
| `CREDIT_CARD` + `PERSON` | 1.5× | Card-not-present fraud |
| `CREDIT_CARD` + `EMAIL_ADDRESS` | 1.5× | Account takeover + fraud |
| `US_BANK_NUMBER` + `PERSON` | 1.5× | ACH fraud, wire transfer |
| `US_SSN` + `PERSON` | 1.5× | Full identity theft |
| `EMAIL_ADDRESS` + `PHONE_NUMBER` | 1.5× | Multi-factor bypass |

**Why combinations matter:**
- Individual data points have limited value to attackers
- Combined data enables sophisticated attacks
- Banks are legally required to secure certain data combinations (PCI-DSS, GLBA)

**Real-world scenario:**
```
Card number alone → Cannot be used online (needs name, CVV, address)
Card number + Name → Card-not-present transaction possible
Card number + Name + Email → Can reset passwords, receive confirmations
```

## Risk Score Calculation

### Formula
```
Base Score = Σ(severity_weight × confidence) for each entity

Volume Multiplier = 1 + (0.2 × (entity_count - 1))

Combination Multiplier = 1.5 if high-risk combo exists, else 1.0

Final Risk Score = Base Score × Volume Multiplier × Combination Multiplier
```

### Risk Level Classification

| Risk Level | Score Range | Action Required |
|------------|-------------|-----------------|
| `CRITICAL` | ≥ 25.0 | Immediate remediation; potential data breach |
| `HIGH` | ≥ 15.0 | Priority review; implement additional controls |
| `MEDIUM` | ≥ 8.0 | Standard security procedures; monitoring |
| `LOW` | ≥ 3.0 | Routine handling; basic protections |
| `MINIMAL` | < 3.0 | Low sensitivity; standard practices |

**Why these thresholds?**

- **CRITICAL (≥25)**: Indicates multiple high-severity items or dangerous combinations
  - Example: Credit card + email + phone = ~22.5 points without combinations
  - With combination multiplier: 22.5 × 1.5 = 33.75 (CRITICAL)

- **HIGH (≥15)**: Single critical item with good confidence or multiple medium items
  - Example: Credit card alone with 1.0 confidence = 10.0 points
  - With 2 additional entities: 10.0 × 1.2 = 12.0 → Would need slight boost to HIGH

- **MEDIUM (≥8)**: Multiple lower-severity items or single medium-severity item
  - Example: Email (5.0) + Phone (5.0) = 10.0 × 1.2 = 12.0 (HIGH)
  - Example: Email (5.0) + Person (4.0) = 9.0 × 1.2 = 10.8 (MEDIUM)

## Implementation Benefits

### 1. **Compliance-Aligned**
- Maps to PCI-DSS requirements (credit cards)
- Aligns with GLBA (bank account numbers)
- Supports GDPR/CCPA risk assessment

### 2. **Prioritization**
- Security teams can focus on CRITICAL and HIGH risk data first
- Reduces alert fatigue from low-risk detections
- Enables data-driven resource allocation

### 3. **Quantifiable Risk**
- Numerical scores enable trend analysis
- Can set organizational thresholds
- Measurable improvement over time

### 4. **Explainable**
- Each score includes breakdown:
  - Entity count
  - Unique entity types
  - Detected combinations
  - Risk level classification
- Auditable and transparent

## Real-World Examples

### Example 1: Low Risk
```json
{
  "content_text": "Customer Name: John Doe",
  "presidio_entities": [{"entity_type": "PERSON", "score": 0.85}],
  "pii_risk_analysis": {
    "risk_score": 3.4,
    "risk_level": "LOW",
    "entity_count": 1,
    "unique_entity_types": 1,
    "has_high_risk_combination": false
  }
}
```
**Analysis**: Single name, no financial data → Low risk

### Example 2: High Risk
```json
{
  "content_text": "Card: 4716190207394368, Name: John Doe",
  "presidio_entities": [
    {"entity_type": "CREDIT_CARD", "score": 1.0},
    {"entity_type": "PERSON", "score": 0.85}
  ],
  "pii_risk_analysis": {
    "risk_score": 21.6,
    "risk_level": "HIGH",
    "entity_count": 2,
    "unique_entity_types": 2,
    "has_high_risk_combination": true
  }
}
```
**Analysis**: (10.0 + 3.4) × 1.2 × 1.5 = 24.12 → HIGH risk (near CRITICAL)

### Example 3: Critical Risk
```json
{
  "content_text": "Email: john@example.com, Phone: 555-1234, Card: 4716190207394368",
  "presidio_entities": [
    {"entity_type": "EMAIL_ADDRESS", "score": 1.0},
    {"entity_type": "PHONE_NUMBER", "score": 0.7},
    {"entity_type": "CREDIT_CARD", "score": 1.0}
  ],
  "pii_risk_analysis": {
    "risk_score": 32.7,
    "risk_level": "CRITICAL",
    "entity_count": 3,
    "unique_entity_types": 3,
    "has_high_risk_combination": true
  }
}
```
**Analysis**: (5.0 + 3.5 + 10.0) × 1.4 × 1.5 = 38.85 → CRITICAL risk

## Usage

### Running PII Analysis
```bash
python3 scripts/analyze_chunks.py
```

### Output Format
Each scanned chunk includes:
```json
{
  "chunk_id": "...",
  "asset_id": "...",
  "record_id": "...",
  "presidio_entities": [...],
  "pii_risk_analysis": {
    "risk_score": 15.3,
    "risk_level": "HIGH",
    "entity_count": 2,
    "unique_entity_types": 2,
    "has_high_risk_combination": true,
    "detected_entity_types": ["CREDIT_CARD", "EMAIL_ADDRESS"]
  }
}
```

## Tuning the Strategy

Organizations can adjust the strategy by modifying:

1. **Severity Weights** (`ENTITY_SEVERITY_WEIGHTS`): Reflect organizational risk tolerance
2. **Risk Thresholds** (`RISK_THRESHOLDS`): Set appropriate alert levels
3. **Combination Rules** (`HIGH_RISK_COMBINATIONS`): Add domain-specific dangerous pairs
4. **Volume Multiplier**: Adjust sensitivity to entity count

## Conclusion

This scoring strategy provides:
- ✅ **Context-aware risk assessment** tailored for banking data
- ✅ **Actionable prioritization** based on real-world threat models
- ✅ **Explainable scores** for audit and compliance
- ✅ **Flexible framework** adaptable to organizational needs

The strategy balances sensitivity (catching genuine risks) with specificity (avoiding false alarms), enabling effective security monitoring at scale.
