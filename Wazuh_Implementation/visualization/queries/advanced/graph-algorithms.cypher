-- ================================================
-- ORBIT Graph Algorithms and Network Analysis
-- ================================================
-- Advanced graph analysis using Neo4j algorithms and network theory for cybersecurity insights

-- === CENTRALITY ANALYSIS ===

-- Host Importance Analysis (Betweenness Centrality Approximation)
MATCH (h:Host)
OPTIONAL MATCH (h)<-[:RESIDES_ON]-(d:DataAsset)
OPTIONAL MATCH (h)-[:CONNECTS_TO]-(connected:Host)
WITH h, 
     count(DISTINCT d) AS hosted_assets,
     count(DISTINCT connected) AS network_connections,
     size([asset IN collect(d) WHERE asset.crown_jewel = true]) AS crown_jewel_count,
     avg([asset IN collect(d) | asset.sensitivity_score]) AS avg_asset_sensitivity
WITH h, hosted_assets, network_connections, crown_jewel_count, avg_asset_sensitivity,
     (hosted_assets * 2) + network_connections + (crown_jewel_count * 5) AS centrality_score
RETURN h.hostname AS host,
       h.ip AS ip_address,
       coalesce(h.os_name + ' ' + h.os_version, h.os_name, 'Unknown') AS operating_system,
       hosted_assets,
       network_connections,
       crown_jewel_count,
       round(COALESCE(avg_asset_sensitivity, 0) * 100) / 100 AS avg_asset_sensitivity,
       centrality_score,
       CASE 
           WHEN centrality_score >= 20 THEN 'Critical Infrastructure Hub'
           WHEN centrality_score >= 10 THEN 'Important Network Node'
           WHEN centrality_score >= 5 THEN 'Standard Host'
           ELSE 'Peripheral Host'
       END AS infrastructure_role
ORDER BY centrality_score DESC
LIMIT 25;

-- Asset Influence Network (PageRank-style Analysis)
MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host)-[:CONNECTS_TO]-(connected_host:Host)<-[:RESIDES_ON]-(connected_asset:DataAsset)
WITH d, connected_asset, h, connected_host
WITH d, 
     count(DISTINCT connected_asset) AS reachable_assets,
     sum([asset IN collect(DISTINCT connected_asset) | asset.sensitivity_score]) AS influence_score,
     count(DISTINCT connected_host) AS network_reach
WITH d, reachable_assets, influence_score, network_reach,
     d.sensitivity_score + (influence_score * 0.1) + (network_reach * 0.05) AS pagerank_score
MATCH (d)-[:RESIDES_ON]->(h:Host)
RETURN d.location_pseudonym AS asset,
       d.sensitivity_score AS base_sensitivity,
       d.crown_jewel AS is_crown_jewel,
       h.hostname AS host,
       reachable_assets,
       round(influence_score * 100) / 100 AS total_influence,
       network_reach,
       round(pagerank_score * 100) / 100 AS influence_rank,
       CASE
           WHEN pagerank_score >= 2.0 THEN 'Highly Influential'
           WHEN pagerank_score >= 1.5 THEN 'Moderately Influential'
           WHEN pagerank_score >= 1.0 THEN 'Limited Influence'
           ELSE 'Isolated Asset'
       END AS network_influence_tier
ORDER BY pagerank_score DESC
LIMIT 20;

-- === COMMUNITY DETECTION AND CLUSTERING ===

-- Host Clustering by Vulnerability Patterns
MATCH (h1:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)<-[:HAS_VULNERABILITY]-(h2:Host)
WHERE id(h1) < id(h2)
WITH h1, h2, count(v) AS shared_vulnerabilities
WHERE shared_vulnerabilities >= 2
MATCH (h1)<-[:RESIDES_ON]-(d1:DataAsset), (h2)<-[:RESIDES_ON]-(d2:DataAsset)
WITH h1, h2, shared_vulnerabilities,
     count(DISTINCT d1) AS h1_assets,
     count(DISTINCT d2) AS h2_assets,
     size([asset IN collect(d1) WHERE asset.crown_jewel = true]) + 
     size([asset IN collect(d2) WHERE asset.crown_jewel = true]) AS combined_crown_jewels
