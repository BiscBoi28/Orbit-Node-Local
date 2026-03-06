# Local ORBIT Bank App Handoff

## Recommendation

Build the application layer in a new local-first repo.

Do not build the orchestrator, Presidio adaptation, and Neo4j model inside this repo. This repo is mainly:

- AWS/CloudFormation deployment scaffolding
- Wazuh setup and agent-registration automation
- a bank-simulation scenario definition

It does not contain a real ORC service yet, and it does not contain a usable Neo4j domain schema for the bank workflow.

Use this repo only as a reference source for the simulated bank environment and future deployment shape.

## What The New Repo Should Build

Build a local application that does this without live Wazuh:

1. Accept a bank-relevant alert/event input.
2. Run Presidio analysis on relevant text fields.
3. Apply orchestrator logic to enrich and classify the event.
4. Persist the result into Neo4j using a clear bank-oriented schema.
5. Return a response or generate a remediation-oriented output.

For now, Wazuh must be stubbed.

Recommended stub model:

- replay JSON files as fake alerts
- keep the input shape close to future Wazuh alerts
- isolate that adapter behind a `WazuhSource` or `AlertSource` interface

## What To Copy From This Repo

Copy these files into the new repo under a `reference/` folder.

Required:

- `cloudFormationScripts-Bank-simulation/ORBIT_simulated_bank.csv`
- `cloudFormationScripts-Bank-simulation/Runbook.md`
- `cloudFormationScripts-Bank-simulation/requirements/requirements.md`
- `cloudFormationScripts-Bank-simulation/requirements/design.md`

Useful optional references:

- `cloudFormationScripts-Bank-simulation/manual_steps/machine_1_ns-01_corebank-db-01.md`
- `cloudFormationScripts-Bank-simulation/manual_steps/machine_2_ns-02_corebank-web-01.md`
- `cloudFormationScripts-Bank-simulation/manual_steps/machine_3_ns-03_corp-ad-01.md`

Do not copy:

- any `logs/` files
- any `output` files
- any secrets or parameter JSONs containing credentials
- the Wazuh deployment scripts
- the current `orbit-dev` AWS setup scripts

## What This Repo Confirms

The bank simulation is valid enough as the application target:

- the CSV defines the target machines and roles
- the runbook defines the intended deployment/configuration workflow
- the manual machine notes describe the kinds of software expected on the bank hosts

But it is not a cleanly complete runtime environment:

- saved logs show deployment/configuration issues
- Wazuh agent setup is unreliable in the captured runs
- Windows configuration is not in a healthy state
- the current ORC is only a placeholder in the AWS path

So the right interpretation is:

- use the bank simulation as domain context
- do not use this repo as the implementation base for the local app

## New Repo Expectations For Codex

Give Codex this file plus the copied references, and ask it to complete the project with Wazuh stubbed out.

The new repo should be treated as the source of truth for:

- orchestrator service
- Presidio integration
- Neo4j schema and persistence
- local test/demo flow

Codex should not spend time on:

- AWS deployment
- CloudFormation
- live Wazuh setup
- EC2 provisioning

## Explicit Product Direction

The project to implement is:

- a local-first ORBIT-style orchestrator for the bank simulation
- not an infra repo
- not a Wazuh deployment project

The first milestone should be:

1. load one or more stubbed bank alerts
2. map them to internal orchestrator models
3. run Presidio over selected text
4. store alert, asset, findings, and relationships in Neo4j
5. expose the result through a simple local API or CLI

## Suggested New Repo Layout

Use something close to this:

```text
new-repo/
├── app/
│   ├── orchestrator/
│   ├── presidio_client/
│   ├── graph/
│   ├── alert_sources/
│   └── api/
├── tests/
├── fixtures/
│   ├── alerts/
│   └── bank/
├── reference/
│   └── copied files from this repo
├── docker-compose.yml
├── README.md
└── AGENTS.md
```

## Initial Domain Inputs To Use

From the bank CSV, start with these assets:

- `corebank-db-01`: database/application host
- `corebank-web-01`: web host
- `corp-ad-01`: Windows AD/jump-host style system

Use them as the first graph entities and as alert ownership targets.

## Neo4j Direction

This repo does not provide a finished Neo4j schema.

So the new repo must define one explicitly. Start simple:

- `Asset`
- `Alert`
- `Finding`
- `Software`
- `Role`

Likely relationships:

- `(:Alert)-[:TARGETS]->(:Asset)`
- `(:Alert)-[:HAS_FINDING]->(:Finding)`
- `(:Asset)-[:HAS_ROLE]->(:Role)`
- `(:Asset)-[:RUNS]->(:Software)`

Only expand the schema after the first end-to-end flow works.

## Presidio Direction

Do not optimize for Juice Shop anymore.

Adapt Presidio to bank-relevant text such as:

- customer names
- account identifiers
- email addresses
- phone numbers
- employee names
- server names
- host/IP references
- free-text alert descriptions

The first version should clearly define which fields are analyzed and how findings are mapped into graph data.

## Stubbed Wazuh Direction

For now, implement a replaceable stub.

Recommended behavior:

- store sample alerts in `fixtures/alerts/*.json`
- support replaying a single alert or a small batch
- keep a mapper that converts raw fixture JSON into the app's internal alert model

The rest of the app must not depend on Wazuh-specific transport details.

## Prompt To Give Codex In The New Repo

Use this as the starting instruction in the new repo:

```text
Build the local-first ORBIT bank application in this repo.

Constraints:
- Wazuh is stubbed for now using local alert fixtures.
- Do not add AWS or CloudFormation work.
- Use the files under reference/ as domain context only.
- Treat ORBIT_simulated_bank.csv as the source of truth for initial bank assets.
- Implement a real orchestrator flow, Presidio integration, and a simple but explicit Neo4j schema.
- Prioritize one working end-to-end demo over completeness.

Expected result:
- local run instructions
- fixture-driven alert ingestion
- Presidio enrichment
- Neo4j persistence
- tests for the core flow
- clear interfaces so real Wazuh can replace the stub later
```

## What To Send Me Next

Send these when ready:

- orchestrator design/spec documents
- current Presidio notes or code summary
- current Neo4j schema ideas or domain model notes
- preferred stack for the new repo if already decided

With those, I can turn this handoff into a concrete implementation spec for the new repo.
