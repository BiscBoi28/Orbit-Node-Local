"""
Ingestion template — Host
==========================
MERGE on host_id.  ON CREATE sets enrollment_ts and created_by.
ON MATCH updates hostname.  Always sets ip, os, agent_version,
last_seen, last_updated.
"""

import logging
from neo4j import Driver

logger = logging.getLogger(__name__)

INGEST_CYPHER = """
MERGE (h:Host {host_id: $host_id})
ON CREATE SET h.enrollment_ts = datetime(),
              h.created_by    = $source
ON MATCH  SET h.hostname      = $hostname
SET h.hostname      = $hostname,
    h.ip            = $ip,
    h.os            = $os,
    h.agent_version = $agent_version,
    h.source        = $source,
    h.last_seen     = datetime(),
    h.last_updated  = datetime()
RETURN h.host_id AS host_id
"""


def ingest_host(driver: Driver, payload: dict) -> str:
    """Ingest a single Host node.  Returns the host_id."""

    host_id = payload.get("host_id")
    if not host_id:
        raise ValueError("host_id is required")

    params = {
        "host_id":       host_id,
        "hostname":      payload.get("hostname", ""),
        "ip":            payload.get("ip", ""),
        "os":            payload.get("os", ""),
        "agent_version": payload.get("agent_version", ""),
        "source":        payload.get("source", "unknown"),
    }

    with driver.session() as session:
        result = session.run(INGEST_CYPHER, params)
        record = result.single()
        logger.info("Ingested host", extra={"host_id": host_id, "action": "merge"})
        return record["host_id"]
