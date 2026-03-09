# Directive: ORBIT.CyberGraph-Node — Neo4j Schema & Implementation

**Deliverable IDs:** D1 (amended), D2, D3, D4 implementation  
**Stack:** Neo4j 5.x, Python 3.10+, `neo4j` driver 5.x  
**Environment:** Docker (WSL2 / Windows), connection via `bolt://localhost:7687`  
**Primary reference:** `resources/Neo4j_Conceptual_Doc_v1.1_Amended.docx` — this is your authoritative spec. Read it fully before writing a single line of code.  
**Secondary references:** `resources/SRS (5).pdf`, `resources/TestPlan (1).pdf`, `resources/ORBIT MVP Use Cases User Stories v0.2 (1).docx`

---

## Your Goal

Implement the complete Neo4j graph layer for the ORBIT.CyberGraph-Node. This means:
1. Setting up the schema (constraints, indexes, SchemaVersion node) from the amended D2 spec
2. Writing idempotent ingestion scripts for every entity type from the amended D4 spec
3. Implementing ActionCard lifecycle management and the HITL (Human-in-the-Loop) patterns
4. Implementing delta computation and DeltaEvent tracking for Core sync
5. Writing a full test suite that validates idempotency, privacy rules, and contract compliance
6. Producing verification Cypher queries for Neo4j Bloom/NeoDash visualisation

The graph must be **privacy-safe by design**: no raw PII ever enters Neo4j. Presidio outputs are metadata only. This rule overrides all convenience.

---

## Theoretical Grounding — Read Before Coding

Before writing any script, reason through the following. Your execution code will be more correct if these ideas are internalised.

### Why MERGE, not CREATE?
The Node Agent runs continuously. Wazuh may send the same host 50 times per hour. Without MERGE, you create 50 duplicate Host nodes. MERGE on the canonical key (`host_id`, `cve_id`, `asset_hash`, `action_id`) is the single rule that makes ingestion safe. Every script you write must use MERGE on the canonical key, never bare CREATE (except for ExecutionEvent and DeltaEvent which are intentionally append-only audit records).

### Why last_updated on everything?
Delta computation works by querying `WHERE n.last_updated > datetime($last_synced_ts)`. If any template forgets to set `last_updated`, that entity becomes invisible to delta exports. It silently corrupts the Core's view. Treat `last_updated = datetime()` like a mandatory field — set it on every write, no exceptions.

### Why is crown_jewel a derived boolean, not an input?
`crown_jewel` is computed as `sensitivity_score >= CROWN_JEWEL_THRESHOLD` (default 0.7 from .env). It must be recomputed on every DataAsset update because Presidio scores can change over time. Never accept `crown_jewel` as an input from an external payload — always derive it locally from the current `sensitivity_score`.

### Why is ActionCard status 'received' initially, not 'pending'?
'received' means "arrived and persisted but not yet validated". 'pending' means "validated and awaiting human assignment". These are distinct states: an ActionCard could be rejected at validation step before it ever becomes 'pending'. The test plan checks for this distinction (tests 51, 52).

### Why are PendingActions not a separate label?
`ActionCard(status='pending') + [:ASSIGNED_TO]->(:Analyst)` is the complete model for UC-06. A separate `:PendingAction` label would duplicate state and cause sync issues. The test plan's references to "PendingAction node" mean ActionCard in pending status.

### Why composite keys for Service and Application?
A service `service_id` is only unique within a host (two different hosts can both run `nginx-001`). If you add a global UNIQUE constraint on `service_id`, MERGE will incorrectly unify two different nginx instances. The correct approach: generate `service_id = f"{host_id}::{port}::{proto}"` at ingestion time, making it globally unique. Same logic for Application: `app_id = f"{host_id}::{name}::{version}"`.

---

## Phase 0 — Environment Verification

**Goal:** Confirm Neo4j is reachable, APOC is loaded, driver version matches server.

**Create:** `execution/schema/00_verify_environment.py`

