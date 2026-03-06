-- ═══════════════════════════════════════════════════════════════════════
-- ORBIT.CyberGraph-Node — Verification Queries for Neo4j Bloom / NeoDash
-- Run these in Neo4j Browser (http://localhost:7474) to validate graph state.
-- ═══════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────
-- UC-01: Asset-to-Threat traversal (Test 24)
-- Shows Host → HAS_VULNERABILITY → Vulnerability → EXPLOITED_BY → Threat
-- ─────────────────────────────────────────────────────────────────────
MATCH path = (h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)-[:EXPLOITED_BY]->(t:Threat)
RETURN h.host_id    AS host,
       h.hostname   AS hostname,
       v.cve_id     AS cve,
       v.cvss       AS cvss,
       t.threat_id  AS threat,
       t.title      AS threat_title,
       t.severity   AS severity
ORDER BY v.cvss DESC;

-- ─────────────────────────────────────────────────────────────────────
-- UC-02: Crown Jewel classification view (Test 25)
-- Shows all DataAssets where crown_jewel=true with sensitivity_score
-- ─────────────────────────────────────────────────────────────────────
MATCH (d:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(h:Host)
RETURN d.asset_hash          AS asset,
       d.sensitivity_score   AS score,
       d.crown_jewel         AS crown_jewel,
       d.scan_status         AS scan_status,
       h.host_id             AS host,
       h.hostname            AS hostname
ORDER BY d.sensitivity_score DESC;

-- ─────────────────────────────────────────────────────────────────────
-- UC-02: Top 10 most sensitive assets
-- Returns DataAssets ordered by sensitivity_score DESC, with linked Host
-- ─────────────────────────────────────────────────────────────────────
MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host)
RETURN d.asset_hash          AS asset,
       d.sensitivity_score   AS score,
       d.crown_jewel         AS crown_jewel,
       d.pii_types           AS pii_types,
       h.host_id             AS host
ORDER BY d.sensitivity_score DESC
LIMIT 10;

-- ─────────────────────────────────────────────────────────────────────
-- UC-05: Pending ActionCards for HITL review (Test 26)
-- Shows ActionCards where status='pending' with affected assets and
-- ASSIGNED_TO analyst
-- ─────────────────────────────────────────────────────────────────────
MATCH (ac:ActionCard {status: 'pending'})
OPTIONAL MATCH (ac)-[:ASSIGNED_TO]->(an:Analyst)
OPTIONAL MATCH (ac)-[:AFFECTS]->(target)
RETURN ac.action_id     AS action_id,
       ac.action_type   AS action_type,
       ac.summary       AS summary,
       ac.confidence    AS confidence,
       an.analyst_id    AS assigned_to,
       collect(DISTINCT labels(target)[0] + ':' +
         COALESCE(target.host_id, target.asset_hash, target.service_id, 'unknown')
       ) AS affected_targets
ORDER BY ac.confidence DESC;

-- ─────────────────────────────────────────────────────────────────────
-- UC-05: Prioritization context — Crown Jewel + Active ActionCard
-- Shows Crown Jewel assets that currently have an active
-- (pending/approved) ActionCard
-- ─────────────────────────────────────────────────────────────────────
MATCH (d:DataAsset {crown_jewel: true})<-[:AFFECTS]-(ac:ActionCard)
WHERE ac.status IN ['pending', 'approved']
RETURN d.asset_hash        AS crown_jewel_asset,
       d.sensitivity_score AS score,
       ac.action_id        AS action_id,
       ac.action_type      AS action_type,
       ac.status           AS ac_status
ORDER BY d.sensitivity_score DESC;

-- ─────────────────────────────────────────────────────────────────────
-- UC-07: Recent delta summary (Test 29)
-- Shows DeltaEvents from last 24h with entity counts
-- ─────────────────────────────────────────────────────────────────────
MATCH (de:DeltaEvent)
WHERE de.generated_ts > datetime() - duration('PT24H')
OPTIONAL MATCH (n)-[:INCLUDED_IN]->(de)
RETURN de.delta_id      AS delta_id,
       de.generated_ts  AS generated,
       de.sent_status   AS status,
       de.entity_count  AS declared_count,
       count(n)         AS actual_linked
ORDER BY de.generated_ts DESC;

-- ─────────────────────────────────────────────────────────────────────
-- PRIVACY CHECK (Test 28): Assert no raw PII in graph
-- Returns any DataAsset where location contains '@' or numeric
-- sequences — should return 0 rows
-- ─────────────────────────────────────────────────────────────────────
MATCH (d:DataAsset)
WHERE d.location_pseudonym CONTAINS '@'
   OR d.location_pseudonym =~ '.*\\d{9,}.*'
RETURN d.asset_hash            AS asset,
       d.location_pseudonym    AS location,
       'PII_DETECTED'          AS violation;

-- ─────────────────────────────────────────────────────────────────────
-- Schema health check
-- Returns count of each node label and relationship type
-- ─────────────────────────────────────────────────────────────────────
CALL db.labels() YIELD label
CALL apoc.cypher.run(
  'MATCH (n:`' + label + '`) RETURN count(n) AS cnt', {}
) YIELD value
WITH label, value.cnt AS node_count
ORDER BY label
RETURN label, node_count
UNION ALL
CALL db.relationshipTypes() YIELD relationshipType AS label
CALL apoc.cypher.run(
  'MATCH ()-[r:`' + label + '`]->() RETURN count(r) AS cnt', {}
) YIELD value
RETURN label, value.cnt AS node_count;
