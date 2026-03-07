"""
Integration tests for the ORC pipeline — requires Neo4j running.

These tests validate the data-change and core-alert flows end-to-end.
Skipped automatically if Neo4j is unreachable.
"""

import json
import os
import pytest
import sys

# Ensure app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def _neo4j_available() -> bool:
    """Check if Neo4j is reachable."""
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


skip_no_neo4j = pytest.mark.skipif(
    not _neo4j_available(),
    reason="Neo4j not available — skipping integration tests",
)


@skip_no_neo4j
class TestORCPipelineIntegration:
    """Integration tests requiring a live Neo4j instance."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Seed graph, run test, then clean up."""
        from app.graph import get_driver, close_driver, apply_schema, ingest_host

        driver = get_driver()
        apply_schema(driver)

        # Seed a test host
        ingest_host(driver, {
            "host_id": "test-db-01",
            "hostname": "test-db-01",
            "ip": "10.0.0.99",
            "os": "Linux",
            "agent_version": "4.7.0",
            "source": "test",
        })

        yield driver

        # Cleanup
        with driver.session() as session:
            session.run(
                "MATCH (n) WHERE n.host_id = 'test-db-01' "
                "OR n.asset_hash STARTS WITH 'test-db-01::' "
                "DETACH DELETE n"
            )
        close_driver()

    def test_data_change_pipeline(self, setup_teardown):
        """Test the full data-change pipeline via FastAPI test client."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post("/ingest/data-change", json={
            "event_type": "data_change",
            "asset_id": "test-db-01",
            "content_items": [
                "Customer: John Doe, email: john@example.com",
                "Account number: 1234567890123456",
            ],
        })

        assert response.status_code == 200
        data = response.json()
        assert data["asset_id"] == "test-db-01"
        assert "current_sensitivity_score" in data
        assert "crown_jewel" in data
        assert isinstance(data["detected_pii_types"], list)

    def test_health_endpoint(self, setup_teardown):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_host_not_found(self, setup_teardown):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post("/ingest/data-change", json={
            "event_type": "data_change",
            "asset_id": "nonexistent-host",
            "content_items": ["test"],
        })
        assert response.status_code == 404
