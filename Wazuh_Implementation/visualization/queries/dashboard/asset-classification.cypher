-- ================================================
-- ORBIT Asset Classification Dashboard Queries
-- ================================================
-- Cypher queries for data asset analysis, PII classification, and sensitivity scoring

-- === ASSET INVENTORY AND CLASSIFICATION ===

-- Total Data Assets with Classification Breakdown
MATCH (d:DataAsset)
WITH CASE
    WHEN d.crown_jewel = true THEN 'Crown Jewel'
    WHEN d.sensitivity_score >= 0.8 THEN 'Very High Sensitivity'
    WHEN d.sensitivity_score >= 0.6 THEN 'High Sensitivity' 
    WHEN d.sensitivity_score >= 0.4 THEN 'Medium Sensitivity'
    WHEN d.sensitivity_score >= 0.2 THEN 'Low Sensitivity'
    ELSE 'Minimal Sensitivity'
END AS classification
RETURN classification, count(*) AS asset_count
ORDER BY asset_count DESC;

-- Asset Distribution by Host
MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host)
WITH h, count(d) AS asset_count,
     avg(d.sensitivity_score) AS avg_sensitivity,
     size([asset IN collect(d) WHERE asset.crown_jewel = true]) AS crown_jewel_count
RETURN h.hostname AS hostname,
       h.ip AS host_ip,
       coalesce(h.os_name + ' ' + h.os_version, h.os_name, 'Unknown') AS operating_system,
       asset_count,
       round(avg_sensitivity * 100) / 100 AS average_sensitivity,
       crown_jewel_count
ORDER BY crown_jewel_count DESC, asset_count DESC
LIMIT 20;

-- Sensitivity Score Distribution Analysis
MATCH (d:DataAsset)
WITH d.sensitivity_score AS score
RETURN 
    count(*) AS total_assets,
    round(min(score) * 100) / 100 AS min_sensitivity,
    round(max(score) * 100) / 100 AS max_sensitivity,
    round(avg(score) * 100) / 100 AS avg_sensitivity,
    round(stdev(score) * 100) / 100 AS sensitivity_std_dev,
    percentileDisc(score, 0.5) AS median_sensitivity,
    percentileDisc(score, 0.9) AS p90_sensitivity;

-- === PII ANALYSIS ===

-- PII Type Prevalence and Risk Analysis
MATCH (d:DataAsset)
WHERE size(d.pii_types) > 0
UNWIND d.pii_types AS pii_type
WITH pii_type, collect(d) AS assets_with_pii
RETURN pii_type,
       count(assets_with_pii) AS asset_count,
       round(avg([asset IN assets_with_pii | asset.sensitivity_score]) * 100) / 100 AS avg_sensitivity,
       size([asset IN assets_with_pii WHERE asset.crown_jewel = true]) AS crown_jewel_count,
       round((count(assets_with_pii) * 100.0) / size(assets_with_pii)) AS prevalence_percentage
ORDER BY asset_count DESC;

-- High-Risk PII Combinations
MATCH (d:DataAsset)
WHERE size(d.pii_types) >= 2
WITH d.pii_types AS pii_combination, 
     d.sensitivity_score AS sensitivity,
     d.crown_jewel AS is_crown_jewel,
     count(*) AS occurrence_count
WHERE sensitivity >= 0.7
RETURN pii_combination,
       occurrence_count,
       round(avg(sensitivity) * 100) / 100 AS avg_sensitivity,
       size([jewel IN collect(is_crown_jewel) WHERE jewel = true]) AS crown_jewel_count
ORDER BY occurrence_count DESC, avg_sensitivity DESC
LIMIT 15;

-- PII Density by Host (Assets with PII per Host)
MATCH (h:Host)<-[:RESIDES_ON]-(d:DataAsset)
WITH h, 
     count(d) AS total_assets,
     size([asset IN collect(d) WHERE size(asset.pii_types) > 0]) AS pii_assets,
     collect(d.pii_types) AS all_pii_types
WITH h, total_assets, pii_assets,
     round((pii_assets * 100.0) / total_assets) AS pii_percentage,
     reduce(flat = [], types IN all_pii_types | flat + types) AS flattened_pii
WITH h, total_assets, pii_assets, pii_percentage,
     reduce(unique = [], pii IN flattened_pii | 
         CASE WHEN pii IN unique THEN unique ELSE unique + pii END) AS unique_pii_types
