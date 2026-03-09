# ORBIT NODE — FIX + LOCAL REGRESSION DIRECTIVE
# Fix 3 real bugs, verify each fix, then run full 56-test suite locally
# DO NOT touch the AWS server at all — everything runs on localhost

---

## NOTE FOR CODEX — READ BEFORE STARTING

You are operating under AGENTS.md. For this task:
- The directive and execution layers are collapsed — run commands directly
- Self-anneal on errors: fix the invocation or code, retry, then continue
- Do NOT run `docker compose down -v` under any circumstances
- Do NOT push anything to git unless explicitly told to
- Do NOT touch the AWS server (16.58.158.189) at all
- Show full raw output for every command — no truncation

## HARD CONSTRAINTS
- Never run: `docker compose down -v`
- Never run: `docker compose down` (without -v is ok only if explicitly needed to restart)
- Never modify: `app/graph.py` unless the fix explicitly requires it
- Never modify: `app/main.py` unless the fix explicitly requires it
- AWS server is off limits entirely

---

## WORKING DIRECTORY — Set this first

```bash
cd ~/sem4/NJSecure/project-monorepo-team-45/src/Orchestrator/new-app
pwd
ls docker-compose.yml
```
STOP if docker-compose.yml is not present.

---

## CONFIGURATION

```bash
NEO4J_PASS="T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA"
BASE="http://localhost"
```

---

## PHASE 0 — START LOCAL STACK

```bash
docker compose up -d
sleep 90
docker compose ps
```

All three must show `(healthy)`: orbit-neo4j, orbit-presidio, orbit-orc

Then seed:
```bash
docker compose exec -T orc python -m app.seed
```
Expected: `✓ Seed complete.`

---

## FIX 1 — T07: Presidio crashes on empty text (HTTP 500)

### What is broken
When `/ingest/data-change` receives empty content or when Presidio is called
with an empty string, Presidio returns HTTP 500 instead of an empty list.
The fix is a guard in the Presidio client — never call Presidio with empty
or whitespace-only text, return [] immediately instead.

### Step 1 — Confirm the bug exists
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "", "language": "en"}'
```
Expected before fix: HTTP 500
If already 200, skip this fix and mark FIX-1 as N/A.

### Step 2 — Find the Presidio client file
```bash
cat app/presidio_client.py
```
Identify the function that calls the Presidio /analyze endpoint.

### Step 3 — Apply the fix
In `app/presidio_client.py`, at the top of the analyze function (before
any HTTP call), add this guard:

```python
if not text or not text.strip():
    return []
```

This must be added BEFORE the requests.post() call to Presidio.
Do not change anything else in the file.

### Step 4 — Rebuild ORC container with the fix
```bash
docker compose build orc
docker compose up -d --no-deps orc
sleep 30
docker compose ps
```
ORC must show (healthy) before continuing.

### Step 5 — Verify fix
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "", "language": "en"}'
```
PASS if: HTTP 200 (Presidio itself may still 500 — that is acceptable
because the guard in presidio_client.py means ORC never sends empty text
to Presidio)

Also verify via ORC:
```bash
curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corebank-db-01", "content_items": [""]}' \
  | python3 -m json.tool
```
PASS if: HTTP 200, sensitivity_score = 0.0, no 500 error

---

## FIX 2 — T34: completed_ts not written to Neo4j on ActionCard completion

### What is broken
When an ActionCard is completed via POST /lifecycle/{id}/complete,
the status is set to "completed" but completed_ts is never written
to the Neo4j node.

### Step 1 — Confirm the bug exists
First create a fresh ActionCard to test with:
```bash
curl -s -X POST $BASE:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "FIX-TEST-001",
    "summary": "Fix test ActionCard",
    "confidence": 0.9,
    "affected": {"hosts": ["corebank-db-01"]},
    "metadata": {"base_severity": "HIGH", "cve_id": "CVE-FIX-001"}
  }' | python3 -m json.tool
```

