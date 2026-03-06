# High-Level Design

## Objective

Build a local-first ORBIT prototype for the bank simulation where:

1. ORC receives bank data-change notifications.
2. ORC sends current relevant asset data to Presidio for PII and sensitivity analysis.
3. ORC stores the current asset security/sensitivity context in Neo4j.
4. ORC receives alerts from Core about vulnerable technologies or versions on an asset.
5. ORC looks up that asset's current importance/sensitivity in Neo4j.
6. ORC generates an action card with priority and sends it onward to Wazuh/UI.

This design is asset-centric, not database-centric.

## Scope

### In Scope

- local ORC implementation
- Presidio integration for bank data
- Neo4j graph layer for current asset context
- Core-alert ingestion
- action-card generation
- Wazuh as downstream sink/UI target only

### Out of Scope

- AWS deployment
- live Wazuh telemetry ingestion
- Wazuh-generated vulnerability detection as the primary alert source
- storing raw PII in Neo4j
- per-chunk lifecycle/history in Neo4j for the first prototype
- explicit database nodes for the first prototype

## Core Design Decisions

### 1. ORC is the decision engine

ORC is not the AWS deployment scripts in `cloudFormationScripts-Bank-simulation/06-orchestrator`.
ORC is the runtime service that coordinates:

- data-change processing
- Presidio scans
- Neo4j updates
- Core alert handling
- action-card generation

### 2. ORC is the only writer to Neo4j

Presidio does not write to Neo4j directly.
Core does not write to Neo4j directly.
Wazuh does not write to Neo4j directly.

All writes flow through ORC so the graph stays consistent and privacy-safe.

### 3. The graph is asset-centric

Neo4j should primarily store the current state of each bank asset/host/system:

- what the asset is
- what technologies it runs
- what the current sensitivity context is
- whether it is considered a crown jewel
- what alerts currently affect it
- what action cards have been generated for it

The graph should not be used as a raw record store for changed chunks.

### 4. Presidio is a sensitivity engine, not a graph engine

Presidio should:

- scan provided text/data
- detect PII entity types
- compute sensitivity/risk outputs
- return those results to ORC

Presidio should not:

- decide action cards
- own crown-jewel classification for the final system
- write to Neo4j

### 5. Core is the alert source for this prototype

For this prototype, the important incoming security alerts come from Core.
Example:

- "This asset is using a vulnerable PostgreSQL version"
- "This operating system version is affected"
- "This technology stack is vulnerable"

These alerts target assets and technologies, not individual databases.

## System Components

### ORC

Responsibilities:

- ingest bank data-change events
- gather current relevant data snapshot for the affected asset
- call Presidio
- compute current asset sensitivity and importance
- update Neo4j
- ingest Core alerts
- evaluate alert severity in business context
- generate action cards
- send action cards outward

### Presidio

Responsibilities:

- detect PII in bank-relevant data
- return detected entity types
- return confidence and scoring inputs
- support risk scoring tuned to banking data

### Neo4j

Responsibilities:

- store current asset context
- store technologies installed on assets
- store current sensitivity/importance state per asset
- support context lookup when a Core alert arrives
- support graph visualization and prioritization queries

### Core

Responsibilities in this prototype:

- send alerts about vulnerable versions/technologies/assets

Core does not need to generate action cards in this prototype.
ORC will generate the action cards locally.

### Wazuh/UI

Responsibilities in this prototype:

- receive action cards and priority from ORC
- later act as display/HITL destination

## Asset Model

For the first prototype, an asset is a bank system/host from the bank simulation, such as:

- `corebank-db-01`
- `corebank-web-01`
- `corp-ad-01`

An asset is the main prioritization unit.

Recommended asset identity for the local prototype:

- `asset_id = Hostname` from `cloudFormationScripts-Bank-simulation/ORBIT_simulated_bank.csv`

This is better than AWS instance ID for the local demo because:

- the prototype is local
- Core alerts will be mapped to simulated bank systems
- the CSV is the stable local source of truth

## Proposed Graph Model

### Main Nodes

#### Asset

Represents the bank system/host.

Suggested properties:

- `asset_id`
- `hostname`
- `technical_roles`
- `operating_system`
- `current_sensitivity_score`
- `asset_importance_score`
- `detected_pii_types`
- `pii_counts_summary`
- `crown_jewel`
- `last_scanned_at`
- `last_updated`

