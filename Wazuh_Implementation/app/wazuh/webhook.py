"""FastAPI router for Wazuh integration events."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.wazuh import logger
from app.wazuh.handlers import (
    handle_auth_failure,
    handle_fim_event,
    handle_vulnerability_event,
    handle_web_event,
)

router = APIRouter(prefix="/webhook", tags=["wazuh"])


def _metadata(alert: dict) -> tuple[str | None, str | None, list[str]]:
    rule = alert.get("rule") or {}
    agent = alert.get("agent") or {}
    groups = rule.get("groups") or []
    if not isinstance(groups, list):
        groups = []
    return rule.get("id"), agent.get("id"), groups


@router.post("/wazuh-event")
async def receive_wazuh_event(request: Request) -> JSONResponse:
    """Receive and process a Wazuh event while always returning HTTP 200."""

    try:
        raw_body = await request.body()
        if not raw_body.strip():
            logger.error("Received empty Wazuh webhook payload")
            return JSONResponse(
                content={"status": "ignored", "detail": "empty payload"}
            )
        alert = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.exception("Failed to decode Wazuh webhook JSON")
        return JSONResponse(content={"status": "ignored", "detail": "invalid json"})
    except Exception:
        logger.exception("Unexpected failure while reading Wazuh webhook payload")
        return JSONResponse(content={"status": "error", "detail": "request read failure"})

    rule_id, agent_id, groups = _metadata(alert)

    try:
        if "syscheck" in groups:
            handle_fim_event(alert)
            handler = "fim"
        elif "vulnerability-detector" in groups:
            handle_vulnerability_event(alert)
            handler = "vulnerability"
        elif "authentication_failed" in groups:
            handle_auth_failure(alert)
            handler = "auth_failure"
        elif "web" in groups:
            handle_web_event(alert)
            handler = "web"
        else:
            logger.info(
                "Ignoring Wazuh event with unsupported groups: rule_id=%s agent_id=%s groups=%s",
                rule_id,
                agent_id,
                groups,
            )
            return JSONResponse(
                content={
                    "status": "ignored",
                    "rule_id": rule_id,
                    "agent_id": agent_id,
                    "groups": groups,
                }
            )
    except Exception:
        logger.exception(
            "Internal Wazuh webhook processing error: rule_id=%s agent_id=%s groups=%s",
            rule_id,
            agent_id,
            groups,
        )
        return JSONResponse(
            content={
                "status": "error",
                "rule_id": rule_id,
                "agent_id": agent_id,
                "groups": groups,
            }
        )

    return JSONResponse(
        content={
            "status": "processed",
            "rule_id": rule_id,
            "agent_id": agent_id,
            "groups": groups,
            "handler": handler,
        }
    )
