-- ================================================
-- ORBIT Security Overview Dashboard Queries
-- ================================================
-- Cypher queries for high-level security metrics and KPIs

-- === BASIC SYSTEM METRICS ===

-- Total Hosts in System
MATCH (h:Host)
RETURN count(h) AS total_hosts;

-- Active Vulnerabilities Count
MATCH (v:Vulnerability)
RETURN count(v) AS total_vulnerabilities;

-- Crown Jewel Assets Count
MATCH (d:DataAsset {crown_jewel: true})
RETURN count(d) AS crown_jewel_count;

-- Pending ActionCards Count
MATCH (ac:ActionCard {status: 'pending'})
RETURN count(ac) AS pending_actions;

-- === VULNERABILITY ANALYSIS ===

-- Vulnerability Severity Distribution
MATCH (v:Vulnerability)
WITH CASE 
    WHEN v.cvss >= 9.0 THEN 'Critical'
    WHEN v.cvss >= 7.0 THEN 'High' 
    WHEN v.cvss >= 4.0 THEN 'Medium'
    ELSE 'Low'
END AS severity
RETURN severity, count(*) AS vulnerability_count
ORDER BY CASE severity
    WHEN 'Critical' THEN 4
    WHEN 'High' THEN 3
    WHEN 'Medium' THEN 2
    ELSE 1
END DESC;

-- Top 10 Most Vulnerable Hosts
MATCH (h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)
WITH h, count(v) AS vulnerability_count
ORDER BY vulnerability_count DESC
LIMIT 10
RETURN h.hostname AS hostname,
       h.ip AS ip_address,
       vulnerability_count;

-- Critical Vulnerabilities (CVSS >= 9.0)
MATCH (h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)
WHERE v.cvss >= 9.0
RETURN h.hostname AS hostname,
       v.cve_id AS cve_id,
       v.title AS vulnerability_title,
       v.cvss AS cvss_score
ORDER BY v.cvss DESC;

-- === ASSET CLASSIFICATION ===

-- Data Asset Sensitivity Distribution
MATCH (d:DataAsset)
WITH CASE
    WHEN d.sensitivity_score >= 0.9 THEN 'Critical (0.9-1.0)'
    WHEN d.sensitivity_score >= 0.8 THEN 'Very High (0.8-0.9)'
    WHEN d.sensitivity_score >= 0.7 THEN 'High (0.7-0.8)'
    WHEN d.sensitivity_score >= 0.6 THEN 'Medium-High (0.6-0.7)'
    WHEN d.sensitivity_score >= 0.4 THEN 'Medium (0.4-0.6)'
    WHEN d.sensitivity_score >= 0.2 THEN 'Low-Medium (0.2-0.4)'
    ELSE 'Low (0.0-0.2)'
END AS sensitivity_level
RETURN sensitivity_level, count(*) AS asset_count
ORDER BY asset_count DESC;

