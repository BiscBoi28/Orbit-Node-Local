-- ================================================
-- ORBIT Threat Intelligence Dashboard Queries
-- ================================================
-- Cypher queries for threat analysis, attack pattern detection, and threat landscape monitoring

-- === THREAT LANDSCAPE OVERVIEW ===

-- Active Threat Categories and Prevalence
MATCH (t:Threat)
WHERE t.status = 'active' OR t.status IS NULL
WITH t.category AS threat_category, 
     t.confidence AS confidence_level,
     collect(t) AS threats
RETURN threat_category,
       count(threats) AS threat_count,
       round(avg([threat IN threats | threat.confidence]) * 100) / 100 AS avg_confidence,
       max([threat IN threats | threat.confidence]) AS max_confidence,
       min([threat IN threats | threat.confidence]) AS min_confidence,
       size([threat IN threats WHERE threat.priority = 'critical']) AS critical_threats,
       size([threat IN threats WHERE threat.priority = 'high']) AS high_priority_threats
ORDER BY threat_count DESC;

-- Threat-Vulnerability Relationship Matrix
MATCH (t:Threat)-[:EXPLOITS]->(v:Vulnerability)
WITH t.category AS threat_category,
     v.type AS vulnerability_type,
     count(*) AS exploitation_count,
     avg(v.cvss) AS avg_cvss_exploited
RETURN threat_category,
       vulnerability_type,
       exploitation_count,
       round(avg_cvss_exploited * 10) / 10 AS avg_cvss_exploited
ORDER BY exploitation_count DESC
LIMIT 20;

-- Threat Priority Distribution
MATCH (t:Threat)
WITH t.priority AS priority_level, count(*) AS threat_count
RETURN priority_level,
       threat_count,
       round((threat_count * 100.0) / size((t:Threat))) AS percentage
ORDER BY CASE priority_level
    WHEN 'critical' THEN 1
    WHEN 'high' THEN 2
    WHEN 'medium' THEN 3
    WHEN 'low' THEN 4
    ELSE 5
END;

-- === ATTACK PATTERN ANALYSIS ===

-- Most Common Attack Vectors
MATCH (t:Threat)
WHERE t.attack_vector IS NOT NULL
WITH t.attack_vector AS attack_vector
UNWIND attack_vector AS vector
WITH vector, count(*) AS usage_count
RETURN vector,
       usage_count,
       round((usage_count * 100.0) / size((t:Threat))) AS prevalence_percentage
ORDER BY usage_count DESC
LIMIT 15;

-- Threat Actor Attribution Patterns
MATCH (t:Threat)
WHERE t.actor IS NOT NULL AND t.actor <> ''
WITH t.actor AS threat_actor,
     collect(t.category) AS threat_categories,
     count(t) AS threat_count,
     avg(t.confidence) AS avg_confidence
RETURN threat_actor,
       threat_count,
       round(avg_confidence * 100) / 100 AS avg_confidence,
       reduce(unique = [], cat IN threat_categories | 
           CASE WHEN cat IN unique THEN unique ELSE unique + cat END) AS unique_categories
ORDER BY threat_count DESC
LIMIT 12;

-- TTPs (Tactics, Techniques, Procedures) Analysis
MATCH (t:Threat)
WHERE size(t.ttps) > 0
UNWIND t.ttps AS ttp
WITH ttp, collect(t) AS associated_threats
RETURN ttp,
       count(associated_threats) AS threat_count,
       round(avg([threat IN associated_threats | threat.confidence]) * 100) / 100 AS avg_confidence,
       collect(DISTINCT [threat IN associated_threats | threat.category])[0..5] AS threat_categories,
       size([threat IN associated_threats WHERE threat.priority = 'critical']) AS critical_threat_count
ORDER BY threat_count DESC
LIMIT 20;

-- === VULNERABILITY-THREAT CORRELATION ===

-- Critical Vulnerabilities Under Active Threat
MATCH (v:Vulnerability)-[:EXPLOITED_BY]->(t:Threat)
WHERE v.cvss >= 7.0 AND (t.status = 'active' OR t.status IS NULL)
MATCH (v)<-[:HAS_VULNERABILITY]-(h:Host)
RETURN v.cve_id AS cve_id,
       v.cvss AS cvss_score,
       v.type AS vulnerability_type,
       count(DISTINCT h) AS affected_hosts,
       count(DISTINCT t) AS exploiting_threats,
       collect(DISTINCT t.category)[0..3] AS threat_categories,
       max(t.confidence) AS max_threat_confidence,
       CASE
           WHEN v.cvss >= 9.0 AND count(DISTINCT t) > 0 THEN 'Immediate Action Required'
           WHEN v.cvss >= 7.0 AND count(DISTINCT t) > 0 THEN 'High Priority Patching'
           ELSE 'Standard Remediation'
       END AS remediation_urgency