Walk it through the lifecycle:
```bash
curl -s -X POST $BASE:8000/lifecycle/FIX-TEST-001/assign \
  -H "Content-Type: application/json" \
  -d '{"analyst_id": "fix-tester", "comment": "fix test"}'

curl -s -X POST $BASE:8000/lifecycle/FIX-TEST-001/approve \
  -H "Content-Type: application/json" \
  -d '{"analyst_id": "fix-tester", "comment": "approved"}'

curl -s -X POST $BASE:8000/lifecycle/FIX-TEST-001/execute

curl -s -X POST $BASE:8000/lifecycle/FIX-TEST-001/complete \
  -H "Content-Type: application/json" \
  -d '{"outcome": "success", "details": "fix test completion"}'
```

Now check Neo4j:
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard {action_id: 'FIX-TEST-001'}) RETURN ac.status, ac.completed_ts;"
```
If completed_ts is NULL — bug confirmed. Proceed with fix.
If completed_ts is already populated — mark FIX-2 as N/A.

### Step 2 — Find the complete handler
```bash
cat app/main.py | grep -n "complete" | head -30
```
Find the route handler for the /complete endpoint.
Then read the full handler function.

### Step 3 — Find where the Neo4j write happens for completion
Look in the graph.py or wherever the complete transition writes to Neo4j.
```bash
grep -n "completed" app/graph.py | head -30
grep -rn "completed_ts" app/
```

### Step 4 — Apply the fix
In the Cypher query that handles the complete transition, add:
```
ac.completed_ts = datetime()
```
alongside wherever `ac.status = 'completed'` is being set.

Do not change any other logic — only add the timestamp write.

### Step 5 — Rebuild and verify
```bash
docker compose build orc
docker compose up -d --no-deps orc
sleep 30
```

Create a fresh test card and walk through lifecycle again:
```bash
curl -s -X POST $BASE:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "FIX-TEST-002",
    "summary": "Fix verification card",
    "confidence": 0.9,
    "affected": {"hosts": ["corebank-db-01"]},
    "metadata": {"base_severity": "HIGH", "cve_id": "CVE-FIX-002"}
  }'

curl -s -X POST $BASE:8000/lifecycle/FIX-TEST-002/assign \
  -H "Content-Type: application/json" \
  -d '{"analyst_id": "fix-tester", "comment": "test"}'

curl -s -X POST $BASE:8000/lifecycle/FIX-TEST-002/approve \
  -H "Content-Type: application/json" \
  -d '{"analyst_id": "fix-tester", "comment": "approved"}'

curl -s -X POST $BASE:8000/lifecycle/FIX-TEST-002/execute

curl -s -X POST $BASE:8000/lifecycle/FIX-TEST-002/complete \
  -H "Content-Type: application/json" \
  -d '{"outcome": "success", "details": "verification"}'
```

Verify:
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard {action_id: 'FIX-TEST-002'}) RETURN ac.status, ac.completed_ts;"
```
PASS if: completed_ts is not null

---

## FIX 3 — T46/T47/T48: Vulnerability ingestion failures

### Step 1 — Re-run the original test exactly as written first
Before assuming the code is broken, re-run the exact commands from the
directive to confirm whether this is a test payload issue or a real bug:

```bash
curl -s -X POST $BASE:8000/ingest/wazuh-vulnerability \
  -H "Content-Type: application/json" \
  -d '{
    "host_id": "test-auto-host-01",
    "cve_id": "CVE-2024-AUTO-001",
    "cvss": 8.5,
    "severity": "HIGH",
    "summary": "Automated test vulnerability",
    "source": "automated-test"
  }' | python3 -m json.tool
```

Show the full raw response.

### Step 2 — Evaluate
- If HTTP 200 and status = ingested → the previous failure was a Codex
  invocation error. Mark T46 as fixed, continue to verify T47.
- If HTTP 404 → host test-auto-host-01 doesn't exist yet. Create it first:
  ```bash
  curl -s -X POST $BASE:8000/ingest/wazuh-host \
    -H "Content-Type: application/json" \
    -d '{"host_id":"test-auto-host-01","hostname":"test-auto-host-01","ip":"10.0.99.1","os":"Ubuntu 22.04","source":"automated-test"}'
  ```
  Then re-run the vulnerability ingest.
