# Directives

Standard Operating Procedures (SOPs) for ORBIT Node.

Each `.md` file in this directory defines:
- **Goal** — what the directive accomplishes
- **Inputs** — data or context required
- **Execution** — which script(s) to run and in what order
- **Outputs** — expected deliverables
- **Edge Cases / Learnings** — known pitfalls discovered during usage

Directives are living documents — update them as you learn.

## Index

| Directive | Purpose |
|-----------|---------|
| `neo4j_graph_management.md` | Ingest, update, and query the asset-centric Neo4j graph |
| `presidio_scanning.md` | Run PII/sensitivity scans via Presidio |
| `orc_pipeline.md` | End-to-end ORC orchestration (data-change → action card) |
| `core_alert_handling.md` | Ingest Core alerts and generate prioritised action cards |
| `infrastructure_deploy.md` | Deploy / teardown AWS stacks (wazuh-dev + orbit-dev) |
