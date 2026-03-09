-- ================================================
-- ORBIT Advanced Analytics Queries
-- ================================================
-- Complex analytical queries for deep insights, predictive analysis, and advanced cybersecurity intelligence

-- === PREDICTIVE RISK ANALYTICS ===

-- Risk Propagation Pathways (Multi-hop Risk Analysis)
MATCH path = (d:DataAsset)-[:RESIDES_ON]->(h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)<-[:EXPLOITS]-(t:Threat)
WHERE d.crown_jewel = true
WITH path, d, h, v, t,
     d.sensitivity_score * v.cvss * t.confidence AS risk_score
OPTIONAL MATCH (h)-[:CONNECTS_TO*1..2]->(connected_host:Host)<-[:RESIDES_ON]-(connected_asset:DataAsset)
WITH d, h, v, t, risk_score,
     count(DISTINCT connected_host) AS lateral_movement_targets,
     sum([asset IN collect(DISTINCT connected_asset) | asset.sensitivity_score]) AS propagation_impact
RETURN d.location_pseudonym AS source_crown_jewel,
       h.hostname AS compromised_host,
       v.cve_id AS vulnerability_vector,
       t.category AS threat_category,
       round(risk_score * 100) / 100 AS initial_risk_score,
       lateral_movement_targets,
       round(propagation_impact * 100) / 100 AS cascading_impact,
       round((risk_score + (propagation_impact * 0.3)) * 100) / 100 AS composite_risk_score
ORDER BY composite_risk_score DESC
LIMIT 15;

-- Vulnerability Clustering and Pattern Analysis
MATCH (v1:Vulnerability)<-[:HAS_VULNERABILITY]-(h:Host)-[:HAS_VULNERABILITY]->(v2:Vulnerability)
WHERE v1.type = v2.type AND id(v1) < id(v2)
WITH v1.type AS vuln_type, h,
     collect([v1.cve_id, v2.cve_id]) AS vuln_pairs,
     count(*) AS cluster_size
WHERE cluster_size >= 2
MATCH (h)<-[:RESIDES_ON]-(d:DataAsset)
WITH vuln_type, h, cluster_size,
     count(d) AS hosted_assets,
     size([asset IN collect(d) WHERE asset.crown_jewel = true]) AS crown_jewel_count,
     avg([asset IN collect(d) | asset.sensitivity_score]) AS avg_sensitivity
RETURN vuln_type,
       h.hostname AS clustered_host,
       cluster_size,
       hosted_assets,
       crown_jewel_count,
       round(avg_sensitivity * 100) / 100 AS avg_asset_sensitivity,
       cluster_size * (crown_jewel_count + 1) * avg_sensitivity AS clustering_risk_factor
ORDER BY clustering_risk_factor DESC;

-- Temporal Attack Pattern Recognition
MATCH (ac:ActionCard)-[:AFFECTS]->(d:DataAsset)-[:RESIDES_ON]->(h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)
WHERE ac.created_ts IS NOT NULL
WITH date.truncate('day', date(datetime(ac.created_ts))) AS incident_date,
     h, v, count(ac) AS incidents_per_day
WHERE incidents_per_day > 1
WITH incident_date, 
     count(DISTINCT h) AS affected_hosts,
     count(DISTINCT v) AS vulnerability_types,
     sum(incidents_per_day) AS total_incidents
WHERE affected_hosts >= 2
RETURN incident_date,
       affected_hosts,
       vulnerability_types,
       total_incidents,
       round(total_incidents / affected_hosts) AS incidents_per_host,
       CASE 
           WHEN affected_hosts >= 5 AND total_incidents >= 10 THEN 'Coordinated Attack Campaign'
           WHEN affected_hosts >= 3 AND total_incidents >= 6 THEN 'Multi-Target Attack'
           WHEN vulnerability_types = 1 AND affected_hosts >= 2 THEN 'Exploit Kit Activity'
           ELSE 'Standard Security Events'
       END AS attack_pattern_classification
ORDER BY total_incidents DESC, affected_hosts DESC
LIMIT 20;

-- === ASSET RELATIONSHIP INTELLIGENCE ===

