"""Pydantic models for Wazuh MCP tool return values."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MCPBaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ToolErrorDetail(MCPBaseModel):
    code: str
    message: str
    action_card_id: str | None = None
    agent_id: str | None = None
    current_status: str | None = None


class ActionCardStateError(Exception):
    """Raised when a tool is invoked against an invalid ActionCard state."""

    def __init__(self, detail: ToolErrorDetail) -> None:
        self.detail = detail
        super().__init__(detail.message)


class HostSummary(MCPBaseModel):
    host_id: str
    hostname: str = ""
    ip: str = ""
    os: str = ""
    vulnerability_count: int = 0
    actioncard_count: int = 0
    max_cvss: float = 0.0


class AgentInfo(MCPBaseModel):
    agent_id: str
    host_id: str
    name: str
    status: str
    ip: str = ""
    version: str = ""
    groups: list[str] = Field(default_factory=list)
    os_name: str = ""
    os_version: str = ""


class AgentsResult(MCPBaseModel):
    source: str
    total: int
    agents: list[AgentInfo]


class VulnerabilityInfo(MCPBaseModel):
    cve_id: str
    title: str = ""
    severity: str = ""
    cvss: float = 0.0
    package_name: str = ""
    package_version: str = ""
    published: str = ""
    detected_at: str = ""
    source: str = ""


class VulnerabilitiesResult(MCPBaseModel):
    source: str
    agent_id: str
    host_id: str
    total: int
    vulnerabilities: list[VulnerabilityInfo]


class CrownJewelInfo(MCPBaseModel):
    host_id: str
    hostname: str = ""
    asset_hash: str
    sensitivity_score: float = 0.0
    pii_types: list[str] = Field(default_factory=list)


class CrownJewelsResult(MCPBaseModel):
    total: int
    items: list[CrownJewelInfo]
    candidate_hosts: list[HostSummary] = Field(default_factory=list)
    note: str = ""


class ActiveAlertInfo(MCPBaseModel):
    alert_id: str
    source: str
    status: str
    summary: str
    timestamp: str = ""
    agent_id: str = ""
    host_id: str = ""
    rule_id: str = ""
    severity: str = ""
    action_card_id: str = ""


class ActiveAlertsResult(MCPBaseModel):
    source: str
    total: int
    alerts: list[ActiveAlertInfo]
    note: str = ""
    used_fallback: bool = False


class PendingActionCardInfo(MCPBaseModel):
    action_id: str
    status: str
    summary: str = ""
    host_ids: list[str] = Field(default_factory=list)
    wazuh_alert_ref: str = ""
    last_updated: str = ""


class PendingActionCardsResult(MCPBaseModel):
    total: int
    actioncards: list[PendingActionCardInfo]


class RelatedActionCardInfo(MCPBaseModel):
    action_id: str
    status: str
    summary: str = ""
    wazuh_alert_ref: str = ""
    last_updated: str = ""


class DataAssetInfo(MCPBaseModel):
    asset_hash: str
    sensitivity_score: float = 0.0
    crown_jewel: bool = False
    pii_types: list[str] = Field(default_factory=list)


class RiskContextResult(MCPBaseModel):
    host: HostSummary
    total_vulnerabilities: int
    pending_actioncards: int
    max_cvss: float
    risk_score: float
    vulnerabilities: list[VulnerabilityInfo]
    related_actioncards: list[RelatedActionCardInfo]
    data_assets: list[DataAssetInfo]
    note: str = ""


class TriggerActiveResponseResult(MCPBaseModel):
    action_card_id: str
    agent_id: str
    host_id: str
    status: str
    command: str
    affected_items: list[str] = Field(default_factory=list)
    message: str = ""
