"""
Ingestion template — DeltaEvent
=================================
Append-only audit record.  Uses CREATE (not MERGE) — each delta export
creates a new node.

Functions:
  create_delta_event   — creates DeltaEvent with sent_status='pending'
  link_entities_to_delta — creates :INCLUDED_IN relationships
  mark_delta_sent      — sets sent_status='sent'
  mark_delta_queued    — sets sent_status='queued' (Core unreachable)
"""

import logging
from neo4j import Driver

logger = logging.getLogger(__name__)

CREATE_CYPHER = """
CREATE (de:DeltaEvent {
  delta_id:     $delta_id,
  generated_ts: datetime(),
  entity_count: $entity_count,
  sent_status:  'pending',
  page_token:   $page_token,
  last_updated: datetime()
})
RETURN de.delta_id AS delta_id
"""

LINK_CYPHER = """
UNWIND $changed_entity_ids AS eid
MATCH (n)
  WHERE n.host_id = eid OR n.asset_hash = eid
     OR n.cve_id  = eid OR n.action_id  = eid
     OR n.threat_id = eid
MATCH (de:DeltaEvent {delta_id: $delta_id})
MERGE (n)-[r:INCLUDED_IN]->(de)
SET r.entity_type  = $entity_type,
    r.operation    = $operation
RETURN count(r) AS linked_count
"""

MARK_SENT_CYPHER = """
MATCH (de:DeltaEvent {delta_id: $delta_id})
SET de.sent_status = 'sent', de.last_updated = datetime()
RETURN de.delta_id AS delta_id
"""

MARK_QUEUED_CYPHER = """
MATCH (de:DeltaEvent {delta_id: $delta_id})
SET de.sent_status = 'queued', de.last_updated = datetime()
RETURN de.delta_id AS delta_id
"""


def create_delta_event(driver: Driver, payload: dict) -> str:
    """Create a DeltaEvent node in 'pending' state.  Returns delta_id."""

    delta_id = payload.get("delta_id")
    if not delta_id:
        raise ValueError("delta_id is required")

    params = {
        "delta_id":     delta_id,
        "entity_count": payload.get("entity_count", 0),
        "page_token":   payload.get("page_token", None),
    }

    with driver.session() as session:
        result = session.run(CREATE_CYPHER, params)
        record = result.single()
        logger.info(
            "Created delta event",
            extra={"delta_id": delta_id, "action": "create"},
        )
        return record["delta_id"]


def link_entities_to_delta(
    driver: Driver,
    delta_id: str,
    changes: list[dict],
) -> None:
    """Create :INCLUDED_IN relationships from changed entities to a DeltaEvent.

    Each item in changes should have: entity_id, entity_type, operation.
    """
    if not delta_id:
        raise ValueError("delta_id is required")

    with driver.session() as session:
        for change in changes:
            entity_ids = [change["entity_id"]] if isinstance(
                change.get("entity_id"), str
            ) else change.get("entity_ids", [])

            session.run(LINK_CYPHER, {
                "delta_id":           delta_id,
                "changed_entity_ids": entity_ids,
                "entity_type":        change.get("entity_type", ""),
                "operation":          change.get("operation", "update"),
            })

        logger.info(
            "Linked entities to delta",
            extra={"delta_id": delta_id, "change_count": len(changes)},
        )


def mark_delta_sent(driver: Driver, delta_id: str) -> None:
    """Mark DeltaEvent as 'sent' after Core confirms receipt."""
    if not delta_id:
        raise ValueError("delta_id is required")

    with driver.session() as session:
        session.run(MARK_SENT_CYPHER, {"delta_id": delta_id})
        logger.info(
            "DeltaEvent marked sent",
            extra={"delta_id": delta_id},
        )


def mark_delta_queued(driver: Driver, delta_id: str) -> None:
    """Mark DeltaEvent as 'queued' when Core is unreachable."""
    if not delta_id:
        raise ValueError("delta_id is required")

    with driver.session() as session:
        session.run(MARK_QUEUED_CYPHER, {"delta_id": delta_id})
        logger.info(
            "DeltaEvent marked queued",
            extra={"delta_id": delta_id},
        )
