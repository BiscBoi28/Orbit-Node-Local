"""Event handlers for Wazuh webhook payloads."""

from __future__ import annotations

from neo4j import Driver

from app.graph import get_driver, ingest_vulnerability
from app.wazuh import logger
from app.wazuh.agent_registry import get_or_create_host_from_agent

UPDATE_FIM_HOST = """
MATCH (h:Host {host_id: $host_id})
SET h.last_fim_alert = $timestamp,
    h.last_alert_rule = $rule_description,
    h.last_fim_path = $path,
    h.last_fim_event = $event_type,
    h.last_updated = datetime()
RETURN h.host_id AS host_id
"""

UPDATE_VULN_HOST = """
MATCH (h:Host {host_id: $host_id})
SET h.last_vulnerability_alert = $timestamp,
    h.last_alert_rule = $rule_description,
    h.last_vulnerability_cve = $cve_id,
    h.last_updated = datetime()
RETURN h.host_id AS host_id
"""

UPDATE_AUTH_FAILURE_HOST = """
MATCH (h:Host {host_id: $host_id})
SET h.last_auth_failure = $timestamp,
    h.last_alert_rule = $rule_description,
    h.auth_failures_24h = coalesce(h.auth_failures_24h, 0) + 1,
    h.last_updated = datetime()
RETURN h.auth_failures_24h AS auth_failures_24h
"""

UPDATE_WEB_HOST = """
MATCH (h:Host {host_id: $host_id})
SET h.last_web_alert = $timestamp,
    h.last_alert_rule = $rule_description,
    h.last_updated = datetime()
RETURN h.host_id AS host_id
"""


def _driver() -> Driver:
    return get_driver()


def _agent_from_alert(alert: dict) -> dict:
    agent = alert.get("agent")
    if not isinstance(agent, dict) or not agent.get("id"):
        raise ValueError("alert.agent.id is required")
    return agent


def _rule_from_alert(alert: dict) -> dict:
    rule = alert.get("rule")
    if not isinstance(rule, dict):
        return {}
    return rule


def _timestamp(alert: dict) -> str:
    return str(alert.get("timestamp", ""))


def _parse_cvss(value: object) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def _run_host_update(driver: Driver, query: str, **params: object) -> None:
    with driver.session() as session:
        session.run(query, params).consume()


def handle_fim_event(alert: dict) -> None:
    """Upsert the Host node and stamp the latest FIM alert metadata."""

    driver = _driver()
    agent = _agent_from_alert(alert)
    rule = _rule_from_alert(alert)
    syscheck = alert.get("syscheck") or {}

    host_id = get_or_create_host_from_agent(driver, agent)
    path = str(syscheck.get("path", ""))
    event_type = str(syscheck.get("event", ""))
    rule_description = str(rule.get("description", ""))

    _run_host_update(
        driver,
        UPDATE_FIM_HOST,
        host_id=host_id,
        timestamp=_timestamp(alert),
        rule_description=rule_description,
        path=path,
        event_type=event_type,
    )

    logger.info(
        "FIM event on %s: %s %s",
        agent.get("name", host_id),
        path or "<unknown-path>",
        event_type or "<unknown-event>",
    )


def handle_vulnerability_event(alert: dict) -> None:
    """Translate the Wazuh vulnerability alert into ingest_vulnerability()."""

    driver = _driver()
    agent = _agent_from_alert(alert)
    rule = _rule_from_alert(alert)
    vulnerability = ((alert.get("data") or {}).get("vulnerability")) or {}

    cve_id = str(vulnerability.get("cve", "")).strip()
    if not cve_id:
        raise ValueError("alert.data.vulnerability.cve is required")

    cvss = vulnerability.get("cvss") or {}
    cvss3 = (cvss.get("cvss3") or {}).get("base_score")
    cvss2 = (cvss.get("cvss2") or {}).get("base_score")

    host_id = get_or_create_host_from_agent(driver, agent)
    payload = {
        "host_id": host_id,
        "cve_id": cve_id,
        "cvss": _parse_cvss(cvss3 if cvss3 not in (None, "") else cvss2),
        "published": str(vulnerability.get("publication_time", "")).split("T", 1)[0],
        "summary": vulnerability.get("title")
        or vulnerability.get("rationale", "")
        or str(rule.get("description", "")),
        "severity": vulnerability.get("severity", ""),
        "source": "wazuh-webhook",
    }
    ingest_vulnerability(driver, payload)

    _run_host_update(
        driver,
        UPDATE_VULN_HOST,
        host_id=host_id,
        timestamp=_timestamp(alert),
        rule_description=str(rule.get("description", "")),
        cve_id=cve_id,
    )

    package = vulnerability.get("package") or {}
    logger.info(
        "Vulnerability event on %s: %s %s",
        agent.get("name", host_id),
        cve_id,
        package.get("name", "<unknown-package>"),
    )


def handle_auth_failure(alert: dict) -> None:
    """Increment auth failure metadata for the mapped Host."""

    driver = _driver()
    agent = _agent_from_alert(alert)
    rule = _rule_from_alert(alert)
    host_id = get_or_create_host_from_agent(driver, agent)

    _run_host_update(
        driver,
        UPDATE_AUTH_FAILURE_HOST,
        host_id=host_id,
        timestamp=_timestamp(alert),
        rule_description=str(rule.get("description", "")),
    )

    logger.info(
        "Authentication failure on %s: %s",
        agent.get("name", host_id),
        rule.get("description", ""),
    )


def handle_web_event(alert: dict) -> None:
    """Record the latest web-category alert on the mapped Host."""

    driver = _driver()
    agent = _agent_from_alert(alert)
    rule = _rule_from_alert(alert)
    host_id = get_or_create_host_from_agent(driver, agent)

    _run_host_update(
        driver,
        UPDATE_WEB_HOST,
        host_id=host_id,
        timestamp=_timestamp(alert),
        rule_description=str(rule.get("description", "")),
    )

    logger.info(
        "Web event on %s: %s",
        agent.get("name", host_id),
        rule.get("description", ""),
    )
