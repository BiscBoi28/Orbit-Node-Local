"""
Ingestion template — Threat
==============================
MERGE Threat on threat_id.  Sets all fields + last_updated.
If cve_id is provided, links (v:Vulnerability)-[:EXPLOITED_BY]->(t:Threat).
"""

import logging
from neo4j import Driver

logger = logging.getLogger(__name__)

INGEST_CYPHER = """
MERGE (t:Threat {threat_id: $threat_id})
ON CREATE SET t.created_ts = datetime()
SET t.title        = $title,
    t.severity     = $severity,
    t.confidence   = $confidence,
    t.published    = $published,
    t.source       = $source,
    t.last_updated = datetime()
RETURN t.threat_id AS threat_id
"""

LINK_CVE_CYPHER = """
MATCH (t:Threat {threat_id: $threat_id})
MATCH (v:Vulnerability {cve_id: $cve_id})
MERGE (v)-[r:EXPLOITED_BY]->(t)
ON CREATE SET r.observed_ts  = datetime(),
              r.last_updated = datetime()
SET r.last_updated = datetime()
RETURN t.threat_id AS threat_id
"""


def ingest_threat(driver: Driver, payload: dict) -> str:
    """Ingest a single Threat node.  Returns the threat_id.

    If payload contains 'cve_id', a :EXPLOITED_BY relationship is also
    created from the matching Vulnerability node.  If the Vulnerability
    does not exist the Threat is still created — the link is best-effort.
    """

    threat_id = payload.get("threat_id")
    if not threat_id:
        raise ValueError("threat_id is required")

    params = {
        "threat_id":  threat_id,
        "title":      payload.get("title", ""),
        "severity":   payload.get("severity", ""),
        "confidence": payload.get("confidence", 0.0),
        "published":  payload.get("published", ""),
        "source":     payload.get("source", "unknown"),
    }

    with driver.session() as session:
        result = session.run(INGEST_CYPHER, params)
        record = result.single()
        logger.info(
            "Ingested threat",
            extra={"threat_id": threat_id, "action": "merge"},
        )

        # Optional CVE link
        cve_id = payload.get("cve_id")
        if cve_id:
            link_result = session.run(
                LINK_CVE_CYPHER,
                {"threat_id": threat_id, "cve_id": cve_id},
            )
            if link_result.single():
                logger.info(
                    "Linked threat to vulnerability",
                    extra={"threat_id": threat_id, "cve_id": cve_id},
                )
            else:
                logger.warning(
                    "Vulnerability %s not found — threat created without CVE link",
                    cve_id,
                )

        return record["threat_id"]
