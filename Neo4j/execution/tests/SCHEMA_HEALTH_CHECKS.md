# Schema Health Checks — Quick Reference

> Run any of these in Neo4j Browser (`http://localhost:7474`) to confirm schema integrity.

## 1. Constraint inventory

**When:** After running `01_apply_schema.py`, or after any schema migration.

```cypher
SHOW CONSTRAINTS YIELD name, type, entityType, labelsOrTypes, properties
RETURN name, type, labelsOrTypes, properties
ORDER BY name;
```

**Expected:** 10 `UNIQUENESS` constraints (Host, Vulnerability, DataAsset, ActionCard, Analyst, Threat, Subscription, DeltaEvent, SchemaVersion, ExecutionEvent). Enterprise edition adds 2 `NODE_PROPERTY_EXISTENCE` constraints.

---

## 2. Index inventory

**When:** After schema apply, or if queries feel slow on filtered properties.

```cypher
SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, properties, state
WHERE type <> 'LOOKUP'
RETURN name, labelsOrTypes, properties, state
ORDER BY name;
```

**Expected:** 9 `RANGE` indexes, all in state `ONLINE`: Host(hostname), Host(ip), Service(name), DataAsset(sensitivity_score), DataAsset(crown_jewel), ActionCard(status), Threat(severity), Subscription(status), DeltaEvent(sent_status).

---

## 3. Schema version

**When:** After any migration or at the start of a development session.

```cypher
MATCH (s:SchemaVersion {name: 'orbit-node'})
RETURN s.version, s.updated, s.notes;
```

**Expected:** `version = '1.1.0'`, `updated` is a recent datetime, `notes` describes the v1.1 amendments.

---

## 4. Node label counts

**When:** After ingestion runs, or to sanity-check before delta exports.

```cypher
CALL db.labels() YIELD label
CALL apoc.cypher.run('MATCH (n:`' + label + '`) RETURN count(n) AS cnt', {}) YIELD value
RETURN label, value.cnt AS count
ORDER BY label;
```

**Expected:** Every label you've ingested appears with a non-zero count. `SchemaVersion` = 1. No unexpected labels.

---

## 5. Orphan `last_updated` check

**When:** After any ingestion or lifecycle operation — catches scripts that forgot to set `last_updated`.

```cypher
MATCH (n)
WHERE n.last_updated IS NULL
  AND NOT 'SchemaVersion' IN labels(n)
RETURN labels(n) AS label, count(n) AS missing_count;
```

**Expected:** 0 rows. Any result here means a write path skipped `last_updated` — fix the corresponding ingestion script immediately.
