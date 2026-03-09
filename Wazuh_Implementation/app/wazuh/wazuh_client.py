"""Thin Wazuh REST API wrapper built on httpx."""

from __future__ import annotations

import time
from typing import Any, Callable

import httpx

from app.wazuh import logger


import os


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


class WazuhClient:
    """Synchronous Wazuh API client with JWT auto-refresh and retry-on-401."""

    TOKEN_TTL_SECONDS = 900
    REFRESH_SKEW_SECONDS = 30

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.token: str | None = None
        self.token_expiry = 0.0
        self._client = httpx.Client(
            base_url=self.base_url,
            verify=False,
            timeout=30.0,
            headers={"Content-Type": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def authenticate(self) -> str:
        response = self._client.post(
            "/security/user/authenticate",
            params={"raw": "true"},
            auth=(self.username, self.password),
        )
        response.raise_for_status()
        self.token = response.text.strip()
        self.token_expiry = time.time() + self.TOKEN_TTL_SECONDS
        logger.info("Authenticated with Wazuh API at %s", self.base_url)
        return self.token

    def _ensure_token(self) -> None:
        refresh_at = self.token_expiry - self.REFRESH_SKEW_SECONDS
        if not self.token or time.time() >= refresh_at:
            logger.info("Wazuh token expired or missing; re-authenticating")
            self.authenticate()

    def _with_auth_retry(self, operation: Callable[[], httpx.Response]) -> httpx.Response:
        try:
            response = operation()
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 401:
                raise
            logger.info("Wazuh API returned 401; re-authenticating and retrying once")
            self.authenticate()
            response = operation()
            response.raise_for_status()
            return response

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        use_token: bool = True,
    ) -> dict[str, Any]:
        def operation() -> httpx.Response:
            headers: dict[str, str] = {}
            if use_token:
                self._ensure_token()
                headers["Authorization"] = f"Bearer {self.token}"
            return self._client.request(
                method,
                path,
                params=params,
                json=json_body,
                headers=headers,
            )

        response = self._with_auth_retry(operation) if use_token else operation()
        if not use_token:
            response.raise_for_status()
        if not response.text:
            return {}
        return response.json()

    @staticmethod
    def _items(payload: dict[str, Any]) -> list[dict]:
        return payload.get("data", {}).get("affected_items", [])

    def get_agents(self) -> list[dict]:
        payload = self._request(
            "GET",
            "/agents",
            params={"status": "active", "limit": 500, "sort": "+id"},
        )
        return self._items(payload)

    def get_agent_packages(self, agent_id: str) -> list[dict]:
        payload = self._request(
            "GET",
            f"/syscollector/{agent_id}/packages",
            params={"limit": 1000},
        )
        return self._items(payload)

    def get_agent_ports(self, agent_id: str) -> list[dict]:
        payload = self._request("GET", f"/syscollector/{agent_id}/ports")
        return self._items(payload)

    def get_agent_vulnerabilities(self, agent_id: str) -> list[dict]:
        payload = self._request(
            "GET",
            f"/vulnerability/{agent_id}",
            params={"limit": 1000},
        )
        return self._items(payload)

    def get_recent_alerts(self, limit: int = 100) -> list[dict]:
        try:
            payload = self._request(
                "GET",
                "/alerts",
                params={"limit": limit, "sort": "-timestamp"},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning("Wazuh /alerts endpoint is unavailable on this stack")
                return []
            raise
        return self._items(payload)

    def trigger_active_response(
        self,
        agent_id: str,
        command: str,
        arguments: list[str],
        *,
        custom: bool = False,
        alert: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "PUT",
            "/active-response",
            params={"agents_list": agent_id},
            json_body={
                "command": command,
                "arguments": arguments,
                "custom": custom,
                "alert": alert or {},
            },
        )

    def get_ar_results(self, agent_id: str, after_ts: str) -> list[dict]:
        alerts = self.get_recent_alerts(limit=200)
        results: list[dict] = []
        for alert in alerts:
            rule = alert.get("rule") or {}
            groups = rule.get("groups") or []
            agent = alert.get("agent") or {}
            timestamp = str(alert.get("timestamp", ""))
            if agent.get("id") != agent_id:
                continue
            if "active_response" not in groups:
                continue
            if after_ts and timestamp and timestamp < after_ts:
                continue
            results.append(alert)
        return results


_CLIENT: WazuhClient | None = None


def get_wazuh_client() -> WazuhClient:
    """Return the process-wide Wazuh API client."""

    global _CLIENT
    if _CLIENT is None:
        _CLIENT = WazuhClient(
            _env("WAZUH_API_URL", "https://wazuh.manager:55000"),
            _env("WAZUH_API_USER", "wazuh-wui"),
            _env("WAZUH_API_PASS", _env("WAZUH_API_PASSWORD", "wazuh-wui")),
        )
    return _CLIENT
