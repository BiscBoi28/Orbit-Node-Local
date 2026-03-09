from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def _load_json(relative_path: str) -> dict:
    with (PROJECT_ROOT / relative_path).open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    import app.main as app_main

    monkeypatch.setattr(app_main, "get_driver", lambda: object())
    monkeypatch.setattr(app_main, "close_driver", lambda: None)

    with TestClient(app_main.app) as test_client:
        yield test_client


def _inventory_harness(monkeypatch: pytest.MonkeyPatch):
    import app.wazuh.inventory_sync as inventory_sync

    inventory_sync._SYNC_STATUS.update(
        {
            "status": "never_run",
            "last_sync_ts": None,
            "counts": {"agents": 0, "packages": 0, "ports": 0, "vulnerabilities": 0},
            "last_error": None,
        }
    )

    state = SimpleNamespace(hosts={}, packages=set(), ports=set(), vulnerabilities=set())

    live_vulns = [
        {
            "cve": "CVE-2024-3094",
            "title": "XZ Utils backdoor allows remote code execution",
            "severity": "Critical",
            "cvss3_score": 10.0,
            "published": "2024-03-29",
        }
    ]
    fallback_vulns = {
        "002": {
            "data": {
                "affected_items": [
                    {
                        "cve": "CVE-2023-44487",
                        "title": "HTTP/2 Rapid Reset Attack",
                        "severity": "High",
                        "cvss3_score": 7.5,
                        "published": "2023-10-10",
                    }
                ]
            }
        }
    }

    class FakeWazuhClient:
        def get_agents(self):
            return [
                {
                    "id": "001",
                    "name": "simulated-bank-host-01",
                    "ip": "172.22.0.7",
                    "version": "Wazuh v4.7.0",
                    "os": {"name": "Ubuntu", "version": "22.04.5 LTS", "platform": "ubuntu"},
                },
                {
                    "id": "002",
                    "name": "simulated-bank-host-02",
                    "ip": "172.22.0.8",
                    "version": "Wazuh v4.7.0",
                    "os": {"name": "Ubuntu", "version": "22.04.5 LTS", "platform": "ubuntu"},
                },
            ]

        def get_agent_packages(self, agent_id: str):
            return [
                {"name": f"pkg-{agent_id}-a", "version": "1.0.0", "vendor": "ORBIT"},
                {"name": f"pkg-{agent_id}-b", "version": "2.0.0", "vendor": "ORBIT"},
            ]

        def get_agent_ports(self, agent_id: str):
            base_port = 8000 if agent_id == "001" else 9000
            return [
                {
                    "protocol": "tcp",
                    "local": {"port": base_port},
                    "process": f"svc-{agent_id}",
                }
            ]

        def get_agent_vulnerabilities(self, agent_id: str):
            return live_vulns if agent_id == "001" else []

    def fake_ingest_host(driver, payload):
        driver.hosts[payload["host_id"]] = dict(payload)
        return payload["host_id"]

    def fake_ingest_application(driver, payload):
        driver.packages.add((payload["host_id"], payload["name"], payload["version"]))
        return f"{payload['host_id']}::{payload['name']}::{payload['version']}"

    def fake_batch_ingest(driver, records, ingest_fn, batch_size=None, fail_fast=False):
        for record in records:
            ingest_fn(driver, record)
        return {"processed": len(records), "failed": 0, "errors": []}

    def fake_ingest_service(driver, payload):
        driver.ports.add((payload["host_id"], payload["name"], payload["port"], payload["proto"]))
        return f"{payload['host_id']}::{payload['port']}"

    def fake_ingest_vulnerability(driver, payload):
        driver.vulnerabilities.add((payload["host_id"], payload["cve_id"]))
        return payload["cve_id"]

    monkeypatch.setattr(inventory_sync, "ingest_host", fake_ingest_host)
    monkeypatch.setattr(inventory_sync, "ingest_application", fake_ingest_application)
    monkeypatch.setattr(inventory_sync, "batch_ingest", fake_batch_ingest)
    monkeypatch.setattr(inventory_sync, "ingest_service", fake_ingest_service)
    monkeypatch.setattr(inventory_sync, "ingest_vulnerability", fake_ingest_vulnerability)
    monkeypatch.setattr(inventory_sync, "_load_fixture_vulnerabilities", lambda: fallback_vulns)

    return inventory_sync, state, FakeWazuhClient()


