"""Wazuh MCP server entrypoint."""

from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP

from wazuh_mcp.tools import (
    get_active_alerts as get_active_alerts_impl,
    get_agents as get_agents_impl,
    get_crown_jewels as get_crown_jewels_impl,
    get_pending_actioncards as get_pending_actioncards_impl,
    get_risk_context as get_risk_context_impl,
    get_vulnerabilities as get_vulnerabilities_impl,
    trigger_active_response as trigger_active_response_impl,
)
from wazuh_mcp.types import (
    ActiveAlertsResult,
    AgentsResult,
    CrownJewelsResult,
    PendingActionCardsResult,
    RiskContextResult,
    TriggerActiveResponseResult,
    VulnerabilitiesResult,
)

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("wazuh_mcp.server")

HOST = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_SERVER_PORT", "8001"))
PATH = os.getenv("MCP_HTTP_PATH", "/mcp")

mcp = FastMCP(
    "Wazuh MCP Server",
    instructions="Typed MCP tools for Wazuh inventory, alerts, risk context, and active response.",
    host=HOST,
    port=PORT,
    streamable_http_path=PATH,
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
async def get_agents() -> AgentsResult:
    return await get_agents_impl()


@mcp.tool()
async def get_vulnerabilities(agent_id: str) -> VulnerabilitiesResult:
    return await get_vulnerabilities_impl(agent_id)


@mcp.tool()
async def get_crown_jewels() -> CrownJewelsResult:
    return await get_crown_jewels_impl()


@mcp.tool()
async def get_active_alerts(agent_id: str | None = None, limit: int = 20) -> ActiveAlertsResult:
    return await get_active_alerts_impl(agent_id=agent_id, limit=limit)


@mcp.tool()
async def get_pending_actioncards() -> PendingActionCardsResult:
    return await get_pending_actioncards_impl()


@mcp.tool()
async def get_risk_context(host_id: str) -> RiskContextResult:
    return await get_risk_context_impl(host_id)


@mcp.tool()
async def trigger_active_response(agent_id: str, action_type: str, action_card_id: str) -> TriggerActiveResponseResult:
    return await trigger_active_response_impl(agent_id, action_type, action_card_id)


def main() -> None:
    logger.info("Wazuh MCP server running on http://%s:%s%s", HOST, PORT, PATH)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