-- Crown Jewel Assets with Host Details
MATCH (d:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(h:Host)
RETURN d.location_pseudonym AS asset_location,
       d.sensitivity_score AS sensitivity_score,
       h.hostname AS host,
       h.ip AS host_ip,
       d.pii_types AS pii_types
ORDER BY d.sensitivity_score DESC;

-- Assets with PII by Type
MATCH (d:DataAsset)
WHERE size(d.pii_types) > 0
UNWIND d.pii_types AS pii_type
RETURN pii_type, count(*) AS asset_count
ORDER BY asset_count DESC;

-- === THREAT INTELLIGENCE ===

-- Threat Severity Distribution
MATCH (t:Threat)
RETURN t.severity AS severity, count(*) AS threat_count
ORDER BY CASE t.severity
    WHEN 'CRITICAL' THEN 4
    WHEN 'HIGH' THEN 3
    WHEN 'MEDIUM' THEN 2
    ELSE 1
END DESC;

-- Threats with Highest Impact (Most Affected Hosts)
MATCH (t:Threat)<-[:EXPLOITED_BY]-(v:Vulnerability)<-[:HAS_VULNERABILITY]-(h:Host)
WITH t, count(DISTINCT h) AS affected_hosts, 
     count(DISTINCT v) AS exploited_vulnerabilities,
     avg(v.cvss) AS avg_cvss
ORDER BY affected_hosts DESC, avg_cvss DESC
LIMIT 15
RETURN t.title AS threat_name,
       t.severity AS threat_severity,
       affected_hosts,
       exploited_vulnerabilities,
       round(avg_cvss * 100) / 100 AS average_cvss;

-- Active Attack Paths (Host -> Vulnerability -> Threat)
MATCH path = (h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)-[:EXPLOITED_BY]->(t:Threat)
WHERE v.cvss >= 7.0
RETURN h.hostname AS vulnerable_host,
       v.cve_id AS vulnerability,
       v.cvss AS cvss_score,
       t.title AS threat_name,
       t.severity AS threat_severity
ORDER BY v.cvss DESC
LIMIT 20;

-- === ACTIONCARD WORKFLOW METRICS ===

-- ActionCard Status Distribution
MATCH (ac:ActionCard)
RETURN ac.status AS status, count(*) AS card_count
ORDER BY CASE ac.status
    WHEN 'received' THEN 1
    WHEN 'pending' THEN 2
    WHEN 'approved' THEN 3
    WHEN 'executing' THEN 4
    WHEN 'completed' THEN 5
    WHEN 'rejected' THEN 6
    WHEN 'failed' THEN 7
END;

-- Analyst Workload Distribution
MATCH (ac:ActionCard)
WHERE ac.analyst_id IS NOT NULL
WITH ac.analyst_id AS analyst_id,
     count(ac) AS assigned_cards,
     collect(DISTINCT ac.status) AS card_statuses
RETURN analyst_id AS analyst,
       assigned_cards,
       card_statuses
ORDER BY assigned_cards DESC;

-- ActionCards by Priority (if metadata.priority exists)
MATCH (ac:ActionCard)
WHERE ac.priority IS NOT NULL
RETURN ac.priority AS priority,
       ac.status AS status,
       count(*) AS card_count
ORDER BY CASE ac.priority
    WHEN 'critical' THEN 4
    WHEN 'high' THEN 3
    WHEN 'medium' THEN 2
    ELSE 1
END DESC, ac.status;

-- Workflow Completion Rate
MATCH (ac:ActionCard)
WITH count(ac) AS total_cards,
     size([ac IN collect(ac) WHERE ac.status = 'completed']) AS completed_cards,
     size([ac IN collect(ac) WHERE ac.status IN ['rejected', 'failed']]) AS failed_cards
RETURN total_cards,
       completed_cards,
       failed_cards,
       round((completed_cards * 100.0) / total_cards) AS completion_rate_percent;

-- === SYSTEM HEALTH METRICS ===

-- Recent Activity Summary (Last 7 Days)
MATCH (n)
WHERE n.last_updated IS NOT NULL 
  AND n.last_updated > datetime() - duration('P7D')
  AND NOT 'SchemaVersion' IN labels(n)
WITH date(n.last_updated) AS activity_date,
     labels(n)[0] AS entity_type
RETURN activity_date, entity_type, count(*) AS activity_count
ORDER BY activity_date DESC, activity_count DESC;

-- Data Freshness Check
MATCH (n)
WHERE n.last_updated IS NOT NULL
  AND NOT 'SchemaVersion' IN labels(n)
WITH labels(n)[0] AS entity_type,
     min(n.last_updated) AS oldest_update,
     max(n.last_updated) AS newest_update,
     count(n) AS entity_count
RETURN entity_type,
       oldest_update,
       newest_update,
       entity_count
ORDER BY oldest_update ASC;

-- Assets Requiring Attention (High Sensitivity + Vulnerabilities)
MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host)
WHERE d.sensitivity_score >= 0.7
OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
WITH d, h, count(v) AS vulnerability_count
WHERE vulnerability_count > 0
RETURN d.location_pseudonym AS sensitive_asset,
       d.sensitivity_score AS sensitivity,
       h.hostname AS host,
       vulnerability_count,
       d.crown_jewel AS is_crown_jewel
ORDER BY d.sensitivity_score DESC, vulnerability_count DESC
LIMIT 15;

-- Unprotected Critical Assets (Crown Jewels without Active ActionCards)
MATCH (d:DataAsset {crown_jewel: true})
WHERE NOT EXISTS {
    MATCH (d)<-[:AFFECTS]-(ac:ActionCard)
    WHERE ac.status IN ['pending', 'approved', 'executing']
}
MATCH (d)-[:RESIDES_ON]->(h:Host)
RETURN d.location_pseudonym AS unprotected_crown_jewel,
       d.sensitivity_score AS sensitivity,
       h.hostname AS host,
       h.ip AS host_ip
ORDER BY d.sensitivity_score DESC;
