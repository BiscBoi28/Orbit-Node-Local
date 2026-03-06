# Presidio PII Scanner for Banking Data

A comprehensive PII (Personally Identifiable Information) detection and risk scoring system built with Microsoft Presidio Analyzer, designed for banking and financial dataset security analysis.

##  Purpose

This project implements an automated PII scanning pipeline with intelligent risk scoring to identify and prioritize sensitive information in banking datasets. While currently tested on JuiceShop sample data, it's designed for real bank information dataset analysis.

##  Features

-  **Automated PII Detection** using Microsoft Presidio Analyzer
-  **Context-Aware Risk Scoring** tailored for banking/financial data
-  **10 PII Entity Types** including credit cards, bank numbers, SSN, email, phone, etc.
-  **Risk Level Classification** (CRITICAL, HIGH, MEDIUM, LOW, MINIMAL, NONE)
-  **High-Risk Combination Detection** (e.g., Credit Card + Name)
-  **Comprehensive Test Suite** with validation for all entity types
-  **Detailed Documentation** of scoring methodology

## 🏗️ Project Structure

```
presidio-local/
├── docker-compose.yml                    # Presidio Analyzer service configuration
├── PII_SCORING_STRATEGY.md              # Detailed scoring methodology documentation
├── testing.json                          # Test case specifications
├── README.md                             # This file
├── scripts/
│   └── analyze_chunks.py                # Main PII scanning script with risk scoring
├── data/
    ├── request/
    │   ├── scan_request_chunks.jsonl    # Input: JuiceShop dataset chunks
    │   ├── juiceshop_seed_export.jsonl  # Raw JuiceShop seed data
    │   ├── scan_request_manifest.json   # Dataset metadata
    │   └── build_report.json            # Build information
    └── result/
        └── scan_result_chunks.jsonl     # Output: PII scan results with risk scores
```

##  Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.x
- `requests` library: `pip install requests`

### Step 1: Start Presidio Service
```bash
docker compose up -d
```

Verify service is running:
```bash
curl http://localhost:5001/health
# Should return: "Presidio Analyzer service is up"
```

### Step 2: Run PII Scan
```bash
python3 scripts/analyze_chunks.py
```

### Step 3: View Results
```bash
# View summary statistics (displayed after scan)
# Check output file
head data/result/scan_result_chunks.jsonl

# Find critical risk chunks
grep "CRITICAL" data/result/scan_result_chunks.jsonl
```

##  Understanding the Output

Each scanned chunk includes:

```json
{
  "chunk_id": "chk_xxx",
  "asset_id": "xxx",
  "record_id": "js_user:admin",
  "presidio_entities": [
    {
      "entity_type": "CREDIT_CARD",
      "score": 1.0,
      "start": 12,
      "end": 28
    }
  ],
  "pii_risk_analysis": {
    "risk_score": 29.19,
    "risk_level": "CRITICAL",
    "entity_count": 3,
    "unique_entity_types": 3,
    "has_high_risk_combination": true,
    "detected_entity_types": ["CREDIT_CARD", "PERSON", "US_BANK_NUMBER"]
  }
}
```

### Risk Levels

| Level | Score | Meaning |
|-------|-------|---------|
| **CRITICAL** | ≥25.0 | Immediate action required; multiple high-value PII or dangerous combinations |
| **HIGH** | ≥15.0 | Priority review needed; critical financial data detected |
| **MEDIUM** | ≥8.0 | Standard security procedures; moderate sensitivity |
| **LOW** | ≥3.0 | Routine handling; basic PII detected |
| **MINIMAL** | <3.0 | Low sensitivity; limited PII |
| **NONE** | 0.0 | No PII detected |

##  Risk Scoring Methodology

Our scoring strategy considers four key factors:

### 1. Entity Severity Weights
| Entity | Weight | Risk |
|--------|--------|------|
| Credit Card / Bank Number / SSN | 10.0 | Critical financial/identity data |
| Email / Phone | 5.0 | Account access vectors |
| Person Name | 4.0 | Identity correlation |
| IP / Location | 3.0 | Network/physical tracking |
| Date/Time | 2.0 | Transaction correlation |

### 2. Confidence Weighting
```
Entity Score = Severity Weight × Presidio Confidence
```

### 3. Volume Multiplier
```
Multiplier = 1 + (0.2 × (entity_count - 1))
```
More entities = higher risk profile

