# ORBIT NODE — LOCAL TEST DIRECTIVE
# Run this NOW on your laptop while waiting for Vinay to fix the AWS network
# All commands run in WSL terminal from the new-app/ directory
# This is identical to the AWS directive except BASE=localhost and
# docker commands run directly (no SSH) plus T53 (Presidio offline) is included

---

## NOTE FOR CODEX — READ BEFORE STARTING

You are operating under AGENTS.md which defines a 3-layer architecture.
For this task, the directive and execution layers are collapsed into one:
the commands in this file ARE the execution layer. They are deterministic
bash/curl/docker commands — do NOT wrap them in Python scripts, do NOT look
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

## CONFIGURATION

```bash
NEO4J_PASS="T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA"
BASE="http://localhost"
```

Helper for cypher-shell:
```bash
cypher() {
  docker exec orbit-neo4j cypher-shell -u neo4j -p "$NEO4J_PASS" "$1"
}
```

---

## PRE-FLIGHT — Confirm stack is running

```bash
cd ~/sem4/NJSecure/project-monorepo-team-45/src/Orchestrator/new-app
docker compose ps
```

All three must be `(healthy)`: orbit-neo4j, orbit-presidio, orbit-orc

If not:
```bash
docker compose up -d
sleep 90
docker compose ps
```

Seed:
```bash
docker compose exec -T orc python -m app.seed
```
Expected: lines showing `Seeded host:` ending with `✓ Seed complete.`

---

## PHASE 1 — Infrastructure Verification (UC-02, UC-01)

### T01 — Presidio health
```bash
curl -s -o /dev/null -w "%{http_code}" $BASE:5001/health
```
PASS if: HTTP 200

### T02 — Presidio EMAIL_ADDRESS
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "email: test.user@example.com", "language": "en"}'
```
PASS if: contains `"EMAIL_ADDRESS"`

### T03 — Presidio CREDIT_CARD
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "card number 4716190207394368", "language": "en"}'
```
PASS if: contains `"CREDIT_CARD"`

### T04 — Presidio PHONE_NUMBER
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Contact: 9876543210", "language": "en"}'
```
PASS if: contains `"PHONE_NUMBER"`

### T05 — Presidio PERSON
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "Customer Name: Rahul Sharma", "language": "en"}'
```
PASS if: contains `"PERSON"`

### T06 — Presidio US_SSN
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "SSN 123-45-6789", "language": "en"}'
```
PASS if: contains `"US_SSN"`

### T07 — Presidio empty text graceful
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "", "language": "en"}'
```
PASS if: HTTP 200

### T08 — Presidio multiple PII types
```bash
curl -s -X POST $BASE:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "John Smith email john@bank.com card 4111111111111111 SSN 123-45-6789", "language": "en"}'
```
PASS if: at least 3 distinct entity_type values in response

### T09 — ORC health / Neo4j connected
```bash
curl -s $BASE:8000/health
```
PASS if: `{"status":"healthy","neo4j":"connected"}`

### T10 — Neo4j has exactly 3 seeded hosts
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host) RETURN h.host_id ORDER BY h.host_id;"
```
PASS if: exactly 3 rows — corebank-db-01, corebank-web-01, corp-ad-01

### T11 — All hosts have required properties
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host) WHERE h.host_id IS NULL OR h.os IS NULL RETURN count(h) AS missing;"
```
PASS if: missing = 0

### T12 — Vulnerabilities linked to hosts
```bash
# Discover relationship type first
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host)-[r]->() RETURN DISTINCT type(r);"

# Count vuln relationships
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host)-[r]->(v) WHERE type(r) CONTAINS 'VULN' OR type(r) CONTAINS 'VULNERABILITY' RETURN h.host_id, count(v) AS vuln_count;"
```
PASS if: at least one host has vuln_count > 0

### T13 — Seed idempotency
```bash
docker compose exec -T orc python -m app.seed
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host {host_id: 'corebank-db-01'}) RETURN count(h) AS count;"
```
PASS if: count = 1

---

## PHASE 2 — Privacy Scan & Crown Jewel (UC-02)

### T14 — Dense PII → high sensitivity + crown jewel
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

### T15 — DataAsset in Neo4j with correct properties
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host {host_id: 'corebank-db-01'})
   RETURN d.sensitivity_score, d.crown_jewel, d.scan_status;"
