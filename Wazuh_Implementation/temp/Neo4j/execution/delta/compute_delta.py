"""
Phase 4 — Delta Computation & Export (D4 §9)
===============================================
Computes what has changed since the last successful sync and packages
it into the D3 delta JSON format.

Functions:
  compute_delta      — finds all nodes updated since last_synced_ts
  export_delta       — persists a DeltaEvent + JSON file
  acknowledge_delta  — marks DeltaEvent 'sent', stamps entities
  soft_delete        — marks a node deleted=True (no physical removal)
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))

from dotenv import load_dotenv
from neo4j import Driver

from ingest_delta_event import (
    create_delta_event,
    link_entities_to_delta,
    mark_delta_sent,
)

load_dotenv()

logger = logging.getLogger(__name__)

# Labels excluded from delta computation (metadata / tracking nodes)
_EXCLUDED_LABELS = {"SchemaVersion", "DeltaEvent", "IngestLog"}

# ── Canonical key map ────────────────────────────────────────────────────────
_KEY_PROPS = [
    "host_id", "asset_hash", "cve_id", "action_id",
    "threat_id", "subscription_id", "service_id", "app_id",
    "analyst_id", "exec_id",
]

DELTA_QUERY = """
MATCH (n)
WHERE n.last_updated > datetime($last_synced_ts)
  AND NOT 'SchemaVersion' IN labels(n)
  AND NOT 'DeltaEvent'    IN labels(n)
  AND NOT 'IngestLog'     IN labels(n)
RETURN labels(n) AS entity_labels,
       n AS node_props,
       CASE WHEN n.host_id       IS NOT NULL THEN n.host_id
            WHEN n.asset_hash    IS NOT NULL THEN n.asset_hash
            WHEN n.cve_id        IS NOT NULL THEN n.cve_id
            WHEN n.action_id     IS NOT NULL THEN n.action_id
            WHEN n.threat_id     IS NOT NULL THEN n.threat_id
            WHEN n.subscription_id IS NOT NULL THEN n.subscription_id
            WHEN n.service_id    IS NOT NULL THEN n.service_id
            WHEN n.app_id        IS NOT NULL THEN n.app_id
            WHEN n.analyst_id    IS NOT NULL THEN n.analyst_id
            WHEN n.exec_id       IS NOT NULL THEN n.exec_id
            ELSE 'unknown' END AS entity_id
ORDER BY n.last_updated ASC
LIMIT $page_size
"""

STAMP_SYNCED_CYPHER = """
UNWIND $entity_ids AS eid
MATCH (n)
  WHERE n.host_id = eid OR n.asset_hash = eid
     OR n.cve_id  = eid OR n.action_id  = eid
     OR n.threat_id = eid OR n.subscription_id = eid
     OR n.service_id = eid OR n.app_id = eid
     OR n.analyst_id = eid OR n.exec_id = eid
SET n.last_synced_ts = datetime(),
    n.last_updated   = datetime()
"""

SOFT_DELETE_CYPHER_TEMPLATE = """
MATCH (n:{label} {{{key}: $value}})
SET n.deleted      = true,
    n.deleted_ts   = datetime(),
    n.last_updated = datetime()