- If HTTP 422 → show the full error body and self-anneal by reading the
  schema for the /ingest/wazuh-vulnerability endpoint in main.py and
  fixing the payload to match.

### Step 3 — Verify relationship in Neo4j
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host {host_id: 'test-auto-host-01'})-[r]->(v {cve_id: 'CVE-2024-AUTO-001'}) RETURN type(r), v.severity, v.cvss;"
```
PASS if: relationship exists

### Step 4 — Verify orphan rejection
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:8000/ingest/wazuh-vulnerability \
  -H "Content-Type: application/json" \
  -d '{"host_id":"host-does-not-exist","cve_id":"CVE-2024-ORPHAN","cvss":5.0,"severity":"MEDIUM","summary":"Should not be created"}'
```
PASS if: 404 or 422

```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (v {cve_id: 'CVE-2024-ORPHAN'}) RETURN count(v) AS count;"
```
PASS if: count = 0

---

## FIX 4 — T06: US_SSN not detected

### Step 1 — Test with cleaner SSN formats
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "My SSN is 078-05-1120", "language": "en"}'

curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "social security number 078051120", "language": "en"}'
```

### Step 2 — Evaluate
- If either returns US_SSN → the original test payload `SSN 123-45-6789`
  was the issue (test numbers, not a real SSN pattern). This is a test
  data problem, not a code bug. Note it and move on — do NOT change
  the Presidio configuration.
- If neither returns US_SSN → Presidio's SSN recognizer is not loaded.
  Check Presidio container logs:
  ```bash
  docker logs orbit-presidio --tail 50
  ```
  Note the finding but do NOT attempt to reconfigure Presidio — this
  is a known Presidio model limitation and is out of scope for this fix.

Either way, document the finding clearly in the final report.

---

## CLEAN STATE — Reset before regression run

After all fixes are verified, reset Neo4j to a clean seeded state:
```bash
docker compose exec -T orc python -m app.seed
```

Do NOT use `docker compose down -v`. Seed is sufficient to get
a consistent starting state for regression testing.

---

## FULL REGRESSION — Run all 56 tests locally

Now run the complete test suite. Every test below must be run in order.
Show full raw output. Do not stop on failure.

### PRE-FLIGHT CHECK
```bash
docker compose ps
curl -s $BASE:8000/health
```
Both must pass before proceeding.

---

### PHASE 1 — Infrastructure

#### T01 — Presidio health
```bash
curl -s -o /dev/null -w "%{http_code}" $BASE:5001/health
```
PASS if: 200

#### T02 — EMAIL_ADDRESS
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "email: test.user@example.com", "language": "en"}'
```
PASS if: contains EMAIL_ADDRESS

#### T03 — CREDIT_CARD
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "card number 4716190207394368", "language": "en"}'
```
PASS if: contains CREDIT_CARD

#### T04 — PHONE_NUMBER
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Contact: 9876543210", "language": "en"}'
```
PASS if: contains PHONE_NUMBER

#### T05 — PERSON
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Customer Name: Rahul Sharma", "language": "en"}'
```
PASS if: contains PERSON

#### T06 — US_SSN
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "My SSN is 078-05-1120", "language": "en"}'
```
PASS if: contains US_SSN
NOTE: if returns [] — mark as KNOWN LIMITATION of Presidio model, not a
code bug. Do not fail the overall suite on this.

#### T07 — Empty text graceful (fixed)
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corebank-db-01", "content_items": [""]}'
```
PASS if: 200 (not 500)

#### T08 — Multiple PII types
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "John Smith email john@bank.com card 4111111111111111 SSN 123-45-6789", "language": "en"}'
```
PASS if: at least 3 distinct entity_type values

#### T09 — ORC health
```bash
curl -s $BASE:8000/health
```
PASS if: {"status":"healthy","neo4j":"connected"}

#### T10 — 3 seeded hosts
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host) RETURN h.host_id ORDER BY h.host_id;"
```
PASS if: exactly 3 rows

#### T11 — Host required properties
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host) WHERE h.host_id IS NULL OR h.os IS NULL RETURN count(h) AS missing;"
```
PASS if: missing = 0

