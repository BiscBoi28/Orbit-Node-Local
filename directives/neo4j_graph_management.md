# Neo4j Graph Management

## Goal

Maintain the asset-centric Neo4j graph: ingest bank simulation data, update asset sensitivity/importance, and run prioritisation queries.

## Inputs

- `cloudFormationScripts-Bank-simulation/ORBIT_simulated_bank.csv` — source of truth for assets, technologies, and roles.
- ORC output: computed `current_sensitivity_score`, `asset_importance_score`, `detected_pii_types`, `pii_counts_summary`, `crown_jewel`.

## Execution

1. **Seed the graph** — `python execution/seed_graph.py`
   - Reads the CSV, creates `Asset` and `Technology` nodes, and `RUNS` relationships.
2. **Update asset context** — `python execution/update_asset_context.py --asset-id <ID> --payload '<json>'`
   - Merges sensitivity metadata onto an existing Asset node.
3. **Query helpers** — `python execution/query_graph.py <query-name>`
   - Canned queries: `crown-jewels`, `assets-by-technology`, `high-sensitivity`.

## Outputs

- Neo4j graph with up-to-date Asset + Technology nodes.
- JSON query results to stdout / `.tmp/query_results/`.

## Edge Cases / Learnings

- Neo4j APOC plugin takes 2-3 min on first boot — wait before seeding.
- Always use `MERGE` (not `CREATE`) so re-runs are idempotent.
