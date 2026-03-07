"""
query_graph.py — Run canned queries against the Neo4j graph.

Directive: directives/neo4j_graph_management.md

Usage:
    python execution/query_graph.py crown-jewels
    python execution/query_graph.py assets-by-technology --tech "PostgreSQL"
    python execution/query_graph.py high-sensitivity --threshold 0.7
"""

import os
import json
import argparse

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

QUERIES = {
    "crown-jewels": """
        MATCH (a:Asset)
        WHERE a.crown_jewel = true
        RETURN a.asset_id AS asset_id,
               a.current_sensitivity_score AS sensitivity,
               a.asset_importance_score AS importance
        ORDER BY a.asset_importance_score DESC
    """,
    "assets-by-technology": """
        MATCH (a:Asset)-[:RUNS]->(t:Technology {name: $tech})
        RETURN a.asset_id AS asset_id,
               a.hostname AS hostname,
               t.name AS technology
    """,
    "high-sensitivity": """
        MATCH (a:Asset)
        WHERE a.current_sensitivity_score >= $threshold
        RETURN a.asset_id AS asset_id,
               a.current_sensitivity_score AS sensitivity,
               a.asset_importance_score AS importance,
               a.crown_jewel AS crown_jewel
        ORDER BY a.current_sensitivity_score DESC
    """,
}


def run_query(query_name: str, params: dict) -> list:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    cypher = QUERIES[query_name]

    with driver.session() as session:
        result = session.run(cypher, **params)
        records = [dict(r) for r in result]

    driver.close()
    return records


def main():
    parser = argparse.ArgumentParser(description="Query the ORBIT Neo4j graph")
    parser.add_argument("query", choices=QUERIES.keys())
    parser.add_argument("--tech", default=None, help="Technology name for assets-by-technology")
    parser.add_argument("--threshold", type=float, default=0.7, help="Sensitivity threshold")
    args = parser.parse_args()

    params = {}
    if args.query == "assets-by-technology":
        params["tech"] = args.tech
    elif args.query == "high-sensitivity":
        params["threshold"] = args.threshold

    records = run_query(args.query, params)
    print(json.dumps(records, indent=2, default=str))


if __name__ == "__main__":
    main()