def test_webhook_receives_fim_event(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import app.wazuh.webhook as webhook

    seen: dict[str, dict] = {}
    monkeypatch.setattr(webhook, "handle_fim_event", lambda alert: seen.setdefault("alert", alert))

    response = client.post("/webhook/wazuh-event", json=_load_json("wazuh/fixtures/fim_event.json"))

    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    assert response.json()["handler"] == "fim"
    assert seen["alert"]["agent"]["id"] == "001"


def test_webhook_receives_vulnerability_event(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import app.wazuh.webhook as webhook

    seen: dict[str, dict] = {}
    monkeypatch.setattr(webhook, "handle_vulnerability_event", lambda alert: seen.setdefault("alert", alert))

    response = client.post("/webhook/wazuh-event", json=_load_json("wazuh/fixtures/vuln_alert.json"))

    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    assert response.json()["handler"] == "vulnerability"
    assert seen["alert"]["data"]["vulnerability"]["cve"] == "CVE-2024-3094"


def test_webhook_always_returns_200(client: TestClient):
    response = client.post(
        "/webhook/wazuh-event",
        content='{"broken": json',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "detail": "invalid json"}


def test_inventory_sync_creates_hosts(monkeypatch: pytest.MonkeyPatch):
    inventory_sync, state, wazuh_client = _inventory_harness(monkeypatch)

    counts = inventory_sync.sync_full_inventory(state, wazuh_client)

    assert counts == {"agents": 2, "packages": 4, "ports": 2, "vulnerabilities": 2}
    assert set(state.hosts) == {"wazuh-agent-001", "wazuh-agent-002"}
    assert inventory_sync.get_sync_status()["status"] == "completed"


def test_inventory_sync_idempotent(monkeypatch: pytest.MonkeyPatch):
    inventory_sync, state, wazuh_client = _inventory_harness(monkeypatch)

    first_counts = inventory_sync.sync_full_inventory(state, wazuh_client)
    host_count_before = len(state.hosts)
    package_count_before = len(state.packages)
    port_count_before = len(state.ports)
    vulnerability_count_before = len(state.vulnerabilities)

    second_counts = inventory_sync.sync_full_inventory(state, wazuh_client)

    assert first_counts == second_counts
    assert len(state.hosts) == host_count_before == 2
    assert len(state.packages) == package_count_before == 4
    assert len(state.ports) == port_count_before == 2
    assert len(state.vulnerabilities) == vulnerability_count_before == 2


def test_actioncard_injection_writes_alert_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import app.wazuh.alert_injector as injector

    log_path = tmp_path / "orbit_alerts.log"
    stored: dict[str, str] = {}

    def store_ref(action_id: str, wazuh_alert_ref: str) -> str:
        stored[action_id] = wazuh_alert_ref
        return wazuh_alert_ref

    monkeypatch.setattr(injector, "ORBIT_ALERTS_LOG", str(log_path))
    monkeypatch.setattr(injector, "_existing_ref", lambda action_id: None)
    monkeypatch.setattr(injector, "_store_ref", store_ref)

    ref = injector.inject_actioncard_as_alert(
        SimpleNamespace(base_url="https://localhost:55000"),
        {
            "action_id": "ORBIT-AC-900",
            "status": "pending",
            "priority": "HIGH",
            "origin": "orbit-core",
            "action_type": "patch_vulnerability",
            "summary": "Patch simulated-bank-host-01",
            "confidence": 0.91,
        },
        {"host_id": "wazuh-agent-001", "hostname": "simulated-bank-host-01"},
    )

    payload = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert ref == "orbit-alert::ORBIT-AC-900"
    assert stored["ORBIT-AC-900"] == ref
    assert payload["orbit_action_id"] == "ORBIT-AC-900"
    assert payload["priority"] == "HIGH"
    assert payload["affected_host"] == "wazuh-agent-001"


def test_active_response_triggered_on_approval(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    import app.main as app_main

    calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr(
        app_main,
        "approve_action",
        lambda driver, action_id, analyst_id, comment: calls.append(("approve", action_id, analyst_id)),
    )
    monkeypatch.setattr(
        app_main,
        "get_primary_affected_host",
        lambda action_id: {"host_id": "wazuh-agent-001", "hostname": "simulated-bank-host-01"},
    )
    monkeypatch.setattr(app_main, "is_wazuh_managed_host", lambda host_id: True)
    monkeypatch.setattr(
        app_main,
        "trigger_active_response",
        lambda action_id, analyst_id="": calls.append(("trigger", action_id, analyst_id)),
    )

    response = client.post(
        "/lifecycle/ORBIT-AC-901/approve",
        json={"analyst_id": "analyst-test", "comment": "Approved"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "action_id": "ORBIT-AC-901",
        "status": "approved",
        "execution": "triggered",
    }
    assert ("approve", "ORBIT-AC-901", "analyst-test") in calls
    assert ("trigger", "ORBIT-AC-901", "analyst-test") in calls


def test_ar_completion_updates_actioncard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import app.wazuh.active_response as active_response

    log_path = tmp_path / "orbit_ar.log"
    log_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-03-09T19:26:25Z",
                "status": "executed",
                "action": "ADD",
                "user": "analyst-test",
                "ip": "172.22.0.7",
                "action_type": "patch_vulnerability",
                "action_card_id": "ORBIT-AC-902",
                "host_id": "wazuh-agent-001",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    recorded: dict[str, str] = {}

    def fake_record_execution_result(driver, action_id, exec_id, outcome, details):
        recorded["action_id"] = action_id
        recorded["exec_id"] = exec_id
        recorded["outcome"] = outcome
        recorded["details"] = details

    monkeypatch.setattr(active_response, "ORBIT_AR_LOG", log_path)
    monkeypatch.setattr(active_response, "get_driver", lambda: object())
    monkeypatch.setattr(active_response, "record_execution_result", fake_record_execution_result)

    active_response.poll_ar_completion("ORBIT-AC-902", start_offset=0, timeout_seconds=1)

    assert recorded["action_id"] == "ORBIT-AC-902"
    assert recorded["exec_id"] == "orbit-ar::ORBIT-AC-902"
    assert recorded["outcome"] == "success"
    assert "ORBIT-AC-902" in recorded["details"]


def test_wazuh_client_token_refresh(monkeypatch: pytest.MonkeyPatch):
    from app.wazuh.wazuh_client import WazuhClient

    class DummyHTTPClient:
        def __init__(self) -> None:
            self.headers_seen: list[dict[str, str]] = []

        def request(self, method, path, params=None, json=None, headers=None):
            self.headers_seen.append(headers or {})
            request = httpx.Request(method, f"https://wazuh.local{path}")
            return httpx.Response(
                200,
                request=request,
                json={"data": {"affected_items": [{"id": "001", "name": "simulated-bank-host-01"}]}},
            )

        def close(self):
            return None

    client = WazuhClient("https://wazuh.local", "user", "pass")
    client._client = DummyHTTPClient()

    auth_calls = {"count": 0}

    def fake_authenticate() -> str:
        auth_calls["count"] += 1
        client.token = f"token-{auth_calls['count']}"
        client.token_expiry = time.time() + client.TOKEN_TTL_SECONDS
        return client.token

    monkeypatch.setattr(client, "authenticate", fake_authenticate)
    client.token = "expired-token"
    client.token_expiry = time.time() - 1

    agents = client.get_agents()

    assert auth_calls["count"] == 1
    assert agents[0]["id"] == "001"
    assert client._client.headers_seen[-1]["Authorization"] == "Bearer token-1"
    client.close()


def test_agent_host_id_mapping_deterministic():
    from app.wazuh.agent_registry import agent_id_to_host_id, host_payload_from_agent

    agent = {
        "id": "001",
        "name": "simulated-bank-host-01",
        "ip": "172.22.0.7",
        "version": "Wazuh v4.7.0",
        "os": {"name": "Ubuntu", "version": "22.04.5 LTS", "platform": "ubuntu"},
    }

    first = agent_id_to_host_id("001")
    second = agent_id_to_host_id("001")
    payload = host_payload_from_agent(agent)

    assert first == second == "wazuh-agent-001"
    assert payload["host_id"] == "wazuh-agent-001"
    assert payload["hostname"] == "simulated-bank-host-01"
