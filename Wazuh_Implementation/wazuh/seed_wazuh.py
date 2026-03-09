#!/usr/bin/env python3
"""Phase 1 Wazuh seeding helper."""

from __future__ import annotations

import base64
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request


BASE_URL = os.getenv("WAZUH_API_URL", "https://localhost:55000").rstrip("/")
USERNAME = os.getenv("WAZUH_API_USER", "wazuh-wui")
PASSWORD = os.getenv("WAZUH_API_PASSWORD", "wazuh-wui")
GROUP_NAME = os.getenv("WAZUH_AGENT_GROUP", "bank-hosts")
AGENT_NAME = os.getenv("WAZUH_AGENT_NAME", "simulated-bank-host-01")
TOKEN_TTL_SECONDS = 840


class WazuhApiError(RuntimeError):
    """Raised when the Wazuh API returns an unexpected error."""


class WazuhClient:
    """Minimal Wazuh API client with JWT refresh support."""

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url
        self.username = username
        self.password = password
        self._token: str | None = None
        self._token_expiry = 0.0
        self._ssl_context = ssl._create_unverified_context()

    def _basic_auth_header(self) -> str:
        raw = f"{self.username}:{self.password}".encode("utf-8")
        encoded = base64.b64encode(raw).decode("ascii")
        return f"Basic {encoded}"

    def authenticate(self) -> str:
        request = urllib.request.Request(
            f"{self.base_url}/security/user/authenticate?raw=true",
            method="POST",
            headers={"Authorization": self._basic_auth_header()},
        )
        try:
            with urllib.request.urlopen(
                request, context=self._ssl_context, timeout=30
            ) as response:
                token = response.read().decode("utf-8").strip()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise WazuhApiError(
                f"Authentication failed with HTTP {exc.code}: {detail or exc.reason}"
            ) from exc

        if not token:
            raise WazuhApiError("Authentication succeeded but no JWT token was returned.")

        self._token = token
        self._token_expiry = time.time() + TOKEN_TTL_SECONDS
        return token

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
        payload: dict[str, object] | None = None,
        retry_on_unauthorized: bool = True,
    ) -> dict:
        if not self._token or time.time() >= self._token_expiry:
            self.authenticate()

        url = f"{self.base_url}{path}"
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            url = f"{url}?{query}"

        headers = {"Authorization": f"Bearer {self._token}"}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(
                request, context=self._ssl_context, timeout=30
            ) as response:
                raw_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 401 and retry_on_unauthorized:
                self.authenticate()
                return self._request(
                    method,
                    path,
                    params=params,
                    payload=payload,
                    retry_on_unauthorized=False,
                )
            raise WazuhApiError(
                f"{method} {path} failed with HTTP {exc.code}: {body or exc.reason}"
            ) from exc

        if not raw_body:
            return {}
        return json.loads(raw_body)

    def get_groups(self) -> list[dict]:
        response = self._request("GET", "/groups")
        return response.get("data", {}).get("affected_items", [])

    def ensure_group(self, group_name: str) -> str:
        groups = self.get_groups()
        if any(group.get("name") == group_name for group in groups):
            return "existing"

        try:
            self._request("POST", "/groups", payload={"group_id": group_name})
        except WazuhApiError:
            groups = self.get_groups()
            if any(group.get("name") == group_name for group in groups):
                return "existing"
            raise
        return "created"

    def get_agent_by_name(self, agent_name: str) -> dict | None:
        response = self._request(
            "GET",
            "/agents",
            params={"name": agent_name, "limit": 10, "sort": "+id"},
        )
        items = response.get("data", {}).get("affected_items", [])
        for item in items:
            if item.get("name") == agent_name:
                return item
        return None

    def assign_agent_to_group(self, agent_id: str, group_name: str) -> None:
        path = f"/agents/{urllib.parse.quote(agent_id)}/group/{urllib.parse.quote(group_name)}"
        self._request("PUT", path)


def print_agent_summary(agent: dict) -> None:
    summary = {
        "id": agent.get("id"),
        "name": agent.get("name"),
        "status": agent.get("status"),
        "ip": agent.get("ip"),
        "groups": agent.get("group", []),
        "version": agent.get("version"),
        "lastKeepAlive": agent.get("lastKeepAlive"),
    }
    print("Agent registration status:")
    print(json.dumps(summary, indent=2))


def main() -> int:
    client = WazuhClient(BASE_URL, USERNAME, PASSWORD)

    print(f"Authenticating to {BASE_URL} ...")
    client.authenticate()
    print("Authenticated successfully.")

    print(f"Checking for group '{GROUP_NAME}' ...")
    group_state = client.ensure_group(GROUP_NAME)
    if group_state == "created":
        print(f"Group '{GROUP_NAME}' created.")
    else:
        print(f"Group '{GROUP_NAME}' already exists.")

    print(f"Looking up agent '{AGENT_NAME}' ...")
    agent = client.get_agent_by_name(AGENT_NAME)
    if agent is None:
        print(f"Agent '{AGENT_NAME}' is not registered.")
        print("Seed complete.")
        return 0

    print_agent_summary(agent)

    groups = agent.get("group", [])
    if GROUP_NAME in groups:
        print(f"Agent '{agent['id']}' is already assigned to '{GROUP_NAME}'.")
    else:
        print(f"Assigning agent '{agent['id']}' to '{GROUP_NAME}' ...")
        client.assign_agent_to_group(agent["id"], GROUP_NAME)
        refreshed_agent = client.get_agent_by_name(AGENT_NAME) or agent
        print_agent_summary(refreshed_agent)
        print(f"Agent '{agent['id']}' assigned to '{GROUP_NAME}'.")

    print("Seed complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
