"""Wazuh integration helpers for ORC."""

from __future__ import annotations

import logging
import os

from app.config import LOG_DIR, LOG_LEVEL

LOGGER_NAME = "app.wazuh"
LOG_FILE = os.path.join(LOG_DIR, "wazuh_webhook.log")


def get_logger() -> logging.Logger:
    """Return a package logger that always writes to a file."""

    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    os.makedirs(LOG_DIR, exist_ok=True)

    handler = logging.FileHandler(LOG_FILE)
    handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    )

    logger.addHandler(handler)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.propagate = True
    return logger


logger = get_logger()

__all__ = ["logger", "get_logger", "LOG_FILE"]