-- Critical Asset Dependency Mapping
MATCH (source:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(h1:Host)
OPTIONAL MATCH (h1)-[:CONNECTS_TO]->(h2:Host)<-[:RESIDES_ON]-(dependent:DataAsset)
WHERE dependent.sensitivity_score >= 0.5
WITH source, h1, 
     count(DISTINCT h2) AS connected_hosts,
     count(DISTINCT dependent) AS dependent_assets,
     sum([asset IN collect(DISTINCT dependent) | asset.sensitivity_score]) AS dependency_value
OPTIONAL MATCH (h1)-[:HAS_VULNERABILITY]->(v:Vulnerability)
WITH source, h1, connected_hosts, dependent_assets, dependency_value,
     count(v) AS host_vulnerabilities,
     max(v.cvss) AS max_host_cvss
RETURN source.location_pseudonym AS crown_jewel_asset,
       source.sensitivity_score AS asset_sensitivity,
       h1.hostname AS primary_host,
       connected_hosts,
       dependent_assets,
       round(dependency_value * 100) / 100 AS total_dependency_value,
       host_vulnerabilities,
       COALESCE(max_host_cvss, 0) AS max_vulnerability_score,
       round((source.sensitivity_score + dependency_value) * 
             (1 + (host_vulnerabilities * 0.1)) * 100) / 100 AS cascading_risk_index
ORDER BY cascading_risk_index DESC;

-- Service Interdependency Risk Assessment
MATCH (s1:Service)-[:DEPENDS_ON]->(s2:Service)
MATCH (s1)<-[:RUNS_SERVICE]-(h1:Host) 
MATCH (s2)<-[:RUNS_SERVICE]-(h2:Host)
WITH s1, s2, h1, h2
OPTIONAL MATCH (h1)-[:HAS_VULNERABILITY]->(v1:Vulnerability)
OPTIONAL MATCH (h2)-[:HAS_VULNERABILITY]->(v2:Vulnerability)
WITH s1, s2, h1, h2,
     count(DISTINCT v1) AS upstream_vulns,
     count(DISTINCT v2) AS downstream_vulns,
     max(v1.cvss) AS max_upstream_cvss,
     max(v2.cvss) AS max_downstream_cvss
MATCH (h1)<-[:RESIDES_ON]-(d1:DataAsset)
MATCH (h2)<-[:RESIDES_ON]-(d2:DataAsset)
WITH s1, s2, h1, h2, upstream_vulns, downstream_vulns, max_upstream_cvss, max_downstream_cvss,
     avg([asset IN collect(d1) | asset.sensitivity_score]) AS upstream_sensitivity,
     avg([asset IN collect(d2) | asset.sensitivity_score]) AS downstream_sensitivity,
     size([asset IN collect(d1) WHERE asset.crown_jewel = true]) AS upstream_crown_jewels,
     size([asset IN collect(d2) WHERE asset.crown_jewel = true]) AS downstream_crown_jewels
RETURN s1.name AS upstream_service,
       s2.name AS downstream_service,
       h1.hostname AS upstream_host,
       h2.hostname AS downstream_host,
       upstream_vulns,
       downstream_vulns,
       COALESCE(max_upstream_cvss, 0) AS max_upstream_cvss,
       COALESCE(max_downstream_cvss, 0) AS max_downstream_cvss,
       round(upstream_sensitivity * 100) / 100 AS upstream_sensitivity,
       round(downstream_sensitivity * 100) / 100 AS downstream_sensitivity,
       upstream_crown_jewels + downstream_crown_jewels AS total_crown_jewels,
       round(((upstream_sensitivity + downstream_sensitivity) * 
              (upstream_vulns + downstream_vulns + 2) * 
              (upstream_crown_jewels + downstream_crown_jewels + 1)) * 100) / 100 AS interdependency_risk
ORDER BY interdependency_risk DESC
LIMIT 20;

-- === BEHAVIORAL ANOMALY DETECTION ===

-- Unusual ActionCard Creation Patterns
MATCH (ac:ActionCard)
WHERE ac.created_ts IS NOT NULL
WITH date.truncate('day', date(datetime(ac.created_ts))) AS creation_date
MATCH (ac:ActionCard)
WHERE date.truncate('day', date(datetime(ac.created_ts))) = creation_date
WITH creation_date, 
     count(ac) AS daily_actioncards,
     collect(ac.priority) AS priorities,
     collect(ac.status) AS statuses
WITH creation_date, daily_actioncards, priorities, statuses,
     avg([day_count IN [(other_date) IN collect(creation_date) | 
         size([(ac:ActionCard) WHERE date.truncate('day', date(datetime(ac.created_ts))) = other_date | ac])]
     WHERE day_count IS NOT NULL | day_count]) AS avg_daily_actioncards
WHERE daily_actioncards > (avg_daily_actioncards * 2.5)
RETURN creation_date,
       daily_actioncards,
       round(avg_daily_actioncards * 100) / 100 AS average_baseline,
       round((daily_actioncards / avg_daily_actioncards) * 100) / 100 AS spike_multiplier,
       size([p IN priorities WHERE p = 'critical']) AS critical_priority_count,
       size([s IN statuses WHERE s = 'pending']) AS pending_count,
       CASE
           WHEN daily_actioncards > (avg_daily_actioncards * 5) THEN 'Severe Anomaly - Possible Incident'
           WHEN daily_actioncards > (avg_daily_actioncards * 3) THEN 'Major Anomaly - Investigation Required'
           ELSE 'Moderate Anomaly - Monitor Trends'
       END AS anomaly_classification
ORDER BY spike_multiplier DESC;

-- Host Scanning Behavior Analysis
MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host)
WHERE d.scan_ts IS NOT NULL
WITH h, 
     count(d) AS scanned_assets,
     min(datetime(d.scan_ts)) AS first_scan,
     max(datetime(d.scan_ts)) AS last_scan,
     avg([asset IN collect(d) | duration.between(datetime(asset.scan_ts), datetime()).days]) AS avg_scan_age
