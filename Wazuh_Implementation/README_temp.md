# ORBIT Orchestrator

This directory contains the ORBIT ORC service: the FastAPI-based orchestrator that sits between Neo4j, Presidio, Wazuh-shaped inventory/vulnerability data, and ORBIT Core-style alerts.

The orchestrator does four main jobs:

1. Seeds and maintains graph state in Neo4j.
2. Scans data-change events for PII via Presidio and stores derived DataAssets.
3. Converts external security alerts into ActionCards, enriches them with business context, and drives their lifecycle.
4. Computes graph deltas for export back to the wider system.

## What Lives Here

Key files and directories:

- `app/main.py`: FastAPI app and all HTTP endpoints.
- `app/seed.py`: bootstrap script that applies schema and loads fixture data.
- `app/graph.py`: Neo4j driver wrapper plus re-exported graph operations.
- `app/presidio_client.py`: low-level Presidio REST client.
- `app/presidio_bank.py`: bank-oriented PII/risk adapter on top of Presidio.
- `app/priority.py`: sensitivity, importance, crown-jewel, and action priority logic.
- `app/stubs/`: stub integrations for Wazuh and Core.
- `fixtures/`: local fixture data used by the seed path.
- `docker-compose.yml`: starts Neo4j and Presidio only.
- `.env.example`: runtime configuration template.

## Runtime Architecture

The service is split into three runtime pieces:

- Neo4j stores the graph, relationships, ActionCards, DataAssets, DeltaEvents, Analysts, and ExecutionEvents.
- Presidio performs entity detection over incoming content.
- The ORC FastAPI app coordinates ingestion, scoring, enrichment, lifecycle changes, and delta export.

Important current reality: `docker-compose.yml` does not start the FastAPI app. It starts only Neo4j and Presidio. The API itself is started separately with `uvicorn`.

## Ports

- `7474`: Neo4j Browser
- `7687`: Neo4j Bolt
- `5001`: Presidio Analyzer
- `8000`: ORC FastAPI API

## Configuration

Environment is loaded through `python-dotenv` from `.env`.

Main settings:

- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `PRESIDIO_URL`
- `CROWN_JEWEL_THRESHOLD`
- `ROLE_BONUS_DB`
- `ROLE_BONUS_WEB`
- `BREADTH_BONUS_MAX`

Notes:

- `.env.example` currently sets `CROWN_JEWEL_THRESHOLD=0.75`.
- If that variable is omitted entirely, the code defaults to `0.7`.
- The Neo4j password in `.env` must match the password used when the Neo4j container was initialized.

## Startup Workflow

### 1. Install Python dependencies

Recommended from this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Create `.env`

Copy the example and set a real Neo4j password:

```bash
cp .env.example .env
```

Minimum expected values:

```env
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme
PRESIDIO_URL=http://127.0.0.1:5001
```

### 3. Start infrastructure

Use Docker Compose if available:

```bash
docker compose up -d
```

If your environment does not have Compose, start equivalent Neo4j and Presidio containers manually.

### 4. Seed Neo4j

Run the seed script before starting the API:

```bash
python -m app.seed
```

What the seed does:

1. Applies the Neo4j schema.
2. Loads host data from `fixtures/bank/ORBIT_simulated_bank.csv`.
3. Derives services and applications from the CSV software column.
4. Loads Wazuh-shaped host and vulnerability fixtures from `fixtures/wazuh/`.

Expected seeded hosts:

- `corebank-db-01`
- `corebank-web-01`
- `corp-ad-01`

### 5. Start the API

Only start `uvicorn` after `python -m app.seed` succeeds:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

If you want to avoid accidentally starting the API after a failed seed, chain them:

```bash
python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## End-to-End Functional Workflows

### Workflow 1: Bootstrap and Graph Seeding

Purpose: create the initial graph the orchestrator needs in order to do anything useful.

Flow:

1. Connect to Neo4j.
2. Apply schema objects.
3. Ingest hosts from the bank CSV.
4. Ingest applications and services inferred from installed software.
5. Augment those hosts with Wazuh fixture data.
6. Ingest fixture vulnerabilities.

Result:

- Hosts exist in the graph.
- Vulnerabilities are attached to hosts.
- Application and service relationships exist.
- The API can now resolve host IDs during data-change and alert workflows.

### Workflow 2: Data-Change Event to DataAsset

Endpoint: `POST /ingest/data-change`

Input:

- `asset_id`
- `content_items[]`

Flow:

1. Check that the host exists in Neo4j.
2. Send each content item to Presidio through the bank adapter.
3. Aggregate entity detections into banking-oriented risk analysis.
4. Convert per-item risk into chunk sensitivity scores.
5. Compute `current_sensitivity_score`.
6. Infer a role hint from the host ID (`db`, `web`, `ad`).
7. Compute `asset_importance_score`.
8. Determine `crown_jewel`.
9. Hash the content payload into a stable `asset_hash`.
10. Persist a `DataAsset` in Neo4j linked to the host.

Returned fields:

- `asset_id`
- `asset_hash`
- `current_sensitivity_score`
- `asset_importance_score`
- `crown_jewel`
- `detected_pii_types`
- `pii_counts_summary`
- `risk_analysis`

Privacy behavior:

- The stored `location_pseudonym` is `host:<asset_id>`.
- Raw PII is not written into the graph by this endpoint.

Operational caveat:

- If Presidio is unreachable, the client currently falls back to empty detections instead of failing the request. That means this endpoint can still write a DataAsset with zero sensitivity.
- The HTTP response computes `crown_jewel` from importance in the API layer, but Neo4j persistence currently recomputes `d.crown_jewel` from sensitivity only. The response value and the stored graph value can therefore diverge.

### Workflow 3: Core Alert to ActionCard

Endpoint: `POST /ingest/core-alert`

Input:

- `alert_id`
- `origin`
- `action_type`
- `summary`
- `confidence`
- `recommended_ts`
- `affected`
- `metadata`

Flow:

1. Persist the incoming alert as an `ActionCard`.
2. Validate the ActionCard and auto-transition `received -> pending` if valid.
3. Look up any affected host IDs.
4. If a host has DataAssets, pick the highest-sensitivity one.
5. Recompute importance using host role and detected PII breadth.
6. Combine technical severity and business importance into a final priority.
7. Return the ActionCard state plus enrichment data.

Important behavior:

- If no matching DataAsset exists yet for the affected host, the ActionCard is still created.
- In that case, enrichment may be empty and priority falls back to `MEDIUM`.
- Missing affected hosts, assets, or services do not fail ingestion; unresolved targets are stored on the ActionCard instead.

### Workflow 4: ActionCard Lifecycle

Endpoints:

- `GET /lifecycle/{action_id}/status`
- `POST /lifecycle/{action_id}/assign`
- `POST /lifecycle/{action_id}/approve`
- `POST /lifecycle/{action_id}/reject`
- `POST /lifecycle/{action_id}/execute`
- `POST /lifecycle/{action_id}/complete`

State machine:

- `received -> pending | failed`
- `pending -> approved | rejected`
- `approved -> executing | rejected`
- `executing -> completed | failed`
- `completed`, `rejected`, and `failed` are terminal

Notes:

- Assigning requires the ActionCard to be `pending`.
- Approving requires the ActionCard to be in a state that allows `approved`.
- Rejecting is allowed from `pending` or `approved`.
- Completing uses the request `outcome`:
  - `"success"` becomes `completed`
  - anything else becomes `failed`
- The `assign` endpoint returns `"assigned"` in the HTTP response, but the persisted ActionCard status remains `pending`. Assignment is represented by relationships and fields, not by a separate lifecycle state.

Lifecycle side effects:

- `ASSIGNED_TO` relationships connect ActionCards to Analysts.
- `APPROVED_BY` relationships record approval.
- `EXECUTED` relationships connect ActionCards to ExecutionEvents.

### Workflow 5: Direct Wazuh Ingestion

Endpoints:

- `POST /ingest/wazuh-host`
- `POST /ingest/wazuh-vulnerability`

Purpose:

- Allow direct ingestion of a single host or vulnerability payload without re-running the seed process.

Typical use:

- Add a new host discovered by Wazuh.
- Add a vulnerability record for that host.
- Then enrich later alerts against the updated graph.

### Workflow 6: Delta Export

Endpoints:

- `POST /delta/compute`
- `POST /delta/acknowledge/{delta_id}`

Flow:

1. Compute changed entities since `last_synced_ts`.
2. Export them as a `DeltaEvent`.
3. Return the `delta_id` and change count.
4. Later, acknowledge that delta once the receiver confirms it.

Result:

- Delta history is tracked in Neo4j.
- `DeltaEvent.sent_status` moves through its own delivery flow.

## Scoring and Decision Logic

### Sensitivity

Computed from Presidio-derived per-item chunk scores:

```text
current_sensitivity_score = 0.6 * max_score + 0.4 * avg(top_5_scores)
```

If there are no chunk scores, sensitivity is `0.0`.

### Importance

Computed from sensitivity plus business context:

```text
importance = sensitivity + role_bonus + breadth_bonus
```

Role bonuses:

- database/application-server-like roles: `ROLE_BONUS_DB`
- web roles: `ROLE_BONUS_WEB`

Breadth bonus:

- based on the number of high-risk PII categories present
- capped by `BREADTH_BONUS_MAX`

### Crown Jewel

```text
crown_jewel = importance >= CROWN_JEWEL_THRESHOLD
```

Implementation note:

- The API layer follows the rule above.
- Neo4j `DataAsset` persistence currently recomputes `d.crown_jewel` from `sensitivity_score >= threshold` instead of importance.
- Query endpoints that read `d.crown_jewel` therefore use the persisted graph value, not necessarily the API response value.

### Action Priority

Priority combines:

- mapped technical severity
- business importance
- crown-jewel bump

Output labels:

- `CRITICAL`
- `HIGH`
- `MEDIUM`
- `LOW`

## Presidio Bank Adapter Behavior

The bank adapter adds domain-specific logic on top of raw Presidio detections:

- entity severity weights
- volume multiplier
- high-risk combination multiplier
- normalized risk-to-sensitivity mapping

High-risk combinations include examples like:

- `CREDIT_CARD + PERSON`
- `CREDIT_CARD + EMAIL_ADDRESS`
- `US_BANK_NUMBER + PERSON`
- `US_SSN + PERSON`

This makes data-change scoring more opinionated than plain entity counting.

## API Surface

| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| `GET` | `/health` | Check API to Neo4j connectivity | Only verifies Neo4j, not Presidio |
| `POST` | `/ingest/data-change` | Scan content and create/update a DataAsset | Requires host to already exist |
| `POST` | `/ingest/core-alert` | Create and enrich an ActionCard | Enrichment depends on existing DataAssets |
| `POST` | `/ingest/wazuh-host` | Ingest a host payload | Direct graph update |
| `POST` | `/ingest/wazuh-vulnerability` | Ingest a vulnerability payload | Direct graph update |
| `GET` | `/query/crown-jewels` | Return crown-jewel DataAssets | Uses graph query helper |
| `GET` | `/query/high-sensitivity` | Return DataAssets above threshold | Threshold defaults to `0.5` |
| `POST` | `/delta/compute` | Compute and export a delta | Accepts `last_synced_ts` query param |
| `POST` | `/delta/acknowledge/{delta_id}` | Mark a delta acknowledged | Delivery bookkeeping |
| `GET` | `/lifecycle/{action_id}/status` | Read ActionCard status | Read-only |
| `POST` | `/lifecycle/{action_id}/assign` | Assign pending ActionCard to analyst | Creates analyst relation |
| `POST` | `/lifecycle/{action_id}/approve` | Approve ActionCard | Transitions status |
| `POST` | `/lifecycle/{action_id}/reject` | Reject ActionCard | Records reason |
| `POST` | `/lifecycle/{action_id}/execute` | Move approved ActionCard into execution | Sets execution started timestamp |
| `POST` | `/lifecycle/{action_id}/complete` | Record execution outcome | Success completes, other outcomes fail |

## Minimal Verification Flow

### Infrastructure checks

```bash
curl http://127.0.0.1:5001/health
curl http://127.0.0.1:8000/health
```

### Seed verification in Neo4j Browser

```cypher
MATCH (h:Host) RETURN h.host_id, h.os;
```

### End-to-end data-change smoke test

```bash
curl -s -X POST http://127.0.0.1:8000/ingest/data-change \
  -H 'Content-Type: application/json' \
  -d '{
    "asset_id": "corebank-db-01",
    "content_items": [
      "John Doe SSN 123-45-6789 email john@example.com card 4111111111111111"
    ]
  }'