ORDER BY v.cvss DESC, count(DISTINCT t) DESC
LIMIT 25;

-- Threat-Vulnerability Exploitation Timeline
MATCH (t:Threat)-[:EXPLOITS]->(v:Vulnerability)
WHERE t.first_seen IS NOT NULL
WITH date.truncate('week', date(datetime(t.first_seen))) AS threat_week,
     count(DISTINCT t) AS new_threats,
     count(DISTINCT v) AS vulnerabilities_exploited,
     avg(v.cvss) AS avg_exploited_cvss
WHERE threat_week > date() - duration('P12W')
RETURN threat_week,
       new_threats,
       vulnerabilities_exploited,
       round(avg_exploited_cvss * 10) / 10 AS avg_exploited_cvss
ORDER BY threat_week DESC;

-- === HOST-THREAT EXPOSURE ANALYSIS ===

-- Host Threat Exposure Ranking
MATCH (h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)<-[:EXPLOITS]-(t:Threat)
WITH h, 
     count(DISTINCT v) AS vulnerable_components,
     count(DISTINCT t) AS threatening_actors,
     max(v.cvss) AS highest_cvss,
     avg(t.confidence) AS avg_threat_confidence
MATCH (h)<-[:RESIDES_ON]-(d:DataAsset)
WITH h, vulnerable_components, threatening_actors, highest_cvss, avg_threat_confidence,
     count(d) AS hosted_assets,
     size([asset IN collect(d) WHERE asset.crown_jewel = true]) AS crown_jewel_count,
     avg([asset IN collect(d) | asset.sensitivity_score]) AS avg_asset_sensitivity
RETURN h.hostname AS hostname,
       h.ip AS host_ip,
       h.os AS operating_system,
       vulnerable_components,
       threatening_actors,
       round(highest_cvss * 10) / 10 AS highest_cvss,
       round(avg_threat_confidence * 100) / 100 AS avg_threat_confidence,
       hosted_assets,
       crown_jewel_count,
       round(avg_asset_sensitivity * 100) / 100 AS avg_asset_sensitivity,
       threatening_actors * highest_cvss * (crown_jewel_count + 1) AS composite_risk_score
ORDER BY composite_risk_score DESC
LIMIT 20;

-- Critical Assets Under Threat
MATCH (d:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)<-[:EXPLOITS]-(t:Threat)
WITH d, h, 
     count(DISTINCT v) AS vulnerabilities,
     count(DISTINCT t) AS active_threats,
     max(v.cvss) AS max_cvss,
     collect(DISTINCT t.category) AS threat_categories
RETURN d.location_pseudonym AS crown_jewel_asset,
       d.sensitivity_score AS sensitivity_score,
       h.hostname AS host,
       vulnerabilities,
       active_threats,
       max_cvss,
       threat_categories,
       CASE
           WHEN active_threats >= 3 AND max_cvss >= 8.0 THEN 'Critical - Immediate Protection'
           WHEN active_threats >= 2 AND max_cvss >= 7.0 THEN 'High - Urgent Action'
           WHEN active_threats >= 1 AND max_cvss >= 6.0 THEN 'Medium - Monitor Closely'
           ELSE 'Low - Standard Monitoring'
       END AS protection_priority
ORDER BY active_threats DESC, max_cvss DESC;

-- === EMERGING THREAT DETECTION ===

-- Recently Discovered Threats (Last 30 Days)
MATCH (t:Threat)
WHERE t.first_seen IS NOT NULL 
  AND datetime(t.first_seen) > datetime() - duration('P30D')
OPTIONAL MATCH (t)-[:EXPLOITS]->(v:Vulnerability)
RETURN t.threat_id AS threat_id,
       t.category AS category,
       t.priority AS priority,
       t.confidence AS confidence,
       t.actor AS threat_actor,
       date(datetime(t.first_seen)) AS first_seen,
       count(v) AS exploited_vulnerabilities,
       t.description AS description
ORDER BY datetime(t.first_seen) DESC
LIMIT 15;

-- Threat Intelligence Confidence Trends
MATCH (t:Threat)
WHERE t.first_seen IS NOT NULL
WITH date.truncate('week', date(datetime(t.first_seen))) AS discovery_week,
     collect(t.confidence) AS confidence_values
WHERE discovery_week > date() - duration('P16W')
RETURN discovery_week,
       count(confidence_values) AS threats_discovered,
       round(avg([conf IN confidence_values | conf]) * 100) / 100 AS avg_confidence,
       round(min([conf IN confidence_values | conf]) * 100) / 100 AS min_confidence,
       round(max([conf IN confidence_values | conf]) * 100) / 100 AS max_confidence
