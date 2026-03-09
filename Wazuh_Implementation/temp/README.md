# ORBIT Node — Security Orchestration for Banking Infrastructure

> **Academic + Industry Prototype** | IIIT Hyderabad | Built on AWS EC2

ORBIT Node is a security orchestration system that monitors bank infrastructure, detects PII exposure, scores asset risk, and generates prioritised action items for security teams — all represented as a live graph.

---

## What It Does

When a security event occurs on a bank host — a vulnerability is detected, sensitive data is accessed, or a configuration changes — ORBIT:

1. **Receives the alert** via its REST API
2. **Scans for PII** using Microsoft Presidio (SSNs, credit cards, emails, etc.)
3. **Scores the risk** based on data sensitivity, host role, and alert severity
4. **Classifies crown jewels** — assets above a configurable importance threshold
5. **Creates an ActionCard** with a priority level (CRITICAL / HIGH / MEDIUM / LOW)
6. **Stores everything** in a Neo4j graph for visual exploration and querying

The result: a security team sees exactly which assets matter most and what needs to be done, ranked by business impact — not just technical severity.

---

## Architecture

```
                        ┌─────────────────────────────────────┐
                        │           orbit-dev (AWS EC2)        │
                        │                                      │
  Security Alerts ─────►│  ┌─────────┐     ┌──────────────┐  │
  Data Changes   ─────►│  │   ORC   │────►│    Neo4j     │  │
                        │  │ :8000   │     │  :7474/:7687 │  │
                        │  └────┬────┘     └──────────────┘  │
                        │       │                              │
                        │  ┌────▼────┐                        │
                        │  │Presidio │                        │
                        │  │  :5001  │                        │
                        │  └─────────┘                        │
                        └─────────────────────────────────────┘
```

| Component | Role | Port |
|-----------|------|------|
| **ORC** | FastAPI orchestrator — all endpoints, scoring logic, ActionCard generation | `8000` |
| **Neo4j** | Graph database — hosts, vulnerabilities, DataAssets, ActionCards | `7474` (browser), `7687` (bolt) |
| **Presidio** | Microsoft PII analyser — scans text for sensitive data | `5001` |

All three run as Docker containers under a single `docker-compose.yml` on one EC2 instance.

---

## Scoring Model

Every DataAsset gets an **importance score** that determines whether it's a crown jewel and the priority of any ActionCards generated against it.

```
sensitivity  = 0.6 × max_pii_score + 0.4 × avg(top_5_pii_scores)
importance   = sensitivity + role_bonus + breadth_bonus
crown_jewel  = importance >= CROWN_JEWEL_THRESHOLD (default: 0.75)
```

Role bonuses: `+0.2` for database hosts, `+0.1` for web hosts.

ActionCard priority is then determined by combining alert severity with the asset's importance score — a CRITICAL vulnerability on a crown jewel asset always surfaces at the top.

---

## Project Structure

```
new-app/
├── app/
│   ├── main.py              ← FastAPI app — all API endpoints
│   ├── seed.py              ← Bootstrap script — loads bank data into Neo4j
│   ├── graph.py             ← Neo4j driver and graph query layer
│   ├── presidio_client.py   ← Presidio API wrapper
│   ├── presidio_bank.py     ← Bank-specific PII/risk adapter
│   ├── priority.py          ← Scoring and priority logic
│   ├── config.py            ← Environment variable config
│   └── stubs/
│       ├── wazuh_source.py  ← Wazuh telemetry stub (real integration pending)
│       └── core_source.py   ← CORE alert stub
├── fixtures/
│   ├── bank/ORBIT_simulated_bank.csv   ← Simulated bank asset data
│   └── wazuh/hosts.json + vulnerabilities.json
├── Neo4j/execution/         ← Graph schema and ingestion utilities
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Deployment

- Note that the IP is now elastic, and `16.58.158.189` is the address

### Prerequisites

- AWS CLI configured (`aws configure`, region: `us-east-2`)
- SSH key at `~/.ssh/iiith-orbit-key.pem` with permissions `400`
- Docker Desktop (for local testing)
- WSL (Ubuntu) on Windows, or any Linux/macOS terminal

### Local Build and Test

```bash
# From the new-app directory:
docker compose up -d

# Wait ~90 seconds for Neo4j to initialise, then:
curl http://localhost:8000/health
# Expected: {"status":"healthy","neo4j":"connected"}

# Seed the database:
docker compose exec -T orc python -m app.seed
```

### Deploy to AWS

```bash
# Copy to server:
rsync -avz \
  --exclude '__pycache__' --exclude '*.pyc' --exclude '.env' --exclude '.git' \
  -e "ssh -i ~/.ssh/iiith-orbit-key.pem" \
  ./ ubuntu@<SERVER_IP>:~/orbit/

# Build and start on server:
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@<SERVER_IP> \
  "cd ~/orbit && docker compose build orc && docker compose up -d"