This script must:
- Load `.env` via `python-dotenv`
- Connect using `GraphDatabase.driver()` and call `driver.verify_connectivity()`
- Run `RETURN apoc.version() AS v` and assert result is not null
- Run `CALL dbms.components() YIELD name, versions, edition` and assert the Neo4j **server** major version is 5 (the server is Neo4j 5.x even though the Python driver is 6.x — these version numbers are independent)
- Print the server version, driver version (`import neo4j; neo4j.__version__`), and APOC version in the summary
- Exit with code 1 on any failure

**Run and verify before Phase 1. Do not proceed if this fails.**

---

## Phase 1 — Schema Setup (D2)

**Goal:** Apply all constraints and indexes from the amended D2 spec. Set SchemaVersion to 1.1.0.

**Create:** `execution/schema/01_apply_schema.py`

This script must apply the following in order. Use `IF NOT EXISTS` on every statement so re-running is safe.

### Uniqueness constraints (canonical keys — enables safe MERGE)
```
Host.host_id
Vulnerability.cve_id
DataAsset.asset_hash
ActionCard.action_id
Analyst.analyst_id
Threat.threat_id
Subscription.subscription_id
DeltaEvent.delta_id
SchemaVersion.name
ExecutionEvent.exec_id
```

### Existence constraints (optional, apply only if Neo4j Enterprise — check edition first)
```
Host.hostname
Vulnerability.cve_id
```
> Check `CALL dbms.components()` — if edition is 'community', skip existence constraints silently and log a warning. Do not fail.

### Indexes
```
Host(hostname)
Host(ip)
Service(name)
DataAsset(sensitivity_score)
DataAsset(crown_jewel)        ← new in v1.1
ActionCard(status)
Threat(severity)
Subscription(status)          ← new in v1.1
DeltaEvent(sent_status)       ← new in v1.1
```

### SchemaVersion node
After all constraints and indexes succeed, MERGE the SchemaVersion node:
```cypher
MERGE (s:SchemaVersion {name: 'orbit-node'})
SET s.version = '1.1.0',
    s.updated = datetime(),
    s.notes   = 'Initial implementation: Subscription, DeltaEvent, crown_jewel, scan_status, 6-state ActionCard lifecycle, standardised last_updated'
```

**Create:** `execution/schema/02_verify_schema.py`

This script must:
- Query all constraints via `SHOW CONSTRAINTS` and assert each expected constraint exists by name/type
- Query all indexes via `SHOW INDEXES` and assert each expected index exists
- Query SchemaVersion and assert version = '1.1.0'
- Print a clean ✓/✗ line per item
- Exit code 1 if any assertion fails

**Both scripts must be idempotent** (running them twice produces the same result, no errors on second run).

---

## Phase 2 — Core Ingestion Templates (D4)

**Goal:** Implement one Python module per entity type. Each module contains a single `ingest_*` function that takes a driver + payload dict and executes the MERGE pattern from D4.

All ingestion functions share these rules:
- Accept `driver` (Neo4j driver instance) and `payload` (dict, already validated)
- Use parameterised Cypher — zero string concatenation
- Set `last_updated = datetime()` on every node write
- Return the canonical ID of the node created/updated
- Raise a typed exception (not a bare Exception) on validation failure so callers can distinguish bad input from DB errors

### 2.1 — `execution/ingestion/ingest_host.py`

Function: `ingest_host(driver, payload) -> str`

Payload fields: `host_id`, `hostname`, `ip`, `os`, `agent_version`, `source`

Cypher: MERGE on `host_id`. ON CREATE sets `enrollment_ts`, `created_by`. ON MATCH updates `hostname`. Always sets `ip`, `os`, `agent_version`, `last_seen`, `last_updated`.

Edge cases:
- If `host_id` is None or empty string → raise `ValueError("host_id is required")`
- If `ip` is a list, store as-is (Neo4j supports list properties)

### 2.2 — `execution/ingestion/ingest_service.py`

