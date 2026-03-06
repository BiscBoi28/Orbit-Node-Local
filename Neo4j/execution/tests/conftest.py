"""
Pytest fixtures for ORBIT.CyberGraph-Node test suite.

Provides:
  - neo4j_driver: session-scoped driver connected via .env
  - clean_graph:  function-scoped fixture that wipes all data nodes
                  (keeps SchemaVersion) and re-applies schema before each test
"""

import os
import sys
import pytest

# ── Path setup so all execution modules are importable ───────────────────
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "execution"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "execution", "ingestion"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "execution", "lifecycle"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "execution", "delta"))

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from neo4j import GraphDatabase


@pytest.fixture(scope="session")
def neo4j_driver():
    """Session-scoped Neo4j driver.  Closed after all tests complete."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    yield driver
    driver.close()


@pytest.fixture()
def clean_graph(neo4j_driver):
    """Wipe all data nodes (keep SchemaVersion), re-apply schema.

    Yields the driver for convenience so tests can do:
        def test_foo(clean_graph):
            driver = clean_graph
    """
    with neo4j_driver.session() as session:
        # Delete everything EXCEPT SchemaVersion
        session.run("MATCH (n) WHERE NOT n:SchemaVersion DETACH DELETE n")

    # Re-apply schema (idempotent — IF NOT EXISTS on every statement)
    from schema.apply_schema_fn import apply_schema
    apply_schema(neo4j_driver)

    yield neo4j_driver