```
PASS if: sensitivity_score > 0, crown_jewel = true, scan_status = 'scanned'

### T16 — Crown jewels endpoint returns corebank-db-01
```bash
curl -s $BASE:8000/query/crown-jewels | python3 -m json.tool
```
PASS if: contains corebank-db-01

### T17 — Low-sensitivity content not crown jewel
```bash
curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corp-ad-01", "content_items": ["Server configuration file updated"]}' \
  | python3 -m json.tool
```
PASS if: crown_jewel = false

### T18 — Single PERSON field below threshold
```bash
curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corp-ad-01", "content_items": ["Name: John Doe"]}' \
  | python3 -m json.tool
```
PASS if: crown_jewel = false

### T19 — Multiple PII fields accumulate higher score
```bash
SCORE1=$(curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corebank-web-01", "content_items": ["email: a@test.com"]}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('current_sensitivity_score',0))")
echo "Score after 1 field: $SCORE1"

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
  -d '{"asset_id": "nonexistent-host-99", "content_items": ["test"]}'
```
PASS if: 404

### T21 — High sensitivity query works
```bash
curl -s "$BASE:8000/query/high-sensitivity?threshold=0.3" | python3 -m json.tool
```
PASS if: at least 1 result with corebank-db-01

### T22 — Privacy audit — no raw PII in graph
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (d:DataAsset)
   WHERE d.location_pseudonym CONTAINS '@'
      OR d.location_pseudonym =~ '.*[0-9]{9,}.*'
   RETURN count(d) AS violations;"
```
PASS if: violations = 0

---

## PHASE 3 — ActionCard Ingestion (UC-04)

### T23 — Valid alert creates ActionCard
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

### T24 — ActionCard node in Neo4j
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard {action_id: 'AUTO-TEST-001'}) RETURN ac.action_id, ac.status, ac.priority;"
```
PASS if: node exists with status = pending

### T25 — ActionCard AFFECTS correct host
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard {action_id: 'AUTO-TEST-001'})-[:AFFECTS]->(h:Host) RETURN h.host_id;"
```
PASS if: returns corebank-db-01

### T26 — Crown jewel host gets higher priority
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
PASS if: CJ >= NCJ (CRITICAL > HIGH > MEDIUM > LOW)

### T27 — Malformed alert → 422 not 500
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d '{"bad_field": "missing required fields"}'
```
PASS if: 422 or 400

---

## PHASE 4 — ActionCard Lifecycle (UC-05, UC-06)

### T28 — Status check
```bash
curl -s $BASE:8000/lifecycle/AUTO-TEST-001/status
```
PASS if: status = pending

### T29 — Assign to analyst
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-TEST-001/assign \
  -H "Content-Type: application/json" \
  -d '{"analyst_id": "analyst-autotest", "comment": "Automated test assignment"}' \
  | python3 -m json.tool
```
PASS if: status = assigned

### T30 — ASSIGNED_TO relationship in Neo4j
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard {action_id: 'AUTO-TEST-001'})-[:ASSIGNED_TO]->(a:Analyst) RETURN a.analyst_id;"
```
PASS if: returns analyst-autotest

### T31 — Approve
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-TEST-001/approve \
  -H "Content-Type: application/json" \
  -d '{"analyst_id": "analyst-autotest", "comment": "Approved"}' \
  | python3 -m json.tool
```
PASS if: status = approved

### T32 — Execute
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-TEST-001/execute | python3 -m json.tool
```
PASS if: status = executing

### T33 — Complete
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-TEST-001/complete \
  -H "Content-Type: application/json" \
  -d '{"outcome": "success", "details": "Patched by automated test"}' \
  | python3 -m json.tool
```
PASS if: status = completed

### T34 — Completed card verified in Neo4j
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard {action_id: 'AUTO-TEST-001'}) RETURN ac.status, ac.approved_ts, ac.completed_ts;"
```
PASS if: status = completed, approved_ts not null

### T35 — Reject ActionCard
```bash
curl -s -X POST $BASE:8000/lifecycle/AUTO-NCJ/reject \
  -H "Content-Type: application/json" \
  -d '{"analyst_id": "analyst-autotest", "reason": "False positive — automated test"}' \
  | python3 -m json.tool
