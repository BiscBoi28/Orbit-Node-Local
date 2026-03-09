#!/usr/bin/env python3
"""
NeoDash Testing Data Generator
=============================
Generate realistic stub data with noise for comprehensive NeoDash dashboard testing.
Creates dynamic cybersecurity scenarios to test visualization refresh and interactivity.
"""

import random
import json
from datetime import datetime, timedelta, timezone
from neo4j import GraphDatabase

class NeoDashTestGenerator:
    """Generate realistic cybersecurity test data for NeoDash visualization testing."""
    
    def __init__(self):
        self.driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "orbit_secure_pass"))
        
        # Test data templates
        self.host_types = ["web-server", "database", "workstation", "proxy", "firewall", "switch", "router"]
        self.os_types = ["Ubuntu 20.04", "Windows Server 2019", "CentOS 8", "Red Hat 8", "Windows 10"]
        self.vulnerability_types = ["SQL Injection", "XSS", "Buffer Overflow", "Privilege Escalation", "RCE"]
        self.pii_types = ["US_SSN", "CREDIT_CARD", "EMAIL", "PHONE", "US_BANK_NUMBER", "IBAN_CODE"]
        self.threat_names = ["APT29", "Lazarus", "FIN7", "Carbanak", "Emotet", "Ryuk", "Trickbot"]
        
    def cleanup_test_data(self):
        """Remove existing test data (keep schema)."""
        print("🧹 Cleaning existing test data...")
        
        with self.driver.session() as session:
            session.run("""
                MATCH (n) 
                WHERE NOT 'SchemaVersion' IN labels(n)
                DETACH DELETE n
            """)
        print("✅ Cleanup completed")

    def generate_comprehensive_test_data(self, scale="medium"):
        """Generate comprehensive test data with realistic relationships."""
        
        scales = {
            "small": {"hosts": 8, "vulns": 15, "assets": 20, "threats": 8, "cards": 12},
            "medium": {"hosts": 15, "vulns": 30, "assets": 40, "threats": 12, "cards": 25},
            "large": {"hosts": 30, "vulns": 60, "assets": 80, "threats": 20, "cards": 45}
        }
        
        config = scales.get(scale, scales["medium"])
        print(f"🚀 Generating {scale} scale test data...")
        
        with self.driver.session() as session:
            # 1. Generate Hosts with variety
            print("📊 Creating hosts...")
            hosts = []
            for i in range(config["hosts"]):
                host_data = {
                    "host_id": f"HOST-{i+1:03d}",
                    "hostname": f"{random.choice(self.host_types)}-{i+1:02d}",
                    "ip": f"192.168.{random.randint(1,10)}.{random.randint(10,254)}",
                    "os": random.choice(self.os_types),
                    "agent_version": f"5.{random.randint(0,3)}.{random.randint(0,9)}",
                    "source": random.choice(["wazuh", "manual", "scan"]),
                    "last_seen": datetime.now(timezone.utc),
                    "criticality": random.choice(["low", "medium", "high", "critical"])
                }
                
                session.run("""
                    MERGE (h:Host {host_id: $host_id})
                    SET h.hostname = $hostname,
                        h.ip = $ip,
                        h.os = $os,
                        h.agent_version = $agent_version,
                        h.source = $source,
                        h.last_seen = $last_seen,
                        h.criticality = $criticality,
                        h.last_updated = datetime()
                """, host_data)
                hosts.append(host_data)
            
            # 2. Generate Vulnerabilities with CVSS scores
            print("🔍 Creating vulnerabilities...")
            vulns = []
            for i in range(config["vulns"]):
                vuln_data = {
                    "cve_id": f"CVE-2024-{random.randint(1000,9999)}",
                    "title": f"{random.choice(self.vulnerability_types)} in {random.choice(['Apache', 'IIS', 'MySQL', 'Oracle', 'PHP'])}",
                    "cvss": round(random.uniform(2.0, 9.9), 1),
                    "severity": random.choice(["low", "medium", "high", "critical"]),
                    "description": f"Critical {random.choice(self.vulnerability_types)} vulnerability",
                    "source": "NVD",
                    "discovered": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 365))
                }
                
                session.run("""
                    MERGE (v:Vulnerability {cve_id: $cve_id})
                    SET v.title = $title,
                        v.cvss = $cvss,
                        v.severity = $severity,
                        v.description = $description,
                        v.source = $source,
                        v.discovered = $discovered,
                        v.last_updated = datetime()
                """, vuln_data)
                vulns.append(vuln_data)
                
                # Link vulnerabilities to hosts (realistic distribution)
                target_hosts = random.sample(hosts, random.randint(1, min(4, len(hosts))))
                for host in target_hosts:
                    session.run("""
                        MATCH (h:Host {host_id: $host_id})
                        MATCH (v:Vulnerability {cve_id: $cve_id})
                        MERGE (h)-[r:HAS_VULNERABILITY]->(v)
                        SET r.detected = datetime(),
                            r.status = $status
                    """, {
                        "host_id": host["host_id"], 
                        "cve_id": vuln_data["cve_id"],
                        "status": random.choice(["open", "patched", "mitigated"])
                    })
            
            # 3. Generate Data Assets with PII and crown jewels
            print("💎 Creating data assets...")
            crown_jewel_count = 0
            for i in range(config["assets"]):
                sensitivity = random.uniform(0.1, 1.0)
                is_crown_jewel = sensitivity > 0.75 and crown_jewel_count < 8
                if is_crown_jewel:
                    crown_jewel_count += 1
                    
                asset_data = {
                    "asset_hash": f"ASSET-{hash(f'asset-{i}') % 10000:04d}",
                    "name": f"{'Database' if i % 3 == 0 else 'File Share' if i % 3 == 1 else 'Application'}-{i+1:02d}",
                    "type": random.choice(["database", "file_share", "application", "backup"]),
                    "sensitivity_score": round(sensitivity, 2),
                    "crown_jewel": is_crown_jewel,
                    "pii_types": random.sample(self.pii_types, random.randint(1, 3)),
                    "size_mb": random.randint(100, 50000),
                    "owner": f"team-{random.randint(1,5)}",
                    "created": datetime.now(timezone.utc) - timedelta(days=random.randint(30, 730))
                }
                
                session.run("""
                    MERGE (da:DataAsset {asset_hash: $asset_hash})
                    SET da.name = $name,
                        da.type = $type,
                        da.sensitivity_score = $sensitivity_score,
                        da.crown_jewel = $crown_jewel,
                        da.pii_types = $pii_types,
                        da.size_mb = $size_mb,
                        da.owner = $owner,
                        da.created = $created,
                        da.last_updated = datetime()
                """, asset_data)
                
                # Link assets to hosts
                host = random.choice(hosts)
                session.run("""
                    MATCH (h:Host {host_id: $host_id})
                    MATCH (da:DataAsset {asset_hash: $asset_hash})
                    MERGE (h)-[r:HOSTS]->(da)
                    SET r.access_level = $access_level
                """, {
                    "host_id": host["host_id"],
                    "asset_hash": asset_data["asset_hash"],
                    "access_level": random.choice(["read", "write", "admin"])
                })
            
            # 4. Generate Threats
            print("⚠️ Creating threats...")
            for i in range(config["threats"]):
                threat_data = {
                    "threat_id": f"THREAT-{i+1:03d}",
                    "name": random.choice(self.threat_names),
                    "type": random.choice(["malware", "apt", "ransomware", "trojan"]),
                    "severity": random.choice(["medium", "high", "critical"]),
                    "active": random.choice([True, False]),
                    "first_seen": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 90)),
                    "iocs": random.randint(5, 25)
                }
                
                session.run("""
                    MERGE (t:Threat {threat_id: $threat_id})
                    SET t.name = $name,
                        t.type = $type,
                        t.severity = $severity,
                        t.active = $active,
                        t.first_seen = $first_seen,
                        t.iocs = $iocs,
                        t.last_updated = datetime()
                """, threat_data)
            
            # 5. Generate ActionCards for workflow visualization  
            print("🎯 Creating action cards...")
            statuses = ["pending", "assigned", "approved", "executing", "completed", "rejected"]
            for i in range(config["cards"]):
                card_data = {
                    "action_id": f"AC-{i+1:04d}",
                    "title": f"Investigate {random.choice(['CVE', 'IOC', 'Alert'])} #{random.randint(1000,9999)}",
                    "description": f"Security response for {random.choice(self.vulnerability_types)} detected",
                    "status": random.choice(statuses),
                    "priority": random.choice(["low", "medium", "high", "critical"]),
                    "created": datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 168)),
                    "origin": random.choice(["wazuh", "manual", "core", "automated"])
                }
                
                session.run("""
                    MERGE (ac:ActionCard {action_id: $action_id})
                    SET ac.title = $title,
                        ac.description = $description,
                        ac.status = $status,
                        ac.priority = $priority,
                        ac.created = $created,
                        ac.origin = $origin,
                        ac.last_updated = datetime()
                """, card_data)
        
        print(f"✅ Generated comprehensive test dataset:")
        print(f"   📊 {config['hosts']} Hosts")  
        print(f"   🔍 {config['vulns']} Vulnerabilities")
        print(f"   💎 {config['assets']} Data Assets ({crown_jewel_count} crown jewels)")
        print(f"   ⚠️  {config['threats']} Threats") 
        print(f"   🎯 {config['cards']} Action Cards")

    def add_realistic_noise(self):
        """Add dynamic changes to simulate real-time environment."""
        print("🔄 Adding realistic noise and changes...")
        
        with self.driver.session() as session:
            # Simulate new vulnerability discovery
            session.run("""
                MERGE (v:Vulnerability {cve_id: 'CVE-2024-ZERO-DAY'})
                SET v.title = 'Zero-Day Vulnerability in Web Framework',
                    v.cvss = 9.8,
                    v.severity = 'critical',
                    v.description = 'Critical RCE vulnerability discovered',  
                    v.source = 'Security Research',
                    v.discovered = datetime(),
                    v.last_updated = datetime()
            """)
            
            # Update some ActionCard statuses
            session.run("""
                MATCH (ac:ActionCard)
                WHERE ac.status = 'pending'
                WITH ac LIMIT 3
                SET ac.status = 'assigned',
                    ac.assigned_to = 'analyst-' + toString(rand() * 3 + 1),
                    ac.last_updated = datetime()
            """)
            
            # Mark some vulnerabilities as patched
            session.run("""
                MATCH (h:Host)-[r:HAS_VULNERABILITY]->(v:Vulnerability)
                WHERE r.status = 'open'
                WITH r LIMIT 5
                SET r.status = 'patched',
                    r.patched_date = datetime()
            """)
            
            # Add new high-sensitivity data asset
            session.run("""
                MERGE (da:DataAsset {asset_hash: 'ASSET-CRITICAL-NEW'})
                SET da.name = 'Customer Payment Database',
                    da.type = 'database',
                    da.sensitivity_score = 0.95,
                    da.crown_jewel = true,
                    da.pii_types = ['CREDIT_CARD', 'US_SSN', 'US_BANK_NUMBER'],
                    da.size_mb = 125000,
                    da.owner = 'finance-team',
                    da.created = datetime(),
                    da.last_updated = datetime()
            """)
            
        print("✅ Added realistic noise: new vulnerabilities, status changes, patching activity")

    def get_dashboard_stats(self):
        """Get current statistics for NeoDash verification."""
        print("📈 Current Database Statistics:")
        
        with self.driver.session() as session:
            # Basic counts
            stats = session.run("""
                MATCH (n) 
                RETURN labels(n)[0] as type, count(n) as count 
                ORDER BY count DESC
            """).data()
            
            for stat in stats:
                if stat['type'] and stat['type'] != 'SchemaVersion':
                    print(f"   {stat['type']}: {stat['count']} nodes")
            
            # Crown jewels
            crown_jewels = session.run("""
                MATCH (da:DataAsset {crown_jewel: true}) 
                RETURN count(da) as count
            """).single()['count']
            print(f"   💎 Crown Jewels: {crown_jewels}")
            
            # Critical vulnerabilities
            critical_vulns = session.run("""
                MATCH (v:Vulnerability) 
                WHERE v.cvss >= 9.0 
                RETURN count(v) as count
            """).single()['count']
            print(f"   🚨 Critical Vulns: {critical_vulns}")
            
            # Pending actions
            pending_actions = session.run("""
                MATCH (ac:ActionCard {status: 'pending'}) 
                RETURN count(ac) as count
            """).single()['count']
            print(f"   ⏳ Pending Actions: {pending_actions}")

    def close(self):
        """Close database connection."""
        if self.driver:
            self.driver.close()

# Test execution
if __name__ == "__main__":
    generator = NeoDashTestGenerator()
    
    try:
        # Clean and generate fresh test data
        generator.cleanup_test_data()
        generator.generate_comprehensive_test_data("medium")
        generator.add_realistic_noise()
        generator.get_dashboard_stats()
        
        print("\n🎉 NeoDash test data generation completed!")
        print("\n📋 Next Steps:")
        print("1. Open NeoDash: https://neodash.graphapp.io")
        print("2. Connect: bolt://localhost:7687 (neo4j/orbit_secure_pass)")
        print("3. Import: src\\Neo4j\\visualization\\dashboards\\orbit-security-dashboard.json")
        print("4. Watch live data refresh every 30 seconds!")
        
    finally:
        generator.close()