# Directive — ORC Pipeline

## Goal
Run the full ORBIT orchestrator pipeline: receive a data-change event or Core
alert, enrich it with Presidio scan results and Neo4j context, compute priority,
and persist the result as a DataAsset or ActionCard in Neo4j.

## Inputs
1. **Data-change event**: `{"event_type": "data_change", "asset_id": "...", "content_items": ["..."]}`
2. **Core alert**: Contract-A ActionCard payload from fixtures or live Core

## Execution

### Data-Change Pipeline (`POST /ingest/data-change`)
1. Validate host exists in Neo4j (→ 404 if not)
2. Call `app.presidio_bank.scan_bank_content(content_items)` → PII analysis
3. Call `app.priority.compute_sensitivity_score(chunk_scores)` → sensitivity
4. Call `app.priority.compute_importance_score(sensitivity, role, pii_types)` → importance
5. Derive `crown_jewel = importance >= CROWN_JEWEL_THRESHOLD`
6. Generate `asset_hash = host_id::sha256(content)[:16]`
7. Call `app.graph.ingest_dataasset(driver, payload)` → Neo4j DataAsset node

### Core Alert Pipeline (`POST /ingest/core-alert`)
1. Call `app.graph.ingest_actioncard(driver, payload)` → ActionCard (received→pending)
2. Look up affected host and DataAssets in Neo4j
3. Call `app.priority.compute_action_priority(severity, importance, crown_jewel)` → priority
4. Return enriched response with priority

### Running the Service
```bash
docker compose up -d           # Neo4j + Presidio
python3 -m app.seed            # Seed graph (run once)
uvicorn app.main:app --port 8000
```

## Outputs
- DataAsset nodes with sensitivity_score, pii_types, crown_jewel in Neo4j
- ActionCard nodes with priority enrichment in Neo4j
- JSON response with scoring breakdown

## Edge Cases
- Presidio unreachable → all scores default to 0.0, scan_status='pending_retry'
- Host not found → 404 error (must seed first)
- Privacy violation → PrivacyViolationError before any Cypher executes

## References
- `app/main.py` — FastAPI service (13 endpoints)
- `app/priority.py` — D5 scoring formulas
- `app/presidio_bank.py` — bank-oriented PII scanning
- `app/graph.py` — Neo4j bridge
- `app/seed.py` — initial graph population
