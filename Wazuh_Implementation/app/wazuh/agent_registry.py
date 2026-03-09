"""Helpers for deterministic Wazuh agent -> Host mapping."""

from __future__ import annotations

from neo4j import Driver

from app.graph import ingest_host


def agent_id_to_host_id(agent_id: str) -> str:
    """Map a Wazuh agent ID to the canonical ORC host ID."""

    if not agent_id:
        raise ValueError("agent.id is required")
    return f"wazuh-agent-{agent_id}"


def _os_label(agent: dict) -> str:
    os_info = agent.get("os")
    if not isinstance(os_info, dict):
        return ""

    parts = [os_info.get("name", ""), os_info.get("version", "")]
    platform = os_info.get("platform", "")
    if platform:
        parts.append(f"({platform})")
    return " ".join(part for part in parts if part).strip()


def host_payload_from_agent(agent: dict) -> dict:
    """Build the ingest_host payload for a Wazuh agent."""

    agent_id = str(agent.get("id", "")).strip()
    host_id = agent_id_to_host_id(agent_id)
    return {
        "host_id": host_id,
        "hostname": agent.get("name", host_id),
        "ip": agent.get("ip", ""),
        "os": _os_label(agent),
        "agent_version": agent.get("version", ""),
        "source": "wazuh-webhook",
    }


def get_or_create_host_from_agent(driver: Driver, agent: dict) -> str:
    """Ensure the mapped Host exists and return its deterministic host_id."""

    payload = host_payload_from_agent(agent)
    ingest_host(driver, payload)
    return payload["host_id"]