```
PASS if: status = rejected

### T36 — Reject reason in Neo4j
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard {action_id: 'AUTO-NCJ'}) RETURN ac.status, ac.reject_reason;"
```
PASS if: status = rejected, reject_reason not null

### T37 — Full lifecycle graph summary
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard)
   OPTIONAL MATCH (ac)-[:ASSIGNED_TO]->(a)
   OPTIONAL MATCH (ac)-[:APPROVED_BY]->(ap)
   OPTIONAL MATCH (ac)-[:EXECUTED]->(ev)
   RETURN ac.action_id, ac.status, a.analyst_id AS assigned, ap.analyst_id AS approved_by, ev.exec_id AS execution
   ORDER BY ac.action_id;"
```
PASS if: AUTO-TEST-001 shows all 3 relationships populated

---

## PHASE 5 — Delta Computation (UC-07)

### T38 — Delta from epoch
```bash
DELTA_RESPONSE=$(curl -s -X POST \
  "$BASE:8000/delta/compute?last_synced_ts=2000-01-01T00:00:00Z")
echo $DELTA_RESPONSE | python3 -m json.tool
DELTA_ID=$(echo $DELTA_RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin).get('delta_id',''))")
echo "delta_id: $DELTA_ID"
```
PASS if: changes_count > 0, delta_id non-empty

### T39 — DeltaEvent in Neo4j
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (de:DeltaEvent) RETURN de.delta_id, de.entity_count, de.sent_status ORDER BY de.generated_ts DESC LIMIT 1;"
```
PASS if: node exists, entity_count > 0

### T40 — Acknowledge delta
```bash
curl -s -X POST "$BASE:8000/delta/acknowledge/$DELTA_ID" | python3 -m json.tool
```
PASS if: status = acknowledged or sent

### T41 — DeltaEvent marked sent in Neo4j
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (de:DeltaEvent) WHERE de.sent_status IN ['sent','acknowledged'] RETURN count(de) AS acked_count;"
```
PASS if: acked_count >= 1

### T42 — Future timestamp → empty delta
```bash
FUTURE_TS=$(date -u -d '+1 hour' +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -v+1H +"%Y-%m-%dT%H:%M:%SZ")
curl -s -X POST "$BASE:8000/delta/compute?last_synced_ts=$FUTURE_TS" | python3 -m json.tool
```
PASS if: changes_count = 0

---

## PHASE 6 — Wazuh Ingestion Graph Layer (UC-01)

### T43 — Ingest new host
```bash
curl -s -X POST $BASE:8000/ingest/wazuh-host \
  -H "Content-Type: application/json" \
  -d '{"host_id":"test-auto-host-01","hostname":"test-auto-host-01","ip":"10.0.99.1","os":"Ubuntu 22.04","source":"automated-test"}' \
  | python3 -m json.tool
```
PASS if: status = ingested

### T44 — Host in Neo4j with correct properties
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host {host_id: 'test-auto-host-01'}) RETURN h.host_id, h.ip, h.os;"
```
PASS if: ip = 10.0.99.1

### T45 — Re-ingest same host — no duplicate
```bash
curl -s -X POST $BASE:8000/ingest/wazuh-host \
  -H "Content-Type: application/json" \
  -d '{"host_id":"test-auto-host-01","hostname":"test-auto-host-01","ip":"10.0.99.1","os":"Ubuntu 22.04","source":"automated-test"}'

docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host {host_id: 'test-auto-host-01'}) RETURN count(h) AS count;"
```
PASS if: count = 1

### T46 — Ingest vulnerability
```bash
curl -s -X POST $BASE:8000/ingest/wazuh-vulnerability \
  -H "Content-Type: application/json" \
  -d '{"host_id":"test-auto-host-01","cve_id":"CVE-2024-AUTO-001","cvss":8.5,"severity":"HIGH","summary":"Automated test vuln","source":"automated-test"}' \
  | python3 -m json.tool
```
PASS if: status = ingested

