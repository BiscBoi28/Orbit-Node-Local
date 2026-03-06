# Manual Testing Guide — ORBIT.CyberGraph-Node

> Run these checks in **Neo4j Browser** (`http://localhost:7474`) whenever
> you need to visually confirm graph state beyond what `pytest` covers.

---

## 1. Schema Integrity

Verify all constraints and indexes exist.

```cypher
SHOW CONSTRAINTS
YIELD name, type, entityType, labelsOrTypes, properties
RETURN name, type, entityType, labelsOrTypes, properties
ORDER BY name;
```

**Expected:** 10 uniqueness constraints matching the labels and properties
defined in `01_apply_schema.py`.

```cypher
SHOW INDEXES
YIELD name, type, labelsOrTypes, properties
RETURN name, type, labelsOrTypes, properties
ORDER BY name;
```

**Expected:** 9 range indexes + 10 constraint-backing indexes.

---

## 2. Node & Relationship Counts

Quick sanity check on overall graph size.

```cypher
CALL db.labels() YIELD label
CALL apoc.cypher.run('MATCH (n:`' + label + '`) RETURN count(n) AS cnt', {}) YIELD value
RETURN label, value.cnt AS count ORDER BY label;
```

**Expected:** Counts should align with your last ingestion run.
At minimum: Host ≥ 1, SchemaVersion = 1.

---

## 3. Crown Jewel Classification

Verify `crown_jewel` is computed correctly.

```cypher
MATCH (d:DataAsset)
RETURN d.asset_hash, d.sensitivity_score, d.crown_jewel
ORDER BY d.sensitivity_score DESC;
```

**Expected:** All DataAssets with `sensitivity_score >= 0.7` have
`crown_jewel = true`.  Never `null`.

---

## 4. ActionCard Lifecycle

Walk through the full status pipeline.

```cypher
MATCH (ac:ActionCard)
OPTIONAL MATCH (ac)-[:ASSIGNED_TO]->(an:Analyst)
OPTIONAL MATCH (ac)-[:APPROVED_BY]->(ap:Analyst)
OPTIONAL MATCH (ac)-[:EXECUTED]->(ev:ExecutionEvent)
RETURN ac.action_id, ac.status,
       an.analyst_id AS assigned,
       ap.analyst_id AS approved_by,
       ev.exec_id    AS execution
ORDER BY ac.created_ts DESC;
```

**Expected:** Completed cards have all three relationships.
Rejected cards have no `:EXECUTED` relationship.

---

## 5. Delta Export & Acknowledgement

Check recent delta activity.

```cypher
MATCH (de:DeltaEvent)
OPTIONAL MATCH (n)-[:INCLUDED_IN]->(de)
RETURN de.delta_id, de.sent_status, de.entity_count,
       count(n) AS actual_linked
ORDER BY de.generated_ts DESC
LIMIT 10;
```

**Expected:** `sent_status = 'sent'` for acknowledged deltas.
`entity_count` should match `actual_linked`.

---

## 6. Privacy Audit

Assert zero raw PII in the graph.

```cypher
MATCH (d:DataAsset)
WHERE d.location_pseudonym CONTAINS '@'
   OR d.location_pseudonym =~ '.*\\d{9,}.*'
RETURN d.asset_hash, d.location_pseudonym, 'PII_DETECTED' AS violation;
```

**Expected:** 0 rows.  If any rows appear, the Privacy Guard has a
gap — investigate immediately.

---

## 7. Orphan `last_updated` Check

Every node (except SchemaVersion) must have `last_updated` set.

```cypher
MATCH (n)
WHERE n.last_updated IS NULL
  AND NOT 'SchemaVersion' IN labels(n)
RETURN labels(n) AS label, count(n) AS orphan_count;
```

**Expected:** 0 rows.  Any orphans indicate an ingestion or lifecycle
function that forgot to set `last_updated`.

---

## When to Run These Checks

| Check | When |
|---|---|
| Schema Integrity | After any schema migration or `01_apply_schema.py` run |
| Node Counts | After batch ingestion or before a demo |
| Crown Jewel | After changing `CROWN_JEWEL_THRESHOLD` in `.env` |
| ActionCard Lifecycle | After running lifecycle transitions |
| Delta Export | After `compute_delta` + `export_delta` + `acknowledge_delta` |
| Privacy Audit | Before any data export or review |
| Orphan Check | After any ingestion run — catches bugs early |
