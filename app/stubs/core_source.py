"""
Core Source Stub
=================
Abstract base class + mock implementation for ORBIT Core integration.

Core sends ActionCards (Contract A) to the Node.
Node sends deltas (Contract B) and subscriptions (Contract C) to Core.
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime

from app.config import FIXTURES_DIR, PROJECT_ROOT

logger = logging.getLogger(__name__)

_MOCK_DIR = os.path.join(PROJECT_ROOT, ".tmp", "core_mock")


class CoreSource(ABC):
    """Abstract interface for ORBIT Core communication."""

    @abstractmethod
    def receive_actioncard(self) -> dict | None:
        """Receive the next ActionCard payload from Core (Contract A).
        Returns None if no more cards available.
        """
        ...

    @abstractmethod
    def send_delta(self, payload: dict) -> bool:
        """Send a delta export to Core (Contract B).
        Returns True on success.
        """
        ...

    @abstractmethod
    def send_subscription(self, payload: dict) -> bool:
        """Send a subscription to Core (Contract C).
        Returns True on success.
        """
        ...


class MockCoreSource(CoreSource):
    """Mock implementation that reads fixtures and stores outputs locally."""

    def __init__(self, fixtures_dir: str | None = None):
        self._alerts_dir = fixtures_dir or os.path.join(FIXTURES_DIR, "alerts")
        self._files = sorted(
            [f for f in os.listdir(self._alerts_dir) if f.endswith(".json")]
        ) if os.path.exists(self._alerts_dir) else []
        self._index = 0

    def receive_actioncard(self) -> dict | None:
        if self._index >= len(self._files):
            return None
        path = os.path.join(self._alerts_dir, self._files[self._index])
        self._index += 1
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        logger.info("Mock Core: read alert fixture %s", path)
        return payload

    def send_delta(self, payload: dict) -> bool:
        os.makedirs(_MOCK_DIR, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        path = os.path.join(_MOCK_DIR, f"delta_{ts}.json")
        with open(path, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        logger.info("Mock Core: delta stored at %s", path)
        return True

    def send_subscription(self, payload: dict) -> bool:
        os.makedirs(_MOCK_DIR, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        path = os.path.join(_MOCK_DIR, f"subscription_{ts}.json")
        with open(path, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        logger.info("Mock Core: subscription stored at %s", path)
        return True
