# Core Alert Handling

## Goal

Ingest a Core vulnerability alert, look up the affected asset's business context in Neo4j, and generate a prioritised action card.

## Inputs

- Core alert JSON:
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

## Execution

1. **Handle alert** — `python execution/handle_core_alert.py --alert '<json>'`
   - Looks up the asset in Neo4j (sensitivity, importance, crown-jewel status, technologies).
   - Combines `base_severity` with asset importance to compute final priority.
   - Creates an `ActionCard` node in Neo4j.
   - Outputs the action card JSON.

## Outputs

```json
{
  "action_id": "AC-001",
  "asset_id": "corebank-db-01",
  "priority": "CRITICAL",
  "summary": "Patch PostgreSQL on crown-jewel asset",
  "reason": "...",
  "recommended_action": "..."
}
```

## Edge Cases / Learnings

- If the asset doesn't exist in Neo4j yet, log a warning and seed it first.
- If the technology version doesn't match, still generate a card but flag it.
