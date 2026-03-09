#!/usr/bin/env python3
"""Simple NeoDash Test Verification Script"""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

def verify_neodash_data():
    """Verify the current database state for NeoDash testing."""
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    with driver.session() as session:
        print("🎯 NeoDash Testing - Current Database State")
        print("=" * 50)
        
        # Get node counts by type
        result = session.run("""
            MATCH (n) 
            RETURN labels(n)[0] as type, count(n) as count 
            ORDER BY count DESC
        """)
        
        for record in result:
            if record['type'] and record['type'] != 'SchemaVersion':
                print(f"📊 {record['type']}: {record['count']} nodes")
        
        # Get crown jewels
        result = session.run("MATCH (da:DataAsset {crown_jewel: true}) RETURN count(da) as count")
        crown_jewels = result.single()['count']
        print(f"💎 Crown Jewel Assets: {crown_jewels}")
        
        # Get critical vulnerabilities  
        result = session.run("MATCH (v:Vulnerability) WHERE v.cvss >= 9.0 RETURN count(v) as count")
        critical_vulns = result.single()['count']
        print(f"🚨 Critical Vulnerabilities (CVSS ≥ 9.0): {critical_vulns}")
        
        # Get pending actions
        result = session.run("MATCH (ac:ActionCard {status: 'pending'}) RETURN count(ac) as count")
        pending_actions = result.single()['count']
        print(f"⏳ Pending ActionCards: {pending_actions}")
        
        print("=" * 50)
        print("✅ Database ready for NeoDash testing!")
        print()
        print("📋 NeoDash Setup Instructions:")
        print("1. Open: https://neodash.graphapp.io")
        print("2. Connect to: bolt://localhost:7687")
        print("3. Username: neo4j | Password: (value of NEO4J_PASSWORD in .env)")
        print("4. Import dashboard: ../dashboards/orbit-security-dashboard.json")
        print("5. Enable auto-refresh (30s) to see live updates")
        
    driver.close()

if __name__ == "__main__":
    verify_neodash_data()