WHERE pii_assets > 0
RETURN h.hostname AS hostname,
       h.ip AS host_ip,
       total_assets,
       pii_assets,
       pii_percentage,
       size(unique_pii_types) AS unique_pii_type_count,
       unique_pii_types
ORDER BY pii_percentage DESC, pii_assets DESC;

-- === CROWN JEWEL ANALYSIS ===

-- Crown Jewel Asset Details with Risk Context
MATCH (d:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(h:Host)
OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
OPTIONAL MATCH (d)<-[:AFFECTS]-(ac:ActionCard)
WITH d, h, 
     count(DISTINCT v) AS vulnerability_count,
     max(v.cvss) AS max_cvss,
     count(DISTINCT ac) AS actioncard_count,
     collect(DISTINCT ac.status) AS actioncard_statuses
RETURN d.location_pseudonym AS crown_jewel_asset,
       d.sensitivity_score AS sensitivity_score,
       d.pii_types AS pii_types,
       h.hostname AS host,
       h.ip AS host_ip,
       vulnerability_count,
       COALESCE(max_cvss, 0) AS highest_cvss,
       actioncard_count,
       actioncard_statuses,
       CASE 
           WHEN vulnerability_count > 0 AND actioncard_count = 0 THEN 'High Risk - Unprotected'
           WHEN vulnerability_count > 0 AND actioncard_count > 0 THEN 'Medium Risk - Protected'
           WHEN vulnerability_count = 0 THEN 'Low Risk - Secure'
           ELSE 'Unknown Risk'
       END AS risk_assessment
ORDER BY d.sensitivity_score DESC, vulnerability_count DESC;

-- Crown Jewel Protection Coverage
MATCH (d:DataAsset {crown_jewel: true})
OPTIONAL MATCH (d)<-[:AFFECTS]-(ac:ActionCard)
WITH d, collect(ac) AS action_cards
WITH d,
     CASE 
         WHEN size([ac IN action_cards WHERE ac.status = 'completed']) > 0 THEN 'Protected'
         WHEN size([ac IN action_cards WHERE ac.status IN ['approved', 'executing']]) > 0 THEN 'In Progress'
         WHEN size([ac IN action_cards WHERE ac.status = 'pending']) > 0 THEN 'Scheduled'
         ELSE 'Unprotected'
     END AS protection_status
RETURN protection_status, count(d) AS crown_jewel_count
ORDER BY CASE protection_status
    WHEN 'Protected' THEN 1
    WHEN 'In Progress' THEN 2
    WHEN 'Scheduled' THEN 3
    ELSE 4
END;

-- === ASSET SENSITIVITY PATTERNS ===

-- Sensitivity Score vs PII Type Correlation
MATCH (d:DataAsset)
WHERE size(d.pii_types) > 0
WITH size(d.pii_types) AS pii_count,
     d.sensitivity_score AS sensitivity,
     d.pii_types AS pii_types
RETURN pii_count,
       count(*) AS asset_count,
       round(avg(sensitivity) * 100) / 100 AS avg_sensitivity,
       round(min(sensitivity) * 100) / 100 AS min_sensitivity,
       round(max(sensitivity) * 100) / 100 AS max_sensitivity,
       collect(DISTINCT pii_types)[0..3] AS sample_pii_combinations
ORDER BY pii_count DESC;

-- Assets with Sensitivity-PII Misalignment
MATCH (d:DataAsset)
WITH d,
     CASE
         WHEN size(d.pii_types) = 0 AND d.sensitivity_score > 0.5 THEN 'High Sensitivity - No PII'
         WHEN size(d.pii_types) >= 2 AND d.sensitivity_score < 0.4 THEN 'Multiple PII - Low Sensitivity'
         WHEN 'US_SSN' IN d.pii_types AND d.sensitivity_score < 0.7 THEN 'SSN Present - Low Sensitivity'
         WHEN 'CREDIT_CARD' IN d.pii_types AND d.sensitivity_score < 0.6 THEN 'Credit Card - Low Sensitivity'
         ELSE null
     END AS misalignment_type
WHERE misalignment_type IS NOT NULL
MATCH (d)-[:RESIDES_ON]->(h:Host)
RETURN misalignment_type,
       d.location_pseudonym AS asset_location,
       d.sensitivity_score AS current_sensitivity,
       d.pii_types AS pii_types,
       h.hostname AS host
ORDER BY misalignment_type, d.sensitivity_score
LIMIT 20;

-- === ASSET SCANNING AND COMPLIANCE ===

-- Asset Scan Status Overview
MATCH (d:DataAsset)
WITH d.scan_status AS status, collect(d) AS assets
RETURN status,
       count(assets) AS asset_count,
       round(avg([asset IN assets | asset.sensitivity_score]) * 100) / 100 AS avg_sensitivity,
       size([asset IN assets WHERE asset.crown_jewel = true]) AS crown_jewel_count
ORDER BY asset_count DESC;

-- Assets Requiring Rescanning (Stale Scan Data)
MATCH (d:DataAsset)
WHERE d.scan_ts IS NOT NULL 
  AND datetime(d.scan_ts) < datetime() - duration('P30D')
MATCH (d)-[:RESIDES_ON]->(h:Host)
WITH d, h, duration.between(datetime(d.scan_ts), datetime()).days AS days_since_scan
RETURN d.location_pseudonym AS stale_asset,
       d.sensitivity_score AS sensitivity,
       d.crown_jewel AS is_crown_jewel,
       h.hostname AS host,
       days_since_scan,
       CASE 
           WHEN days_since_scan > 90 THEN 'Critical - Rescan Immediately'
           WHEN days_since_scan > 60 THEN 'High Priority - Rescan Soon'
           WHEN days_since_scan > 30 THEN 'Medium Priority - Schedule Rescan'
           ELSE 'Low Priority'
       END AS rescan_priority
ORDER BY d.crown_jewel DESC, days_since_scan DESC, d.sensitivity_score DESC
LIMIT 25;

-- Monthly Asset Discovery Trends
MATCH (d:DataAsset)
WHERE d.scan_ts IS NOT NULL
WITH date.truncate('month', date(datetime(d.scan_ts))) AS discovery_month
WHERE discovery_month > date() - duration('P12M')
MATCH (d:DataAsset)
WHERE date.truncate('month', date(datetime(d.scan_ts))) = discovery_month
WITH discovery_month,
     count(d) AS assets_discovered,
     size([asset IN collect(d) WHERE asset.crown_jewel = true]) AS crown_jewels_discovered,
     round(avg([asset IN collect(d) | asset.sensitivity_score]) * 100) / 100 AS avg_sensitivity
RETURN discovery_month,
       assets_discovered,
       crown_jewels_discovered,
       avg_sensitivity
ORDER BY discovery_month DESC;

-- === COMPLIANCE AND RISK METRICS ===

-- Data Classification Compliance Report
MATCH (d:DataAsset)
WITH d,
     CASE
         WHEN d.crown_jewel = true AND size(d.pii_types) = 0 THEN 'Crown Jewel - No PII Detected'
         WHEN d.crown_jewel = false AND size(d.pii_types) >= 3 THEN 'Non-Crown Jewel - Multiple PII Types'
         WHEN d.sensitivity_score >= 0.8 AND d.crown_jewel = false THEN 'High Sensitivity - Not Crown Jewel'
         WHEN d.scan_status <> 'scanned' THEN 'Unscanned Asset'
         ELSE 'Compliant'
     END AS compliance_issue
RETURN compliance_issue, count(*) AS asset_count
ORDER BY asset_count DESC;

-- Asset Risk Scoring (Sensitivity + Vulnerability + Threat Context)
MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host)
OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
OPTIONAL MATCH (v)-[:EXPLOITED_BY]->(t:Threat)
WITH d, h,
     count(DISTINCT v) AS vulnerability_count,
     count(DISTINCT t) AS threat_count,
     max(v.cvss) AS max_cvss
WITH d, h, vulnerability_count, threat_count, max_cvss,
     d.sensitivity_score + 
     (vulnerability_count * 0.05) + 
     (threat_count * 0.1) + 
     (COALESCE(max_cvss, 0) * 0.05) AS composite_risk_score
RETURN d.location_pseudonym AS asset_location,
       d.sensitivity_score AS base_sensitivity,
       d.crown_jewel AS is_crown_jewel,
       h.hostname AS host,
       vulnerability_count,
       threat_count,
       COALESCE(max_cvss, 0) AS highest_cvss,
       round(composite_risk_score * 100) / 100 AS composite_risk_score,
       CASE
           WHEN composite_risk_score >= 1.0 THEN 'Critical Risk'
           WHEN composite_risk_score >= 0.8 THEN 'High Risk'
           WHEN composite_risk_score >= 0.6 THEN 'Medium Risk'
           WHEN composite_risk_score >= 0.4 THEN 'Low Risk'
           ELSE 'Minimal Risk'
       END AS risk_category
ORDER BY composite_risk_score DESC
LIMIT 30;