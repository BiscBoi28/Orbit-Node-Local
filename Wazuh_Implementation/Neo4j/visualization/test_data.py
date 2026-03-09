#!/usr/bin/env python3
"""Quick test script to verify sample data."""

import sys
import os
sys.path.insert(0, "../neo4j-local")

from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv("../neo4j-local/.env")

def test_sample_data():
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "orbit_secure_pass"))
    
    with driver.session() as session:
        # Test basic counts
        result = session.run("MATCH (n) RETURN labels(n)[0] as type, count(*) as count ORDER BY count DESC")
        print("=== Database Overview ===")
        for record in result:
            print(f"{record['type']}: {record['count']} nodes")
        
        # Test crown jewel assets
        result = session.run("MATCH (d:DataAsset {crown_jewel: true}) RETURN count(*) as crown_jewels")
        crown_count = result.single()["crown_jewels"]
        print(f"\nCrown Jewel Assets: {crown_count}")
        
        # Test vulnerability-threat relationships
        result = session.run("MATCH (v:Vulnerability)<-[:EXPLOITS]-(t:Threat) RETURN count(*) as threat_vulns")
        threat_vulns = result.single()["threat_vulns"]
        print(f"Threat-Vulnerability relationships: {threat_vulns}")
        
    driver.close()
    print("\n✅ Sample data verification completed!")

if __name__ == "__main__":
    test_sample_data()