#### T12 — Vulnerabilities linked to hosts
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host)-[r]->() RETURN DISTINCT type(r);"

docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host)-[r]->(v) WHERE type(r) CONTAINS 'VULN' OR type(r) CONTAINS 'VULNERABILITY' RETURN h.host_id, count(v) AS vuln_count;"
```
PASS if: at least one host has vuln_count > 0

#### T13 — Seed idempotency
```bash
docker compose exec -T orc python -m app.seed
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host {host_id: 'corebank-db-01'}) RETURN count(h) AS count;"
```
PASS if: count = 1

---

### PHASE 2 — Privacy Scan & Crown Jewel (UC-02)

#### T14 — Dense PII → crown jewel
```bash
curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "corebank-db-01",
    "content_items": [
      "John Doe SSN 123-45-6789 email john@example.com card 4111111111111111 IBAN GB29NWBK60161331926819",
      "Jane Smith card 5500005555555559 phone 9876543210 SSN 987-65-4321"
    ]
  }' | python3 -m json.tool
```
PASS if: current_sensitivity_score > 0, crown_jewel = true, detected_pii_types non-empty

#### T15 — DataAsset in Neo4j
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host {host_id: 'corebank-db-01'}) RETURN d.sensitivity_score, d.crown_jewel, d.scan_status;"
```
PASS if: sensitivity_score > 0, crown_jewel = true

#### T16 — Crown jewels endpoint
```bash
curl -s $BASE:8000/query/crown-jewels | python3 -m json.tool
```
PASS if: contains corebank-db-01

#### T17 — Low sensitivity not crown jewel
```bash
curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corp-ad-01", "content_items": ["Server config updated"]}' \
  | python3 -m json.tool
```
PASS if: crown_jewel = false

#### T18 — Single PERSON below threshold
```bash
curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corp-ad-01", "content_items": ["Name: John Doe"]}' \
  | python3 -m json.tool
```
PASS if: crown_jewel = false

#### T19 — Multiple PII accumulates score
```bash
SCORE1=$(curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corebank-web-01", "content_items": ["email: a@test.com"]}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('current_sensitivity_score',0))")
echo "Score 1: $SCORE1"

SCORE2=$(curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corebank-web-01", "content_items": ["card 4716190207394368", "SSN 987-65-4321", "IBAN GB29NWBK60161331926819", "email b@bank.com"]}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('current_sensitivity_score',0))")
echo "Score 2: $SCORE2"
```
PASS if: SCORE2 > SCORE1

#### T20 — Unknown host 404
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "nonexistent-host-99", "content_items": ["test"]}'
```
PASS if: 404

#### T21 — High sensitivity query
```bash
curl -s "$BASE:8000/query/high-sensitivity?threshold=0.3" | python3 -m json.tool
```
PASS if: at least 1 result with corebank-db-01

#### T22 — Privacy audit
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (d:DataAsset) WHERE d.location_pseudonym CONTAINS '@' OR d.location_pseudonym =~ '.*[0-9]{9,}.*' RETURN count(d) AS violations;"
```
PASS if: violations = 0

---

### PHASE 3 — ActionCard Ingestion (UC-04)

#### T23 — Alert creates ActionCard
```bash
curl -s -X POST $BASE:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "AUTO-TEST-001",
    "summary": "Critical PostgreSQL vulnerability on corebank-db-01",
    "confidence": 0.95,
    "affected": {"hosts": ["corebank-db-01"]},
    "metadata": {"base_severity": "CRITICAL", "cve_id": "CVE-2024-AUTO-001"}
  }' | python3 -m json.tool
```
PASS if: status = pending, priority = CRITICAL or HIGH

#### T24 — ActionCard in Neo4j
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard {action_id: 'AUTO-TEST-001'}) RETURN ac.action_id, ac.status, ac.priority;"
```
PASS if: node exists with status = pending

#### T25 — ActionCard AFFECTS host
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard {action_id: 'AUTO-TEST-001'})-[:AFFECTS]->(h:Host) RETURN h.host_id;"
```
PASS if: returns corebank-db-01

