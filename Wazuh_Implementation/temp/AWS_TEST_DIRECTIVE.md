# ORBIT NODE — AWS TEST DIRECTIVE
# Run this AFTER Vinay confirms the network is fixed
# All commands run via SSH from your WSL terminal
# Codex executes these sequentially and captures every output

---

## NOTE FOR CODEX — READ BEFORE STARTING

You are operating under AGENTS.md which defines a 3-layer architecture.
For this task, the directive and execution layers are collapsed into one:
the commands in this file ARE the execution layer. They are deterministic
bash/curl/SSH commands — do NOT wrap them in Python scripts, do NOT look
for execution/ scripts to run. Just execute each command directly in the
terminal, capture the full raw output, and evaluate the PASS/FAIL criteria
stated after each one.

Self-anneal as normal: if a command errors, read the error, fix the
invocation (e.g. wrong flag, path issue, container name mismatch), and
retry before marking it FAIL. Only mark FAIL if the application itself
is not meeting the stated criteria.

## WORKING DIRECTORY — Set this first, before anything else

```bash
cd ~/sem4/NJSecure/project-monorepo-team-45/src/Orchestrator/new-app
```

Confirm you are in the right place:
```bash
pwd
ls docker-compose.yml
```
STOP if docker-compose.yml is not present. You are in the wrong directory.

---

## CONFIGURATION — Set these before running anything

```bash
SSH_KEY="$HOME/.ssh/iiith-orbit-key.pem"
SERVER="ubuntu@16.58.158.189"
NEO4J_PASS="T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA"
BASE="http://16.58.158.189"
```

Helper aliases — run these once at the start of the session:
```bash
# SSH shorthand
alias SSH="ssh -i $SSH_KEY $SERVER"

# Remote curl shorthand
rcurl() { ssh -i $SSH_KEY $SERVER "curl -s $*"; }

# Remote cypher shorthand
cypher() {
  ssh -i $SSH_KEY $SERVER \
    "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \"$1\""
}
```

---

## PRE-FLIGHT — Confirm everything is running

### Step 1 — Confirm SSH works
```bash
ssh -i $SSH_KEY $SERVER "echo SSH_OK"
```
STOP if this does not return `SSH_OK`. Network is not fixed yet — wait for Vinay.

### Step 2 — Confirm all containers are healthy
```bash
ssh -i $SSH_KEY $SERVER "cd ~/orbit && docker compose ps"
```
Expected: orbit-neo4j, orbit-presidio, orbit-orc all showing `(healthy)`

If any container is not healthy:
```bash
ssh -i $SSH_KEY $SERVER "cd ~/orbit && docker compose up -d && sleep 90 && docker compose ps"
```

### Step 3 — Seed the database (idempotent, safe to re-run)
```bash
ssh -i $SSH_KEY $SERVER "cd ~/orbit && docker compose exec -T orc python -m app.seed"
```
Expected: lines showing `Seeded host:` ending with `✓ Seed complete.`

---

## PHASE 1 — Infrastructure Verification
### Maps to: UC-02 (Presidio), UC-01 (Neo4j seeded graph)

### T01 — Presidio health check
```bash
curl -s -o /dev/null -w "%{http_code}" $BASE:5001/health
```
PASS if: HTTP 200

### T02 — Presidio detects EMAIL_ADDRESS
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "email: test.user@example.com", "language": "en"}'
```
PASS if: response contains `"EMAIL_ADDRESS"`

### T03 — Presidio detects CREDIT_CARD
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "card number 4716190207394368", "language": "en"}'
```
PASS if: response contains `"CREDIT_CARD"`

### T04 — Presidio detects PHONE_NUMBER
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Contact: 9876543210", "language": "en"}'
```
PASS if: response contains `"PHONE_NUMBER"`

### T05 — Presidio detects PERSON
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Customer Name: Rahul Sharma", "language": "en"}'
```
PASS if: response contains `"PERSON"`

### T06 — Presidio detects US_SSN
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "SSN 123-45-6789", "language": "en"}'
```
PASS if: response contains `"US_SSN"`

### T07 — Presidio handles empty text without crashing
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "", "language": "en"}'
```
PASS if: HTTP 200