RETURN h1.hostname AS host1,
       h2.hostname AS host2,
       shared_vulnerabilities,
       h1_assets + h2_assets AS total_assets,
       combined_crown_jewels,
       shared_vulnerabilities * (combined_crown_jewels + 1) AS cluster_risk_factor,
       CASE
           WHEN shared_vulnerabilities >= 5 AND combined_crown_jewels > 0 THEN 'High-Risk Cluster'
           WHEN shared_vulnerabilities >= 3 THEN 'Medium-Risk Cluster'
           ELSE 'Standard Vulnerability Cluster'
       END AS cluster_classification
ORDER BY cluster_risk_factor DESC
LIMIT 15;

-- Service Dependency Communities
MATCH path = (s1:Service)-[:DEPENDS_ON*1..3]->(s2:Service)
WHERE s1 <> s2
WITH s1, collect(DISTINCT s2) AS dependent_services
WHERE size(dependent_services) >= 2
MATCH (s1)<-[:RUNS_SERVICE]-(h1:Host)<-[:RESIDES_ON]-(d:DataAsset)
WITH s1, dependent_services, h1,
     count(d) AS supported_assets,
     size([asset IN collect(d) WHERE asset.crown_jewel = true]) AS crown_jewel_support
UNWIND dependent_services AS dep_service
MATCH (dep_service)<-[:RUNS_SERVICE]-(dep_host:Host)
WITH s1, h1, supported_assets, crown_jewel_support,
     count(DISTINCT dep_service) AS dependency_count,
     count(DISTINCT dep_host) AS dependent_hosts
RETURN s1.name AS core_service,
       h1.hostname AS primary_host,
       dependency_count,
       dependent_hosts,
       supported_assets,
       crown_jewel_support,
       dependency_count * (crown_jewel_support + 1) AS service_criticality_score,
       CASE
           WHEN dependency_count >= 3 AND crown_jewel_support > 0 THEN 'Critical Service Hub'
           WHEN dependency_count >= 2 THEN 'Important Service Node'
           ELSE 'Standard Service'
       END AS service_tier
ORDER BY service_criticality_score DESC;

-- === SHORTEST PATH AND ATTACK SURFACE ANALYSIS ===

