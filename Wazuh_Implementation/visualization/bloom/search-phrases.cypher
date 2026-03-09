-- =====================================================
-- ORBIT Security Analysis - Bloom Search Phrases
-- =====================================================
-- Predefined Cypher queries for common security analysis patterns
-- Import these into Neo4j Bloom for natural language search capabilities

-- ===== ASSET DISCOVERY AND CLASSIFICATION =====

-- Show all crown jewel assets with their hosting details
"Show crown jewel assets"
MATCH (d:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(h:Host)
RETURN d, h

-- Find high-sensitivity data assets (above threshold)
"Show high sensitivity assets"
MATCH (d:DataAsset)
WHERE d.sensitivity_score >= 0.8
MATCH (d)-[:RESIDES_ON]->(h:Host)
RETURN d, h
ORDER BY d.sensitivity_score DESC

-- Show assets containing specific PII types
"Show assets with {pii_type}"
MATCH (d:DataAsset) 
WHERE $pii_type IN d.pii_types
MATCH (d)-[:RESIDES_ON]->(h:Host)
RETURN d, h

-- Find assets with multiple PII types (high risk combinations)
"Show high risk PII combinations"
MATCH (d:DataAsset)
WHERE size(d.pii_types) >= 2 AND d.sensitivity_score >= 0.7
MATCH (d)-[:RESIDES_ON]->(h:Host)
RETURN d, h
ORDER BY d.sensitivity_score DESC

-- ===== VULNERABILITY ANALYSIS =====

-- Find hosts with high vulnerability counts  
"Find vulnerable hosts"
MATCH (h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)
WITH h, count(v) AS vuln_count
WHERE vuln_count >= 5
MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
RETURN h, v

-- Show critical vulnerabilities (CVSS >= 9.0)
"Show critical vulnerabilities"
MATCH (v:Vulnerability)
WHERE v.cvss >= 9.0
MATCH (h:Host)-[:HAS_VULNERABILITY]->(v)
RETURN h, v
ORDER BY v.cvss DESC

-- Find vulnerabilities by CVSS score range
"Show vulnerabilities with CVSS above {cvss_threshold}"
MATCH (v:Vulnerability)
WHERE v.cvss >= $cvss_threshold
MATCH (h:Host)-[:HAS_VULNERABILITY]->(v)
RETURN h, v
ORDER BY v.cvss DESC

-- Show unpatched vulnerabilities (no ActionCards)
"Show unpatched vulnerabilities"
MATCH (h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)
WHERE NOT EXISTS {
    MATCH (h)<-[:AFFECTS]-(ac:ActionCard)
    WHERE ac.action_type = 'patch'
}
RETURN h, v

-- ===== THREAT INTELLIGENCE =====

-- Trace threat exploitation paths
"Trace threat paths" 
MATCH path = (h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability)-[:EXPLOITED_BY]->(t:Threat)
RETURN path

-- Show threats by severity level
"Show {severity} threats"
MATCH (t:Threat {severity: $severity})<-[:EXPLOITED_BY]-(v:Vulnerability)<-[:HAS_VULNERABILITY]-(h:Host)
RETURN t, v, h

-- Find active threats (recently detected)
"Show recent threats"
MATCH (t:Threat)
WHERE datetime(t.first_seen) > datetime() - duration('P30D')
MATCH (t)<-[:EXPLOITED_BY]-(v:Vulnerability)<-[:HAS_VULNERABILITY]-(h:Host)
RETURN t, v, h
ORDER BY t.first_seen DESC

-- Show threats targeting crown jewel assets
"Show threats to crown jewels"
MATCH (d:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(h:Host)
MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)-[:EXPLOITED_BY]->(t:Threat)
RETURN d, h, v, t

-- ===== ACTIONCARD WORKFLOW MANAGEMENT =====

-- Show pending ActionCards requiring analyst attention
"Show pending actions"
MATCH (ac:ActionCard {status: 'pending'})-[:AFFECTS]->(target)
OPTIONAL MATCH (ac)-[:ASSIGNED_TO]->(an:Analyst)
RETURN ac, target, an

-- Show ActionCards by status
"Show {status} ActionCards"
MATCH (ac:ActionCard {status: $status})
OPTIONAL MATCH (ac)-[:ASSIGNED_TO]->(an:Analyst)
OPTIONAL MATCH (ac)-[:AFFECTS]->(target)
RETURN ac, an, target

-- Find ActionCards assigned to specific analyst
"Show ActionCards for {analyst_id}"
MATCH (an:Analyst {analyst_id: $analyst_id})<-[:ASSIGNED_TO]-(ac:ActionCard)
OPTIONAL MATCH (ac)-[:AFFECTS]->(target)
RETURN an, ac, target

-- Show completed ActionCard workflow
"Show completed workflows"
MATCH (ac:ActionCard {status: 'completed'})
MATCH (ac)-[:ASSIGNED_TO]->(an:Analyst)
MATCH (ac)-[:APPROVED_BY]->(ap:Analyst)
MATCH (ac)-[:EXECUTED]->(ex:ExecutionEvent)
OPTIONAL MATCH (ac)-[:AFFECTS]->(target)
RETURN ac, an, ap, ex, target

-- ===== HOST AND SERVICE ANALYSIS =====

-- Asset impact analysis for specific host
"Asset impact for {hostname}"
MATCH (h:Host {hostname: $hostname})
OPTIONAL MATCH (h)<-[:RESIDES_ON]-(d:DataAsset)
OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
OPTIONAL MATCH (h)<-[:AFFECTS]-(ac:ActionCard)
RETURN h, d, v, ac

-- Show services running on specific host
"Show services on {hostname}"
MATCH (h:Host {hostname: $hostname})-[:RUNS]->(s:Service)
OPTIONAL MATCH (h)-[:HAS_APP]->(app:Application)
RETURN h, s, app

-- Find hosts by IP address
"Find host {ip_address}"
MATCH (h:Host {ip: $ip_address})
OPTIONAL MATCH (h)-[:RUNS]->(s:Service)
OPTIONAL MATCH (h)<-[:RESIDES_ON]-(d:DataAsset)
RETURN h, s, d

-- Show host infrastructure inventory
"Show all hosts"
MATCH (h:Host)
OPTIONAL MATCH (h)-[:RUNS]->(s:Service)
WITH h, count(s) AS service_count
RETURN h, service_count
ORDER BY h.hostname

-- ===== CROSS-ENTITY ANALYSIS =====

-- Complete security context for asset
"Security context for asset {asset_hash}"
MATCH (d:DataAsset {asset_hash: $asset_hash})-[:RESIDES_ON]->(h:Host)
OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
OPTIONAL MATCH (v)-[:EXPLOITED_BY]->(t:Threat)
OPTIONAL MATCH (d)<-[:AFFECTS]-(ac:ActionCard)
RETURN d, h, v, t, ac

-- Show attack surface for specific host
"Attack surface for {hostname}"
MATCH (h:Host {hostname: $hostname})
OPTIONAL MATCH (h)-[:RUNS]->(s:Service)
OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
OPTIONAL MATCH (h)<-[:RESIDES_ON]-(d:DataAsset)
RETURN h, s, v, d

-- Find relationships between entities
"Show connections between {entity1} and {entity2}"
MATCH (n1), (n2)
WHERE toString(id(n1)) = $entity1 AND toString(id(n2)) = $entity2
MATCH path = shortestPath((n1)-[*..5]-(n2))
RETURN path

-- ===== COMPLIANCE AND RISK ANALYSIS =====

-- Show unprotected crown jewels (no active ActionCards)
"Show unprotected crown jewels"
MATCH (d:DataAsset {crown_jewel: true})
WHERE NOT EXISTS {
    MATCH (d)<-[:AFFECTS]-(ac:ActionCard)
    WHERE ac.status IN ['pending', 'approved', 'executing']
}
MATCH (d)-[:RESIDES_ON]->(h:Host)
RETURN d, h

-- Find high-risk scenarios (crown jewels + vulnerabilities + threats)
"Show high risk scenarios"
MATCH (d:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(h:Host)
MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)-[:EXPLOITED_BY]->(t:Threat)
WHERE v.cvss >= 7.0
RETURN d, h, v, t

-- Show assets requiring scanning
"Show unscanned assets"
MATCH (d:DataAsset)
WHERE d.scan_status <> 'scanned'
MATCH (d)-[:RESIDES_ON]->(h:Host)
RETURN d, h

-- ===== ANALYST WORKLOAD ANALYSIS =====

-- Show analyst assignment distribution
"Show analyst workload"
MATCH (an:Analyst)<-[:ASSIGNED_TO]-(ac:ActionCard)
WITH an, count(ac) AS assigned_count, 
     collect(DISTINCT ac.status) AS statuses
RETURN an, assigned_count, statuses
ORDER BY assigned_count DESC

-- Find overloaded analysts
"Show overloaded analysts"
MATCH (an:Analyst)<-[:ASSIGNED_TO]-(ac:ActionCard)
WITH an, count(ac) AS workload
WHERE workload >= 10
MATCH (an)<-[:ASSIGNED_TO]-(ac:ActionCard)
RETURN an, ac
ORDER BY workload DESC

-- ===== TEMPORAL ANALYSIS =====

-- Show recent activity (last 7 days)
"Show recent activity"
MATCH (n)
WHERE n.last_updated > datetime() - duration('P7D')
RETURN n
ORDER BY n.last_updated DESC

-- Find stale data (not updated in 30 days)
"Show stale data"
MATCH (n)
WHERE n.last_updated < datetime() - duration('P30D')
  AND NOT 'SchemaVersion' IN labels(n)
RETURN n
ORDER BY n.last_updated ASC

-- ===== NETWORK EXPLORATION PATTERNS =====

-- Explore neighborhood around specific node
"Explore around {node_id}"
MATCH (center)
WHERE toString(id(center)) = $node_id
MATCH (center)-[r]-(neighbor)
RETURN center, r, neighbor

-- Show two-hop relationships
"Two hop from {node_id}"
MATCH (center)
WHERE toString(id(center)) = $node_id  
MATCH (center)-[r1]-(hop1)-[r2]-(hop2)
RETURN center, r1, hop1, r2, hop2
LIMIT 20

-- Find shortest path between any two nodes
"Path between nodes {start_id} and {end_id}"
MATCH (start), (end)
WHERE toString(id(start)) = $start_id AND toString(id(end)) = $end_id
MATCH path = shortestPath((start)-[*..6]-(end))
RETURN path