Function: `ingest_service(driver, payload) -> str`

Payload fields: `host_id`, `name`, `port`, `proto`, `source`

**Composite key rule:** Generate `service_id = f"{host_id}::{port}::{proto}"` inside the function before the Cypher call. Never accept `service_id` from the payload directly — always derive it.

Cypher: MERGE on `service_id`. Then MATCH Host by `host_id`. MERGE `(h)-[:RUNS]->(s)` with `installed_ts`.

Edge cases:
- If host does not exist → raise `ValueError(f"Host {host_id} not found — ingest host first")`

### 2.3 — `execution/ingestion/ingest_application.py`

Function: `ingest_application(driver, payload) -> str`

Payload fields: `host_id`, `name`, `version`, `vendor`, `source`

Composite key: `app_id = f"{host_id}::{name}::{version}"`

Cypher: MERGE Application on `app_id`. MATCH Host. MERGE `(h)-[:HAS_APP]->(a)` with `first_seen`, `installed_version`.

### 2.4 — `execution/ingestion/ingest_vulnerability.py`

Function: `ingest_vulnerability(driver, payload) -> str`

Payload fields: `host_id`, `cve_id`, `cvss`, `published`, `summary`, `severity`, `source`

Cypher: MERGE `Vulnerability` on `cve_id`. MERGE `Host` on `host_id`. MERGE `(h)-[:HAS_VULNERABILITY]->(v)` setting `detected_on`, `source`, `severity` on relationship. Sets `last_updated` on both node and relationship.

Edge cases:
- Validate `cve_id` format: must match `^CVE-\d{4}-\d{4,}$`. Reject with `ValueError` if invalid.
- `cvss` must be float between 0.0 and 10.0. Reject if out of range.
- If `host_id` not found → raise `ValueError` (do not create orphan vulnerabilities)

### 2.5 — `execution/ingestion/ingest_dataasset.py`

Function: `ingest_dataasset(driver, payload) -> str`

Payload fields: `asset_hash`, `location_pseudonym`, `sensitivity_score`, `pii_types`, `host_id`, `scan_ts`, `source`

**Crown Jewel rule:** `crown_jewel = sensitivity_score >= float(os.getenv("CROWN_JEWEL_THRESHOLD", "0.7"))`. Compute this in Python before the Cypher call. Never accept `crown_jewel` as an input field.

Cypher: MERGE DataAsset on `asset_hash`. Sets all fields including `crown_jewel`, `scan_status='scanned'`, `last_updated`. MATCH Host. MERGE `(d)-[:RESIDES_ON]->(h)`.

