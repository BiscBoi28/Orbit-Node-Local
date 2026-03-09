"""Typed MCP tools backed by Wazuh and Neo4j."""

from __future__ import annotations

import asyncio
import json
import os
import socket
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
from neo4j import GraphDatabase

from app.wazuh.agent_registry import agent_id_to_host_id
from app.wazuh.wazuh_client import WazuhClient
from wazuh_mcp.types import (
    ActionCardStateError,
    ActiveAlertInfo,
    ActiveAlertsResult,
    AgentsResult,
    AgentInfo,
    CrownJewelInfo,
    CrownJewelsResult,
    DataAssetInfo,
    HostSummary,
    PendingActionCardInfo,
    PendingActionCardsResult,
    RelatedActionCardInfo,
    RiskContextResult,
    ToolErrorDetail,
    TriggerActiveResponseResult,
    VulnerabilityInfo,
    VulnerabilitiesResult,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

FIXTURE_VULNS_PATH = PROJECT_ROOT / "wazuh" / "fixtures" / "vulnerabilities.json"
ACTIVE_RESPONSE_COMMAND = os.getenv("WAZUH_MCP_AR_COMMAND", "!orbit_action.sh")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _can_connect(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _resolve_http_url(url: str, default: str) -> str:
    candidate = (url or default).rstrip("/")
    parsed = urlparse(candidate)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if _can_connect(host, port):
        return candidate
    resolved = parsed._replace(netloc=f"localhost:{port}")
    return urlunparse(resolved).rstrip("/")


def _resolve_neo4j_uri(uri: str, default: str = "bolt://localhost:7687") -> str:
    candidate = uri or default
    parsed = urlparse(candidate)
    host = parsed.hostname or "localhost"
    port = parsed.port or 7687
    if _can_connect(host, port):
        return candidate
    return f"{parsed.scheme or 'bolt'}://localhost:{port}"


@lru_cache(maxsize=1)
def _wazuh_client() -> WazuhClient:
    return WazuhClient(
        _resolve_http_url(_env("WAZUH_API_URL", "https://wazuh.manager:55000"), "https://localhost:55000"),
        _env("WAZUH_API_USER", "wazuh-wui"),
        _env("WAZUH_API_PASS", _env("WAZUH_API_PASSWORD", "wazuh-wui")),
    )


@lru_cache(maxsize=1)
def _driver():
    uri = _resolve_neo4j_uri(_env("NEO4J_URI", "bolt://neo4j:7687"))
    driver = GraphDatabase.driver(uri, auth=(_env("NEO4J_USER", "neo4j"), _env("NEO4J_PASSWORD", "")))
    driver.verify_connectivity()
    return driver


@lru_cache(maxsize=1)
def _graph_labels() -> set[str]:
    with _driver().session() as session:
        record = session.run("CALL db.labels() YIELD label RETURN collect(label) AS labels").single()
    labels = record["labels"] if record else []
    return {str(label) for label in labels}


@lru_cache(maxsize=1)
def _graph_relationship_types() -> set[str]:
    with _driver().session() as session:
        record = session.run(
            "CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) AS rel_types"
        ).single()
    rel_types = record["rel_types"] if record else []
    return {str(rel_type) for rel_type in rel_types}


def _supports_data_assets() -> bool:
    return "DataAsset" in _graph_labels() and "RESIDES_ON" in _graph_relationship_types()


@lru_cache(maxsize=1)
def _fixture_vulnerabilities() -> dict[str, dict]:
    if not FIXTURE_VULNS_PATH.exists():
        return {}
    with FIXTURE_VULNS_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _agent_groups(agent: dict) -> list[str]:
    groups = agent.get("group") or agent.get("groups") or []
    return [str(group) for group in groups]


def _os_name(agent: dict) -> str:
    os_info = agent.get("os") or {}
    return str(os_info.get("name", ""))


def _os_version(agent: dict) -> str:
    os_info = agent.get("os") or {}
    return str(os_info.get("version", ""))


def _map_agent(agent: dict) -> AgentInfo:
    agent_id = str(agent.get("id", ""))
    return AgentInfo(
        agent_id=agent_id,
        host_id=agent_id_to_host_id(agent_id),
        name=str(agent.get("name", agent_id)),
        status=str(agent.get("status", "")),
        ip=str(agent.get("ip", "")),
        version=str(agent.get("version", "")),
        groups=_agent_groups(agent),
        os_name=_os_name(agent),
        os_version=_os_version(agent),
    )


def _vulnerability_payloads(agent_id: str) -> tuple[list[dict], str]:
    live_items = _wazuh_client().get_agent_vulnerabilities(agent_id)
    if live_items:
        return live_items, "wazuh-api"

    fixture = _fixture_vulnerabilities().get(agent_id, {})
    fixture_items = fixture.get("data", {}).get("affected_items", [])
    if fixture_items:
        return fixture_items, "wazuh-fixture"
    return [], "wazuh-api"


def _map_vulnerability(item: dict, source: str) -> VulnerabilityInfo:
    cvss = item.get("cvss3_score")
    if cvss in (None, ""):
        cvss = item.get("cvss2_score", 0.0)
    return VulnerabilityInfo(
        cve_id=str(item.get("cve", "")),
        title=str(item.get("title", "")),
        severity=str(item.get("severity", "")),
        cvss=float(cvss or 0.0),
        package_name=str(item.get("name", "")),
        package_version=str(item.get("version", "")),
        published=str(item.get("published", "")),
        detected_at=str(item.get("detection_time", item.get("updated", ""))),
        source=source,
    )


def _host_candidates(limit: int = 5) -> list[HostSummary]:
    query = """
    MATCH (h:Host)
    OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
    OPTIONAL MATCH (ac:ActionCard)-[:AFFECTS]->(h)
    RETURN h.host_id AS host_id,
           coalesce(h.hostname, '') AS hostname,
           coalesce(h.ip, '') AS ip,
           coalesce(h.os, '') AS os,
           count(DISTINCT v) AS vulnerability_count,
           count(DISTINCT ac) AS actioncard_count,
           max(coalesce(v.cvss, 0.0)) AS max_cvss
    ORDER BY vulnerability_count DESC, actioncard_count DESC, max_cvss DESC, host_id ASC
    LIMIT $limit
    """
    with _driver().session() as session:
        records = session.run(query, {"limit": limit})
        return [HostSummary(**dict(record)) for record in records]


def _status_alerts_fallback(agent_id: str | None, limit: int) -> list[ActiveAlertInfo]:
    host_id = agent_id_to_host_id(agent_id) if agent_id else None
    query = """
    MATCH (ac:ActionCard)-[:AFFECTS]->(h:Host)
    WHERE ac.status IN ['pending', 'approved', 'executing']
      AND ($host_id IS NULL OR h.host_id = $host_id)
    RETURN coalesce(ac.wazuh_alert_ref, 'actioncard::' + ac.action_id) AS alert_id,
           'neo4j-actioncard' AS source,
           ac.status AS status,
           coalesce(ac.summary, '') AS summary,
           toString(ac.last_updated) AS timestamp,
           replace(h.host_id, 'wazuh-agent-', '') AS agent_id,
           h.host_id AS host_id,
           '' AS rule_id,
           '' AS severity,
           ac.action_id AS action_card_id
    ORDER BY ac.last_updated DESC
    LIMIT $limit
    """
    with _driver().session() as session:
        records = session.run(query, {"host_id": host_id, "limit": limit})
        return [ActiveAlertInfo(**dict(record)) for record in records]


def _pending_actioncards_sync() -> PendingActionCardsResult:
    query = """
    MATCH (ac:ActionCard {status: 'pending'})
    OPTIONAL MATCH (ac)-[:AFFECTS]->(h:Host)
    WITH ac, [host_id IN collect(DISTINCT h.host_id) WHERE host_id IS NOT NULL] AS host_ids
    ORDER BY ac.last_updated DESC
    RETURN ac.action_id AS action_id,
           ac.status AS status,
           coalesce(ac.summary, '') AS summary,
           host_ids AS host_ids,
           coalesce(ac.wazuh_alert_ref, '') AS wazuh_alert_ref,
           toString(ac.last_updated) AS last_updated
    """
    with _driver().session() as session:
        records = session.run(query)
        items = [PendingActionCardInfo(**dict(record)) for record in records]
    return PendingActionCardsResult(total=len(items), actioncards=items)


def _get_agents_sync() -> AgentsResult:
    agents = [_map_agent(agent) for agent in _wazuh_client().get_agents()]
    return AgentsResult(source=_wazuh_client().base_url, total=len(agents), agents=agents)


def _get_vulnerabilities_sync(agent_id: str) -> VulnerabilitiesResult:
    items, source = _vulnerability_payloads(agent_id)
    vulnerabilities = [_map_vulnerability(item, source) for item in items if item.get("cve")]
    return VulnerabilitiesResult(
        source=source,
        agent_id=agent_id,
        host_id=agent_id_to_host_id(agent_id),
        total=len(vulnerabilities),
        vulnerabilities=vulnerabilities,
    )


def _get_crown_jewels_sync() -> CrownJewelsResult:
    items: list[CrownJewelInfo] = []
    if _supports_data_assets():
        query = """
        MATCH (d:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(h:Host)
        RETURN h.host_id AS host_id,
               coalesce(h.hostname, '') AS hostname,
               d.asset_hash AS asset_hash,
               coalesce(d.sensitivity_score, 0.0) AS sensitivity_score,
               coalesce(d.pii_types, []) AS pii_types
        ORDER BY d.sensitivity_score DESC
        """
        with _driver().session() as session:
            records = session.run(query)
            items = [CrownJewelInfo(**dict(record)) for record in records]

    note = ""
    candidates: list[HostSummary] = []
    if not items:
        note = "No DataAssets are currently marked as crown jewels in Neo4j."
        candidates = _host_candidates()

    return CrownJewelsResult(total=len(items), items=items, candidate_hosts=candidates, note=note)


def _get_active_alerts_sync(agent_id: str | None, limit: int) -> ActiveAlertsResult:
    alerts = _wazuh_client().get_recent_alerts(limit=limit)
    mapped: list[ActiveAlertInfo] = []
    for alert in alerts:
        agent = alert.get("agent") or {}
        current_agent_id = str(agent.get("id", ""))
        if agent_id and current_agent_id != agent_id:
            continue
        rule = alert.get("rule") or {}
        mapped.append(
            ActiveAlertInfo(
                alert_id=str(alert.get("id", "")),
                source="wazuh-api",
                status="active",
                summary=str(rule.get("description", "")),
                timestamp=str(alert.get("timestamp", "")),
                agent_id=current_agent_id,
                host_id=agent_id_to_host_id(current_agent_id) if current_agent_id else "",
                rule_id=str(rule.get("id", "")),
                severity=str(rule.get("level", "")),
                action_card_id="",
            )
        )

    if mapped:
        return ActiveAlertsResult(
            source="wazuh-api",
            total=len(mapped),
            alerts=mapped[:limit],
            note="",
            used_fallback=False,
        )

    fallback = _status_alerts_fallback(agent_id, limit)
    return ActiveAlertsResult(
        source="neo4j-actioncards",
        total=len(fallback),
        alerts=fallback,
        note="Wazuh /alerts is unavailable on this stack; returning active ActionCards from Neo4j instead.",
        used_fallback=True,
    )


def _get_risk_context_sync(host_id: str) -> RiskContextResult:
    if _supports_data_assets():
        query = """
        MATCH (h:Host {host_id: $host_id})
        OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
        OPTIONAL MATCH (ac:ActionCard)-[:AFFECTS]->(h)
        OPTIONAL MATCH (d:DataAsset)-[:RESIDES_ON]->(h)
        RETURN h.host_id AS host_id,
               coalesce(h.hostname, '') AS hostname,
               coalesce(h.ip, '') AS ip,
               coalesce(h.os, '') AS os,
               collect(DISTINCT CASE
                 WHEN v IS NULL THEN null
                 ELSE {
                   cve_id: v.cve_id,
                   title: coalesce(v.summary, ''),
                   severity: coalesce(v.severity, ''),
                   cvss: coalesce(v.cvss, 0.0)
                 }
               END) AS vulnerabilities,
               collect(DISTINCT CASE
                 WHEN ac IS NULL THEN null
                 ELSE {
                   action_id: ac.action_id,
                   status: ac.status,
                   summary: coalesce(ac.summary, ''),
                   wazuh_alert_ref: coalesce(ac.wazuh_alert_ref, ''),
                   last_updated: toString(ac.last_updated)
                 }
               END) AS actioncards,
               collect(DISTINCT CASE
                 WHEN d IS NULL THEN null
                 ELSE {
                   asset_hash: d.asset_hash,
                   sensitivity_score: coalesce(d.sensitivity_score, 0.0),
                   crown_jewel: coalesce(d.crown_jewel, false),
                   pii_types: coalesce(d.pii_types, [])
                 }
               END) AS data_assets
        """
    else:
        query = """
        MATCH (h:Host {host_id: $host_id})
        OPTIONAL MATCH (h)-[:HAS_VULNERABILITY]->(v:Vulnerability)
        OPTIONAL MATCH (ac:ActionCard)-[:AFFECTS]->(h)
        RETURN h.host_id AS host_id,
               coalesce(h.hostname, '') AS hostname,
               coalesce(h.ip, '') AS ip,
               coalesce(h.os, '') AS os,
               collect(DISTINCT CASE
                 WHEN v IS NULL THEN null
                 ELSE {
                   cve_id: v.cve_id,
                   title: coalesce(v.summary, ''),
                   severity: coalesce(v.severity, ''),
                   cvss: coalesce(v.cvss, 0.0)
                 }
               END) AS vulnerabilities,
               collect(DISTINCT CASE
                 WHEN ac IS NULL THEN null
                 ELSE {
                   action_id: ac.action_id,
                   status: ac.status,
                   summary: coalesce(ac.summary, ''),
                   wazuh_alert_ref: coalesce(ac.wazuh_alert_ref, ''),
                   last_updated: toString(ac.last_updated)
                 }
               END) AS actioncards,
               [] AS data_assets
        """
    with _driver().session() as session:
        record = session.run(query, {"host_id": host_id}).single()

    if record is None:
        raise ValueError(f"Host '{host_id}' not found")

    vulnerabilities = [
        VulnerabilityInfo(
            cve_id=item["cve_id"],
            title=item["title"],
            severity=item["severity"],
            cvss=float(item["cvss"] or 0.0),
            source="neo4j",
        )
        for item in (record["vulnerabilities"] or [])
        if item
    ]
    related_actioncards = [
        RelatedActionCardInfo(**item)
        for item in (record["actioncards"] or [])
        if item
    ]
    data_assets = [
        DataAssetInfo(**item)
        for item in (record["data_assets"] or [])
        if item
    ]

    max_cvss = max((item.cvss for item in vulnerabilities), default=0.0)
    pending_actioncards = sum(1 for item in related_actioncards if item.status == "pending")
    risk_score = round(min(100.0, (max_cvss * 8.0) + (len(vulnerabilities) * 4.0) + (pending_actioncards * 10.0)), 2)

    host = HostSummary(
        host_id=str(record["host_id"]),
        hostname=str(record["hostname"]),
        ip=str(record["ip"]),
        os=str(record["os"]),
        vulnerability_count=len(vulnerabilities),
        actioncard_count=len(related_actioncards),
        max_cvss=max_cvss,
    )

    note = ""
    if not data_assets:
        note = "No DataAssets are currently linked to this host, so risk is driven by vulnerabilities and ActionCards."

    return RiskContextResult(
        host=host,
        total_vulnerabilities=len(vulnerabilities),
        pending_actioncards=pending_actioncards,
        max_cvss=max_cvss,
        risk_score=risk_score,
        vulnerabilities=vulnerabilities,
        related_actioncards=related_actioncards,
        data_assets=data_assets,
        note=note,
    )


def _ensure_actioncard_approved(action_card_id: str) -> dict:
    query = """
    MATCH (ac:ActionCard {action_id: $action_id})-[:AFFECTS]->(h:Host)
    RETURN ac.action_id AS action_id,
           ac.status AS status,
           ac.action_type AS action_type,
           coalesce(ac.summary, '') AS summary,
           h.host_id AS host_id,
           coalesce(h.hostname, '') AS hostname,
           coalesce(h.ip, '') AS ip
    LIMIT 1
    """
    with _driver().session() as session:
        record = session.run(query, {"action_id": action_card_id}).single()

    if record is None:
        raise ActionCardStateError(
            ToolErrorDetail(
                code="actioncard_not_found",
                message=f"ActionCard '{action_card_id}' was not found",
                action_card_id=action_card_id,
            )
        )

    if record["status"] != "approved":
        raise ActionCardStateError(
            ToolErrorDetail(
                code="actioncard_not_approved",
                message=f"ActionCard '{action_card_id}' must be in status 'approved' before active response can run",
                action_card_id=action_card_id,
                current_status=str(record["status"]),
            )
        )

    return dict(record)


def _mark_executing(action_card_id: str) -> None:
    query = """
    MATCH (ac:ActionCard {action_id: $action_id})
    SET ac.status = 'executing',
        ac.execution_started_ts = datetime(),
        ac.last_updated = datetime()
    """
    with _driver().session() as session:
        session.run(query, {"action_id": action_card_id}).consume()


def _trigger_active_response_sync(agent_id: str, action_type: str, action_card_id: str) -> TriggerActiveResponseResult:
    actioncard = _ensure_actioncard_approved(action_card_id)
    expected_host_id = agent_id_to_host_id(agent_id)
    host_id = str(actioncard["host_id"])
    if host_id != expected_host_id:
        raise ActionCardStateError(
            ToolErrorDetail(
                code="agent_host_mismatch",
                message=f"ActionCard '{action_card_id}' targets host '{host_id}', not '{expected_host_id}'",
                action_card_id=action_card_id,
                agent_id=agent_id,
                current_status=str(actioncard["status"]),
            )
        )

    _mark_executing(action_card_id)
    response = _wazuh_client().trigger_active_response(
        agent_id,
        ACTIVE_RESPONSE_COMMAND,
        [
            "ADD",
            "wazuh-mcp",
            str(actioncard["ip"] or "127.0.0.1"),
            f"{action_type}::{action_card_id}::{host_id}",
        ],
        custom=True,
        alert={
            "data": {
                "action_id": action_card_id,
                "host_id": host_id,
                "hostname": str(actioncard["hostname"]),
                "action_type": action_type,
                "summary": str(actioncard["summary"]),
            }
        },
    )
    data = response.get("data", {})
    return TriggerActiveResponseResult(
        action_card_id=action_card_id,
        agent_id=agent_id,
        host_id=host_id,
        status="triggered",
        command=ACTIVE_RESPONSE_COMMAND,
        affected_items=[str(item) for item in data.get("affected_items", [])],
        message=str(response.get("message", "")),
    )


async def get_agents() -> AgentsResult:
    return await asyncio.to_thread(_get_agents_sync)


async def get_vulnerabilities(agent_id: str) -> VulnerabilitiesResult:
    return await asyncio.to_thread(_get_vulnerabilities_sync, agent_id)


async def get_crown_jewels() -> CrownJewelsResult:
    return await asyncio.to_thread(_get_crown_jewels_sync)


async def get_active_alerts(agent_id: str | None = None, limit: int = 20) -> ActiveAlertsResult:
    return await asyncio.to_thread(_get_active_alerts_sync, agent_id, limit)


async def get_pending_actioncards() -> PendingActionCardsResult:
    return await asyncio.to_thread(_pending_actioncards_sync)


async def get_risk_context(host_id: str) -> RiskContextResult:
    return await asyncio.to_thread(_get_risk_context_sync, host_id)


async def trigger_active_response(agent_id: str, action_type: str, action_card_id: str) -> TriggerActiveResponseResult:
    return await asyncio.to_thread(_trigger_active_response_sync, agent_id, action_type, action_card_id)


__all__ = [
    "get_active_alerts",
    "get_agents",
    "get_crown_jewels",
    "get_pending_actioncards",
    "get_risk_context",
    "get_vulnerabilities",
    "trigger_active_response",
]
