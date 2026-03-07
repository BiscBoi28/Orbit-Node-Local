# ORBIT ORC — Manual Testing Guide

> Complete step-by-step guide to verify the entire ORC orchestrator and its integration with Neo4j and Presidio.

---

## Prerequisites

### 1. Install Python Dependencies

```bash
pip install --break-system-packages -r requirements.txt
# Or if using a venv:
# python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### 2. Start Infrastructure

```bash
docker compose up -d
```

Wait for both containers to be healthy:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

**Expected:**
```
NAMES            STATUS
orbit-neo4j      Up X minutes (healthy)
orbit-presidio   Up X minutes (healthy)
```

### 3. Create .env (if not exists)

```bash
cat .env
```

Should contain:
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme
PRESIDIO_URL=http://localhost:5001
CROWN_JEWEL_THRESHOLD=0.7
```

### 4. Seed Neo4j

```bash
python3 -m app.seed
```

**Expected:** Lines showing `Seeded host:`, `Ingested vulnerability:`, ending with `✓ Seed complete.`

---

## Phase 1: Unit Tests (No External Dependencies)

### Test 1.1 — Priority Scoring (20 tests)

```bash
python3 -m pytest tests/test_priority.py -v
```

**Expected:** `20 passed`

These verify:
- `compute_sensitivity_score()` handles empty, single, multiple, and edge-case inputs
- `compute_importance_score()` applies role bonuses, breadth bonuses, clamping
- `is_crown_jewel()` threshold logic
- `compute_action_priority()` combines severity + importance + crown_jewel

---

## Phase 2: Infrastructure Verification

### Test 2.1 — Neo4j Browser

Open http://localhost:7474 in a browser.  
Login: `neo4j` / `changeme`

Run these Cypher queries:

**2.1a — Count all nodes:**
```cypher
MATCH (n) RETURN labels(n) AS type, count(n) AS count ORDER BY count DESC
```

**Expected:** Host (3), Application (10+), Service (5+), Vulnerability (4), SchemaVersion (1)

**2.1b — Verify hosts:**
```cypher
MATCH (h:Host) RETURN h.host_id, h.hostname, h.ip, h.os
```

**Expected:** 3 rows — `corebank-db-01`, `corebank-web-01`, `corp-ad-01`

**2.1c — Verify vulnerabilities linked to hosts:**
```cypher
MATCH (h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability) 
RETURN h.host_id, v.cve_id, v.cvss, v.severity
```

**Expected:** 4 rows (2 on corebank-db-01, 1 each on the others)

**2.1d — Verify schema version:**
```cypher
MATCH (sv:SchemaVersion) RETURN sv
```

**Expected:** 1 node with `version: "1.1.0"`

### Test 2.2 — Presidio Health

```bash
curl http://localhost:5001/health
```

**Expected:** `{"status":"success"}`

### Test 2.3 — Presidio Analyze

```bash
curl -X POST http://localhost:5001/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text": "John Doe email john@example.com card 4716190207394368", "language": "en"}'
```

**Expected:** JSON array with entities like `PERSON`, `EMAIL_ADDRESS`, `CREDIT_CARD`

---

## Phase 3: ORC Service Tests

### Test 3.0 — Start ORC

```bash
uvicorn app.main:app --port 8000 --host 0.0.0.0
```

> [!NOTE]
> uvicorn does NOT auto-reload by default. After any code changes, restart it with `Ctrl+C` then re-run. You can add `--reload` for development: `uvicorn app.main:app --port 8000 --reload`

Keep this running in a separate terminal. All following tests use `curl` against port 8000.

### Test 3.1 — Health Check

```bash
curl http://localhost:8000/health
```

**Expected:** `{"status":"healthy","neo4j":"connected"}`

### Test 3.2 — Crown Jewels (should be empty initially)

```bash
curl http://localhost:8000/query/crown-jewels
```

**Expected:** `{"crown_jewels":[]}`  
(No data-change events processed yet, so no DataAssets with crown_jewel=true)

---

## Phase 4: Data-Change Pipeline (End-to-End)

### Test 4.1 — Send a Data-Change Event

```bash
curl -s -X POST http://localhost:8000/ingest/data-change \
  -H 'Content-Type: application/json' \
  -d @fixtures/data_changes/bank_data_change_001.json | python3 -m json.tool
```

**Expected response structure:**
```json
{
    "asset_id": "corebank-db-01",
    "asset_hash": "corebank-db-01::...",
    "current_sensitivity_score": <number 0.0-1.0>,
    "asset_importance_score": <number 0.0-1.0>,
    "crown_jewel": true/false,
    "detected_pii_types": ["CREDIT_CARD", "EMAIL_ADDRESS", "IBAN_CODE", ...],
    "pii_counts_summary": {"CREDIT_CARD": ..., ...},
    "risk_analysis": {
        "risk_score": <number>,
        "risk_level": "CRITICAL"/"HIGH"/"MEDIUM"/"LOW",
        ...
    }
}
```

