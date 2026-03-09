"""Full Wazuh inventory pull sync into Neo4j."""

from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone

from app.config import PROJECT_ROOT
from app.graph import (
    batch_ingest,
    ingest_host,
    ingest_application,
    ingest_service,
    ingest_vulnerability,
)
from app.wazuh import logger
from app.wazuh.agent_registry import host_payload_from_agent
from app.wazuh.wazuh_client import WazuhClient

FIXTURE_VULNS_PATH = os.path.join(PROJECT_ROOT, "wazuh", "fixtures", "vulnerabilities.json")

_SYNC_STATUS: dict = {
    "status": "never_run",
    "last_sync_ts": None,
    "counts": {"agents": 0, "packages": 0, "ports": 0, "vulnerabilities": 0},
    "last_error": None,
}


def _application_payload(host_id: str, package: dict) -> dict:
    return {
        "host_id": host_id,
        "name": package.get("name", ""),
        "version": package.get("version", "unknown"),
        "vendor": package.get("vendor", ""),
        "source": "wazuh-api",
    }


def _service_payload(host_id: str, port: dict) -> dict | None:
    local = port.get("local") or {}
    port_number = local.get("port")
    if port_number in (None, ""):
        return None
    return {
        "host_id": host_id,
        "name": port.get("process") or f"port-{port_number}",
        "port": int(port_number),
        "proto": port.get("protocol", "tcp"),
        "source": "wazuh-api",
    }


def _vulnerability_payload(host_id: str, vulnerability: dict, source: str) -> dict | None:
    cve_id = vulnerability.get("cve")
    if not cve_id:
        return None
    cvss = vulnerability.get("cvss3_score")
    if cvss in (None, ""):
        cvss = vulnerability.get("cvss2_score", 0.0)
    return {
        "host_id": host_id,
        "cve_id": cve_id,
        "cvss": float(cvss or 0.0),
        "published": vulnerability.get("published", ""),
        "summary": vulnerability.get("title", ""),
        "severity": vulnerability.get("severity", ""),
        "source": source,
    }


def _load_fixture_vulnerabilities() -> dict[str, dict]:
    if not os.path.exists(FIXTURE_VULNS_PATH):
        return {}
    with open(FIXTURE_VULNS_PATH, encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _get_agent_vulnerabilities(
    wazuh_client: WazuhClient,
    agent_id: str,
    fixture_vulns: dict[str, dict],
) -> tuple[list[dict], str]:
    vulnerabilities = wazuh_client.get_agent_vulnerabilities(agent_id)
    if vulnerabilities:
        return vulnerabilities, "wazuh-api"

    fixture_response = fixture_vulns.get(agent_id, {})
    fixture_items = fixture_response.get("data", {}).get("affected_items", [])
    if fixture_items:
        logger.info(
            "Using API-shaped fixture vulnerabilities for agent %s because Wazuh returned none",
            agent_id,
        )
        return fixture_items, "wazuh-fixture"
    return [], "wazuh-api"


def _set_sync_status(*, status: str, counts: dict, last_error: str | None) -> None:
    _SYNC_STATUS["status"] = status
    _SYNC_STATUS["last_sync_ts"] = datetime.now(timezone.utc).isoformat()
    _SYNC_STATUS["counts"] = counts
    _SYNC_STATUS["last_error"] = last_error


def get_sync_status() -> dict:
    return copy.deepcopy(_SYNC_STATUS)


def sync_full_inventory(driver, wazuh_client: WazuhClient) -> dict:
    """Pull the current Wazuh state and merge it into Neo4j."""

    counts = {"agents": 0, "packages": 0, "ports": 0, "vulnerabilities": 0}
    fixture_vulns = _load_fixture_vulnerabilities()

    try:
        agents = wazuh_client.get_agents()
        for agent in agents:
            host_payload = host_payload_from_agent(agent)
            host_id = ingest_host(driver, host_payload)
            counts["agents"] += 1

            packages = wazuh_client.get_agent_packages(str(agent.get("id", "")))
            package_payloads = [
                payload
                for payload in (_application_payload(host_id, package) for package in packages)
                if payload.get("name")
            ]
            batch_result = batch_ingest(driver, package_payloads, ingest_application)
            counts["packages"] += batch_result["processed"]

            ports = wazuh_client.get_agent_ports(str(agent.get("id", "")))
            for port in ports:
                payload = _service_payload(host_id, port)
                if payload is None:
                    continue
                ingest_service(driver, payload)
                counts["ports"] += 1

            vulnerabilities, source = _get_agent_vulnerabilities(
                wazuh_client,
                str(agent.get("id", "")),
                fixture_vulns,
            )
            for vulnerability in vulnerabilities:
                payload = _vulnerability_payload(host_id, vulnerability, source)
                if payload is None:
                    continue
                ingest_vulnerability(driver, payload)
                counts["vulnerabilities"] += 1

        _set_sync_status(status="completed", counts=counts, last_error=None)
        logger.info("Completed Wazuh inventory sync: %s", counts)
        return counts
    except Exception as exc:
        _set_sync_status(status="failed", counts=counts, last_error=str(exc))
        logger.exception("Wazuh inventory sync failed")
        raise