**Privacy enforcement:** Before executing, assert that `location_pseudonym` does not contain any of these patterns: `@` (email), sequences of 9+ digits (SSN/phone), raw filesystem paths containing `/home/` or `C:\Users\`. If any raw PII pattern detected → raise `PrivacyViolationError` with the field name. This is a hard stop.

Offline/retry path: `ingest_dataasset_pending_retry(driver, asset_hash) -> None` — a separate function that only sets `scan_status='pending_retry'` and `last_updated` on an existing or new stub DataAsset node. Called by the Node Agent when Presidio is unreachable.

### 2.6 — `execution/ingestion/ingest_threat.py`

Function: `ingest_threat(driver, payload) -> str`

Payload fields: `threat_id`, `title`, `severity`, `confidence`, `published`, `source`

Optional: `cve_id` — if present, link `(v:Vulnerability)-[:EXPLOITED_BY]->(t:Threat)` after creating Threat node.

Cypher: MERGE Threat on `threat_id`. Sets all fields + `last_updated`. Separate MATCH+MERGE for CVE link if provided.

### 2.7 — `execution/ingestion/ingest_actioncard.py`

Function: `ingest_actioncard(driver, payload) -> str`

Payload fields (D3 Contract A schema): `action_id`, `origin`, `action_type`, `summary`, `confidence`, `recommended_ts`, `affected` (dict with `hosts`, `assets`, `services`), optional `metadata`

Initial status: `'received'` (not 'pending'). Set `created_ts` and `last_updated` on CREATE.

Cypher: MERGE ActionCard on `action_id`. Then three UNWIND loops for `affected.hosts`, `affected.assets`, `affected.services` — each does MATCH + MERGE AFFECTS relationship.

**Unresolved target handling:** If a host/asset/service in `affected` does not exist in the graph, do NOT fail the whole ingestion. Instead:
- Store the unresolved ID in `ac.unresolved_targets` (list property) on the ActionCard node
- Log a WARNING with the unresolved ID and type
- Continue with the rest of the ingestion

Validation transition: After persisting with status='received', immediately call `validate_and_transition(driver, action_id)` which checks required fields and transitions to status='pending' if valid, or status='failed' with a reason if not.

### 2.8 — `execution/ingestion/ingest_subscription.py`

Function: `ingest_subscription(driver, payload) -> str`

Payload fields (D3 Contract C schema): `subscription_id`, `context_summary` (dict), `preferred_action_types` (list)

Cypher: Archive any existing active Subscription first (set status='archived'). Then CREATE new Subscription with status='active'. If old exists, MERGE `(old)-[:GENERATED]->(new)`.

Offline path: `mark_subscription_queued(driver, subscription_id) -> None` — sets status='queued' when Core is unreachable.

Restore path: `mark_subscription_sent(driver, subscription_id) -> None` — sets status='active' + `last_sent_ts` after Core acknowledges.

### 2.9 — `execution/ingestion/ingest_delta_event.py`

Functions:
- `create_delta_event(driver, payload) -> str` — creates the DeltaEvent node in 'pending' state
- `link_entities_to_delta(driver, delta_id, changes) -> None` — creates :INCLUDED_IN relationships
- `mark_delta_sent(driver, delta_id) -> None` — sets sent_status='sent'
- `mark_delta_queued(driver, delta_id) -> None` — sets sent_status='queued' when Core unreachable

---

## Phase 3 — ActionCard Lifecycle Management (D4 §8)

**Create:** `execution/lifecycle/actioncard_lifecycle.py`

This module implements every status transition as a named function. Each function:
- Takes `driver` + required IDs/payloads
- Asserts the ActionCard is in the correct predecessor state before applying the transition — if not in expected state, raise `InvalidStateTransitionError` with current and attempted states
- Sets `last_updated = datetime()` on every write

Functions to implement:

```python
validate_and_transition(driver, action_id) -> str
# pending_received → 'pending' if valid, 'failed' if not
# Called automatically by ingest_actioncard

assign_to_analyst(driver, action_id, analyst_id, comment=None) -> None
# Creates :ASSIGNED_TO relationship (the "PendingAction" pattern — UC-06)
# ActionCard must be status='pending'

approve_action(driver, action_id, analyst_id, comment=None) -> None
# status: pending → approved
# Creates :APPROVED_BY relationship

reject_action(driver, action_id, analyst_id, reason) -> None
# status: pending → rejected
# Records reason on ActionCard node

begin_execution(driver, action_id) -> None
# status: approved → executing
# Records execution_started_ts

record_execution_result(driver, action_id, exec_id, outcome, details) -> None
# Creates ExecutionEvent node
# status: executing → completed (if outcome=='success') or failed
# Sets last_execution_ts and last_updated

