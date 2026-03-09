#!/usr/bin/env python3
"""
Sample Data Generator for ORBIT Visualization Testing
=====================================================
Generates realistic test data for the ORBIT cybersecurity graph database
to demonstrate visualization capabilities and test dashboard functionality.

Usage:
    python sample-data-generator.py --scenario basic
    python sample-data-generator.py --scenario enterprise --hosts 100
    python sample-data-generator.py --scenario demo --cleanup
"""

import argparse
import json
import logging
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from dotenv import load_dotenv
from neo4j import GraphDatabase

# Add parent paths for ORBIT ingestion functions
sys.path.insert(0, "../../neo4j-local/execution/ingestion")
sys.path.insert(0, "../../neo4j-local/execution/lifecycle")

# Use direct Neo4j operations for simpler testing
from neo4j import GraphDatabase

load_dotenv("../../neo4j-local/.env")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VisualizationDataGenerator:
    """Generates sample data optimized for visualization testing."""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "orbit_secure_pass")
        )
        
    def cleanup_database(self):
        """Remove all non-schema nodes for fresh testing."""
        logger.info("Cleaning up existing test data...")
        
        cleanup_cypher = """
        MATCH (n) 
        WHERE NOT 'SchemaVersion' IN labels(n)
        DETACH DELETE n
        """
        
        with self.driver.session() as session:
            session.run(cleanup_cypher)
            
        logger.info("Database cleanup completed")
    
    def generate_basic_scenario(self):
        """Generate basic test scenario with core relationships."""
        logger.info("Generating basic visualization scenario...")
        
        with self.driver.session() as session:
            # Generate 10 Hosts
            hosts = []
            for i in range(10):
                host_data = {
                    "host_id": f"HOST-{i+1:03d}",
                    "hostname": f"server-{i+1:02d}",
                    "ip": f"192.168.1.{i+10}",
                    "os": random.choice(["Ubuntu 20.04", "Windows Server 2019", "CentOS 8"]),
                    "agent_version": "5.2.1",
                    "source": random.choice(["wazuh", "manual", "scan"])
                }
                
                session.run("""
                    MERGE (h:Host {host_id: $host_id})
                    SET h.hostname = $hostname,
                        h.ip = $ip,
                        h.os = $os,
                        h.agent_version = $agent_version,
                        h.source = $source,
                        h.last_updated = datetime()
                """, host_data)
                hosts.append(host_data)
            
            # Generate 30 Vulnerabilities
            vulns = []
            vuln_types = ["SQL Injection", "XSS", "Buffer Overflow", "RCE", "Privilege Escalation"]
            for i in range(30):
                vuln_data = {
                    "cve_id": f"CVE-2024-{random.randint(1000,9999)}",
                    "title": f"{random.choice(vuln_types)} in Web Application",
                    "cvss": round(random.uniform(3.0, 9.8), 1),
                    "severity": random.choice(["low", "medium", "high", "critical"]),
                    "description": f"Critical {random.choice(vuln_types)} vulnerability",
                    "source": "NVD"
                }
                
                session.run("""
                    MERGE (v:Vulnerability {cve_id: $cve_id})
                    SET v.title = $title,
                        v.cvss = $cvss,
                        v.severity = $severity,
                        v.description = $description,
                        v.source = $source,
                        v.last_updated = datetime()
                """, vuln_data)
                vulns.append(vuln_data)
                
                # Link to random hosts
                target_hosts = random.sample(hosts, random.randint(1, 3))
                for host in target_hosts:
                    session.run("""
                        MATCH (h:Host {host_id: $host_id})
                        MATCH (v:Vulnerability {cve_id: $cve_id})
                        MERGE (h)-[r:HAS_VULNERABILITY]->(v)
                        SET r.detected = datetime()
                    """, {"host_id": host["host_id"], "cve_id": vuln_data["cve_id"]})
            
            # Generate 40 Data Assets (including crown jewels)
            crown_jewel_count = 0
            pii_types = ["US_SSN", "CREDIT_CARD", "EMAIL", "PHONE", "US_BANK_NUMBER"]
            for i in range(40):
                sensitivity = random.uniform(0.1, 1.0)
                is_crown_jewel = sensitivity > 0.75 and crown_jewel_count < 12
                if is_crown_jewel:
                    crown_jewel_count += 1
                    
                asset_data = {
                    "asset_hash": f"ASSET-{hash(f'asset-{i}') % 10000:04d}",
                    "name": f"Database-{i+1:02d}" if i % 3 == 0 else f"FileShare-{i+1:02d}",
                    "type": random.choice(["database", "file_share", "application"]),
                    "sensitivity_score": round(sensitivity, 2),
                    "crown_jewel": is_crown_jewel,
                    "pii_types": random.sample(pii_types, random.randint(1, 3)),
                    "size_mb": random.randint(100, 50000)
                }
                
                session.run("""
                    MERGE (da:DataAsset {asset_hash: $asset_hash})
                    SET da.name = $name,
                        da.type = $type,
                        da.sensitivity_score = $sensitivity_score,
                        da.crown_jewel = $crown_jewel,
                        da.pii_types = $pii_types,
                        da.size_mb = $size_mb,
                        da.last_updated = datetime()
                """, asset_data)
                
                # Link to hosts
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
            
            # Generate 15 Threats
            threat_names = ["APT29", "Lazarus", "FIN7", "Carbanak", "Emotet"]
            for i in range(15):
                threat_data = {
                    "threat_id": f"THREAT-{i+1:03d}",
                    "name": f"{random.choice(threat_names)}-{i+1}",
                    "type": random.choice(["malware", "apt", "ransomware"]),
                    "severity": random.choice(["medium", "high", "critical"]),
                    "active": random.choice([True, False])
                }
                
                session.run("""
                    MERGE (t:Threat {threat_id: $threat_id})
                    SET t.name = $name,
                        t.type = $type,
                        t.severity = $severity,
                        t.active = $active,
                        t.last_updated = datetime()
                """, threat_data)
            
            # Generate 20 ActionCards
            statuses = ["pending", "assigned", "approved", "executing", "completed"]
            for i in range(20):
                card_data = {
                    "action_id": f"AC-{i+1:04d}",
                    "title": f"Investigate Alert #{i+1:03d}",
                    "description": f"Security response required for detected threat",
                    "status": random.choice(statuses),
                    "priority": random.choice(["low", "medium", "high", "critical"]),
                    "origin": random.choice(["wazuh", "manual", "core"])
                }
                
                session.run("""
                    MERGE (ac:ActionCard {action_id: $action_id})
                    SET ac.title = $title,
                        ac.description = $description,
                        ac.status = $status,
                        ac.priority = $priority,
                        ac.origin = $origin,
                        ac.last_updated = datetime()
                """, card_data)
        
        logger.info("Generated basic scenario: 10 hosts, 30 vulnerabilities, 40 assets, 15 threats, 20 action cards")
    
    def add_realistic_noise(self):
        """Add dynamic changes to simulate real-time environment."""
        logger.info("Adding realistic noise and changes...")
        
        with self.driver.session() as session:
            # Simulate new vulnerability discovery
            session.run("""
                MERGE (v:Vulnerability {cve_id: 'CVE-2024-ZERO-DAY'})
                SET v.title = 'Zero-Day Vulnerability in Web Framework',
                    v.cvss = 9.8,
                    v.severity = 'critical',
                    v.description = 'Critical RCE vulnerability discovered',  
                    v.source = 'Security Research',
                    v.last_updated = datetime()
            """)
            
            # Update some ActionCard statuses
            session.run("""
                MATCH (ac:ActionCard)
                WHERE ac.status = 'pending'
                WITH ac LIMIT 3
                SET ac.status = 'assigned',
                    ac.assigned_to = 'analyst-' + toString(toInteger(rand() * 3) + 1),
                    ac.last_updated = datetime()
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
                    da.last_updated = datetime()
            """)
            
        logger.info("Added realistic noise: new vulnerabilities, status changes, new critical asset")

    def get_current_stats(self):
        """Get current database statistics for NeoDash verification."""
        with self.driver.session() as session:
            stats = session.run("""
                MATCH (n) 
                RETURN labels(n)[0] as type, count(n) as count 
                ORDER BY count DESC
            """).data()
            
            logger.info("Current Database Statistics:")
            for stat in stats:
                if stat['type'] and stat['type'] != 'SchemaVersion':
                    logger.info(f"  {stat['type']}: {stat['count']} nodes")
            
            # Crown jewels count
            crown_jewels = session.run("""
                MATCH (da:DataAsset {crown_jewel: true}) 
                RETURN count(da) as count
            """).single()['count']
            logger.info(f"  Crown Jewels: {crown_jewels}")
            
            # Critical vulnerabilities
            critical_vulns = session.run("""
                MATCH (v:Vulnerability) 
                WHERE v.cvss >= 9.0 
                RETURN count(v) as count
            """).single()['count']
            logger.info(f"  Critical Vulnerabilities: {critical_vulns}")
    
    def generate_enterprise_scenario(self, num_hosts: int = 50):
        """Generate enterprise-scale scenario for performance testing."""
        logger.info(f"Generating enterprise scenario with {num_hosts} hosts...")
        
        # Large-scale infrastructure
        hosts = self._generate_hosts(num_hosts)
        services = self._generate_services(hosts, num_hosts * 3)
        applications = self._generate_applications(hosts, num_hosts * 2)
        
        # Realistic vulnerability distribution
        vulnerabilities = self._generate_vulnerabilities(hosts, num_hosts * 4)
        threats = self._generate_threats(50)
        self._link_threat_vulnerabilities(threats, vulnerabilities)
        
        # Enterprise data assets with realistic PII distribution
        data_assets = self._generate_data_assets(hosts, num_hosts * 5, enterprise=True)
        
        # Complex ActionCard workflows
        action_cards = self._generate_action_cards(hosts + data_assets, num_hosts * 2)
        analysts = self._generate_analysts(12)
        self._simulate_actioncard_workflow(action_cards, analysts, complex=True)
        
        logger.info(f"Generated enterprise scenario: {num_hosts} hosts, {len(vulnerabilities)} vulnerabilities, {len(data_assets)} assets")
    
    def generate_demo_scenario(self):
        """Generate focused demo scenario for presentation purposes."""
        logger.info("Generating demo visualization scenario...")
        
        # Curated demo infrastructure
        demo_hosts = [
            {"host_id": "WEB-PROD-01", "hostname": "web-production", "ip": "10.0.1.10", "os": "Ubuntu 20.04", "role": "web"},
            {"host_id": "DB-PROD-01", "hostname": "database-primary", "ip": "10.0.1.20", "os": "Ubuntu 20.04", "role": "database"}, 
            {"host_id": "APP-PROD-01", "hostname": "app-server", "ip": "10.0.1.30", "os": "CentOS 8", "role": "application"},
            {"host_id": "FILE-PROD-01", "hostname": "file-server", "ip": "10.0.1.40", "os": "Windows Server 2019", "role": "storage"},
            {"host_id": "DMZ-WEB-01", "hostname": "dmz-webserver", "ip": "192.168.1.10", "os": "Ubuntu 18.04", "role": "dmz"}
        ]
        
        for host_data in demo_hosts:
            ingest_host(self.driver, {
                "host_id": host_data["host_id"],
                "hostname": host_data["hostname"], 
                "ip": host_data["ip"],
                "os": host_data["os"],
                "agent_version": "5.2.1",
                "source": "demo"
            })
        
        # Critical vulnerabilities for demo
        demo_vulns = [
            {"cve_id": "CVE-2024-1234", "title": "SQL Injection in Web App", "cvss": 9.8, "host": "WEB-PROD-01"},
            {"cve_id": "CVE-2024-5678", "title": "Remote Code Execution", "cvss": 8.1, "host": "APP-PROD-01"},
            {"cve_id": "CVE-2023-9999", "title": "Privilege Escalation", "cvss": 7.2, "host": "DB-PROD-01"},
            {"cve_id": "CVE-2024-0001", "title": "Directory Traversal", "cvss": 6.5, "host": "FILE-PROD-01"}
        ]
        
        for vuln in demo_vulns:
            ingest_vulnerability(self.driver, {
                "cve_id": vuln["cve_id"],
                "title": vuln["title"],
                "description": f"Critical vulnerability: {vuln['title']}",
                "cvss": vuln["cvss"],
                "host_id": vuln["host"],
                "source": "demo"
            })
        
        # Crown jewel data assets
        crown_jewels = [
            {"hash": "CROWN_CUSTOMER_DB", "location": "customer_database", "sensitivity": 0.95, "host": "DB-PROD-01"},
            {"hash": "CROWN_FINANCIAL_DATA", "location": "financial_records", "sensitivity": 0.89, "host": "FILE-PROD-01"},
            {"hash": "CROWN_PII_STORE", "location": "user_profiles", "sensitivity": 0.92, "host": "APP-PROD-01"}
        ]
        
        for asset in crown_jewels:
            ingest_dataasset(self.driver, {
                "asset_hash": asset["hash"],
                "location_pseudonym": asset["location"],
                "sensitivity_score": asset["sensitivity"],
                "pii_types": ["CREDIT_CARD", "US_SSN", "EMAIL_ADDRESS"],
                "host_id": asset["host"],
                "scan_ts": datetime.now(timezone.utc).isoformat(),
                "source": "demo"
            })
        
        # Active threats targeting demo environment
        demo_threats = [
            {"threat_id": "APT-DEMO-001", "title": "Advanced Persistent Threat Campaign", "severity": "CRITICAL"},
            {"threat_id": "RANSOM-DEMO-001", "title": "Ransomware Attack Vector", "severity": "HIGH"},
            {"threat_id": "INSIDER-DEMO-001", "title": "Insider Threat Activity", "severity": "MEDIUM"}
        ]
        
        for threat in demo_threats:
            ingest_threat(self.driver, {
                "threat_id": threat["threat_id"],
                "title": threat["title"],
                "description": f"Demo threat: {threat['title']}",
                "severity": threat["severity"],
                "source": "demo"
            })
        
        # Critical ActionCards in various states  
        demo_actions = [
            {"action_id": "AC-CRITICAL-001", "type": "patch", "summary": "Emergency SQL Injection Patch", "status": "pending"},
            {"action_id": "AC-HIGH-001", "type": "isolate", "summary": "Isolate Compromised Web Server", "status": "approved"},
            {"action_id": "AC-MEDIUM-001", "type": "monitor", "summary": "Enhanced Monitoring for File Server", "status": "executing"}
        ]
        
        for action in demo_actions:
            ingest_actioncard(self.driver, {
                "action_id": action["action_id"],
                "origin": "core",
                "action_type": action["type"],
                "summary": action["summary"],
                "confidence": 0.85,
                "affected": {"hosts": ["WEB-PROD-01"], "assets": [], "services": []},
                "metadata": {"demo": True, "priority": "high"}
            })
        
        logger.info("Generated focused demo scenario with crown jewels and critical vulnerabilities")
    
    def _generate_hosts(self, count: int) -> List[str]:
        """Generate diverse host inventory."""
        hosts = []
        host_types = ["web", "database", "application", "file", "mail", "dns", "proxy", "backup"]
        os_types = ["Ubuntu 20.04", "CentOS 8", "Windows Server 2019", "RHEL 8", "Ubuntu 18.04"]
        
        for i in range(count):
            host_type = random.choice(host_types)
            host_id = f"{host_type.upper()}-{random.randint(10,99):02d}"
            
            host_data = {
                "host_id": host_id,
                "hostname": f"{host_type}-server-{i+1:02d}",
                "ip": f"10.0.{random.randint(1,10)}.{random.randint(10,200)}",
                "os": random.choice(os_types),
                "agent_version": f"5.{random.randint(0,3)}.{random.randint(0,5)}",
                "source": "sample_generator"
            }
            
            ingest_host(self.driver, host_data)
            hosts.append(host_id)
            
        return hosts
    
    def _generate_services(self, hosts: List[str], count: int) -> List[str]:
        """Generate services running on hosts.""" 
        services = []
        service_types = ["nginx", "apache", "mysql", "postgresql", "redis", "elasticsearch", "mongodb", "ssh", "ftp", "smtp"]
        
        for i in range(count):
            host_id = random.choice(hosts)
            service_name = random.choice(service_types)
            port = random.choice([22, 80, 443, 3306, 5432, 6379, 9200, 27017, 21, 25])
            
            service_data = {
                "service_id": f"SVC-{service_name}-{port}-{i}",
                "name": service_name,
                "port": port,
                "protocol": "TCP",
                "state": random.choice(["running", "stopped", "starting"]),
                "host_id": host_id,
                "source": "sample_generator"
            }
            
            ingest_service(self.driver, service_data)
            services.append(service_data["service_id"])
            
        return services
    
    def _generate_applications(self, hosts: List[str], count: int) -> List[str]:
        """Generate applications installed on hosts."""
        applications = []
        app_types = ["wordpress", "drupal", "joomla", "jenkins", "gitlab", "jira", "confluence", "nextcloud"]
        
        for i in range(count):
            host_id = random.choice(hosts)
            app_name = random.choice(app_types)
            
            app_data = {
                "app_id": f"APP-{app_name}-{i}",
                "name": app_name,
                "version": f"{random.randint(1,5)}.{random.randint(0,10)}.{random.randint(0,20)}",
                "install_path": f"/opt/{app_name}",
                "host_id": host_id,
                "source": "sample_generator"
            }
            
            ingest_application(self.driver, app_data)
            applications.append(app_data["app_id"])
            
        return applications
    
    def _generate_vulnerabilities(self, hosts: List[str], count: int) -> List[str]:
        """Generate realistic vulnerability distribution."""
        vulnerabilities = []
        
        # CVE patterns and realistic CVSS distribution
        cve_patterns = [
            "SQL Injection", "Cross-Site Scripting", "Remote Code Execution", 
            "Buffer Overflow", "Privilege Escalation", "Directory Traversal",
            "Authentication Bypass", "Information Disclosure", "Denial of Service"
        ]
        
        for i in range(count):
            cve_id = f"CVE-2024-{random.randint(1000,9999)}"
            vuln_type = random.choice(cve_patterns)
            
            # Realistic CVSS distribution (more medium than critical)
            cvss_weights = [(3.0, 6.0, 0.2), (6.0, 7.5, 0.5), (7.5, 9.0, 0.25), (9.0, 10.0, 0.05)]
            min_score, max_score, _ = random.choices(cvss_weights, weights=[w[2] for w in cvss_weights])[0]
            cvss = round(random.uniform(min_score, max_score), 1)
            
            vuln_data = {
                "cve_id": cve_id,
                "title": f"{vuln_type} Vulnerability",
                "description": f"Sample {vuln_type.lower()} vulnerability for visualization testing",
                "cvss": cvss,
                "published_date": (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
                "host_id": random.choice(hosts),
                "source": "sample_generator"
            }
            
            ingest_vulnerability(self.driver, vuln_data)
            vulnerabilities.append(cve_id)
            
        return vulnerabilities
    
    def _generate_threats(self, count: int) -> List[str]:
        """Generate threat intelligence data."""
        threats = []
        threat_types = [
            "Advanced Persistent Threat", "Ransomware Campaign", "Phishing Attack",
            "Malware Distribution", "Botnet Activity", "Data Exfiltration",
            "Insider Threat", "Supply Chain Attack", "Zero-Day Exploit"
        ]
        
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        
        for i in range(count):
            threat_type = random.choice(threat_types)
            threat_id = f"THR-{threat_type.replace(' ', '').upper()}-{random.randint(100,999)}"
            
            threat_data = {
                "threat_id": threat_id,
                "title": f"{threat_type} - Campaign {random.randint(1000,9999)}",
                "description": f"Sample threat intelligence: {threat_type}",
                "severity": random.choice(severities),
                "first_seen": (datetime.now() - timedelta(days=random.randint(1, 90))).isoformat(),
                "source": "sample_generator"
            }
            
            ingest_threat(self.driver, threat_data)
            threats.append(threat_id)
            
        return threats
    
    def _link_threat_vulnerabilities(self, threats: List[str], vulnerabilities: List[str]):
        """Create EXPLOITED_BY relationships between threats and vulnerabilities."""
        # Link ~30% of vulnerabilities to threats
        num_links = int(len(vulnerabilities) * 0.3)
        
        link_cypher = """
        MATCH (v:Vulnerability {cve_id: $cve_id}), (t:Threat {threat_id: $threat_id})
        MERGE (v)-[r:EXPLOITED_BY]->(t)
        ON CREATE SET r.first_observed = datetime(),
                      r.confidence = $confidence
        """
        
        with self.driver.session() as session:
            for _ in range(num_links):
                session.run(link_cypher, {
                    "cve_id": random.choice(vulnerabilities),
                    "threat_id": random.choice(threats), 
                    "confidence": round(random.uniform(0.6, 0.95), 2)
                })
    
    def _generate_data_assets(self, hosts: List[str], count: int, enterprise: bool = False) -> List[str]:
        """Generate data assets with realistic PII and sensitivity distribution."""
        assets = []
        
        # Asset location patterns
        locations = [
            "customer_database", "user_profiles", "financial_records", "employee_data",
            "application_logs", "backup_files", "configuration_data", "temporary_files",
            "cached_data", "analytics_warehouse", "audit_logs", "system_metadata"
        ]
        
        # PII type combinations
        pii_combinations = [
            [],  # No PII
            ["EMAIL_ADDRESS"],
            ["PHONE_NUMBER"],
            ["EMAIL_ADDRESS", "PHONE_NUMBER"],
            ["CREDIT_CARD", "PERSON"],
            ["US_SSN", "PERSON", "EMAIL_ADDRESS"],
            ["US_BANK_NUMBER", "CREDIT_CARD", "PERSON"],
            ["IBAN_CODE", "PERSON", "PHONE_NUMBER"]
        ]
        
        for i in range(count):
            asset_hash = f"ASSET-{uuid.uuid4().hex[:8].upper()}"
            location = random.choice(locations)
            pii_types = random.choice(pii_combinations)
            
            # Sensitivity scoring based on PII content
            base_sensitivity = random.uniform(0.1, 0.4)
            if pii_types:
                pii_bonus = len(pii_types) * 0.15
                if any(pii in ["US_SSN", "CREDIT_CARD", "US_BANK_NUMBER"] for pii in pii_types):
                    pii_bonus += 0.2
                sensitivity = min(0.98, base_sensitivity + pii_bonus)
            else:
                sensitivity = base_sensitivity
                
            asset_data = {
                "asset_hash": asset_hash,
                "location_pseudonym": f"{location}_{random.randint(1000,9999)}",
                "sensitivity_score": round(sensitivity, 2),
                "pii_types": pii_types,
                "host_id": random.choice(hosts),
                "scan_ts": (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),
                "source": "sample_generator"
            }
            
            ingest_dataasset(self.driver, asset_data)
            assets.append(asset_hash)
            
        return assets
    
    def _generate_action_cards(self, affected_entities: List[str], count: int) -> List[str]:
        """Generate ActionCards for workflow visualization."""
        action_cards = []
        action_types = ["patch", "isolate", "monitor", "scan", "remediate", "investigate"]
        
        for i in range(count):
            action_id = f"AC-{random.randint(10000,99999)}"
            action_type = random.choice(action_types)
            
            # Select affected entities (mix of hosts and assets)
            affected_count = random.randint(1, 3)
            affected_hosts = [e for e in affected_entities[:len(affected_entities)//2]][:affected_count]
            
            action_data = {
                "action_id": action_id,
                "origin": random.choice(["core", "wazuh", "manual", "automated"]),
                "action_type": action_type,
                "summary": f"{action_type.title()} action for security remediation",
                "confidence": round(random.uniform(0.6, 0.95), 2),
                "affected": {"hosts": affected_hosts, "assets": [], "services": []},
                "metadata": {"priority": random.choice(["low", "medium", "high", "critical"])}
            }
            
            ingest_actioncard(self.driver, action_data)
            action_cards.append(action_id)
            
        return action_cards
    
    def _generate_analysts(self, count: int) -> List[str]:
        """Generate analyst accounts for workflow simulation."""
        analysts = []
        analyst_names = ["alice", "bob", "charlie", "diana", "eve", "frank", "grace", "henry"]
        
        for i in range(count):
            analyst_id = f"ANALYST-{analyst_names[i % len(analyst_names)].upper()}-{i+1:02d}"
            
            # Create analyst through ActionCard assignment (will auto-create)
            analysts.append(analyst_id)
            
        return analysts
    
    def _simulate_actioncard_workflow(self, action_cards: List[str], analysts: List[str], complex: bool = False):
        """Simulate realistic ActionCard workflow progression."""
        # Distribute ActionCards across different lifecycle states
        for i, action_id in enumerate(action_cards):
            analyst_id = random.choice(analysts)
            
            try:
                # Assign to analyst
                assign_to_analyst(self.driver, action_id, analyst_id, 
                                comment="Assigned for security review")
                
                # Simulate workflow progression 
                if i % 4 == 0:  # 25% approved and executing
                    approve_action(self.driver, action_id, analyst_id, 
                                 comment="Approved for execution")
                    begin_execution(self.driver, action_id)
                    
                    if i % 8 == 0:  # 12.5% completed
                        exec_id = f"EXEC-{action_id}-001"
                        record_execution_result(self.driver, action_id, exec_id, 
                                              "success", "Action completed successfully")
                        
            except Exception as e:
                logger.warning(f"Workflow simulation failed for {action_id}: {e}")
                continue

def main():
    """Main entry point for sample data generation."""
    parser = argparse.ArgumentParser(description="Generate sample data for ORBIT visualization testing")
    parser.add_argument("--scenario", choices=["basic", "enterprise", "demo"], 
                       default="basic", help="Data generation scenario")
    parser.add_argument("--hosts", type=int, default=50, 
                       help="Number of hosts for enterprise scenario")
    parser.add_argument("--cleanup", action="store_true", 
                       help="Clean up existing data before generation")
    
    args = parser.parse_args()
    
    generator = VisualizationDataGenerator()
    
    try:
        if args.cleanup:
            generator.cleanup_database()
            
        if args.scenario == "basic":
            generator.generate_basic_scenario()
            generator.add_realistic_noise()
        elif args.scenario in ["enterprise", "demo"]:  # Use basic for now
            logger.info(f"Using basic scenario (simplified for NeoDash testing)")
            generator.generate_basic_scenario()
            generator.add_realistic_noise()
            
        generator.get_current_stats()
        logger.info(f"✅ Sample data generation completed: {args.scenario} scenario")
        logger.info("🎯 Ready for NeoDash testing!")
        logger.info("📋 Next steps:")
        logger.info("  1. Open NeoDash: https://neodash.graphapp.io")
        logger.info("  2. Connect: bolt://localhost:7687 (neo4j/orbit_secure_pass)")
        logger.info("  3. Import: ../dashboards/orbit-security-dashboard.json")
        
    except Exception as e:
        logger.error(f"Data generation failed: {e}")
        sys.exit(1)
    finally:
        generator.driver.close()

if __name__ == "__main__":
    main()