### T47 — Vulnerability linked to host
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host {host_id: 'test-auto-host-01'})-[r]->(v {cve_id: 'CVE-2024-AUTO-001'}) RETURN type(r), v.severity, v.cvss;"
```
PASS if: relationship exists, severity = HIGH, cvss = 8.5

### T48 — Orphan vulnerability rejected
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:8000/ingest/wazuh-vulnerability \
  -H "Content-Type: application/json" \
  -d '{"host_id":"host-does-not-exist","cve_id":"CVE-2024-ORPHAN","cvss":5.0,"severity":"MEDIUM","summary":"Should not be created"}'
```
PASS if: 404 or 422

### T49 — Orphan CVE not in graph
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (v {cve_id: 'CVE-2024-ORPHAN'}) RETURN count(v) AS count;"
```
PASS if: count = 0

---

## PHASE 7 — Graph Integrity (all use cases)

### T50 — No orphan nodes missing last_updated
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (n) WHERE n.last_updated IS NULL AND NOT 'SchemaVersion' IN labels(n) RETURN labels(n) AS label, count(n) AS count;"
```
PASS if: 0 rows

### T51 — Unique constraint on host_id
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "SHOW CONSTRAINTS YIELD name, labelsOrTypes, properties WHERE 'Host' IN labelsOrTypes RETURN name, labelsOrTypes, properties;"
```
PASS if: uniqueness constraint on Host.host_id exists

### T52 — Full graph relationship summary
```bash
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (n)-[r]->(m) RETURN labels(n) AS from_type, type(r) AS rel, labels(m) AS to_type, count(*) AS count ORDER BY count DESC;"
```
PASS if: output shows Host, DataAsset, ActionCard relationships

---

## PHASE 8 — Resilience (LOCAL ONLY — do not run on AWS)

### T53 — ORC handles Presidio offline gracefully (UC-02 alternate flow)
```bash
docker stop orbit-presidio
sleep 5

