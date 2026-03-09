"""Write pending ActionCards into the shared ORBIT alert log for Wazuh."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.graph import get_driver
from app.wazuh import logger
from app.wazuh.wazuh_client import WazuhClient

ORBIT_ALERTS_LOG = os.getenv("ORBIT_ALERTS_LOG", "/orbit-alerts/orbit_alerts.log")

GET_ACTIONCARD_REF = """
MATCH (ac:ActionCard {action_id: $action_id})
RETURN ac.wazuh_alert_ref AS wazuh_alert_ref
"""

SET_ACTIONCARD_REF = """
MATCH (ac:ActionCard {action_id: $action_id})
SET ac.wazuh_alert_ref = $wazuh_alert_ref,
    ac.wazuh_injected_ts = datetime(),
    ac.last_updated = datetime()
RETURN ac.wazuh_alert_ref AS wazuh_alert_ref
"""


def _deterministic_ref(action_id: str) -> str:
    return f"orbit-alert::{action_id}"


def _existing_ref(action_id: str) -> str | None:
    driver = get_driver()
    with driver.session() as session:
        record = session.run(GET_ACTIONCARD_REF, {"action_id": action_id}).single()
    if not record:
        return None
    return record["wazuh_alert_ref"]


def _store_ref(action_id: str, wazuh_alert_ref: str) -> str:
    driver = get_driver()
    with driver.session() as session:
        record = session.run(
            SET_ACTIONCARD_REF,
            {"action_id": action_id, "wazuh_alert_ref": wazuh_alert_ref},
        ).single()
    if not record:
        raise ValueError(f"ActionCard '{action_id}' not found while storing wazuh_alert_ref")
    return record["wazuh_alert_ref"]


def inject_actioncard_as_alert(
    wazuh_client: WazuhClient,
    actioncard: dict,
    affected_host: dict,
) -> str:
    """Write the ActionCard as a JSON line and store a stable alert reference."""

    action_id = actioncard.get("action_id")
    if not action_id:
        raise ValueError("actioncard.action_id is required")

    existing = _existing_ref(action_id)
    if existing:
        logger.info("Skipping duplicate ActionCard alert injection for %s", action_id)
        return existing

    wazuh_alert_ref = _deterministic_ref(action_id)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "orbit_source": "ORBIT",
        "orbit_type": "actioncard_pending",
        "orbit_action_id": action_id,
        "wazuh_alert_ref": wazuh_alert_ref,
        "status": actioncard.get("status", "pending"),
        "priority": actioncard.get("priority", "MEDIUM"),
        "origin": actioncard.get("origin", "orbit-core"),
        "action_type": actioncard.get("action_type", ""),
        "summary": actioncard.get("summary", ""),
        "confidence": actioncard.get("confidence", 0.0),
        "affected_host": affected_host.get("host_id", ""),
        "affected_hostname": affected_host.get("hostname", ""),
        "wazuh_api_url": getattr(wazuh_client, "base_url", ""),
    }

    path = Path(ORBIT_ALERTS_LOG)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")

    _store_ref(action_id, wazuh_alert_ref)
    logger.info("Injected ActionCard %s into %s", action_id, path)
    return wazuh_alert_ref
