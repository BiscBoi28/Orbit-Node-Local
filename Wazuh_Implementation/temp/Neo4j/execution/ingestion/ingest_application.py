"""
Ingestion template — Application
==================================
Composite key: app_id = f"{host_id}::{name}::{version}"
MERGE Application on app_id.  MATCH Host.  MERGE (h)-[:HAS_APP]->(a).
"""

import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from exceptions import OrphanEntityError

from neo4j import Driver

logger = logging.getLogger(__name__)

INGEST_CYPHER = """
MERGE (a:Application {app_id: $app_id})
ON CREATE SET a.first_seen = datetime()
SET a.name              = $name,
    a.version           = $version,
    a.vendor            = $vendor,
    a.installed_version = $version,
    a.source            = $source,
    a.last_updated      = datetime()
WITH a
MATCH (h:Host {host_id: $host_id})
MERGE (h)-[r:HAS_APP]->(a)
ON CREATE SET r.first_seen         = datetime(),
              r.installed_version  = $version
SET r.last_updated = datetime()
RETURN a.app_id AS app_id
"""

HOST_EXISTS_CHECK = """
MATCH (h:Host {host_id: $host_id}) RETURN h.host_id AS hid
"""


def ingest_application(driver: Driver, payload: dict) -> str:
    """Ingest a single Application node.  Returns the derived app_id."""

    host_id = payload.get("host_id")
    if not host_id:
        raise ValueError("host_id is required")

    name = payload.get("name")
    version = payload.get("version", "unknown")
    if not name:
        raise ValueError("name is required")

    # Composite key — always derived
    app_id = f"{host_id}::{name}::{version}"

    with driver.session() as session:
        check = session.run(HOST_EXISTS_CHECK, {"host_id": host_id})
        if check.single() is None:
            raise OrphanEntityError(
                f"Host {host_id} not found — ingest host first"
            )

        params = {
            "app_id":  app_id,
            "host_id": host_id,
            "name":    name,
            "version": version,
            "vendor":  payload.get("vendor", ""),
            "source":  payload.get("source", "unknown"),
        }

        result = session.run(INGEST_CYPHER, params)
        record = result.single()
        logger.info(
            "Ingested application",
            extra={"app_id": app_id, "action": "merge"},
        )
        return record["app_id"]