**Key things to verify:**
- `detected_pii_types` includes critical banking entities (CREDIT_CARD, IBAN_CODE, US_SSN, etc.)
- `risk_analysis.risk_level` is HIGH or CRITICAL (the fixture has dense PII)
- `current_sensitivity_score` > 0
- `asset_importance_score` > `current_sensitivity_score` (DB role bonus adds 0.10)

### Test 4.2 — Verify DataAsset Created in Neo4j

Open Neo4j Browser and run:
```cypher
MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host {host_id: "corebank-db-01"})
RETURN d.asset_hash, d.sensitivity_score, d.crown_jewel, d.pii_types, d.scan_status
```

**Expected:** 1 row with `scan_status: "scanned"`, sensitivity_score matching the API response.

### Test 4.3 — Crown Jewels (after scan)

```bash
curl http://localhost:8000/query/crown-jewels | python3 -m json.tool
```

**Expected:** If sensitivity was high enough (≥0.7 after role/breadth bonuses), the asset appears here.

### Test 4.4 — High Sensitivity Query

```bash
curl "http://localhost:8000/query/high-sensitivity?threshold=0.3" | python3 -m json.tool
```

**Expected:** At least 1 result for `corebank-db-01`.

### Test 4.5 — Error Case: Unknown Host

```bash
curl -s -X POST http://localhost:8000/ingest/data-change \
  -H 'Content-Type: application/json' \
  -d '{"asset_id": "nonexistent-host-99", "content_items": ["test"]}' | python3 -m json.tool
```

**Expected:** HTTP 404, `"Host 'nonexistent-host-99' not found in Neo4j"`

---

## Phase 5: Core Alert Handling

### Test 5.1 — Ingest Core Alert (PostgreSQL CVE)

```bash
curl -s -X POST http://localhost:8000/ingest/core-alert \
  -H 'Content-Type: application/json' \
  -d @fixtures/alerts/core_alert_001.json | python3 -m json.tool
```

**Expected response:**
```json
{
    "action_id": "ALT-001",
    "status": "pending",
    "priority": "HIGH"/"CRITICAL"/"MEDIUM",
    "summary": "Critical PostgreSQL vulnerability on corebank-db-01",
    "enrichment": {
        "host_id": "corebank-db-01",
        "sensitivity_score": ...,
        "importance_score": ...,
        "crown_jewel": ...,
        "computed_priority": ...
    }
}
```

**Key things to verify:**
- `status` should be `"pending"` (auto-validated from `received`)
- If you ran Test 4.1 first, `enrichment` should have non-zero scores
- If no prior data-change, enrichment may be empty (no DataAssets yet)

### Test 5.2 — Ingest Second Alert (nginx CVE)

```bash
curl -s -X POST http://localhost:8000/ingest/core-alert \
  -H 'Content-Type: application/json' \
  -d @fixtures/alerts/core_alert_002.json | python3 -m json.tool
```

**Expected:** Similar structure with `action_id: "ALT-002"`, `status: "pending"`

### Test 5.3 — Verify ActionCards in Neo4j

```cypher
MATCH (ac:ActionCard) RETURN ac.action_id, ac.status, ac.origin, ac.action_type, ac.summary
```

**Expected:** 2 rows, both with `status: "pending"`

### Test 5.4 — Verify AFFECTS Relationships

```cypher
MATCH (ac:ActionCard)-[:AFFECTS]->(h:Host) 
RETURN ac.action_id, h.host_id
```

**Expected:** ALT-001 → corebank-db-01, ALT-002 → corebank-web-01

---

## Phase 6: ActionCard Lifecycle

### Test 6.1 — Check Status

```bash
curl http://localhost:8000/lifecycle/ALT-001/status
```

**Expected:** `{"action_id":"ALT-001","status":"pending"}`

### Test 6.2 — Assign to Analyst

```bash
curl -s -X POST http://localhost:8000/lifecycle/ALT-001/assign \
  -H 'Content-Type: application/json' \
  -d '{"analyst_id": "analyst-jsmith", "comment": "Assigned for review"}' | python3 -m json.tool
```

**Expected:** `{"action_id":"ALT-001","status":"assigned","analyst_id":"analyst-jsmith"}`

### Test 6.3 — Approve ActionCard

```bash
curl -s -X POST http://localhost:8000/lifecycle/ALT-001/approve \
  -H 'Content-Type: application/json' \
  -d '{"analyst_id": "analyst-jsmith", "comment": "Approved for patching"}' | python3 -m json.tool
```

**Expected:** `{"action_id":"ALT-001","status":"approved"}`

### Test 6.4 — Begin Execution

```bash
curl -s -X POST http://localhost:8000/lifecycle/ALT-001/execute | python3 -m json.tool
```