ORDER BY discovery_week DESC;

-- === THREAT MITIGATION ANALYSIS ===

-- ActionCard Response to Threats
MATCH (t:Threat)-[:EXPLOITS]->(v:Vulnerability)<-[:HAS_VULNERABILITY]-(h:Host)<-[:RESIDES_ON]-(d:DataAsset)
OPTIONAL MATCH (d)<-[:AFFECTS]-(ac:ActionCard)
WITH t, v, d, h,
     count(ac) AS actioncard_count,
     collect(ac.status) AS actioncard_statuses
RETURN t.threat_id AS threat_id,
       t.category AS threat_category,
       t.priority AS threat_priority,
       v.cve_id AS affected_cve,
       v.cvss AS vulnerability_cvss,
       count(DISTINCT d) AS affected_assets,
       count(DISTINCT h) AS affected_hosts,
       actioncard_count,
       CASE
           WHEN actioncard_count = 0 THEN 'No Response'
           WHEN size([status IN actioncard_statuses WHERE status = 'completed']) > 0 THEN 'Mitigated'
           WHEN size([status IN actioncard_statuses WHERE status IN ['approved', 'executing']]) > 0 THEN 'In Progress'
           ELSE 'Response Planned'
       END AS mitigation_status
ORDER BY t.priority, v.cvss DESC;

-- Threat Coverage Gaps
MATCH (v:Vulnerability)<-[:EXPLOITS]-(t:Threat)
WHERE t.priority IN ['critical', 'high']
OPTIONAL MATCH (v)<-[:HAS_VULNERABILITY]-(h:Host)<-[:RESIDES_ON]-(d:DataAsset)<-[:AFFECTS]-(ac:ActionCard)
WITH t, v, count(ac) AS protection_measures
WHERE protection_measures = 0
MATCH (v)<-[:HAS_VULNERABILITY]-(h:Host)
RETURN t.threat_id AS unprotected_threat,
       t.category AS threat_category,
       t.priority AS priority,
       v.cve_id AS vulnerable_component,
       v.cvss AS cvss_score,
       count(DISTINCT h) AS exposed_hosts,
       duration.between(datetime(t.first_seen), datetime()).days AS days_unprotected
ORDER BY t.priority, v.cvss DESC, days_unprotected DESC
LIMIT 20;

-- === THREAT INTELLIGENCE QUALITY METRICS ===

-- Source Reliability Assessment
MATCH (t:Threat)
WHERE t.source IS NOT NULL
WITH t.source AS intelligence_source,
     count(t) AS threat_reports,
     avg(t.confidence) AS avg_confidence,
     collect(t.priority) AS priority_distribution
RETURN intelligence_source,
       threat_reports,
       round(avg_confidence * 100) / 100 AS avg_confidence,
       size([p IN priority_distribution WHERE p = 'critical']) AS critical_reports,
       size([p IN priority_distribution WHERE p = 'high']) AS high_priority_reports,
       round((size([p IN priority_distribution WHERE p IN ['critical', 'high']]) * 100.0) / threat_reports) AS high_value_percentage
ORDER BY threat_reports DESC;

-- Threat Verification Status
MATCH (t:Threat)
WITH t.verification_status AS status, collect(t) AS threats
RETURN status,
       count(threats) AS threat_count,
       round(avg([threat IN threats | threat.confidence]) * 100) / 100 AS avg_confidence,
       size([threat IN threats WHERE threat.priority = 'critical']) AS critical_threats
ORDER BY threat_count DESC;

-- === ADVANCED THREAT PATTERNS ===

-- Multi-Vector Attack Campaigns
MATCH (t:Threat)
WHERE size(t.attack_vector) > 1
WITH t, size(t.attack_vector) AS vector_count
RETURN t.threat_id AS campaign_threat,
       t.category AS threat_category,
       t.actor AS threat_actor,
       vector_count,
       t.attack_vector AS attack_vectors,
       t.confidence AS confidence,
       t.priority AS priority
ORDER BY vector_count DESC, t.confidence DESC
LIMIT 15;

-- Cross-Category Threat Actors
MATCH (t:Threat)
WHERE t.actor IS NOT NULL AND t.actor <> ''
WITH t.actor AS actor, collect(DISTINCT t.category) AS categories
WHERE size(categories) > 1
MATCH (t:Threat {actor: actor})
RETURN actor,
       size(categories) AS category_diversity,
       categories,
       count(t) AS total_threats,
       round(avg(t.confidence) * 100) / 100 AS avg_confidence
ORDER BY category_diversity DESC, total_threats DESC;