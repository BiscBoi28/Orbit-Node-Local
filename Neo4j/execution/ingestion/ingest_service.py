"""
Ingestion template — Service
==============================
Composite key: service_id = f"{host_id}::{port}::{proto}"
Never accept service_id from payload — always derive it.
MERGE on service_id.  MATCH Host by host_id.  MERGE (h)-[:RUNS]->(s).
"""

import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from exceptions import OrphanEntityError

from neo4j import Driver

logger = logging.getLogger(__name__)

INGEST_CYPHER = """
MERGE (s:Service {service_id: $service_id})
SET s.name         = $name,
    s.port         = $port,
    s.proto        = $proto,
    s.source       = $source,
    s.last_updated = datetime()
WITH s
MATCH (h:Host {host_id: $host_id})
MERGE (h)-[r:RUNS]->(s)
ON CREATE SET r.installed_ts = datetime()
SET r.last_updated = datetime()
RETURN s.service_id AS service_id
"""

HOST_EXISTS_CHECK = """
MATCH (h:Host {host_id: $host_id}) RETURN h.host_id AS hid
"""


def ingest_service(driver: Driver, payload: dict) -> str:
    """Ingest a single Service node.  Returns the derived service_id."""

    host_id = payload.get("host_id")
    if not host_id:
        raise ValueError("host_id is required")

    port = payload.get("port")
    proto = payload.get("proto", "tcp")
    if port is None:
        raise ValueError("port is required")

    # Composite key — always derived, never from payload
    service_id = f"{host_id}::{port}::{proto}"

    with driver.session() as session:
        # Check host exists first
        check = session.run(HOST_EXISTS_CHECK, {"host_id": host_id})
        if check.single() is None:
            raise OrphanEntityError(
                f"Host {host_id} not found — ingest host first"
            )

        params = {
            "service_id": service_id,
            "host_id":    host_id,
            "name":       payload.get("name", ""),
            "port":       port,
            "proto":      proto,
            "source":     payload.get("source", "unknown"),
        }

        result = session.run(INGEST_CYPHER, params)
        record = result.single()
        logger.info(
            "Ingested service",
            extra={"service_id": service_id, "action": "merge"},
        )
        return record["service_id"]