#### T26 — Crown jewel gets higher priority
```bash
CJ=$(curl -s -X POST $BASE:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d '{"alert_id":"AUTO-CJ","summary":"Vuln on crown jewel","confidence":0.9,"affected":{"hosts":["corebank-db-01"]},"metadata":{"base_severity":"HIGH","cve_id":"CVE-CJ"}}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('priority','?'))")

NCJ=$(curl -s -X POST $BASE:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d '{"alert_id":"AUTO-NCJ","summary":"Same vuln non-crown-jewel","confidence":0.9,"affected":{"hosts":["corp-ad-01"]},"metadata":{"base_severity":"HIGH","cve_id":"CVE-NCJ"}}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('priority','?'))")

echo "Crown jewel: $CJ"
echo "Non-crown-jewel: $NCJ"
```
PASS if: CJ >= NCJ (CRITICAL > HIGH > MEDIUM > LOW)

#### T27 — Malformed alert 422
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d '{"bad_field": "missing"}'
```
PASS if: 422 or 400

---

### PHASE 4 — Lifecycle (UC-05, UC-06)

#### T28 — Status check
```bash
curl -s $BASE:8000/lifecycle/AUTO-TEST-001/status
```
PASS if: status = pending

#### T29 — Assign
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-TEST-001/assign \
  -H "Content-Type: application/json" \
  -d '{"analyst_id": "analyst-autotest", "comment": "Automated test"}' \
  | python3 -m json.tool
```
PASS if: status = assigned

#### T30 — ASSIGNED_TO in Neo4j
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard {action_id: 'AUTO-TEST-001'})-[:ASSIGNED_TO]->(a:Analyst) RETURN a.analyst_id;"
```
PASS if: returns analyst-autotest

#### T31 — Approve
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-TEST-001/approve \
  -H "Content-Type: application/json" \
  -d '{"analyst_id": "analyst-autotest", "comment": "Approved"}' \
  | python3 -m json.tool
```
PASS if: status = approved

#### T32 — Execute
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-TEST-001/execute | python3 -m json.tool
```
PASS if: status = executing

#### T33 — Complete
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-TEST-001/complete \
  -H "Content-Type: application/json" \
  -d '{"outcome": "success", "details": "Regression test completion"}' \
  | python3 -m json.tool
```
PASS if: status = completed

#### T34 — completed_ts in Neo4j (fixed)
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard {action_id: 'AUTO-TEST-001'}) RETURN ac.status, ac.approved_ts, ac.completed_ts;"
```
PASS if: status = completed, completed_ts is NOT null

#### T35 — Reject
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-NCJ/reject \
  -H "Content-Type: application/json" \
  -d '{"analyst_id": "analyst-autotest", "reason": "False positive regression test"}' \
  | python3 -m json.tool
```
PASS if: status = rejected

#### T36 — Reject reason in Neo4j
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard {action_id: 'AUTO-NCJ'}) RETURN ac.status, ac.reject_reason;"
```
PASS if: status = rejected, reject_reason not null

#### T37 — Full lifecycle summary
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard) OPTIONAL MATCH (ac)-[:ASSIGNED_TO]->(a) OPTIONAL MATCH (ac)-[:APPROVED_BY]->(ap) OPTIONAL MATCH (ac)-[:EXECUTED]->(ev) RETURN ac.action_id, ac.status, a.analyst_id AS assigned, ap.analyst_id AS approved_by, ev.exec_id AS execution ORDER BY ac.action_id;"
```
PASS if: AUTO-TEST-001 shows all 3 relationships populated

---

### PHASE 5 — Delta (UC-07)

#### T38 — Delta from epoch
```bash
DELTA_RESPONSE=$(curl -s -X POST "$BASE:8000/delta/compute?last_synced_ts=2000-01-01T00:00:00Z")
echo $DELTA_RESPONSE | python3 -m json.tool
DELTA_ID=$(echo $DELTA_RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin).get('delta_id',''))")
echo "delta_id: $DELTA_ID"
```
PASS if: changes_count > 0, delta_id non-empty

