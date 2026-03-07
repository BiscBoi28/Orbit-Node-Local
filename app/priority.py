"""
D5 — Priority Scoring Formula
===============================
Implements the sensitivity, importance, and action-card priority formulas
from high_level_design.md §Sensitivity and Importance Logic.

All functions are pure — no Neo4j or I/O — easy to unit-test.
"""

from app.config import (
    CROWN_JEWEL_THRESHOLD,
    ROLE_BONUS_DB,
    ROLE_BONUS_WEB,
    BREADTH_BONUS_MAX,
    HIGH_RISK_PII,
    SEVERITY_MAP,
)


# ── Sensitivity ─────────────────────────────────────────────────────────────

def compute_sensitivity_score(chunk_scores: list[float]) -> float:
    """Compute current_sensitivity_score from per-chunk Presidio scores.

    Formula:
        current_sensitivity_score = 0.6 * max_score + 0.4 * avg(top-5)

    Returns 0.0 if no scores provided.
    """
    if not chunk_scores:
        return 0.0
    max_score = max(chunk_scores)
    top_scores = sorted(chunk_scores, reverse=True)[:5]
    avg_top = sum(top_scores) / len(top_scores)
    return round(0.6 * max_score + 0.4 * avg_top, 4)


# ── Importance ──────────────────────────────────────────────────────────────

def _role_bonus(technical_roles: str) -> float:
    """Return role-based bonus from the asset's Technical_Role field."""
    roles = technical_roles.lower() if technical_roles else ""
    if any(kw in roles for kw in ("database", "db", "application server")):
        return ROLE_BONUS_DB
    if "web" in roles:
        return ROLE_BONUS_WEB
    return 0.0


def _breadth_bonus(pii_types: set[str]) -> float:
    """Return breadth bonus based on how many high-risk PII categories exist."""
    high_risk_count = len(pii_types & HIGH_RISK_PII)
    return min(high_risk_count * 0.025, BREADTH_BONUS_MAX)


def compute_importance_score(
    sensitivity: float,
    technical_roles: str = "",
    pii_types: set[str] | None = None,
) -> float:
    """Compute asset_importance_score.

    Formula:
        importance = sensitivity + role_bonus + breadth_bonus
        Clamped to [0.0 .. 1.0].
    """
    if pii_types is None:
        pii_types = set()
    raw = sensitivity + _role_bonus(technical_roles) + _breadth_bonus(pii_types)
    return round(min(max(raw, 0.0), 1.0), 4)


def is_crown_jewel(importance: float) -> bool:
    """Determine crown-jewel status from importance score."""
    return importance >= CROWN_JEWEL_THRESHOLD


# ── Action Card Priority ────────────────────────────────────────────────────

def compute_action_priority(
    base_severity: str,
    importance: float,
    crown_jewel: bool,
) -> str:
    """Combine technical severity with business importance to produce
    a priority label: CRITICAL / HIGH / MEDIUM / LOW.

    Steps:
      1. Map base_severity string to numeric (1–4).
      2. Scale importance to 0–4 range.
      3. Weighted average: 50% severity, 50% importance.
      4. Crown-jewel bump (+0.5).
      5. Threshold: ≥3.0 CRITICAL, ≥2.0 HIGH, ≥1.0 MEDIUM, else LOW.
    """
    sev_score = SEVERITY_MAP.get(base_severity.upper(), 2)
    combined = sev_score * 0.5 + importance * 4 * 0.5
    if crown_jewel:
        combined += 0.5

    if combined >= 3.0:
        return "CRITICAL"
    elif combined >= 2.0:
        return "HIGH"
    elif combined >= 1.0:
        return "MEDIUM"
    return "LOW"
