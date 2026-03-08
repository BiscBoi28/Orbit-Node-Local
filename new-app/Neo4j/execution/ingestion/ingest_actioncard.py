"""
Ingestion template — ActionCard
=================================
MERGE on action_id.  Initial status is 'received' (not 'pending').
Unresolved targets are stored in ac.unresolved_targets — never fail the
whole ingestion due to missing affected entities.

After persisting, calls validate_and_transition() to move from
'received' → 'pending' if valid, or 'failed' if not.
"""

import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from neo4j import Driver

logger = logging.getLogger(__name__)

INGEST_CYPHER = """
MERGE (ac:ActionCard {action_id: $action_id})
ON CREATE SET ac.created_ts = datetime(),
              ac.status     = 'received'
SET ac.origin         = $origin,
    ac.action_type    = $action_type,
    ac.summary        = $summary,
    ac.confidence     = $confidence,
    ac.recommended_ts = CASE WHEN $recommended_ts <> ''
                             THEN datetime($recommended_ts)
                             ELSE null END,
    ac.metadata       = $metadata,
    ac.last_updated   = datetime()
RETURN ac.action_id AS action_id, ac.status AS status
"""

# Link affected hosts — only those that exist
LINK_HOSTS_CYPHER = """
MATCH (ac:ActionCard {action_id: $action_id})
UNWIND $host_ids AS hid
OPTIONAL MATCH (h:Host {host_id: hid})
WITH ac, hid, h
WHERE h IS NOT NULL
MERGE (ac)-[:AFFECTS]->(h)
RETURN collect(hid) AS linked
"""

LINK_ASSETS_CYPHER = """
MATCH (ac:ActionCard {action_id: $action_id})
UNWIND $asset_hashes AS ah
OPTIONAL MATCH (d:DataAsset {asset_hash: ah})
WITH ac, ah, d
WHERE d IS NOT NULL
MERGE (ac)-[:AFFECTS]->(d)
RETURN collect(ah) AS linked
"""

LINK_SERVICES_CYPHER = """
MATCH (ac:ActionCard {action_id: $action_id})
UNWIND $service_ids AS sid
OPTIONAL MATCH (s:Service {service_id: sid})
WITH ac, sid, s
WHERE s IS NOT NULL
MERGE (ac)-[:AFFECTS]->(s)
RETURN collect(sid) AS linked
"""

SET_UNRESOLVED_CYPHER = """
MATCH (ac:ActionCard {action_id: $action_id})
SET ac.unresolved_targets = $unresolved,
    ac.last_updated       = datetime()
"""

VALIDATE_TRANSITION_CYPHER = """
MATCH (ac:ActionCard {action_id: $action_id})
WHERE ac.status = 'received'
SET ac.status       = 'pending',
    ac.last_updated = datetime()
RETURN ac.status AS status
"""

FAIL_TRANSITION_CYPHER = """
MATCH (ac:ActionCard {action_id: $action_id})
WHERE ac.status = 'received'
SET ac.status           = 'failed',
    ac.failure_reason   = $reason,
    ac.last_updated     = datetime()
RETURN ac.status AS status
"""


def validate_and_transition(driver: Driver, action_id: str) -> str:
    """Transition ActionCard from 'received' → 'pending' if valid,
    or → 'failed' with a reason if not.  Returns the new status."""

    # For now, basic validation: action_id must exist, have origin & action_type
    with driver.session() as session:
        result = session.run(
            "MATCH (ac:ActionCard {action_id: $action_id}) "
            "RETURN ac.origin AS origin, ac.action_type AS atype, ac.status AS status",
            {"action_id": action_id},
        )
        record = result.single()
        if record is None:
            return "failed"

        if record["status"] != "received":
            return record["status"]

        errors = []
        if not record["origin"]:
            errors.append("missing origin")
        if not record["atype"]:
            errors.append("missing action_type")

        if errors:
            reason = "; ".join(errors)
            session.run(FAIL_TRANSITION_CYPHER, {
                "action_id": action_id, "reason": reason
            })
            logger.warning(
                "ActionCard validation failed",
                extra={"action_id": action_id, "reason": reason},
            )
            return "failed"

        session.run(VALIDATE_TRANSITION_CYPHER, {"action_id": action_id})
        logger.info(
            "ActionCard transitioned to pending",
            extra={"action_id": action_id},
        )
        return "pending"


def ingest_actioncard(driver: Driver, payload: dict) -> str:
    """Ingest a single ActionCard.  Returns the action_id.

    Initial status is 'received'.  Unresolved affected targets are stored
    in ac.unresolved_targets — the ingestion never fails due to missing
    targets.
    """

    action_id = payload.get("action_id")
    if not action_id:
        raise ValueError("action_id is required")

    affected = payload.get("affected", {})
    host_ids = affected.get("hosts", [])
    asset_hashes = affected.get("assets", [])
    service_ids = affected.get("services", [])

    params = {
        "action_id":      action_id,
        "origin":         payload.get("origin", ""),
        "action_type":    payload.get("action_type", ""),
        "summary":        payload.get("summary", ""),
        "confidence":     payload.get("confidence", 0.0),
        "recommended_ts": payload.get("recommended_ts", ""),
        "metadata":       str(payload.get("metadata", {})),
    }

    with driver.session() as session:
        result = session.run(INGEST_CYPHER, params)
        record = result.single()
        logger.info(
            "Ingested actioncard",
            extra={"action_id": action_id, "status": record["status"], "action": "merge"},
        )

        # ── Link affected entities, collecting unresolved ────────────────
        unresolved = []

        if host_ids:
            r = session.run(LINK_HOSTS_CYPHER, {
                "action_id": action_id, "host_ids": host_ids
            })
            linked = r.single()["linked"]
            for hid in host_ids:
                if hid not in linked:
                    unresolved.append(f"host:{hid}")
                    logger.warning("Unresolved host target: %s", hid)

        if asset_hashes:
            r = session.run(LINK_ASSETS_CYPHER, {
                "action_id": action_id, "asset_hashes": asset_hashes
            })
            linked = r.single()["linked"]
            for ah in asset_hashes:
                if ah not in linked:
                    unresolved.append(f"asset:{ah}")
                    logger.warning("Unresolved asset target: %s", ah)

        if service_ids:
            r = session.run(LINK_SERVICES_CYPHER, {
                "action_id": action_id, "service_ids": service_ids
            })
            linked = r.single()["linked"]
            for sid in service_ids:
                if sid not in linked:
                    unresolved.append(f"service:{sid}")
                    logger.warning("Unresolved service target: %s", sid)

        if unresolved:
            session.run(SET_UNRESOLVED_CYPHER, {
                "action_id": action_id, "unresolved": unresolved
            })

        # ── Auto-validate ────────────────────────────────────────────────
        validate_and_transition(driver, action_id)

        return action_id
