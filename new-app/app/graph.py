"""
Neo4j driver wrapper — bridges the ORC app to the existing Neo4j layer.

Provides:
  - get_driver()     singleton driver
  - close_driver()   teardown
  - Re-exports of existing Neo4j ingestion/lifecycle/delta functions

The existing Neo4j code lives in Neo4j/execution/.  This module adds
the parent paths so those imports work, then re-exports the public API.
"""

import os
import sys
import logging

from neo4j import GraphDatabase, Driver

from app.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

logger = logging.getLogger(__name__)

# ── Path setup so Neo4j execution modules are importable ────────────────────
_NEO4J_ROOT = os.path.join(os.path.dirname(__file__), "..", "Neo4j")
for sub in ("execution", "execution/ingestion", "execution/lifecycle",
            "execution/delta", "execution/schema"):
    _p = os.path.join(_NEO4J_ROOT, sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Re-export ingestion functions ───────────────────────────────────────────
from ingest_host import ingest_host                           # noqa: E402
from ingest_service import ingest_service                     # noqa: E402
from ingest_application import ingest_application             # noqa: E402
from ingest_vulnerability import ingest_vulnerability         # noqa: E402
from ingest_dataasset import (                                # noqa: E402
    ingest_dataasset,
    ingest_dataasset_pending_retry,
)
from ingest_threat import ingest_threat                       # noqa: E402
from ingest_actioncard import ingest_actioncard               # noqa: E402
from ingest_subscription import (                             # noqa: E402
    ingest_subscription,
    mark_subscription_queued,
    mark_subscription_sent,
)
from ingest_delta_event import (                              # noqa: E402
    create_delta_event,
    link_entities_to_delta,
    mark_delta_sent,
    mark_delta_queued,
)
from batch_ingest import batch_ingest                         # noqa: E402

# ── Re-export lifecycle functions ───────────────────────────────────────────
from actioncard_lifecycle import (                            # noqa: E402
    get_actioncard_status,
    validate_and_transition,
    assign_to_analyst,
    approve_action,
    reject_action,
    begin_execution,
    record_execution_result,
    VALID_TRANSITIONS,
)

# ── Re-export delta functions ───────────────────────────────────────────────
from compute_delta import (                                   # noqa: E402
    compute_delta,
    export_delta,
    acknowledge_delta,
    soft_delete,
)

# ── Re-export schema functions ──────────────────────────────────────────────
from apply_schema_fn import apply_schema                      # noqa: E402

# ── Re-export exceptions ────────────────────────────────────────────────────
from exceptions import (                                      # noqa: E402
    PrivacyViolationError,
    InvalidStateTransitionError,
    OrphanEntityError,
    ContractValidationError,
)

# ── Driver singleton ────────────────────────────────────────────────────────
_driver: Driver | None = None


def get_driver() -> Driver:
    """Return the singleton Neo4j driver, creating it on first call."""
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
        _driver.verify_connectivity()
        logger.info("Neo4j driver connected to %s", NEO4J_URI)
    return _driver


def close_driver() -> None:
    """Close the driver (call on app shutdown)."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
        logger.info("Neo4j driver closed")


# ── Convenience query helpers ───────────────────────────────────────────────

def lookup_host(host_id: str) -> dict | None:
    """Fetch a Host node's properties.  Returns None if not found."""
    driver = get_driver()
    with driver.session() as session:
        rec = session.run(
            "MATCH (h:Host {host_id: $id}) RETURN h AS node",
            id=host_id,
        ).single()
        return dict(rec["node"]) if rec else None


def lookup_dataassets_for_host(host_id: str) -> list[dict]:
    """Return all DataAsset nodes linked to a Host."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host {host_id: $id}) "
            "RETURN d AS node ORDER BY d.sensitivity_score DESC",
            id=host_id,
        )
        return [dict(r["node"]) for r in result]


def get_crown_jewels() -> list[dict]:
    """Return all crown-jewel DataAssets with their Host."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (d:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(h:Host) "
            "RETURN h.host_id AS host_id, h.hostname AS hostname, "
            "       d.asset_hash AS asset_hash, "
            "       d.sensitivity_score AS sensitivity_score, "
            "       d.pii_types AS pii_types "
            "ORDER BY d.sensitivity_score DESC"
        )
        return [dict(r) for r in result]


def get_high_sensitivity_assets(threshold: float = 0.5) -> list[dict]:
    """Return DataAssets with sensitivity_score >= threshold."""
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            "MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host) "
            "WHERE d.sensitivity_score >= $threshold "
            "RETURN h.host_id AS host_id, h.hostname AS hostname, "
            "       d.asset_hash AS asset_hash, "
            "       d.sensitivity_score AS sensitivity_score, "
            "       d.crown_jewel AS crown_jewel "
            "ORDER BY d.sensitivity_score DESC",
            threshold=threshold,
        )
        return [dict(r) for r in result]