WITH h, scanned_assets, first_scan, last_scan, avg_scan_age,
     duration.between(first_scan, last_scan).days AS scan_timespan
WHERE scan_timespan > 0
MATCH (d:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(h)
WITH h, scanned_assets, avg_scan_age, scan_timespan,
     count(d) AS crown_jewel_count
WHERE crown_jewel_count > 0
RETURN h.hostname AS host,
       coalesce(h.os_name + ' ' + h.os_version, h.os_name, 'Unknown') AS operating_system,
       scanned_assets,
       crown_jewel_count,
       round(avg_scan_age) AS avg_scan_age_days,
       scan_timespan AS total_scan_period_days,
       round(scanned_assets / scan_timespan) AS scan_velocity,
       CASE
           WHEN avg_scan_age > 90 AND crown_jewel_count > 0 THEN 'Critical - Crown Jewels Stale'
           WHEN avg_scan_age > 60 THEN 'High Priority - Schedule Rescans'
           WHEN avg_scan_age < 7 THEN 'Excellent - Current Status'
           ELSE 'Standard - Within Policy'
       END AS scan_health_status
ORDER BY (crown_jewel_count * avg_scan_age) DESC;

-- === CROSS-DOMAIN CORRELATION ANALYSIS ===

-- PII-Threat-Vulnerability Correlation Matrix
MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)<-[:EXPLOITS]-(t:Threat)
WHERE size(d.pii_types) > 0
UNWIND d.pii_types AS pii_type
WITH pii_type, v.type AS vuln_type, t.category AS threat_category,
     count(*) AS correlation_frequency,
     avg(d.sensitivity_score) AS avg_sensitivity,
     avg(v.cvss) AS avg_cvss,
     avg(t.confidence) AS avg_threat_confidence
RETURN pii_type,
       vuln_type,
       threat_category,
       correlation_frequency,
       round(avg_sensitivity * 100) / 100 AS avg_sensitivity,
       round(avg_cvss * 10) / 10 AS avg_cvss,
       round(avg_threat_confidence * 100) / 100 AS avg_threat_confidence,
       round(correlation_frequency * avg_sensitivity * avg_cvss * avg_threat_confidence) AS risk_correlation_score
ORDER BY risk_correlation_score DESC
LIMIT 25;

-- Subscription-Asset Risk Exposure Analysis
MATCH (sub:Subscription)-[:ACCESSES]->(d:DataAsset)-[:RESIDES_ON]->(h:Host)
OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)<-[:EXPLOITS]-(t:Threat)
WITH sub, 
     count(DISTINCT d) AS accessible_assets,
     size([asset IN collect(DISTINCT d) WHERE asset.crown_jewel = true]) AS crown_jewel_access,
     sum([asset IN collect(DISTINCT d) | asset.sensitivity_score]) AS total_sensitivity_exposure,
     count(DISTINCT v) AS vulnerable_vectors,
     count(DISTINCT t) AS applicable_threats,
     max(v.cvss) AS max_vulnerability_score