HTTP=$(curl -s -o /tmp/down_response.json -w "%{http_code}" \
  -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corebank-db-01", "content_items": ["test while presidio offline"]}')
echo "HTTP while Presidio offline: $HTTP"
cat /tmp/down_response.json

docker start orbit-presidio
sleep 30
docker compose ps
```
PASS if: HTTP is 200 or 503 — not 500, ORC does not crash

### T54 — Empty content_items no crash
```bash
curl -s -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{"asset_id": "corebank-db-01", "content_items": []}' \
  | python3 -m json.tool
```
PASS if: HTTP 200, sensitivity_score = 0.0

### T55 — Malformed JSON → clean error
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST $BASE:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d 'this is not json'
```
PASS if: 422 or 400 (not 500)

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
| B04 | UC-06: Wazuh workflow assignment | Wazuh not connected |
| B05 | UC-03: Subscription send to ORBIT Core | Core not implemented |
| B06 | UC-08: Completion feedback to Core | Core not implemented |
| B07 | UC-07: Delta transmission to Core | Core not implemented |
| B08 | NeoDash Intelligence Dashboard | NeoDash not set up |
| B09 | Neo4j Bloom visual traversal | Bloom not set up |
| B10 | R2 MCP Agentic Brain | R2 out of scope |

---

## FINAL REPORT — Produce this table exactly

```
============================================================
ORBIT NODE — LOCAL TEST RESULTS
============================================================

| Test | Description                                    | Status      | Notes |
|------|------------------------------------------------|-------------|-------|
| T01  | Presidio health                                | ✅ / ❌     |       |
| T02  | Presidio EMAIL_ADDRESS                         | ✅ / ❌     |       |
| T03  | Presidio CREDIT_CARD                           | ✅ / ❌     |       |
| T04  | Presidio PHONE_NUMBER                          | ✅ / ❌     |       |
| T05  | Presidio PERSON                                | ✅ / ❌     |       |
| T06  | Presidio US_SSN                                | ✅ / ❌     |       |
| T07  | Presidio empty text graceful                   | ✅ / ❌     |       |
| T08  | Presidio multiple PII types                    | ✅ / ❌     |       |
| T09  | ORC health / Neo4j connected                   | ✅ / ❌     |       |
| T10  | Neo4j 3 seeded hosts                           | ✅ / ❌     |       |
| T11  | Hosts have required properties                 | ✅ / ❌     |       |
| T12  | Vulnerabilities linked to hosts                | ✅ / ❌     |       |
| T13  | Seed idempotency                               | ✅ / ❌     |       |
| T14  | Dense PII → high sensitivity + crown jewel     | ✅ / ❌     |       |
| T15  | DataAsset in Neo4j correct props               | ✅ / ❌     |       |
| T16  | Crown jewels endpoint returns db host          | ✅ / ❌     |       |
| T17  | Low-sensitivity not crown jewel                | ✅ / ❌     |       |
| T18  | Single PERSON below threshold                  | ✅ / ❌     |       |
| T19  | Multiple PII accumulates score                 | ✅ / ❌     |       |
| T20  | Unknown host returns 404                       | ✅ / ❌     |       |
| T21  | High-sensitivity query works                   | ✅ / ❌     |       |
| T22  | Privacy audit — no raw PII in graph            | ✅ / ❌     |       |
| T23  | Alert creates ActionCard                       | ✅ / ❌     |       |
| T24  | ActionCard in Neo4j                            | ✅ / ❌     |       |
| T25  | ActionCard AFFECTS host                        | ✅ / ❌     |       |
| T26  | Crown jewel gets higher priority               | ✅ / ❌     |       |
| T27  | Malformed alert → 422 not 500                  | ✅ / ❌     |       |
| T28  | Status check on pending ActionCard             | ✅ / ❌     |       |
| T29  | Assign ActionCard                              | ✅ / ❌     |       |
| T30  | ASSIGNED_TO in Neo4j                           | ✅ / ❌     |       |
| T31  | Approve ActionCard                             | ✅ / ❌     |       |
| T32  | Execute ActionCard                             | ✅ / ❌     |       |
| T33  | Complete ActionCard                            | ✅ / ❌     |       |
| T34  | Completed card in Neo4j with timestamps        | ✅ / ❌     |       |
| T35  | Reject ActionCard                              | ✅ / ❌     |       |
| T36  | Reject reason in Neo4j                         | ✅ / ❌     |       |
| T37  | Full lifecycle graph summary                   | ✅ / ❌     |       |
| T38  | Delta from epoch                               | ✅ / ❌     |       |
| T39  | DeltaEvent in Neo4j                            | ✅ / ❌     |       |
| T40  | Acknowledge delta                              | ✅ / ❌     |       |
| T41  | DeltaEvent marked sent                         | ✅ / ❌     |       |
| T42  | Future timestamp → empty delta                 | ✅ / ❌     |       |
| T43  | Ingest new host                                | ✅ / ❌     |       |
| T44  | New host in Neo4j                              | ✅ / ❌     |       |
| T45  | Re-ingest no duplicate                         | ✅ / ❌     |       |
| T46  | Ingest vulnerability                           | ✅ / ❌     |       |
| T47  | Vulnerability linked in Neo4j                  | ✅ / ❌     |       |
| T48  | Orphan vulnerability rejected                  | ✅ / ❌     |       |
| T49  | Orphan CVE not in graph                        | ✅ / ❌     |       |
| T50  | No orphan nodes                                | ✅ / ❌     |       |
| T51  | Unique constraint enforced                     | ✅ / ❌     |       |
| T52  | Graph relationship summary                     | ✅ / ❌     |       |
| T53  | ORC handles Presidio offline (LOCAL ONLY)      | ✅ / ❌     |       |
| T54  | Empty content_items no crash                   | ✅ / ❌     |       |
| T55  | Malformed JSON → clean error                   | ✅ / ❌     |       |
| T56  | ORC healthy after all error tests              | ✅ / ❌     |       |
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
  Passed:    X
  Failed:    X
Blocked:     10 (external systems not implemented)

UC Coverage:
  UC-01  Local Knowledge Graph      ✅ T09-T13, T43-T49
  UC-02  Privacy Scan/Crown Jewel   ✅ T01-T08, T14-T22
  UC-03  Subscription Optimization  ⏸ BLOCKED — Core not implemented
  UC-04  ActionCard Injection        ✅ T23-T27
  UC-05  HITL Execution             ✅ T28-T37
  UC-06  Pending Action Assignment  ✅ T29-T30, T35-T37
  UC-07  Differential Updates       ✅ T38-T42 (local delta; Core send blocked)
  UC-08  Completion Feedback        ✅ T33-T34 (local graph; Core send blocked)
============================================================
```