### T08 — Presidio detects multiple PII types in one payload
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "John Smith email john@bank.com card 4111111111111111 SSN 123-45-6789", "language": "en"}'
```
PASS if: response contains at least 3 distinct `entity_type` values

### T09 — ORC health check confirms Neo4j connected
```bash
curl -s $BASE:8000/health
```
PASS if: `{"status":"healthy","neo4j":"connected"}`

### T10 — Neo4j has exactly 3 seeded hosts
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (h:Host) RETURN h.host_id ORDER BY h.host_id;'"
```
PASS if: exactly 3 rows — `corebank-db-01`, `corebank-web-01`, `corp-ad-01`

### T11 — All hosts have required properties
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (h:Host) WHERE h.host_id IS NULL OR h.os IS NULL RETURN count(h) AS missing;'"
```
PASS if: `missing = 0`

### T12 — Vulnerabilities are linked to hosts
```bash
# First, discover the correct relationship type
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (h:Host)-[r]->() RETURN DISTINCT type(r);'"

# Then count vulnerability relationships
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (h:Host)-[r]->(v) WHERE type(r) CONTAINS \"VULN\" OR type(r) CONTAINS \"VULNERABILITY\" RETURN h.host_id, count(v) AS vuln_count;'"
```
PASS if: at least one host has vuln_count > 0

### T13 — Seed idempotency — re-seeding does not duplicate hosts
```bash
ssh -i $SSH_KEY $SERVER "cd ~/orbit && docker compose exec -T orc python -m app.seed"
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (h:Host {host_id: \"corebank-db-01\"}) RETURN count(h) AS count;'"
```
PASS if: count = 1

---

## PHASE 2 — Privacy Scan & Crown Jewel Classification (UC-02)

### T14 — Dense PII creates high-sensitivity DataAsset and crown jewel
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
PASS if:
- `current_sensitivity_score` > 0
- `crown_jewel` = true
- `detected_pii_types` is non-empty list

### T15 — DataAsset stored in Neo4j with correct properties
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host {host_id: \"corebank-db-01\"}) RETURN d.sensitivity_score, d.crown_jewel, d.scan_status;'"
```
PASS if: sensitivity_score > 0, crown_jewel = true, scan_status = 'scanned'

### T16 — Crown jewels endpoint returns corebank-db-01
```bash
curl -s $BASE:8000/query/crown-jewels | python3 -m json.tool
```
PASS if: response contains `corebank-db-01`

### T17 — Low-sensitivity content does not produce crown jewel
```bash
curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "corp-ad-01",
    "content_items": ["Server configuration file updated at 2025-01-01"]
  }' | python3 -m json.tool
```
PASS if: `crown_jewel` = false, `current_sensitivity_score` is 0 or very low

### T18 — Single PERSON field stays below crown jewel threshold
```bash
curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corp-ad-01", "content_items": ["Name: John Doe"]}' \
  | python3 -m json.tool
```
PASS if: `crown_jewel` = false

### T19 — Multiple PII fields on same asset accumulate higher score
```bash
SCORE1=$(curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corebank-web-01", "content_items": ["email: a@test.com"]}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('current_sensitivity_score',0))")
echo "Score after 1 PII field: $SCORE1"

SCORE2=$(curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corebank-web-01", "content_items": ["card 4716190207394368", "SSN 987-65-4321", "IBAN GB29NWBK60161331926819", "email b@bank.com"]}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('current_sensitivity_score',0))")
echo "Score after dense PII: $SCORE2"
```
PASS if: SCORE2 > SCORE1

### T20 — Unknown host returns 404
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "nonexistent-host-99", "content_items": ["test data"]}'
```
PASS if: HTTP 404

### T21 — High sensitivity query endpoint returns results
```bash
curl -s "$BASE:8000/query/high-sensitivity?threshold=0.3" | python3 -m json.tool
```
PASS if: at least 1 result containing corebank-db-01

### T22 — Privacy audit — no raw PII stored in graph nodes
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (d:DataAsset) WHERE d.location_pseudonym CONTAINS \"@\" OR d.location_pseudonym =~ \".*[0-9]{9,}.*\" RETURN count(d) AS violations;'"
```
PASS if: violations = 0

---

## PHASE 3 — ActionCard Ingestion (UC-04)

### T23 — Valid alert creates ActionCard with correct priority
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
PASS if: `status` = pending, `priority` = CRITICAL or HIGH

### T24 — ActionCard node stored in Neo4j
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (ac:ActionCard {action_id: \"AUTO-TEST-001\"}) RETURN ac.action_id, ac.status, ac.priority;'"
```
PASS if: node exists with status = pending

### T25 — ActionCard has AFFECTS relationship to correct host
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (ac:ActionCard {action_id: \"AUTO-TEST-001\"})-[:AFFECTS]->(h:Host) RETURN h.host_id;'"
```
PASS if: returns corebank-db-01

### T26 — Crown jewel host gets higher priority than non-crown-jewel
```bash
CJ=$(curl -s -X POST $BASE:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d '{"alert_id":"AUTO-CJ","summary":"Vuln on crown jewel","confidence":0.9,"affected":{"hosts":["corebank-db-01"]},"metadata":{"base_severity":"HIGH","cve_id":"CVE-CJ"}}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('priority','?'))")

NCJ=$(curl -s -X POST $BASE:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d '{"alert_id":"AUTO-NCJ","summary":"Same vuln on non-crown-jewel","confidence":0.9,"affected":{"hosts":["corp-ad-01"]},"metadata":{"base_severity":"HIGH","cve_id":"CVE-NCJ"}}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('priority','?'))")

echo "Crown jewel priority:     $CJ"
echo "Non-crown-jewel priority: $NCJ"
```
PASS if: CJ priority >= NCJ priority (CRITICAL > HIGH > MEDIUM > LOW)

### T27 — Malformed alert returns 422 not 500
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d '{"bad_field": "missing required fields"}'
```
PASS if: HTTP 422 or 400 (not 500)

---

## PHASE 4 — ActionCard Lifecycle: HITL (UC-05, UC-06)

### T28 — Status check on pending ActionCard
```bash
curl -s $BASE:8000/lifecycle/AUTO-TEST-001/status
```
PASS if: status = pending

### T29 — Assign ActionCard to analyst (UC-06)
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-TEST-001/assign \
  -H "Content-Type: application/json" \
  -d '{"analyst_id": "analyst-autotest", "comment": "Automated test assignment"}' \
  | python3 -m json.tool
```
PASS if: status = assigned, analyst_id = analyst-autotest

### T30 — ASSIGNED_TO relationship in Neo4j
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (ac:ActionCard {action_id: \"AUTO-TEST-001\"})-[:ASSIGNED_TO]->(a:Analyst) RETURN a.analyst_id;'"
```
PASS if: returns analyst-autotest

### T31 — Approve ActionCard (UC-05 human approves)
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-TEST-001/approve \
  -H "Content-Type: application/json" \
  -d '{"analyst_id": "analyst-autotest", "comment": "Approved by automated test"}' \
  | python3 -m json.tool
```
PASS if: status = approved

### T32 — Execute ActionCard
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-TEST-001/execute \
  | python3 -m json.tool
```
PASS if: status = executing

### T33 — Complete ActionCard (UC-08 outcome recorded)
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-TEST-001/complete \
  -H "Content-Type: application/json" \
  -d '{"outcome": "success", "details": "Patched by automated test"}' \
  | python3 -m json.tool
```
PASS if: status = completed

### T34 — Completed ActionCard verified in Neo4j with timestamps
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (ac:ActionCard {action_id: \"AUTO-TEST-001\"}) RETURN ac.status, ac.approved_ts, ac.completed_ts;'"
```
PASS if: status = completed, approved_ts not null

### T35 — Reject a different ActionCard (UC-05 alternate flow)
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-NCJ/reject \
  -H "Content-Type: application/json" \
  -d '{"analyst_id": "analyst-autotest", "reason": "False positive — automated test"}' \
  | python3 -m json.tool
```
PASS if: status = rejected

### T36 — Rejected ActionCard has reject_reason in Neo4j
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (ac:ActionCard {action_id: \"AUTO-NCJ\"}) RETURN ac.status, ac.reject_reason;'"
```
PASS if: status = rejected, reject_reason not null

### T37 — Full lifecycle graph summary
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (ac:ActionCard) OPTIONAL MATCH (ac)-[:ASSIGNED_TO]->(a) OPTIONAL MATCH (ac)-[:APPROVED_BY]->(ap) OPTIONAL MATCH (ac)-[:EXECUTED]->(ev) RETURN ac.action_id, ac.status, a.analyst_id AS assigned, ap.analyst_id AS approved_by, ev.exec_id AS execution ORDER BY ac.action_id;'"
```
PASS if: AUTO-TEST-001 shows assigned, approved_by, and execution all populated

---

## PHASE 5 — Delta Computation (UC-07)

### T38 — Compute delta from epoch returns all changes
```bash
DELTA_RESPONSE=$(curl -s -X POST \
  "$BASE:8000/delta/compute?last_synced_ts=2000-01-01T00:00:00Z")
echo $DELTA_RESPONSE | python3 -m json.tool
DELTA_ID=$(echo $DELTA_RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin).get('delta_id',''))")
echo "Captured delta_id: $DELTA_ID"
```
PASS if: changes_count > 0, delta_id is non-empty

### T39 — DeltaEvent node stored in Neo4j
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (de:DeltaEvent) RETURN de.delta_id, de.entity_count, de.sent_status ORDER BY de.generated_ts DESC LIMIT 1;'"
```
PASS if: node exists, entity_count > 0

### T40 — Acknowledge delta
```bash
curl -s -X POST "$BASE:8000/delta/acknowledge/$DELTA_ID" | python3 -m json.tool
```
PASS if: status = acknowledged or sent

### T41 — DeltaEvent marked sent in Neo4j after acknowledgement
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (de:DeltaEvent) WHERE de.sent_status IN [\"sent\",\"acknowledged\"] RETURN count(de) AS acked_count;'"
```
PASS if: acked_count >= 1

### T42 — Future timestamp returns empty delta
```bash
FUTURE_TS=$(date -u -d '+1 hour' +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -v+1H +"%Y-%m-%dT%H:%M:%SZ")
curl -s -X POST "$BASE:8000/delta/compute?last_synced_ts=$FUTURE_TS" | python3 -m json.tool
```
PASS if: changes_count = 0 or empty delta

---

## PHASE 6 — Wazuh Ingestion Graph Layer (UC-01)

### T43 — Ingest a new host
```bash
curl -s -X POST $BASE:8000/ingest/wazuh-host \
  -H "Content-Type: application/json" \
  -d '{"host_id":"test-auto-host-01","hostname":"test-auto-host-01","ip":"10.0.99.1","os":"Ubuntu 22.04","source":"automated-test"}' \
  | python3 -m json.tool
```
PASS if: status = ingested

### T44 — New host exists in Neo4j with correct properties
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (h:Host {host_id: \"test-auto-host-01\"}) RETURN h.host_id, h.ip, h.os;'"
```
PASS if: node exists with ip = 10.0.99.1

### T45 — Re-ingesting same host creates no duplicate
```bash
curl -s -X POST $BASE:8000/ingest/wazuh-host \
  -H "Content-Type: application/json" \
  -d '{"host_id":"test-auto-host-01","hostname":"test-auto-host-01","ip":"10.0.99.1","os":"Ubuntu 22.04","source":"automated-test"}'

ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (h:Host {host_id: \"test-auto-host-01\"}) RETURN count(h) AS count;'"
```
PASS if: count = 1

### T46 — Ingest vulnerability for new host
```bash
curl -s -X POST $BASE:8000/ingest/wazuh-vulnerability \
  -H "Content-Type: application/json" \
  -d '{"host_id":"test-auto-host-01","cve_id":"CVE-2024-AUTO-001","cvss":8.5,"severity":"HIGH","summary":"Automated test vulnerability","source":"automated-test"}' \
  | python3 -m json.tool
```
PASS if: status = ingested

### T47 — Vulnerability linked to host in Neo4j
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (h:Host {host_id: \"test-auto-host-01\"})-[r]->(v {cve_id: \"CVE-2024-AUTO-001\"}) RETURN type(r), v.cve_id, v.severity, v.cvss;'"
```
PASS if: relationship exists with severity = HIGH, cvss = 8.5

### T48 — Orphan vulnerability rejected
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:8000/ingest/wazuh-vulnerability \
  -H "Content-Type: application/json" \
  -d '{"host_id":"host-does-not-exist","cve_id":"CVE-2024-ORPHAN","cvss":5.0,"severity":"MEDIUM","summary":"Should not be created"}'
```
PASS if: HTTP 404 or 422

### T49 — Orphan CVE not present in graph
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (v {cve_id: \"CVE-2024-ORPHAN\"}) RETURN count(v) AS count;'"
```
PASS if: count = 0

---

## PHASE 7 — Graph Integrity (all use cases)

### T50 — No orphan nodes missing last_updated
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (n) WHERE n.last_updated IS NULL AND NOT \"SchemaVersion\" IN labels(n) RETURN labels(n) AS label, count(n) AS orphan_count;'"
```
PASS if: 0 rows

### T51 — Unique constraint on host_id enforced
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'SHOW CONSTRAINTS YIELD name, labelsOrTypes, properties WHERE \"Host\" IN labelsOrTypes RETURN name, labelsOrTypes, properties;'"
```
PASS if: uniqueness constraint on Host.host_id exists

### T52 — Full graph relationship summary
```bash
ssh -i $SSH_KEY $SERVER \
  "docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  'MATCH (n)-[r]->(m) RETURN labels(n) AS from_type, type(r) AS rel, labels(m) AS to_type, count(*) AS count ORDER BY count DESC;'"
```
PASS if: output includes relationships for Host, DataAsset, ActionCard

---

## PHASE 8 — Resilience and Error Handling

### T53 — Malformed JSON body rejected cleanly
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d 'this is not json'
```
PASS if: HTTP 422 or 400 (not 500)

### T54 — Empty content_items handled without crash
```bash
curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corebank-db-01", "content_items": []}' \
  | python3 -m json.tool
```
PASS if: HTTP 200, sensitivity_score = 0.0, no traceback in response

### T55 — Malformed alert payload does not crash ORC
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d '{"junk": "data"}'
```
PASS if: HTTP 422 or 400 (not 500)

### T56 — ORC still healthy after all error tests
```bash
curl -s $BASE:8000/health
```
PASS if: `{"status":"healthy","neo4j":"connected"}`

---

## BLOCKED TESTS — Record as BLOCKED, do not attempt

| ID  | Use Case | Reason |
|-----|----------|--------|
| B01 | UC-01: Live Wazuh telemetry | Wazuh not connected |
| B02 | UC-04: Inject ActionCard into Wazuh UI | Wazuh not connected |
| B03 | UC-05: Wazuh Active Response execution | Wazuh not connected |
| B04 | UC-06: Wazuh native workflow assignment | Wazuh not connected |
| B05 | UC-03: Subscription send to ORBIT Core | Core not implemented |
| B06 | UC-08: Completion feedback to Core | Core not implemented |
| B07 | UC-07: Delta transmission to Core | Core not implemented |
| B08 | NeoDash Intelligence Dashboard | NeoDash not set up |
| B09 | Neo4j Bloom visual traversal | Bloom not set up |
| B10 | R2 MCP Agentic Brain | R2 out of scope |

---

## FINAL REPORT — Stored AWS run results

```
============================================================
ORBIT NODE — AWS TEST RESULTS
Server: 16.58.158.189
============================================================

| Test | Description                                    | Status      | Notes |
|------|------------------------------------------------|-------------|-------|
| T01  | Presidio health                                | ✅          |       |
| T02  | Presidio EMAIL_ADDRESS                         | ✅          |       |
| T03  | Presidio CREDIT_CARD                           | ✅          |       |
| T04  | Presidio PHONE_NUMBER                          | ✅          |       |
| T05  | Presidio PERSON                                | ✅          |       |
| T06  | Presidio US_SSN                                | ❌          | Returned `[]` |
| T07  | Presidio empty text graceful                   | ❌          | HTTP 500 |
| T08  | Presidio multiple PII types                    | ✅          |       |
| T09  | ORC health / Neo4j connected                   | ✅          |       |
| T10  | Neo4j 3 seeded hosts                           | ✅          |       |
| T11  | Hosts have required properties                 | ✅          |       |
| T12  | Vulnerabilities linked to hosts                | ✅          |       |
| T13  | Seed idempotency                               | ✅          |       |
| T14  | Dense PII → high sensitivity + crown jewel     | ✅          |       |
| T15  | DataAsset in Neo4j correct props               | ✅          |       |
| T16  | Crown jewels endpoint returns db host          | ✅          |       |
| T17  | Low-sensitivity not crown jewel                | ✅          |       |
| T18  | Single PERSON below threshold                  | ✅          |       |
| T19  | Multiple PII accumulates score                 | ✅          |       |
| T20  | Unknown host returns 404                       | ✅          |       |
| T21  | High-sensitivity query works                   | ✅          |       |
| T22  | Privacy audit — no raw PII in graph            | ✅          |       |
| T23  | Alert creates ActionCard                       | ✅          |       |
| T24  | ActionCard in Neo4j                            | ✅          | `ac.priority` was NULL, but node existed with `pending` |
| T25  | ActionCard AFFECTS host                        | ✅          |       |
| T26  | Crown jewel gets higher priority               | ✅          |       |
| T27  | Malformed alert → 422 not 500                  | ✅          |       |
| T28  | Status check on pending ActionCard             | ✅          |       |
| T29  | Assign ActionCard                              | ✅          |       |
| T30  | ASSIGNED_TO in Neo4j                           | ✅          |       |
| T31  | Approve ActionCard                             | ✅          |       |
| T32  | Execute ActionCard                             | ✅          |       |
| T33  | Complete ActionCard                            | ✅          |       |
| T34  | Completed card in Neo4j with timestamps        | ❌          | `completed_ts` was NULL |
| T35  | Reject ActionCard                              | ✅          |       |
| T36  | Reject reason in Neo4j                         | ✅          | Stored text normalized em dash to `?` |
| T37  | Full lifecycle graph summary                   | ✅          |       |
| T38  | Delta from epoch                               | ✅          |       |
| T39  | DeltaEvent in Neo4j                            | ✅          |       |
| T40  | Acknowledge delta                              | ✅          |       |
| T41  | DeltaEvent marked sent                         | ✅          |       |
| T42  | Future timestamp → empty delta                 | ✅          |       |
| T43  | Ingest new host                                | ✅          |       |
| T44  | New host in Neo4j                              | ✅          |       |
| T45  | Re-ingest no duplicate                         | ✅          |       |
| T46  | Ingest vulnerability                           | ❌          | Run used pre-fix invalid CVE payload; API rejected format |
| T47  | Vulnerability linked in Neo4j                  | ❌          | No relationship returned after T46 failure |
| T48  | Orphan vulnerability rejected                  | ❌          | Run used pre-fix invalid CVE payload; returned HTTP 400 |
| T49  | Orphan CVE not in graph                        | ✅          |       |
| T50  | No orphan nodes                                | ✅          |       |
| T51  | Unique constraint enforced                     | ✅          |       |
| T52  | Graph relationship summary                     | ✅          |       |
| T53  | Malformed JSON → clean error                   | ✅          |       |
| T54  | Empty content_items no crash                   | ✅          |       |
| T55  | Malformed alert no crash                       | ✅          |       |
| T56  | ORC healthy after all error tests              | ✅          |       |
| B01  | Wazuh live telemetry                           | ⏸ BLOCKED  | Wazuh not connected |
| B02  | ActionCard inject into Wazuh UI                | ⏸ BLOCKED  | Wazuh not connected |
| B03  | Wazuh Active Response execution                | ⏸ BLOCKED  | Wazuh not connected |
| B04  | Wazuh workflow assignment                      | ⏸ BLOCKED  | Wazuh not connected |
| B05  | Subscription to ORBIT Core                     | ⏸ BLOCKED  | Core not implemented |
| B06  | Completion feedback to Core                    | ⏸ BLOCKED  | Core not implemented |
| B07  | Delta send to Core                             | ⏸ BLOCKED  | Core not implemented |
| B08  | NeoDash dashboard                              | ⏸ BLOCKED  | Not set up |
| B09  | Bloom visual traversal                         | ⏸ BLOCKED  | Not set up |
| B10  | R2 MCP Agentic Brain                           | ⏸ BLOCKED  | R2 out of scope |

------------------------------------------------------------
SUMMARY
------------------------------------------------------------
Automated:   56 tests
  Passed:    50
  Failed:    6
Blocked:     10 (external systems not implemented)

UC Coverage:
  UC-01  Local Knowledge Graph      ❌ T09-T13 passed; T46-T48 failed; T43-T45, T49 passed
  UC-02  Privacy Scan/Crown Jewel   ❌ T06-T07 failed; all other UC-02 tests passed
  UC-03  Subscription Optimization  ⏸ BLOCKED — Core not implemented
  UC-04  ActionCard Injection       ✅ T23-T27
  UC-05  HITL Execution             ❌ T34 failed; T28-T33, T35-T37 passed
  UC-06  Pending Action Assignment  ✅ T29-T30, T35-T37
  UC-07  Differential Updates       ✅ T38-T42 (local delta; Core send blocked)
  UC-08  Completion Feedback        ❌ T33 passed, T34 failed; Core send blocked
============================================================
```