RETURN sub.subscription_id AS subscription,
       sub.type AS subscription_type,
       accessible_assets,
       crown_jewel_access,
       round(total_sensitivity_exposure * 100) / 100 AS total_sensitivity_exposure,
       vulnerable_vectors,
       applicable_threats,
       COALESCE(max_vulnerability_score, 0) AS max_vulnerability_score,
       round((total_sensitivity_exposure * (vulnerable_vectors + 1) * (applicable_threats + 1)) * 100) / 100 AS subscription_risk_exposure
ORDER BY subscription_risk_exposure DESC;

-- === TEMPORAL TREND ANALYSIS ===

-- Security Posture Evolution (90-Day Window)
WITH [d IN range(-90, 0) | date() + duration({days: d})] AS date_range
UNWIND date_range AS analysis_date
OPTIONAL MATCH (ac:ActionCard)
WHERE date.truncate('day', date(datetime(ac.created_ts))) = analysis_date
WITH analysis_date,
     count(ac) AS actioncards_created,
     size([card IN collect(ac) WHERE card.priority = 'critical']) AS critical_actioncards,
     size([card IN collect(ac) WHERE card.status = 'completed']) AS completed_actioncards
OPTIONAL MATCH (d:DataAsset)
WHERE date.truncate('day', date(datetime(d.scan_ts))) = analysis_date
WITH analysis_date, actioncards_created, critical_actioncards, completed_actioncards,
     count(d) AS assets_scanned,
     size([asset IN collect(d) WHERE asset.crown_jewel = true]) AS crown_jewels_scanned
OPTIONAL MATCH (t:Threat)
WHERE date.truncate('day', date(datetime(t.first_seen))) = analysis_date
WITH analysis_date, actioncards_created, critical_actioncards, completed_actioncards,
     assets_scanned, crown_jewels_scanned,
     count(t) AS new_threats,
     size([threat IN collect(t) WHERE threat.priority IN ['critical', 'high']]) AS high_priority_threats
WHERE actioncards_created > 0 OR assets_scanned > 0 OR new_threats > 0
RETURN analysis_date,
       actioncards_created,
       critical_actioncards,
       completed_actioncards,
       CASE WHEN actioncards_created > 0 
            THEN round((completed_actioncards * 100.0) / actioncards_created) 
            ELSE null END AS completion_rate_percent,
       assets_scanned,
       crown_jewels_scanned,
       new_threats,
       high_priority_threats,
       actioncards_created + new_threats - completed_actioncards AS net_security_workload
ORDER BY analysis_date DESC
LIMIT 30;

-- Threat Intelligence Maturity Metrics
MATCH (t:Threat)
WHERE t.first_seen IS NOT NULL
WITH date.truncate('month', date(datetime(t.first_seen))) AS discovery_month
WHERE discovery_month > date() - duration('P12M')
MATCH (t:Threat)
WHERE date.truncate('month', date(datetime(t.first_seen))) = discovery_month
WITH discovery_month,
     count(t) AS threats_discovered,
     avg(t.confidence) AS avg_confidence,
     size([threat IN collect(t) WHERE threat.verification_status = 'verified']) AS verified_threats,
     size([threat IN collect(t) WHERE threat.source IS NOT NULL]) AS sourced_threats,
     size(reduce(actors = [], threat IN collect(t) | 
         CASE WHEN threat.actor IS NOT NULL AND threat.actor <> '' AND NOT threat.actor IN actors 
              THEN actors + threat.actor ELSE actors END)) AS unique_actors
RETURN discovery_month,
       threats_discovered,
       round(avg_confidence * 100) / 100 AS avg_confidence,
       verified_threats,
       CASE WHEN threats_discovered > 0 
            THEN round((verified_threats * 100.0) / threats_discovered) 
            ELSE 0 END AS verification_rate_percent,
       sourced_threats,
       CASE WHEN threats_discovered > 0 
            THEN round((sourced_threats * 100.0) / threats_discovered) 
            ELSE 0 END AS source_attribution_percent,
       unique_actors,
       round((verified_threats + sourced_threats + (unique_actors * 2)) / threats_discovered * 100) / 100 AS intelligence_maturity_score
ORDER BY discovery_month DESC;