# Directive 05 – Seed the Database and Run Smoke Tests

## Goal

1. Run the seed script to load the bank CSV data into Neo4j
2. Verify the graph looks correct
3. Run 5 tests to confirm the full system works end-to-end

This is the "is everything actually working?" directive.

---

## Prerequisites

- [ ] Directive 04 complete — all three containers running and healthy
- [ ] You are SSH'd into orbit-dev: `ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189`
- [ ] You are in the orbit directory: `cd ~/orbit`

---

## Step 1 – Run the Seed Script

The seed script loads the bank CSV file into Neo4j — hosts, services, and vulnerabilities.
It must run after Neo4j is healthy. It is safe to re-run at any time.

```bash
docker compose exec -T orc python -m app.seed
```

Watch the output as it runs. It should print lines showing hosts and vulnerabilities being loaded.

**Expected result:** Three hosts loaded:
- `corebank-db-01`
- `corebank-web-01`
- `corp-ad-01`

If the seed fails, read the error carefully and check Troubleshooting at the bottom.

---

## Step 2 – Verify the Graph in Neo4j

Run these queries to confirm the data was loaded correctly.

### Check all hosts exist

```bash
docker exec orbit-neo4j cypher-shell \
  -u neo4j \
  -p T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA \
  "MATCH (h:Host) RETURN h.host_id, h.os ORDER BY h.host_id;"
```

Expected: 3 rows — `corebank-db-01`, `corebank-web-01`, `corp-ad-01`

### Check vulnerabilities are attached

```bash
docker exec orbit-neo4j cypher-shell \
  -u neo4j \
  -p T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA \
  "MATCH (h:Host)-[:HAS_VULN]->(v) RETURN h.host_id, count(v) as vuln_count;"
```

Expected: rows with non-zero vuln counts against at least some hosts.

You can also open the Neo4j Browser in your web browser to see the graph visually:
- URL: `http://16.58.158.189:7474`
- Login: `neo4j` / `T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA`

---

## Step 3 – Run the 5 Smoke Tests

These tests confirm the full system works — from API call, through ORC logic, through
Presidio scanning, into Neo4j storage, and back out again.

Run all tests from inside the SSH session (still on the server):

### Test A – Health Check
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health
```
Expected: `200`

---

### Test B – PII Detection and DataAsset Creation

This sends a text containing a fake SSN, email, and credit card number to the API.
ORC sends it to Presidio to scan, scores the sensitivity, and stores a DataAsset in Neo4j.

```bash
curl -s -X POST http://localhost:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "corebank-db-01",
    "content_items": [
      "John Doe SSN 123-45-6789 email john@example.com card 4111111111111111"
    ]
  }'
```

Expected response contains:
- `"asset_id": "corebank-db-01"`
- `"current_sensitivity_score"` — a number above 0
- `"crown_jewel": true` — because it's a DB host with high PII
- `"detected_pii_types"` — list including things like `US_SSN`, `CREDIT_CARD`, `EMAIL_ADDRESS`

---

### Test C – Alert Ingestion and ActionCard Creation

This sends a security alert about `corebank-db-01`. ORC looks up the host's DataAsset
(created in Test B), scores the priority, and creates an ActionCard.

```bash
curl -s -X POST http://localhost:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "SMOKE-001",
    "summary": "Critical PostgreSQL vulnerability on corebank-db-01",
    "confidence": 0.95,
    "affected": {"hosts": ["corebank-db-01"]},
    "metadata": {"base_severity": "CRITICAL", "cve_id": "CVE-2024-99999"}
  }'
```

Expected response contains:
- an `alert_id` or `action_id` field
- `"priority": "CRITICAL"` or `"HIGH"`
- `"status": "pending"`

Note: Run Test B before Test C. If Test B hasn't run yet, priority will fall back to `MEDIUM`
because there's no DataAsset yet — this is expected behaviour, not a bug.

---

### Test D – Query Crown Jewels

Confirms the DataAsset from Test B is queryable through the API.

```bash
curl -s http://localhost:8000/query/crown-jewels
```

Expected: a JSON list containing at least one item with `"crown_jewel": true`
linked to `corebank-db-01`.

---

### Test E – Verify DataAsset Exists in Neo4j

Confirms the DataAsset was actually written to the graph.

```bash
docker exec orbit-neo4j cypher-shell \
  -u neo4j \
  -p T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA \
  "MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host {host_id: 'corebank-db-01'}) RETURN d.asset_hash, d.sensitivity_score, d.crown_jewel, d.pii_types;"
```

Expected: one row showing a DataAsset with a non-null `asset_hash`
and `sensitivity_score` greater than 0.

---

## Run All Tests at Once (Optional)

If you've copied the `execution/` folder to the server (it comes with new-app),
you can run all 5 tests in one command:

```bash
bash execution/smoke_test.sh http://localhost:8000
```

This prints ✅ or ❌ for each test and exits with a failure code if any fail.

---

## Done When

- [ ] Seed script completes without errors
- [ ] Neo4j shows exactly 3 hosts
- [ ] Vulnerabilities are attached to hosts
- [ ] Test A: `/health` returns `200`
- [ ] Test B: data-change returns sensitivity score > 0 and detected PII types
- [ ] Test C: core-alert creates ActionCard with priority `CRITICAL` or `HIGH`
- [ ] Test D: crown-jewels endpoint returns at least one result
- [ ] Test E: DataAsset exists in the Neo4j graph

---

## Troubleshooting

**Seed fails with `connection refused` or `Neo4j not reachable`:**
- Neo4j isn't ready yet. Check: `docker compose ps` — neo4j must show `(healthy)`.
- Wait another 60 seconds and try again.

**Seed fails with `authentication failed`:**
- The password in `.env` doesn't match what Neo4j was initialised with.
- Fix (this wipes the database and reinitialises it — fine if it's empty):
  ```bash
  docker compose down -v
  docker compose up -d
  sleep 90
  docker compose exec -T orc python -m app.seed
  ```

**Test B returns `"current_sensitivity_score": 0.0`:**
- Presidio isn't reachable. Check: `curl -s http://localhost:5001/health`
- If that fails, check Presidio logs: `docker compose logs presidio`
- The app degrades silently when Presidio is down — it still creates the DataAsset,
  just with a zero score. This hides outages, so always check Presidio explicitly.

**Test C returns `"priority": "MEDIUM"` instead of CRITICAL:**
- Run Test B first and wait a few seconds before running Test C.
- This is expected behaviour — without a DataAsset, there's no business context to score against.

**`cypher-shell: command not found`:**
- Use the container name explicitly: `docker exec orbit-neo4j cypher-shell ...`
- If that still fails, Neo4j may still be starting. Check: `docker compose ps`
