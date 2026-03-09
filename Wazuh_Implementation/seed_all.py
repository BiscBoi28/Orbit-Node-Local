#!/usr/bin/env python3
"""Seed the full ORBIT + Wazuh stack after the containers are ready."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
EXPECTED_SERVICES = {
    "neo4j",
    "presidio",
    "orc",
    "wazuh.indexer",
    "wazuh.manager",
    "wazuh.dashboard",
    "wazuh.agent",
    "wazuh-mcp",
}


@dataclass
class StepResult:
    name: str
    success: bool
    detail: str


def _run_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _compose_status() -> dict[str, dict]:
    result = _run_command("docker", "compose", "ps", "--format", "json")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "docker compose ps failed")

    services: dict[str, dict] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        services[payload["Service"]] = payload
    return services


def _is_ready(payload: dict) -> bool:
    if payload.get("State") != "running":
        return False
    health = payload.get("Health", "")
    return health in {"", "healthy"}


def wait_for_containers_healthy(max_attempts: int = 30, delay_seconds: int = 10) -> StepResult:
    last_detail = "No compose output captured."
    for attempt in range(1, max_attempts + 1):
        try:
            services = _compose_status()
        except Exception as exc:
            last_detail = str(exc)
            time.sleep(delay_seconds)
            continue

        missing = sorted(EXPECTED_SERVICES - set(services))
        statuses = []
        all_ready = not missing

        for service in sorted(EXPECTED_SERVICES & set(services)):
            payload = services[service]
            ready = _is_ready(payload)
            all_ready = all_ready and ready
            health = payload.get("Health") or "running"
            statuses.append(f"{service}={health}")

        if missing:
            statuses.append("missing=" + ",".join(missing))

        last_detail = f"attempt {attempt}/{max_attempts}: " + "; ".join(statuses)
        if all_ready:
            return StepResult("wait_for_health", True, last_detail)

        time.sleep(delay_seconds)

    return StepResult("wait_for_health", False, last_detail)


def run_app_seed() -> StepResult:
    result = _run_command("python3", "-m", "app.seed")
    detail = result.stdout.strip() or result.stderr.strip() or "app.seed completed"
    return StepResult("app_seed", result.returncode == 0, detail)


def run_wazuh_seed() -> StepResult:
    result = _run_command("python3", "wazuh/seed_wazuh.py")
    detail = result.stdout.strip() or result.stderr.strip() or "seed_wazuh.py completed"
    return StepResult("wazuh_seed", result.returncode == 0, detail)


def run_admin_sync() -> StepResult:
    request = urllib.request.Request("http://localhost:8000/admin/sync", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return StepResult("admin_sync", False, f"HTTP request failed: {exc}")
    except Exception as exc:
        return StepResult("admin_sync", False, f"Unexpected sync failure: {exc}")

    return StepResult("admin_sync", True, json.dumps(payload, sort_keys=True))


def print_results(results: list[StepResult]) -> None:
    name_width = max(len("STEP"), *(len(result.name) for result in results))
    status_width = len("RESULT")
    print(f"{'STEP':<{name_width}}  {'RESULT':<{status_width}}  DETAIL")
    print(f"{'-' * name_width}  {'-' * status_width}  {'-' * 60}")
    for result in results:
        status = "PASS" if result.success else "FAIL"
        print(f"{result.name:<{name_width}}  {status:<{status_width}}  {result.detail}")


def main() -> int:
    results = [
        wait_for_containers_healthy(),
        run_app_seed(),
        run_wazuh_seed(),
        run_admin_sync(),
    ]
    print_results(results)
    return 0 if all(result.success for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