```

### Environment Variables (`.env`)

Create `~/orbit/.env` on the server — never commit this file:

```env
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<your_password>
PRESIDIO_URL=http://presidio:3000
CROWN_JEWEL_THRESHOLD=0.75
ROLE_BONUS_DB=0.2
ROLE_BONUS_WEB=0.1
BREADTH_BONUS_MAX=0.2
```

> **Note:** `PRESIDIO_URL` uses port `3000` — Presidio's internal Docker port. Port `5001` is the external host port only.

---

## API Reference

### Health Check
```
GET /health
```
Returns `{"status":"healthy","neo4j":"connected"}` when all systems are up.

### Ingest a Data Change
```
POST /ingest/data-change
```
Triggers a PII scan on the provided content, scores sensitivity, and creates or updates a DataAsset in Neo4j.

```bash
curl -X POST http://<SERVER_IP>:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "corebank-db-01",
    "content_items": ["Customer SSN 123-45-6789 and card 4111111111111111"]
  }'
```

Response includes: `sensitivity_score`, `crown_jewel`, `detected_pii_types`.

### Ingest a Security Alert
```
POST /ingest/core-alert
```
Creates an ActionCard from a security alert, scored against the affected host's DataAsset.

```bash
curl -X POST http://<SERVER_IP>:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "ALERT-001",
    "summary": "Critical vulnerability on corebank-db-01",
    "confidence": 0.95,
    "affected": {"hosts": ["corebank-db-01"]},
    "metadata": {"base_severity": "CRITICAL", "cve_id": "CVE-2024-XXXXX"}
  }'
```

Response includes: `priority` (CRITICAL/HIGH/MEDIUM/LOW), `status`.

### Query Crown Jewels
```
GET /query/crown-jewels
```
Returns all assets whose importance score meets the crown jewel threshold.

---

## Viewing the Graph

Open the Neo4j Browser at `http://<SERVER_IP>:7474` and run:

```cypher
// See all hosts and their assets
MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host)
RETURN h.host_id, d.sensitivity_score, d.crown_jewel
ORDER BY d.sensitivity_score DESC;

// See all ActionCards
MATCH (a:ActionCard) RETURN a.action_id, a.priority, a.status;

// Full graph view
MATCH (n) RETURN n LIMIT 50;
```

---

## Current Status

| Component | Status |
|-----------|--------|
| ORC FastAPI app | ✅ Live on AWS |
| Neo4j graph database | ✅ Live on AWS |
| Presidio PII scanner | ✅ Live on AWS |
| Bank fixture data (CSV) | ✅ Seeded |
| Smoke tests (5/5) | ✅ Passing |
| Wazuh live telemetry | ⏳ Pending — stub in place |
| Bank simulation (CloudFormation) | ⏳ Pending — scripts ready, not deployed |
| GitHub Actions CI/CD | ⏳ Pending — GitHub access required |
| `/admin/refresh` endpoint | ⏳ Planned |

---

## Known Gaps and Next Steps

**1. Wazuh integration is stubbed**
`app/stubs/wazuh_source.py` reads from fixture files instead of polling a real Wazuh manager. The next step is replacing this with a real Wazuh API poller pointed at the Wazuh manager IP.

**2. Bank simulation not yet connected**
A CloudFormation-based bank simulation exists in `cloudFormationScripts-Bank-simulation/` that deploys simulated bank EC2 hosts with Wazuh agents. Once deployed, these hosts will generate real security telemetry for ORBIT to process. Pending confirmation of Wazuh server IP and AWS configuration.

**3. Delta computation not wired into ORC**
`Neo4j/execution/delta/compute_delta.py` exists but is not called by the API. Currently each `/ingest/data-change` call overwrites the previous state. Delta tracking — what changed vs last known state — needs to be integrated.

**4. Manual refresh only**
There is no automatic re-evaluation of assets when new alerts arrive. A planned `/admin/refresh` endpoint will re-scan all assets and recompute scores on demand. When Wazuh is connected, it will call this endpoint automatically.

**5. Crown jewel field not returned by `/query/crown-jewels`**
The endpoint correctly filters by `crown_jewel: true` in Neo4j but does not echo the field back in the response JSON. Known cosmetic gap — data is correct, response shape needs updating.

**6. No authentication on API endpoints**
All endpoints are currently open. Production deployment would require API key or token-based authentication before exposing to the network.

---

## Tech Stack

- **Python 3.11** + FastAPI + Uvicorn
- **Neo4j 5.18** Community Edition
- **Microsoft Presidio** (PII analyser)
- **Docker** + Docker Compose
- **AWS EC2** (us-east-2)
- **Wazuh 4.x** (security telemetry — integration pending)

---

## Acknowledgements

Built at IIIT Hyderabad. Infrastructure and Wazuh setup by Vinay.