-- Attack Path Discovery (Threat to Crown Jewel)
MATCH (t:Threat)-[:EXPLOITS]->(v:Vulnerability)<-[:HAS_VULNERABILITY]-(entry_host:Host)
MATCH (crown_jewel:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(target_host:Host)
MATCH path = shortestPath((entry_host)-[:CONNECTS_TO*1..4]-(target_host))
WHERE entry_host <> target_host
WITH t, v, entry_host, crown_jewel, target_host, path,
     length(path) AS path_length,
     t.confidence * v.cvss * crown_jewel.sensitivity_score AS attack_impact
RETURN t.threat_id AS threat,
       t.category AS threat_category,
       v.cve_id AS entry_vulnerability,
       entry_host.hostname AS entry_point,
       crown_jewel.location_pseudonym AS target_crown_jewel,
       target_host.hostname AS target_host,
       path_length AS hops_to_target,
       round(attack_impact * 100) / 100 AS potential_impact,
       [node IN nodes(path) | 
           CASE WHEN 'Host' IN labels(node) THEN node.hostname ELSE 'Unknown' END
       ] AS attack_path_hosts
ORDER BY attack_impact DESC, path_length ASC
LIMIT 20;

-- Network Segmentation Analysis
MATCH (h1:Host)-[:CONNECTS_TO*1..2]-(h2:Host)
WHERE h1 <> h2
WITH h1, collect(DISTINCT h2) AS reachable_hosts
MATCH (h1)<-[:RESIDES_ON]-(d1:DataAsset)
WITH h1, reachable_hosts, d1,
     size([host IN reachable_hosts | 
           [(host)<-[:RESIDES_ON]-(asset:DataAsset) WHERE asset.crown_jewel = true | asset]
          ]) AS reachable_crown_jewels
WITH h1, d1, size(reachable_hosts) AS network_exposure, reachable_crown_jewels
WHERE d1.crown_jewel = true OR d1.sensitivity_score >= 0.7
OPTIONAL MATCH (h1)-[:HAS_VULNERABILITY]->(v:Vulnerability)
WITH h1, d1, network_exposure, reachable_crown_jewels,
     count(v) AS host_vulnerabilities,
     max(v.cvss) AS max_cvss
RETURN h1.hostname AS host,
       d1.location_pseudonym AS sensitive_asset,
       d1.sensitivity_score AS asset_sensitivity,
       d1.crown_jewel AS is_crown_jewel,
       network_exposure,
       reachable_crown_jewels,
       host_vulnerabilities,
       COALESCE(max_cvss, 0) AS max_vulnerability_score,
       network_exposure * (reachable_crown_jewels + 1) * (host_vulnerabilities + 1) AS segmentation_risk_score,
       CASE
           WHEN network_exposure >= 10 AND reachable_crown_jewels > 0 THEN 'Poor Segmentation - High Risk'
           WHEN network_exposure >= 5 THEN 'Moderate Segmentation - Medium Risk'
           WHEN network_exposure <= 2 THEN 'Good Segmentation - Low Risk'
           ELSE 'Standard Network Exposure'
       END AS segmentation_assessment
ORDER BY segmentation_risk_score DESC
LIMIT 25;

-- === GRAPH DENSITY AND CONNECTIVITY ANALYSIS ===

-- Network Density Metrics
MATCH (h:Host)
WITH count(h) AS total_hosts
MATCH (h1:Host)-[r:CONNECTS_TO]-(h2:Host)
WITH total_hosts, count(r) AS total_connections
WITH total_hosts, total_connections,
     total_connections AS actual_edges,
     (total_hosts * (total_hosts - 1)) / 2 AS possible_edges,
     round((total_connections * 100.0) / ((total_hosts * (total_hosts - 1)) / 2) * 100) / 100 AS network_density
RETURN total_hosts,
       actual_edges,
       possible_edges,
       network_density AS density_percentage,
       CASE
           WHEN network_density >= 0.7 THEN 'Highly Connected - Flat Network'
           WHEN network_density >= 0.4 THEN 'Well Connected - Moderate Segmentation'
           WHEN network_density >= 0.1 THEN 'Segmented Network - Good Security'
           ELSE 'Highly Segmented - Excellent Security'
       END AS network_topology_assessment;

-- Vulnerability Propagation Network
MATCH (h1:Host)-[:CONNECTS_TO]-(h2:Host)
MATCH (h1)-[:HAS_VULNERABILITY]->(v1:Vulnerability)
MATCH (h2)-[:HAS_VULNERABILITY]->(v2:Vulnerability)
WHERE v1.type = v2.type
WITH h1, h2, v1.type AS shared_vuln_type, count(*) AS shared_vuln_count
MATCH (h1)<-[:RESIDES_ON]-(d1:DataAsset), (h2)<-[:RESIDES_ON]-(d2:DataAsset)
WITH h1, h2, shared_vuln_type, shared_vuln_count,
     max(d1.sensitivity_score) AS h1_max_sensitivity,
     max(d2.sensitivity_score) AS h2_max_sensitivity,
     size([asset IN collect(d1) + collect(d2) WHERE asset.crown_jewel = true]) AS crown_jewel_exposure
RETURN h1.hostname AS host1,
       h2.hostname AS host2,
       shared_vuln_type,
       shared_vuln_count,
       round(h1_max_sensitivity * 100) / 100 AS host1_max_sensitivity,
       round(h2_max_sensitivity * 100) / 100 AS host2_max_sensitivity,
       crown_jewel_exposure,
       shared_vuln_count * (crown_jewel_exposure + 1) * 
       ((h1_max_sensitivity + h2_max_sensitivity) / 2) AS propagation_risk_score
ORDER BY propagation_risk_score DESC
LIMIT 20;

-- === GRAPH TRAVERSAL FOR INCIDENT RESPONSE ===

-- Blast Radius Analysis (Impact of Host Compromise)
MATCH (compromised:Host {hostname: 'target_host'}) // Replace with actual host
MATCH (compromised)-[:CONNECTS_TO*1..3]-(affected:Host)<-[:RESIDES_ON]-(asset:DataAsset)
WITH compromised, affected, asset,
     shortestPath((compromised)-[:CONNECTS_TO*]-(affected)) AS impact_path
WITH compromised, affected, asset, length(impact_path) AS distance_from_source
OPTIONAL MATCH (affected)-[:HAS_VULNERABILITY]->(v:Vulnerability)<-[:EXPLOITS]-(t:Threat)
WITH compromised, affected, asset, distance_from_source,
     count(v) AS host_vulnerabilities,
     count(t) AS applicable_threats
RETURN affected.hostname AS potentially_affected_host,
       asset.location_pseudonym AS at_risk_asset,
       asset.sensitivity_score AS asset_sensitivity,
       asset.crown_jewel AS is_crown_jewel,
       distance_from_source AS hops_from_compromise,
       host_vulnerabilities,
       applicable_threats,
       round(asset.sensitivity_score * (4 - distance_from_source) * 
             (host_vulnerabilities + applicable_threats + 1) * 100) / 100 AS blast_radius_impact_score
ORDER BY blast_radius_impact_score DESC;

-- Emergency Response Prioritization
MATCH (ac:ActionCard {status: 'pending'})
MATCH (ac)-[:AFFECTS]->(d:DataAsset)-[:RESIDES_ON]->(h:Host)
OPTIONAL MATCH (h)-[:CONNECTS_TO*1..2]-(connected:Host)<-[:RESIDES_ON]-(connected_asset:DataAsset)
WHERE connected_asset.crown_jewel = true
WITH ac, d, h, count(DISTINCT connected_asset) AS threatened_crown_jewels
OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)<-[:EXPLOITS]-(t:Threat)
WHERE t.priority IN ['critical', 'high']
WITH ac, d, h, threatened_crown_jewels, count(t) AS critical_threats
WITH ac, d, h, threatened_crown_jewels, critical_threats,
     CASE ac.priority 
         WHEN 'critical' THEN 10
         WHEN 'high' THEN 7
         WHEN medium' THEN 5
         ELSE 3
     END AS base_priority_score,
     d.sensitivity_score * 5 AS asset_sensitivity_score,
     threatened_crown_jewels * 8 AS crown_jewel_impact_score,
     critical_threats * 3 AS threat_urgency_score
WITH ac, d, h, threatened_crown_jewels, critical_threats,
     base_priority_score + asset_sensitivity_score + 
     crown_jewel_impact_score + threat_urgency_score AS emergency_priority_score
RETURN ac.actioncard_id AS actioncard,
       ac.priority AS original_priority,
       ac.description AS description,
       d.location_pseudonym AS affected_asset,
       h.hostname AS affected_host,
       threatened_crown_jewels,
       critical_threats,
       round(emergency_priority_score * 100) / 100 AS emergency_priority_score,
       CASE
           WHEN emergency_priority_score >= 30 THEN 'Immediate - Drop Everything'
           WHEN emergency_priority_score >= 20 THEN 'Urgent - Within Hours'
           WHEN emergency_priority_score >= 10 THEN 'High - Within Day'
           ELSE 'Standard - Normal Queue'
       END AS response_urgency
ORDER BY emergency_priority_score DESC
LIMIT 15;