get_actioncard_status(driver, action_id) -> str
# Simple query — returns current status string
```

**State machine enforcement:** Create a `VALID_TRANSITIONS` dict at module level:
```python
VALID_TRANSITIONS = {
    'received':  ['pending', 'failed'],
    'pending':   ['approved', 'rejected'],
    'approved':  ['executing', 'rejected'],
    'executing': ['completed', 'failed'],
    # terminal states — no transitions
    'completed': [],
    'rejected':  [],
    'failed':    [],
}
```

Any function attempting a transition not in this dict raises `InvalidStateTransitionError`.

---

## Phase 4 — Delta Computation & Export (D4 §9)

**Create:** `execution/delta/compute_delta.py`

This module computes what has changed since the last successful sync and packages it into the D3 delta JSON format.

Functions:

```python
compute_delta(driver, last_synced_ts: str, page_size: int = None) -> dict
```
- `last_synced_ts` is ISO8601 string of last successful Core sync
- Queries all nodes where `last_updated > datetime(last_synced_ts)` excluding SchemaVersion, DeltaEvent, IngestLog nodes
- Returns dict matching D3 Contract B schema including `delta_id`, `generated_ts`, `changes[]`
- Each change item has: `entity_type`, `entity_id`, `operation` (create/update/delete), `properties`, `relationships`, `last_updated`, `source`

**Soft-delete detection:** A node is 'deleted' if it has `deleted=true` property. Do not physically delete nodes — always soft-delete by setting `deleted=true, deleted_ts=datetime(), last_updated=datetime()`.

```python
export_delta(driver, delta_payload: dict) -> str
```
- Calls `create_delta_event()` from Phase 2 ingestion
- Calls `link_entities_to_delta()` 
- Serialises payload to JSON (in `.tmp/deltas/`) with filename `delta_{delta_id}.json`
- Returns `delta_id`

```python
acknowledge_delta(driver, delta_id: str) -> None
```
- Called after Core confirms receipt
- Marks DeltaEvent as 'sent'
- Updates `last_synced_ts` on all included entities: sets `n.last_synced_ts = datetime()` for each entity in the delta

---

## Phase 5 — Verification Queries (Bloom / NeoDash)

**Create:** `execution/queries/verification_queries.cypher`

These are standalone Cypher queries (not Python) for use in Neo4j Bloom and NeoDash. Each query must be preceded by a comment naming the test case it satisfies from the test plan.

Write the following queries:

```
-- UC-01: Asset-to-Threat traversal (Test 24)
-- Shows Host → HAS_VULNERABILITY → Vulnerability → EXPLOITED_BY → Threat

-- UC-02: Crown Jewel classification view (Test 25)
-- Shows all DataAssets where crown_jewel=true with sensitivity_score

-- UC-02: Top 10 most sensitive assets
-- Returns DataAssets ordered by sensitivity_score DESC, with linked Host

-- UC-05: Pending ActionCards for HITL review (Test 26)
-- Shows ActionCards where status='pending' with affected assets and ASSIGNED_TO analyst

-- UC-05: Prioritization context — Crown Jewel + Active ActionCard
-- Shows Crown Jewel assets that currently have an active (pending/approved) ActionCard

-- UC-07: Recent delta summary (Test 29)
-- Shows DeltaEvents from last 24h with entity counts

-- PRIVACY CHECK (Test 28): Assert no raw PII in graph
-- Returns any DataAsset where location contains '@' or numeric sequences — should return 0 rows