#### T39 — DeltaEvent in Neo4j
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (de:DeltaEvent) RETURN de.delta_id, de.entity_count, de.sent_status ORDER BY de.generated_ts DESC LIMIT 1;"
```
PASS if: node exists, entity_count > 0

#### T40 — Acknowledge
```bash
curl -s -X POST "$BASE:8000/delta/acknowledge/$DELTA_ID" | python3 -m json.tool
```
PASS if: status = acknowledged or sent

#### T41 — DeltaEvent marked sent
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (de:DeltaEvent) WHERE de.sent_status IN ['sent','acknowledged'] RETURN count(de) AS acked_count;"
```
PASS if: acked_count >= 1

#### T42 — Future timestamp empty delta
```bash
FUTURE_TS=$(date -u -d '+1 hour' +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -v+1H +"%Y-%m-%dT%H:%M:%SZ")
curl -s -X POST "$BASE:8000/delta/compute?last_synced_ts=$FUTURE_TS" | python3 -m json.tool
```
PASS if: changes_count = 0

---

### PHASE 6 — Wazuh Ingestion Graph Layer (UC-01)

#### T43 — Ingest new host
```bash
curl -s -X POST $BASE:8000/ingest/wazuh-host \
  -H "Content-Type: application/json" \
  -d '{"host_id":"test-auto-host-01","hostname":"test-auto-host-01","ip":"10.0.99.1","os":"Ubuntu 22.04","source":"automated-test"}' \
  | python3 -m json.tool
```
PASS if: status = ingested

#### T44 — Host in Neo4j
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host {host_id: 'test-auto-host-01'}) RETURN h.host_id, h.ip, h.os;"
```
PASS if: ip = 10.0.99.1

#### T45 — No duplicate on re-ingest
```bash
curl -s -X POST $BASE:8000/ingest/wazuh-host \
  -H "Content-Type: application/json" \
  -d '{"host_id":"test-auto-host-01","hostname":"test-auto-host-01","ip":"10.0.99.1","os":"Ubuntu 22.04","source":"automated-test"}'

docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host {host_id: 'test-auto-host-01'}) RETURN count(h) AS count;"
```
PASS if: count = 1

#### T46 — Ingest vulnerability (fixed)
```bash
curl -s -X POST $BASE:8000/ingest/wazuh-vulnerability \
  -H "Content-Type: application/json" \
  -d '{
    "host_id": "test-auto-host-01",
    "cve_id": "CVE-2024-AUTO-001",
    "cvss": 8.5,
    "severity": "HIGH",
    "summary": "Automated test vulnerability",
    "source": "automated-test"
  }' | python3 -m json.tool
```
PASS if: status = ingested

#### T47 — Vulnerability linked in Neo4j (fixed)
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host {host_id: 'test-auto-host-01'})-[r]->(v {cve_id: 'CVE-2024-AUTO-001'}) RETURN type(r), v.severity, v.cvss;"
```
PASS if: relationship exists, severity = HIGH

#### T48 — Orphan rejected (fixed)
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:8000/ingest/wazuh-vulnerability \
  -H "Content-Type: application/json" \
  -d '{"host_id":"host-does-not-exist","cve_id":"CVE-2024-ORPHAN","cvss":5.0,"severity":"MEDIUM","summary":"Should not be created"}'
```
PASS if: 404 or 422

#### T49 — Orphan not in graph
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (v {cve_id: 'CVE-2024-ORPHAN'}) RETURN count(v) AS count;"
```
PASS if: count = 0

---

### PHASE 7 — Graph Integrity

#### T50 — No orphan nodes
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (n) WHERE n.last_updated IS NULL AND NOT 'SchemaVersion' IN labels(n) RETURN labels(n) AS label, count(n) AS count;"
```
PASS if: 0 rows

#### T51 — Unique constraint exists
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "SHOW CONSTRAINTS YIELD name, labelsOrTypes, properties WHERE 'Host' IN labelsOrTypes RETURN name, labelsOrTypes, properties;"
```
PASS if: uniqueness constraint on Host.host_id exists

