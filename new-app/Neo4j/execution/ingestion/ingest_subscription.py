"""
Ingestion template — Subscription
====================================
Archives any existing active Subscription, then CREATEs a new one with
status='active'.  If an old subscription existed, links them via :GENERATED.

Offline path: mark_subscription_queued() sets status='queued'.
Restore path: mark_subscription_sent() sets status='active' + last_sent_ts.
"""

import logging
from neo4j import Driver

logger = logging.getLogger(__name__)

INGEST_CYPHER = """
OPTIONAL MATCH (old:Subscription {status: 'active'})
FOREACH (_ IN CASE WHEN old IS NOT NULL THEN [1] ELSE [] END |
  SET old.status = 'archived', old.last_updated = datetime()
)
WITH old
CREATE (sub:Subscription {
  subscription_id:        $subscription_id,
  context_summary:        $context_summary,
  preferred_action_types: $preferred_action_types,
  status:                 'active',
  generated_ts:           datetime(),
  last_sent_ts:           null,
  last_updated:           datetime()
})
WITH sub, old
FOREACH (_ IN CASE WHEN old IS NOT NULL THEN [1] ELSE [] END |
  MERGE (old)-[:GENERATED]->(sub)
)
RETURN sub.subscription_id AS subscription_id
"""

MARK_QUEUED_CYPHER = """
MATCH (sub:Subscription {subscription_id: $subscription_id})
SET sub.status = 'queued', sub.last_updated = datetime()
RETURN sub.subscription_id AS subscription_id
"""

MARK_SENT_CYPHER = """
MATCH (sub:Subscription {subscription_id: $subscription_id})
SET sub.status       = 'active',
    sub.last_sent_ts = datetime(),
    sub.last_updated = datetime()
RETURN sub.subscription_id AS subscription_id
"""


def ingest_subscription(driver: Driver, payload: dict) -> str:
    """Ingest a Subscription.  Archives any existing active subscription
    first, then creates a new one with status='active'.  Returns subscription_id."""

    subscription_id = payload.get("subscription_id")
    if not subscription_id:
        raise ValueError("subscription_id is required")

    params = {
        "subscription_id":        subscription_id,
        "context_summary":        str(payload.get("context_summary", {})),
        "preferred_action_types": payload.get("preferred_action_types", []),
    }

    with driver.session() as session:
        result = session.run(INGEST_CYPHER, params)
        record = result.single()
        logger.info(
            "Ingested subscription",
            extra={"subscription_id": subscription_id, "action": "create"},
        )
        return record["subscription_id"]


def mark_subscription_queued(driver: Driver, subscription_id: str) -> None:
    """Set status='queued' when Core is unreachable."""
    if not subscription_id:
        raise ValueError("subscription_id is required")

    with driver.session() as session:
        session.run(MARK_QUEUED_CYPHER, {"subscription_id": subscription_id})
        logger.info(
            "Subscription marked queued",
            extra={"subscription_id": subscription_id},
        )


def mark_subscription_sent(driver: Driver, subscription_id: str) -> None:
    """Set status='active' + last_sent_ts after Core acknowledges."""
    if not subscription_id:
        raise ValueError("subscription_id is required")

    with driver.session() as session:
        session.run(MARK_SENT_CYPHER, {"subscription_id": subscription_id})
        logger.info(
            "Subscription marked sent",
            extra={"subscription_id": subscription_id},
        )