**Expected:** `{"action_id":"ALT-001","status":"executing"}`

### Test 6.5 — Complete Execution

```bash
curl -s -X POST http://localhost:8000/lifecycle/ALT-001/complete \
  -H 'Content-Type: application/json' \
  -d '{"outcome": "success", "details": "PostgreSQL patched to 15.6"}' | python3 -m json.tool
```

**Expected:** `{"action_id":"ALT-001","status":"completed"}`

### Test 6.6 — Reject an ActionCard

```bash
curl -s -X POST http://localhost:8000/lifecycle/ALT-002/reject \
  -H 'Content-Type: application/json' \
  -d '{"analyst_id": "analyst-jsmith", "reason": "False positive - version not affected"}' | python3 -m json.tool
```

**Expected:** `{"action_id":"ALT-002","status":"rejected"}`

### Test 6.7 — Verify Final Lifecycle in Neo4j

```cypher
MATCH (ac:ActionCard)
RETURN ac.action_id, ac.status, ac.approved_ts, ac.reject_reason
```

**Expected:** ALT-001 with `status: "completed"`, ALT-002 with `status: "rejected"`

---

## Phase 7: Delta Computation

### Test 7.1 — Compute Delta

```bash
curl -s -X POST "http://localhost:8000/delta/compute?last_synced_ts=2000-01-01T00:00:00Z" | python3 -m json.tool
```

**Expected:** `delta_id` and `changes_count` > 0 (all nodes were created after epoch)

### Test 7.2 — Verify DeltaEvent in Neo4j

```cypher
MATCH (de:DeltaEvent) RETURN de.delta_id, de.entity_count, de.sent_status
```

**Expected:** 1+ DeltaEvent with `sent_status: "pending"` and entity_count matching changes_count

### Test 7.3 — Acknowledge Delta

Use the `delta_id` from Test 7.1:

```bash
curl -s -X POST http://localhost:8000/delta/acknowledge/<DELTA_ID_HERE> | python3 -m json.tool
```

**Expected:** `{"delta_id":"...","status":"acknowledged"}`

---

## Phase 8: Wazuh Ingestion Endpoints

### Test 8.1 — Ingest a New Host

```bash
curl -s -X POST http://localhost:8000/ingest/wazuh-host \
  -H 'Content-Type: application/json' \
  -d '{"host_id": "test-host-99", "hostname": "test-host-99", "ip": "10.0.0.99", "os": "Linux", "source": "manual-test"}' | python3 -m json.tool
```

**Expected:** `{"host_id":"test-host-99","status":"ingested"}`

### Test 8.2 — Ingest a Vulnerability for the New Host

```bash
curl -s -X POST http://localhost:8000/ingest/wazuh-vulnerability \
  -H 'Content-Type: application/json' \
  -d '{"host_id": "test-host-99", "cve_id": "CVE-2024-12345", "cvss": 7.5, "severity": "HIGH", "summary": "Test vuln", "source": "manual-test"}' | python3 -m json.tool
```

**Expected:** `{"cve_id":"CVE-2024-12345","status":"ingested"}`

---

## Phase 9: Integration Tests (Automated)

```bash
python3 -m pytest tests/test_orc_pipeline.py -v
```

**Expected:** Tests run (not skipped) if Neo4j is up, all pass.

---

## Phase 10: Full Graph Inspection

After running all tests, inspect the complete graph:

```cypher
MATCH (n)-[r]->(m) 
RETURN labels(n) AS from_type, type(r) AS rel, labels(m) AS to_type, count(*) AS count
ORDER BY count DESC
```

**Expected relationships:**
| From | Relationship | To | Count |
|------|--------------|----|-------|
| Application | INSTALLED_ON | Host | 10+ |
| Service | RUNS_ON | Host | 5+ |
| Host | HAS_VULNERABILITY | Vulnerability | 4-5 |
| DataAsset | RESIDES_ON | Host | 1+ |
| ActionCard | AFFECTS | Host | 2 |
| ActionCard | APPROVED_BY | Analyst | 1 |
| ActionCard | ASSIGNED_TO | Analyst | 1 |
| ActionCard | EXECUTED | ExecutionEvent | 1 |

---

## Cleanup

```bash
# Stop ORC (Ctrl+C in the uvicorn terminal)

# Stop and remove containers
docker compose down

# Remove Neo4j data volume (full reset)
docker compose down -v
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'neo4j'` | `pip install --break-system-packages -r requirements.txt` |
| Neo4j connection refused | `docker ps` — check orbit-neo4j is healthy; verify `.env` password matches docker-compose |
| Presidio returns empty entities | `curl http://localhost:5001/health` — verify container is running |
| `404 Host not found` | Run `python3 -m app.seed` first |
| ActionCard stuck in `received` | Check origin and action_type are set — missing fields cause `failed` status |
| Schema errors | Run `python3 -m app.seed` — schema apply is idempotent |