```

### Graph verification for that DataAsset

```cypher
MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host {host_id: "corebank-db-01"})
RETURN d.asset_hash, d.sensitivity_score, d.crown_jewel, d.pii_types;
```

### ActionCard smoke test

```bash
curl -s -X POST http://127.0.0.1:8000/ingest/core-alert \
  -H 'Content-Type: application/json' \
  -d '{
    "alert_id": "ALT-001",
    "summary": "Critical PostgreSQL vulnerability on corebank-db-01",
    "confidence": 0.95,
    "affected": {"hosts": ["corebank-db-01"]},
    "metadata": {"base_severity": "CRITICAL", "cve_id": "CVE-2024-99999"}
  }'
```

## Stubs and Fixtures

Current fixture-backed integrations:

- `FixtureWazuhSource` reads `fixtures/wazuh/hosts.json` and `fixtures/wazuh/vulnerabilities.json`.
- `MockCoreSource` is designed to read alert fixtures and write exported payloads into `.tmp/core_mock/`.

Current repo note:

- The `MockCoreSource` expects `fixtures/alerts/`, but that directory is not currently present in this repository.

## Known Gaps and Repo Caveats

1. `docker-compose.yml` does not run the FastAPI app. Start `uvicorn` separately.
2. `GET /health` checks Neo4j only. It does not verify Presidio availability.
3. The data-change path degrades gracefully if Presidio is unavailable, which can hide scanner outages unless you test Presidio directly.
4. `assign` is not a real persisted ActionCard status even though the endpoint returns `"assigned"`.
5. The API-layer and graph-layer `crown_jewel` calculations are currently inconsistent.
6. `TESTING_GUIDE.md` references some fixture files and tests that are not currently in the repo.
7. The Core stub expects alert fixtures that are not currently checked in.

## Related Docs

- `TESTING_GUIDE.md`: manual API and flow checks
- `../Neo4j/neo4j-local/execution/tests/MANUAL_TESTING_GUIDE.md`: deeper Neo4j-side validation
- `../Presidio/presidio-local/PII_SCORING_STRATEGY.md`: Presidio scoring rationale