-- Schema health check
-- Returns count of each node label and relationship type
```

---

## Phase 6 — Test Suite

**Create:** `execution/tests/test_schema.py`

Tests (use pytest):
- `test_all_constraints_exist`: queries `SHOW CONSTRAINTS`, asserts each expected constraint is present
- `test_all_indexes_exist`: queries `SHOW INDEXES`, asserts each expected index is present
- `test_schema_version`: asserts SchemaVersion.version == '1.1.0'
- `test_uniqueness_enforced_host`: attempt to create two Host nodes with same `host_id`, assert constraint error
- `test_uniqueness_enforced_dataasset`: same for DataAsset

**Create:** `execution/tests/test_ingestion.py`

Tests (use a fresh Neo4j database for each test — use a fixture that clears data with `MATCH (n) DETACH DELETE n` before each test):
- `test_host_create`: ingest a host, assert node exists with correct properties
- `test_host_idempotent`: ingest same host twice, assert only 1 node exists
- `test_host_update`: ingest host, modify ip, ingest again, assert ip updated
- `test_vulnerability_link`: ingest host + vulnerability, assert `[:HAS_VULNERABILITY]` relationship
- `test_vulnerability_rejected_bad_cve`: pass `cve_id='INVALID'`, assert ValueError raised, assert no node created
- `test_dataasset_crown_jewel_true`: ingest DataAsset with sensitivity_score=0.85, assert crown_jewel=True
- `test_dataasset_crown_jewel_false`: ingest DataAsset with sensitivity_score=0.5, assert crown_jewel=False
- `test_dataasset_scan_status_scanned`: successful ingest sets scan_status='scanned'
- `test_dataasset_pending_retry`: call offline path, assert scan_status='pending_retry'
- `test_privacy_violation_rejected`: pass DataAsset with raw email in location, assert PrivacyViolationError raised, assert no node created
- `test_actioncard_initial_status`: ingest ActionCard, assert status='received' (NOT 'pending')
- `test_actioncard_unresolved_target`: ingest ActionCard with unknown host_id in affected, assert ActionCard persisted with unresolved_targets populated
- `test_service_composite_key`: ingest two services with same port but different hosts, assert two distinct Service nodes

**Create:** `execution/tests/test_lifecycle.py`

Tests:
- `test_full_lifecycle_happy_path`: received → pending → approved → executing → completed
- `test_rejection_path`: received → pending → rejected (assert no further transitions)
- `test_invalid_transition_raises`: attempt pending → completed directly, assert InvalidStateTransitionError
- `test_assign_to_analyst`: assign ActionCard to analyst, assert :ASSIGNED_TO relationship exists
- `test_approval_records_analyst`: approve action, assert :APPROVED_BY relationship with timestamp
- `test_execution_event_created`: record execution result, assert ExecutionEvent node linked via :EXECUTED

**Create:** `execution/tests/test_delta.py`

Tests:
- `test_delta_includes_updated_nodes`: update a Host, run compute_delta with ts from before the update, assert Host appears in changes
- `test_delta_excludes_unchanged_nodes`: run compute_delta with ts from after last update, assert changes list is empty
- `test_delta_event_created`: export_delta creates a DeltaEvent node
- `test_delta_included_in_relationships`: after export, assert entities are linked to DeltaEvent via :INCLUDED_IN
- `test_delta_ack_marks_sent`: acknowledge_delta transitions DeltaEvent to sent_status='sent'
- `test_delta_no_pii`: export_delta output JSON must not contain any of: `@`, `SSN`, raw IP addresses in the `location` field

**Create:** `execution/tests/test_contracts.py`

Tests validating D3 contract compliance:
- `test_actioncard_contract_v1`: load `resources/` example ActionCard JSON, ingest it, assert all D3→D1 field mappings are correct (use the mapping table from D4)
- `test_delta_contract_schema`: generate a delta from a known graph state, validate output dict matches D3 Contract B JSON schema
- `test_subscription_contract_schema`: generate a subscription, validate output matches D3 Contract C schema

---

## Phase 7 — Batch Ingestion Utility

**Create:** `execution/ingestion/batch_ingest.py`

A general-purpose batch runner:

```python
def batch_ingest(driver, records: list[dict], ingest_fn: callable,
                 batch_size: int = None, fail_fast: bool = False) -> dict
```

- Chunks `records` into batches of `batch_size` (from env `INGEST_BATCH_SIZE`, default 200)
- Processes each batch in its own transaction
- On batch failure: logs the error with batch index and continues (unless `fail_fast=True`)
- Binary-search failed batches: if a batch fails, split in half and retry each half to identify the bad row
- Returns `{"processed": n, "failed": n, "errors": [{"index": i, "error": "..."}]}`

---

## Deliverables & Verification

When all phases are complete, run these in order and confirm all pass:

```bash
# Activate venv
source .venv/bin/activate

# Phase 0
python execution/schema/00_verify_environment.py

# Phase 1
python execution/schema/01_apply_schema.py
python execution/schema/02_verify_schema.py