### 4. High-Risk Combinations (1.5× multiplier)
- Credit Card + Person Name
- Credit Card + Email
- Bank Number + Person Name
- SSN + Person Name
- Email + Phone Number

### Final Formula
```
Risk Score = Base Score × Volume Multiplier × Combination Multiplier
```

📖 **For detailed methodology**, see [PII_SCORING_STRATEGY.md](PII_SCORING_STRATEGY.md)

## 🧪 Testing

The project includes comprehensive test cases covering all PII entity types.

### Test Cases (see `testing.json`)
1.  **UC-02-01**: Presidio Service Health Check
2.  **UC-02-02**: Email Address Detection
3.  **UC-02-03**: Credit Card Detection
4.  **UC-02-04**: Phone Number Detection
5.  **UC-02-05**: Person Name Detection

### Running Tests
```bash
# All test specifications are in testing.json
# Main analysis runs on JuiceShop dataset showing real-world results
python3 scripts/analyze_chunks.py
```

##  Sample Results (JuiceShop Dataset)

```
============================================================
PII SCAN COMPLETE
============================================================
Total chunks processed: 59
Critical risk chunks:   4
High risk chunks:       1
Results written to:     data/result/scan_result_chunks.jsonl
============================================================
```

### Example High-Risk Detection
**Input Text:** `"...card[0].fullName: Jim card[0].cardNum: 5107891722278705..."`

**Risk Analysis:**
- Detected: CREDIT_CARD (1.0 confidence) + PERSON (0.85 confidence)
- Risk Score: 29.19
- Risk Level: **CRITICAL**
- Has high-risk combination: **Yes** (Card + Name)

## 🔧 Configuration

### Modify Entity Detection
Edit `scripts/analyze_chunks.py`:
```python
PII_ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "PERSON",
    "US_BANK_NUMBER",
    # Add more entity types as needed
]
```

### Adjust Risk Thresholds
```python
RISK_THRESHOLDS = {
    "CRITICAL": 25.0,
    "HIGH": 15.0,
    "MEDIUM": 8.0,
    "LOW": 3.0
}
```

### Customize Severity Weights
```python
ENTITY_SEVERITY_WEIGHTS = {
    "CREDIT_CARD": 10.0,  # Adjust based on your risk model
    "EMAIL_ADDRESS": 5.0,
    # ...
}
```

##  Input Data Format

Input file: `data/request/scan_request_chunks.jsonl`

Each line must be a JSON object:
```json
{
  "chunk_id": "unique_id",
  "asset_id": "optional_asset_id",
  "record_id": "record_identifier",
  "content_text": "Text to be scanned for PII..."
}
```

## 🎓 Use Cases

### Banking & Financial Services
- Customer database PII audits
- Compliance reporting (PCI-DSS, GLBA)
- Data breach risk assessment
- Secure data handling verification

### Data Security
- Pre-migration PII discovery
- Data warehouse security analysis
- API response validation
- Log file PII detection

### Compliance & Audit
- GDPR/CCPA data mapping
- PII inventory creation
- Risk-based data classification
- Third-party data sharing audits

##  Security Considerations

- Presidio runs locally via Docker (no cloud API calls) at the moment
- All data processing happens on-premise
- Results include original PII locations (be careful with result storage)
- Consider encrypting result files in production

##  Additional Documentation

- **[PII_SCORING_STRATEGY.md](PII_SCORING_STRATEGY.md)** - Detailed explanation of risk scoring methodology
- **[testing.json](testing.json)** - Complete test case specifications and validation criteria

##  Contributing

To adapt for your banking dataset:

1. Replace input data in `data/request/scan_request_chunks.jsonl`
2. Adjust entity weights in `analyze_chunks.py` based on your risk model
3. Modify risk thresholds for your organization's tolerance
4. Add domain-specific high-risk combinations

##  License

This project uses Microsoft Presidio Analyzer (MIT License).

##  Troubleshooting

### Presidio not starting
```bash
# Check Docker is running
docker ps

# Restart service
docker compose down
docker compose up -d

# Check logs
docker logs presidio-analyzer
```

### No entities detected
- Verify Presidio is running: `curl http://localhost:5001/health`
- Check input data format (must have `content_text` field)
- Review Presidio confidence thresholds

### Low confidence scores
- Some entity types (like phone numbers) may have lower confidence
- Consider adjusting detection patterns in Presidio configuration
- Review false positives vs. false negatives trade-off

---

**Built for secure, intelligent PII detection in banking and financial datasets.**
