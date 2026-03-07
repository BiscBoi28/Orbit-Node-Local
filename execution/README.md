# Execution Scripts

Deterministic Python scripts that handle API calls, data processing, and database interactions.

## Index

| Script | Directive | Purpose |
|--------|-----------|---------|
| `seed_graph.py` | `neo4j_graph_management` | Seed Neo4j with Asset + Technology nodes from CSV |
| `update_asset_context.py` | `neo4j_graph_management` | Merge sensitivity metadata onto an Asset node |
| `query_graph.py` | `neo4j_graph_management` | Run canned queries against Neo4j |
| `presidio_scan.py` | `presidio_scanning` | Call Presidio Analyzer and return structured results |
| `orc_pipeline.py` | `orc_pipeline` | Full data-change → sensitivity → Neo4j pipeline |
| `handle_core_alert.py` | `core_alert_handling` | Ingest Core alert → generate prioritised action card |

## Dependencies

```bash
pip install neo4j requests python-dotenv
```