RETURN n.{key} AS entity_id
"""


def _node_to_dict(node_props) -> dict:
    """Convert a Neo4j node record to a JSON-safe dict."""
    result = {}
    for key, value in dict(node_props).items():
        # Convert Neo4j temporal types to ISO strings
        if hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        elif isinstance(value, list):
            result[key] = [
                v.isoformat() if hasattr(v, "isoformat") else v
                for v in value
            ]
        else:
            result[key] = value
    return result


def compute_delta(
    driver: Driver,
    last_synced_ts: str,
    page_size: int | None = None,
) -> dict:
    """Compute all changes since last_synced_ts.

    Returns a dict matching D3 Contract B schema:
      delta_id, generated_ts, changes[]
    Each change has: entity_type, entity_id, operation, properties,
                     last_updated, source
    """
    if page_size is None:
        page_size = int(os.getenv("DELTA_PAGE_SIZE", "200"))

    delta_id = f"delta-{uuid.uuid4().hex[:12]}"
    generated_ts = datetime.now(timezone.utc).isoformat()

    changes: list[dict] = []

    with driver.session() as session:
        result = session.run(DELTA_QUERY, {
            "last_synced_ts": last_synced_ts,
            "page_size": page_size,
        })

        for record in result:
            labels = record["entity_labels"]
            entity_id = record["entity_id"]
            props = _node_to_dict(record["node_props"])

            # Determine entity_type (primary label, excluding internal)
            entity_type = [l for l in labels if l not in _EXCLUDED_LABELS]
            entity_type_str = entity_type[0] if entity_type else "Unknown"

            # Detect soft-deleted nodes
            is_deleted = props.get("deleted", False)
            operation = "delete" if is_deleted else "update"

            changes.append({
                "entity_type": entity_type_str,
                "entity_id": entity_id,
                "operation": operation,
                "properties": props,
                "last_updated": props.get("last_updated", ""),
                "source": props.get("source", ""),
            })

    logger.info(
        "Computed delta: %d changes since %s",
        len(changes), last_synced_ts,
    )

    return {
        "contract_version": "1.1",
        "delta_id": delta_id,
        "generated_ts": generated_ts,
        "page_token": None,
        "changes": changes,
    }


def export_delta(driver: Driver, delta_payload: dict) -> str:
    """Persist a DeltaEvent node, link entities, write JSON to disk.

    Returns the delta_id.
    """
    delta_id = delta_payload["delta_id"]
    changes = delta_payload.get("changes", [])

    # 1. Create DeltaEvent node
    create_delta_event(driver, {
        "delta_id": delta_id,
        "entity_count": len(changes),
        "page_token": delta_payload.get("page_token"),
    })

    # 2. Link entities via :INCLUDED_IN
    if changes:
        link_entities_to_delta(driver, delta_id, changes)

    # 3. Write JSON to .tmp/deltas/
    deltas_dir = os.path.join(
        os.getenv("LOG_DIR", ".tmp/logs").replace("/logs", ""),
        "deltas",
    )
    os.makedirs(deltas_dir, exist_ok=True)
    filepath = os.path.join(deltas_dir, f"delta_{delta_id}.json")
    with open(filepath, "w") as f:
        json.dump(delta_payload, f, indent=2, default=str)

    logger.info("Exported delta to %s", filepath)
    return delta_id


def acknowledge_delta(driver: Driver, delta_id: str) -> None:
    """Called after Core confirms receipt.

    - Marks DeltaEvent as 'sent'
    - Sets last_synced_ts = datetime() on all included entities
    """
    if not delta_id:
        raise ValueError("delta_id is required")

    # Mark sent
    mark_delta_sent(driver, delta_id)

    # Stamp all included entities
    with driver.session() as session:
        # Get entity IDs from :INCLUDED_IN relationships
        result = session.run(
            "MATCH (n)-[:INCLUDED_IN]->(de:DeltaEvent {delta_id: $delta_id}) "
            "RETURN CASE "
            "  WHEN n.host_id IS NOT NULL THEN n.host_id "
            "  WHEN n.asset_hash IS NOT NULL THEN n.asset_hash "
            "  WHEN n.cve_id IS NOT NULL THEN n.cve_id "
            "  WHEN n.action_id IS NOT NULL THEN n.action_id "
            "  WHEN n.threat_id IS NOT NULL THEN n.threat_id "
            "  WHEN n.subscription_id IS NOT NULL THEN n.subscription_id "
            "  WHEN n.service_id IS NOT NULL THEN n.service_id "
            "  WHEN n.app_id IS NOT NULL THEN n.app_id "
            "  WHEN n.analyst_id IS NOT NULL THEN n.analyst_id "
            "  WHEN n.exec_id IS NOT NULL THEN n.exec_id "
            "  ELSE 'unknown' END AS eid",
            {"delta_id": delta_id},
        )
        entity_ids = [r["eid"] for r in result if r["eid"] != "unknown"]

        if entity_ids:
            session.run(STAMP_SYNCED_CYPHER, {"entity_ids": entity_ids})

    logger.info(
        "Acknowledged delta %s — stamped %d entities",
        delta_id, len(entity_ids),
    )


def soft_delete(
    driver: Driver,
    label: str,
    canonical_key: str,
    value: str,
) -> None:
    """Soft-delete a node: sets deleted=True, deleted_ts, last_updated.

    NEVER physically removes the node.  The next delta export will
    include it with operation='delete' so Core can sync the removal.
    """
    cypher = SOFT_DELETE_CYPHER_TEMPLATE.format(label=label, key=canonical_key)

    with driver.session() as session:
        result = session.run(cypher, {"value": value})
        record = result.single()
        if record is None:
            raise ValueError(
                f"{label} with {canonical_key}='{value}' not found"
            )

    logger.info(
        "Soft-deleted %s(%s=%s)",
        label, canonical_key, value,
    )