# Phase 6 tests
pytest execution/tests/ -v --tb=short

# Verification queries — paste into Neo4j Browser and confirm no errors
# (queries are in execution/queries/verification_queries.cypher)
```

All pytest tests must pass. `02_verify_schema.py` must show all ✓. Privacy check query in Neo4j Browser must return 0 rows.

---

## Error Handling & Logging Standards

Every script must:
- Use Python's `logging` module (not `print`) with level from `os.getenv("LOG_LEVEL", "INFO")`
- Log to file `os.getenv("LOG_DIR", ".tmp/logs")/{script_name}.log` AND to stdout
- Use structured log messages: `logger.info("Ingested host", extra={"host_id": host_id, "action": "create"})`
- Catch `neo4j.exceptions.ConstraintError` explicitly (not generic Exception) and handle as idempotent success (the node already exists — that's fine)
- Catch `neo4j.exceptions.ServiceUnavailable` and retry with exponential backoff (max 3 retries, 2s/4s/8s)

---

## Custom Exceptions to Define

Create `execution/exceptions.py`:

```python
class PrivacyViolationError(Exception):
    """Raised when a payload contains raw PII that must not enter Neo4j."""
    pass

class InvalidStateTransitionError(Exception):
    """Raised when an ActionCard transition is not valid for the current status."""
    pass

class OrphanEntityError(Exception):
    """Raised when an entity references a parent that doesn't exist."""
    pass

class ContractValidationError(Exception):
    """Raised when an incoming payload fails D3 contract schema validation."""
    pass
```

---

## Self-Annealing Checklist

For each script you write, before marking it done:

1. **Run it once** on a clean graph — does it complete without errors?
2. **Run it again** without changing anything — does it produce identical results? (Idempotency)
3. **Run the corresponding test** — does it pass?
4. **Check last_updated** — `MATCH (n) WHERE n.last_updated IS NULL RETURN labels(n), count(n)` should return 0 for any label you just ingested.
5. **Privacy check** — `MATCH (d:DataAsset) WHERE d.location CONTAINS '@' RETURN d` should return 0 rows.

If anything fails: fix the script, re-run all three steps, update this directive with what you learned.

---

## What NOT To Do

- **Never** use `CREATE` where `MERGE` should be used (except ExecutionEvent, DeltaEvent, IngestLog)
- **Never** store raw PII — if you are unsure whether a field contains PII, hash it
- **Never** use string concatenation to build Cypher queries — use parameters only
- **Never** expose `.env` — keep it local only. When git is added to the project later, `.env` must be the first entry in `.gitignore`
- **Never** hardcode the `crown_jewel_threshold` — always read from environment
- **Never** physically delete nodes — always soft-delete with `deleted=true`
- **Never** skip `last_updated` on a write — treat it as a required field
- **Never** accept `crown_jewel` as an input — always compute it locally
- **Never** create a `:PendingAction` label — use `ActionCard(status='pending')` + `:ASSIGNED_TO`

---

## File Summary (Expected at Completion)

```
execution/
├── exceptions.py
├── schema/
│   ├── 00_verify_environment.py
│   ├── 01_apply_schema.py
│   └── 02_verify_schema.py
├── ingestion/
│   ├── ingest_host.py
│   ├── ingest_service.py
│   ├── ingest_application.py
│   ├── ingest_vulnerability.py
│   ├── ingest_dataasset.py
│   ├── ingest_threat.py
│   ├── ingest_actioncard.py
│   ├── ingest_subscription.py
│   ├── ingest_delta_event.py
│   └── batch_ingest.py
├── lifecycle/
│   └── actioncard_lifecycle.py
├── delta/
│   └── compute_delta.py
├── queries/
│   └── verification_queries.cypher
└── tests/
    ├── conftest.py          ← pytest fixtures (driver setup, graph cleanup)
    ├── test_schema.py
    ├── test_ingestion.py
    ├── test_lifecycle.py
    ├── test_delta.py
    └── test_contracts.py
```