"""Active response orchestration for Wazuh-managed ActionCards."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from app.graph import (
    begin_execution,
    get_driver,
    record_execution_result,
)
from app.wazuh import logger
from app.wazuh.wazuh_client import get_wazuh_client

ORBIT_AR_LOG = Path(os.getenv("ORBIT_AR_LOG", "/orbit-ar/orbit_ar.log"))
WAZUH_AR_COMMAND = os.getenv("WAZUH_AR_COMMAND", "!orbit_action.sh")
AR_TIMEOUT_SECONDS = int(os.getenv("WAZUH_AR_TIMEOUT_SECONDS", "30"))
AR_POLL_INTERVAL_SECONDS = float(os.getenv("WAZUH_AR_POLL_INTERVAL_SECONDS", "1"))

GET_ACTIONCARD_CONTEXT = """
MATCH (ac:ActionCard {action_id: $action_id})
OPTIONAL MATCH (ac)-[:AFFECTS]->(h:Host)
RETURN ac.action_id AS action_id,
       ac.action_type AS action_type,
       ac.summary AS summary,
       collect(
         CASE
           WHEN h IS NULL THEN null
           ELSE {
             host_id: h.host_id,
             hostname: h.hostname,
             ip: h.ip
           }
         END
       ) AS hosts
"""


def is_wazuh_managed_host(host_id: str) -> bool:
    return str(host_id or "").startswith("wazuh-agent-")


def _agent_id_from_host_id(host_id: str) -> str:
    if not is_wazuh_managed_host(host_id):
        raise ValueError(f"Host '{host_id}' is not Wazuh-managed")
    return str(host_id).removeprefix("wazuh-agent-")


def get_actioncard_context(action_id: str) -> dict:
    driver = get_driver()
    with driver.session() as session:
        record = session.run(GET_ACTIONCARD_CONTEXT, {"action_id": action_id}).single()

    if record is None:
        raise ValueError(f"ActionCard '{action_id}' not found")

    hosts = [host for host in (record["hosts"] or []) if host and host.get("host_id")]
    return {
        "action_id": record["action_id"],
        "action_type": record["action_type"] or "",
        "summary": record["summary"] or "",
        "hosts": hosts,
    }


def get_primary_affected_host(action_id: str) -> dict | None:
    context = get_actioncard_context(action_id)
    for host in context["hosts"]:
        if host.get("host_id"):
            return host
    return None


def _execution_id(action_id: str) -> str:
    return f"orbit-ar::{action_id}"


def _log_offset(path: Path) -> int:
    if not path.exists():
        return 0
    return path.stat().st_size


def _find_result(path: Path, start_offset: int, action_id: str) -> dict | None:
    if not path.exists():
        return None

    offset = min(start_offset, path.stat().st_size)
    with path.open("r", encoding="utf-8") as handle:
        handle.seek(offset)
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Ignoring invalid JSON line in %s", path)
                continue
            if payload.get("action_card_id") == action_id:
                return payload
    return None


def _record_outcome(action_id: str, outcome: str, details: str) -> None:
    driver = get_driver()
    try:
        record_execution_result(
            driver,
            action_id,
            _execution_id(action_id),
            outcome,
            details,
        )
    except Exception:
        logger.exception("Failed to record execution result for %s", action_id)


def poll_ar_completion(
    action_id: str,
    *,
    start_offset: int = 0,
    timeout_seconds: int = AR_TIMEOUT_SECONDS,
) -> None:
    """Poll the shared orbit_ar.log mirror and persist the execution result."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = _find_result(ORBIT_AR_LOG, start_offset, action_id)
        if result is not None:
            outcome = "success" if str(result.get("status", "")).lower() == "executed" else "failure"
            _record_outcome(action_id, outcome, json.dumps(result, sort_keys=True))
            logger.info("Observed AR completion for %s in %s", action_id, ORBIT_AR_LOG)
            return
        time.sleep(AR_POLL_INTERVAL_SECONDS)

    _record_outcome(
        action_id,
        "failure",
        f"Timed out waiting for active response completion in {ORBIT_AR_LOG}",
    )
    logger.warning("Timed out waiting for AR completion for %s", action_id)


def trigger_active_response(action_id: str, analyst_id: str = "") -> None:
    """Trigger Wazuh active response, mark execution started, then poll for completion."""

    driver = get_driver()
    host = get_primary_affected_host(action_id)
    if host is None:
        raise ValueError(f"ActionCard '{action_id}' has no affected host")

    host_id = host.get("host_id", "")
    if not is_wazuh_managed_host(host_id):
        raise ValueError(f"Host '{host_id}' is not Wazuh-managed")

    context = get_actioncard_context(action_id)
    start_offset = _log_offset(ORBIT_AR_LOG)
    execution_started = False

    try:
        begin_execution(driver, action_id)
        execution_started = True

        arguments = [
            "ADD",
            analyst_id or "orbit-orc",
            host.get("ip") or "127.0.0.1",
            f"{context['action_type']}::{action_id}::{host_id}",
        ]
        alert = {
            "data": {
                "action_id": action_id,
                "host_id": host_id,
                "hostname": host.get("hostname", ""),
                "action_type": context["action_type"],
                "summary": context["summary"],
            }
        }

        response = get_wazuh_client().trigger_active_response(
            _agent_id_from_host_id(host_id),
            WAZUH_AR_COMMAND,
            arguments,
            custom=True,
            alert=alert,
        )
        logger.info("Triggered Wazuh AR for %s: %s", action_id, response)
        poll_ar_completion(action_id, start_offset=start_offset)
    except Exception as exc:
        logger.exception("Wazuh active response failed for %s", action_id)
        if execution_started:
            _record_outcome(action_id, "failure", f"Active response trigger failed: {exc}")


def simulate_execution(action_id: str, delay_seconds: int = 3) -> None:
    """Fallback execution for non-Wazuh fixture hosts."""

    driver = get_driver()
    execution_started = False
    try:
        begin_execution(driver, action_id)
        execution_started = True
        time.sleep(delay_seconds)
        _record_outcome(
            action_id,
            "success",
            json.dumps(
                {
                    "status": "executed",
                    "action_card_id": action_id,
                    "simulated": True,
                },
                sort_keys=True,
            ),
        )
        logger.info("Simulated execution completed for %s", action_id)
    except Exception as exc:
        logger.exception("Simulated execution failed for %s", action_id)
        if execution_started:
            _record_outcome(action_id, "failure", f"Simulated execution failed: {exc}")


__all__ = [
    "get_primary_affected_host",
    "get_actioncard_context",
    "is_wazuh_managed_host",
    "poll_ar_completion",
    "simulate_execution",
    "trigger_active_response",
]
