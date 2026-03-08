"""
Wazuh Source Stub
==================
Abstract base class + fixture-based implementation for Wazuh integration.

The interface is designed so the real Wazuh API connector can be swapped
in later without changing any ORC code.
"""

import json
import logging
import os
from abc import ABC, abstractmethod

from app.config import FIXTURES_DIR

logger = logging.getLogger(__name__)


class WazuhSource(ABC):
    """Abstract interface for Wazuh data ingestion."""

    @abstractmethod
    def get_hosts(self) -> list[dict]:
        """Return host inventory payloads shaped for ingest_host()."""
        ...

    @abstractmethod
    def get_vulnerabilities(self, host_id: str | None = None) -> list[dict]:
        """Return vulnerability payloads shaped for ingest_vulnerability().
        If host_id is given, filter to that host only.
        """
        ...


class FixtureWazuhSource(WazuhSource):
    """Reads host/vulnerability data from local JSON fixture files."""

    def __init__(self, fixtures_dir: str | None = None):
        self._dir = fixtures_dir or os.path.join(FIXTURES_DIR, "wazuh")

    def _load(self, filename: str) -> list[dict]:
        path = os.path.join(self._dir, filename)
        if not os.path.exists(path):
            logger.warning("Fixture file not found: %s", path)
            return []
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else [data]

    def get_hosts(self) -> list[dict]:
        return self._load("hosts.json")

    def get_vulnerabilities(self, host_id: str | None = None) -> list[dict]:
        vulns = self._load("vulnerabilities.json")
        if host_id:
            vulns = [v for v in vulns if v.get("host_id") == host_id]
        return vulns
