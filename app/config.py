"""
Centralised configuration — loaded from .env via python-dotenv.

Every module imports from here instead of reading os.getenv() directly.
This keeps defaults, types, and validation in one place.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Neo4j ────────────────────────────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# ── Presidio ─────────────────────────────────────────────────────────────────
PRESIDIO_URL = os.getenv("PRESIDIO_URL", "http://localhost:5001")

# ── Crown-jewel / sensitivity thresholds ─────────────────────────────────────
CROWN_JEWEL_THRESHOLD = float(os.getenv("CROWN_JEWEL_THRESHOLD", "0.7"))

# Role bonuses (added to sensitivity to compute importance)
ROLE_BONUS_DB = float(os.getenv("ROLE_BONUS_DB", "0.10"))
ROLE_BONUS_WEB = float(os.getenv("ROLE_BONUS_WEB", "0.05"))
BREADTH_BONUS_MAX = float(os.getenv("BREADTH_BONUS_MAX", "0.10"))

# PII entity types considered high-risk for breadth bonus
HIGH_RISK_PII: set[str] = {
    "US_BANK_NUMBER", "CREDIT_CARD", "US_SSN", "IBAN_CODE",
}

# ── Severity mapping (Core alerts) ──────────────────────────────────────────
SEVERITY_MAP: dict[str, int] = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BANK_CSV_PATH = os.path.join(
    PROJECT_ROOT,
    "cloudFormationScripts-Bank-simulation",
    "ORBIT_simulated_bank.csv",
)
FIXTURES_DIR = os.path.join(PROJECT_ROOT, "fixtures")

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = os.getenv("LOG_DIR", os.path.join(PROJECT_ROOT, ".tmp", "logs"))