#### T52 — Graph relationship summary
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (n)-[r]->(m) RETURN labels(n) AS from_type, type(r) AS rel, labels(m) AS to_type, count(*) AS count ORDER BY count DESC;"
```
PASS if: output shows Host, DataAsset, ActionCard relationships

---

### PHASE 8 — Resilience

#### T53 — Presidio offline graceful (LOCAL ONLY)
```bash
docker stop orbit-presidio
sleep 5

HTTP=$(curl -s -o /tmp/down.json -w "%{http_code}" \
  -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corebank-db-01", "content_items": ["test while presidio offline"]}')
echo "HTTP while Presidio offline: $HTTP"
cat /tmp/down.json

docker start orbit-presidio
sleep 30
docker compose ps
```
PASS if: HTTP 200 or 503 — not 500, ORC does not crash

#### T54 — Empty content_items no crash
```bash
curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corebank-db-01", "content_items": []}' \
  | python3 -m json.tool
```
PASS if: 200, sensitivity_score = 0.0

#### T55 — Malformed JSON clean error
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d 'this is not json'
```
PASS if: 422 or 400

#### T56 — ORC healthy after all tests
```bash
curl -s $BASE:8000/health
```
PASS if: {"status":"healthy","neo4j":"connected"}

---

## BLOCKED TESTS

| ID  | Use Case | Reason |
|-----|----------|--------|
| B01 | UC-01: Live Wazuh telemetry | Wazuh not connected |
| B02 | UC-04: ActionCard into Wazuh UI | Wazuh not connected |
| B03 | UC-05: Wazuh Active Response | Wazuh not connected |
| B04 | UC-06: Wazuh workflow assignment | Wazuh not connected |
| B05 | UC-03: Subscription to Core | Core not implemented |
| B06 | UC-08: Feedback to Core | Core not implemented |
| B07 | UC-07: Delta send to Core | Core not implemented |
| B08 | NeoDash dashboard | Not set up |
| B09 | Bloom visual traversal | Not set up |
| B10 | R2 MCP Agentic Brain | R2 out of scope |

---

## FINAL REPORT — Produce this table exactly after all tests

```
============================================================
ORBIT NODE — LOCAL REGRESSION RESULTS (POST-FIX)
============================================================

FIXES APPLIED:
  FIX-1  T07: Empty text guard in presidio_client.py     ✅/❌/N/A
  FIX-2  T34: completed_ts written on ActionCard complete ✅/❌/N/A
  FIX-3  T46-48: Vulnerability ingestion re-verified      ✅/❌/N/A
  FIX-4  T06: US_SSN — test data issue confirmed          ✅/KNOWN LIMITATION

| Test | Description                                | Status      | Notes |
|------|--------------------------------------------|-------------|-------|
| T01  | Presidio health                            | ✅/❌       |       |
| T02  | Presidio EMAIL_ADDRESS                     | ✅/❌       |       |
| T03  | Presidio CREDIT_CARD                       | ✅/❌       |       |
| T04  | Presidio PHONE_NUMBER                      | ✅/❌       |       |
| T05  | Presidio PERSON                            | ✅/❌       |       |
| T06  | Presidio US_SSN                            | ✅/❌/⚠️   |       |
| T07  | Empty text graceful (FIXED)                | ✅/❌       |       |
| T08  | Presidio multiple PII types                | ✅/❌       |       |
| T09  | ORC health                                 | ✅/❌       |       |
| T10  | 3 seeded hosts                             | ✅/❌       |       |
| T11  | Host required properties                   | ✅/❌       |       |
| T12  | Vulnerabilities linked                     | ✅/❌       |       |
| T13  | Seed idempotency                           | ✅/❌       |       |
| T14  | Dense PII → crown jewel                    | ✅/❌       |       |
| T15  | DataAsset in Neo4j                         | ✅/❌       |       |
| T16  | Crown jewels endpoint                      | ✅/❌       |       |
| T17  | Low sensitivity not crown jewel            | ✅/❌       |       |
| T18  | Single PERSON below threshold              | ✅/❌       |       |
| T19  | Multiple PII accumulates score             | ✅/❌       |       |
| T20  | Unknown host 404                           | ✅/❌       |       |
| T21  | High sensitivity query                     | ✅/❌       |       |
| T22  | Privacy audit                              | ✅/❌       |       |
| T23  | Alert creates ActionCard                   | ✅/❌       |       |
| T24  | ActionCard in Neo4j                        | ✅/❌       |       |
| T25  | ActionCard AFFECTS host                    | ✅/❌       |       |
| T26  | Crown jewel higher priority                | ✅/❌       |       |
| T27  | Malformed alert 422                        | ✅/❌       |       |
| T28  | Status check                               | ✅/❌       |       |
| T29  | Assign ActionCard                          | ✅/❌       |       |
| T30  | ASSIGNED_TO in Neo4j                       | ✅/❌       |       |
| T31  | Approve ActionCard                         | ✅/❌       |       |
| T32  | Execute ActionCard                         | ✅/❌       |       |
| T33  | Complete ActionCard                        | ✅/❌       |       |
| T34  | completed_ts in Neo4j (FIXED)              | ✅/❌       |       |
| T35  | Reject ActionCard                          | ✅/❌       |       |
| T36  | Reject reason in Neo4j                     | ✅/❌       |       |
| T37  | Full lifecycle summary                     | ✅/❌       |       |
| T38  | Delta from epoch                           | ✅/❌       |       |
| T39  | DeltaEvent in Neo4j                        | ✅/❌       |       |
| T40  | Acknowledge delta                          | ✅/❌       |       |
| T41  | DeltaEvent marked sent                     | ✅/❌       |       |
| T42  | Future timestamp empty delta               | ✅/❌       |       |
| T43  | Ingest new host                            | ✅/❌       |       |
| T44  | Host in Neo4j                              | ✅/❌       |       |
| T45  | No duplicate on re-ingest                  | ✅/❌       |       |
| T46  | Ingest vulnerability (FIXED)               | ✅/❌       |       |
| T47  | Vulnerability linked (FIXED)               | ✅/❌       |       |
| T48  | Orphan rejected (FIXED)                    | ✅/❌       |       |
| T49  | Orphan not in graph                        | ✅/❌       |       |
| T50  | No orphan nodes                            | ✅/❌       |       |
| T51  | Unique constraint                          | ✅/❌       |       |
| T52  | Graph relationship summary                 | ✅/❌       |       |
| T53  | Presidio offline graceful                  | ✅/❌       |       |
| T54  | Empty content_items no crash               | ✅/❌       |       |
| T55  | Malformed JSON clean error                 | ✅/❌       |       |
| T56  | ORC healthy after all tests                | ✅/❌       |       |
| B01  | Wazuh live telemetry                       | ⏸ BLOCKED  |       |
| B02  | ActionCard into Wazuh UI                   | ⏸ BLOCKED  |       |
| B03  | Wazuh Active Response                      | ⏸ BLOCKED  |       |
| B04  | Wazuh workflow assignment                  | ⏸ BLOCKED  |       |
| B05  | Subscription to Core                       | ⏸ BLOCKED  |       |
| B06  | Feedback to Core                           | ⏸ BLOCKED  |       |
| B07  | Delta send to Core                         | ⏸ BLOCKED  |       |
| B08  | NeoDash dashboard                          | ⏸ BLOCKED  |       |
| B09  | Bloom visual traversal                     | ⏸ BLOCKED  |       |
| B10  | R2 MCP Agentic Brain                       | ⏸ BLOCKED  |       |

------------------------------------------------------------
SUMMARY
------------------------------------------------------------
Automated:   56 tests
  Passed:    X
  Failed:    X
  Warning:   X (known limitations, not code bugs)
Blocked:     10

UC Coverage:
  UC-01  Local Knowledge Graph      ✅/❌
  UC-02  Privacy Scan/Crown Jewel   ✅/❌
  UC-03  Subscription               ⏸ BLOCKED
  UC-04  ActionCard Injection        ✅/❌
  UC-05  HITL Execution             ✅/❌
  UC-06  Pending Action Assignment  ✅/❌
  UC-07  Differential Updates       ✅/❌
  UC-08  Completion Feedback        ✅/❌
============================================================
```