#### Technology

Represents a technology the asset runs.

Suggested properties:

- `technology_id`
- `name`
- `category`
- `version`
- `last_updated`

Examples:

- `RHEL 8`
- `PostgreSQL 15`
- `Tomcat`
- `Node.js`
- `nginx`

#### Alert

Represents an incoming Core alert.

Suggested properties:

- `alert_id`
- `source`
- `alert_type`
- `title`
- `description`
- `base_severity`
- `affected_technology`
- `affected_version`
- `created_at`
- `last_updated`

#### ActionCard

Represents ORC's response to an alert in asset context.

Suggested properties:

- `action_id`
- `alert_id`
- `asset_id`
- `priority`
- `summary`
- `reason`
- `recommended_action`
- `status`
- `created_at`
- `last_updated`

### Relationships

- `(:Asset)-[:RUNS]->(:Technology)`
- `(:Alert)-[:AFFECTS]->(:Asset)`
- `(:Alert)-[:TARGETS_TECHNOLOGY]->(:Technology)`
- `(:ActionCard)-[:GENERATED_FOR]->(:Asset)`
- `(:ActionCard)-[:BASED_ON]->(:Alert)`

This keeps the graph simple and aligned with the current product need.

## Why Neo4j Stores Metadata Instead of Raw Data

The graph should store decision context, not raw bank data.

Example:

Input data to ORC:

```json
{
  "event_type": "data_change",
  "asset_id": "corebank-db-01",
  "content_items": [
    "Jane Doe, jane@example.com, account 021000021",
    "Customer 4716190207394368 updated billing contact"
  ]
}
```

Presidio result:

```json
{
  "detected_pii_types": [
    "PERSON",
    "EMAIL_ADDRESS",
    "US_BANK_NUMBER",
    "CREDIT_CARD"
  ],
  "chunk_scores": [0.62, 0.94]
}
```

What ORC writes to Neo4j:

```json
{
  "asset_id": "corebank-db-01",
  "current_sensitivity_score": 0.89,
  "asset_importance_score": 0.95,
  "detected_pii_types": [
    "PERSON",
    "EMAIL_ADDRESS",
    "US_BANK_NUMBER",
    "CREDIT_CARD"
  ],
  "pii_counts_summary": {
    "PERSON": 12,
    "EMAIL_ADDRESS": 9,
    "US_BANK_NUMBER": 7,
    "CREDIT_CARD": 3
  },
  "crown_jewel": true
}
```

What ORC does not write:

- raw changed text
- raw account numbers
- raw emails
- raw card numbers
- chunk-by-chunk state history for this first prototype

Reason:

- Neo4j should answer prioritization questions
- privacy risk is lower if raw PII stays out of the graph
- the graph remains compact and easier to reason about

## Data-Change Workflow

### Goal

Maintain the current sensitivity and importance state of an asset.

### Flow

1. A data-change event arrives for an asset.
2. ORC identifies the affected asset.
3. ORC gathers the current relevant data snapshot for that asset.
4. ORC sends that data to Presidio.
5. Presidio returns entity detections and scoring inputs.
6. ORC computes the current asset sensitivity and importance.
7. ORC updates the asset node in Neo4j.

### Example

1. Event arrives for `corebank-db-01`.
2. ORC scans the relevant current data snapshot.
3. Presidio finds financial and identity PII.
4. ORC updates:
   - `current_sensitivity_score`
   - `asset_importance_score`
   - `detected_pii_types`
   - `pii_counts_summary`
   - `crown_jewel`

## Core Alert Workflow

### Goal

Prioritize technology or OS alerts using business/sensitivity context.

### Flow

1. Core sends an alert about a vulnerable technology/version on an asset.
2. ORC looks up the affected asset in Neo4j.
3. ORC checks:
   - current sensitivity score
   - current importance score
   - crown-jewel status
   - installed technologies
4. ORC combines technical severity with asset importance.
5. ORC creates an action card.
6. ORC sends the action card to Wazuh/UI.

### Example

Core alert:

```json
{
  "alert_id": "ALT-001",
  "asset_id": "corebank-db-01",
  "affected_technology": "PostgreSQL",
  "affected_version": "15.3",
  "base_severity": "HIGH",
  "title": "PostgreSQL version vulnerability"
}
```

Neo4j current state:

- `current_sensitivity_score = 0.89`
- `asset_importance_score = 0.95`
- `crown_jewel = true`
- technologies include `PostgreSQL 15.3`

ORC output action card:

```json
{
  "action_id": "AC-001",
  "asset_id": "corebank-db-01",
  "priority": "CRITICAL",
  "summary": "Patch PostgreSQL on crown-jewel asset",
  "reason": "High-severity PostgreSQL vulnerability on asset currently associated with highly sensitive banking data",
  "recommended_action": "Patch immediately and verify DB access controls"
}
```

## Presidio Logic

Presidio should identify:

- names
- email addresses
- phone numbers
- bank numbers
- credit cards
- SSNs
- IBAN codes
- locations
- IP addresses

The current Presidio scoring strategy already has a useful banking orientation and should be adapted, not replaced.

### Required Presidio Output

For each scan, ORC should receive:

- detected entity types
- entity counts
- confidence values
- per-item or per-chunk sensitivity score inputs
- optional overall scan summary

## Sensitivity and Importance Logic

### 1. Chunk-level sensitivity

Presidio computes sensitivity evidence per scanned item/chunk.

This is temporary processing state inside ORC.
It does not need to be stored in Neo4j for the first prototype.

### 2. Asset current sensitivity

The prototype should not rely only on the last changed chunk.

Recommended prototype approach:

- when a data-change event arrives, ORC recomputes the asset's current sensitivity from the current relevant asset data snapshot

This avoids:

- stale sensitivity state
- noisy incremental drift
- unnecessary chunk-state storage in Neo4j

Recommended formula:

- normalize each scanned item score to `0..1`
- let:
  - `max_score = max(item_scores)`
  - `avg_top_scores = average(top 5 item_scores or all if fewer)`
- compute:

`current_sensitivity_score = 0.6 * max_score + 0.4 * avg_top_scores`

Reason:

- severe exposures matter
- total exposure breadth also matters

### 3. Asset importance

Asset importance should represent total current business/security importance, not only latest change intensity.

Recommended prototype formula:

`asset_importance_score = current_sensitivity_score + role_bonus + breadth_bonus`

Where:

- `role_bonus`
  - DB/application asset: `+0.10`
  - web asset: `+0.05`
  - other: configurable
- `breadth_bonus`
  - add up to `+0.10` if multiple high-risk PII categories exist

Clamp the result to `0..1`.

### 4. Crown jewel

The current Neo4j package derives `crown_jewel` directly from one sensitivity threshold.
That is too narrow for this prototype.

Recommended prototype rule:

- `crown_jewel = asset_importance_score >= configured_threshold`

Optional later enhancement:

- manual analyst/business override

## Technology Modeling

Technologies must be part of the graph because Core alerts target:

- operating system versions
- middleware versions
- database engine versions
- application stack components

ORC should be able to answer:

- does this asset actually run the vulnerable technology?
- what version is present?
- how sensitive is the asset this technology lives on?

Technologies can be sourced initially from:

- `ORBIT_simulated_bank.csv`
- local configuration
- later, discovered inventory

## Recommended Prototype Assumptions

- local Python implementation
- FastAPI for ORC API unless a different stack is requested
- Neo4j reused from the existing `Neo4j/` folder, but adapted to the asset-centric model
- Presidio reused from the existing `Presidio/presidio-local/` work, but refactored for reusable service calls
- no raw PII stored in Neo4j
- no database nodes in the first version
- no chunk-history graph model in the first version
- full current asset sensitivity recomputation on each change event

## Immediate Implementation Implications

The current Neo4j implementation is useful but not final.
It likely needs adaptation in these areas:

- rename or generalize `Host` into `Asset` or treat `Host` as the asset node
- reduce reliance on `DataAsset` as the main prioritization unit
- replace threshold-only crown-jewel logic with asset-level importance logic
- add asset-level current sensitivity and importance fields
- ensure action cards target assets and technologies cleanly

## Open Questions

These should be confirmed before detailed implementation:

1. Should `Host` simply be reused as the graph label for the bank asset, or should we rename it to `Asset`?
2. Should technologies be modeled as one generic `Technology` node, or split into `OS`, `Application`, and `Service`?
3. Do you want action cards stored in Neo4j for the prototype, or generated and forwarded without graph persistence?
4. Do you want crown-jewel classification to support future manual override, even if we do not implement that now?
