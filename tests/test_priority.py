"""
Unit tests for D5 Priority Scoring — app/priority.py

These are pure-function tests with no Neo4j or Presidio dependency.
"""

import pytest
from app.priority import (
    compute_sensitivity_score,
    compute_importance_score,
    is_crown_jewel,
    compute_action_priority,
)


# ── compute_sensitivity_score ───────────────────────────────────────────────

class TestSensitivityScore:

    def test_empty_scores(self):
        assert compute_sensitivity_score([]) == 0.0

    def test_single_score(self):
        # 0.6 * 0.8 + 0.4 * 0.8 = 0.8
        assert compute_sensitivity_score([0.8]) == 0.8

    def test_multiple_scores(self):
        scores = [0.2, 0.5, 0.9, 0.3, 0.7]
        # max = 0.9, top5 avg = (0.9+0.7+0.5+0.3+0.2)/5 = 0.52
        # result = 0.6*0.9 + 0.4*0.52 = 0.54 + 0.208 = 0.748
        result = compute_sensitivity_score(scores)
        assert 0.7 <= result <= 0.8

    def test_more_than_five_scores(self):
        scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        # max = 1.0, top5 = [1.0, 0.9, 0.8, 0.7, 0.6], avg = 0.8
        # result = 0.6*1.0 + 0.4*0.8 = 0.6 + 0.32 = 0.92
        result = compute_sensitivity_score(scores)
        assert result == 0.92

    def test_all_zeros(self):
        assert compute_sensitivity_score([0.0, 0.0, 0.0]) == 0.0

    def test_all_ones(self):
        # 0.6*1.0 + 0.4*1.0 = 1.0
        assert compute_sensitivity_score([1.0, 1.0, 1.0]) == 1.0


# ── compute_importance_score ────────────────────────────────────────────────

class TestImportanceScore:

    def test_db_role_bonus(self):
        # sensitivity=0.5 + DB bonus=0.10 = 0.60
        result = compute_importance_score(0.5, "Database Server")
        assert result == 0.6

    def test_web_role_bonus(self):
        # sensitivity=0.5 + Web bonus=0.05 = 0.55
        result = compute_importance_score(0.5, "Web Server")
        assert result == 0.55

    def test_no_role_bonus(self):
        result = compute_importance_score(0.5, "Jump Host")
        assert result == 0.5

    def test_breadth_bonus(self):
        # 2 high-risk types * 0.025 = 0.05
        result = compute_importance_score(
            0.5, "", {"US_BANK_NUMBER", "CREDIT_CARD"}
        )
        assert result == 0.55

    def test_clamped_to_one(self):
        # sensitivity=0.95 + DB bonus=0.10 + breadth=0.10
        result = compute_importance_score(
            0.95, "Database Server",
            {"US_BANK_NUMBER", "CREDIT_CARD", "US_SSN", "IBAN_CODE"}
        )
        assert result == 1.0

    def test_zero_sensitivity(self):
        result = compute_importance_score(0.0)
        assert result == 0.0


# ── is_crown_jewel ──────────────────────────────────────────────────────────

class TestCrownJewel:

    def test_above_threshold(self):
        assert is_crown_jewel(0.8) is True

    def test_at_threshold(self):
        assert is_crown_jewel(0.7) is True

    def test_below_threshold(self):
        assert is_crown_jewel(0.69) is False


# ── compute_action_priority ─────────────────────────────────────────────────

class TestActionPriority:

    def test_critical_crown_jewel(self):
        # HIGH sev(3)*0.5 + importance(0.95)*4*0.5 + 0.5 crown = 1.5+1.9+0.5 = 3.9
        result = compute_action_priority("HIGH", 0.95, True)
        assert result == "CRITICAL"

    def test_high_no_crown(self):
        # HIGH sev(3)*0.5 + importance(0.5)*4*0.5 = 1.5+1.0 = 2.5
        result = compute_action_priority("HIGH", 0.5, False)
        assert result == "HIGH"

    def test_medium(self):
        # MEDIUM sev(2)*0.5 + importance(0.3)*4*0.5 = 1.0+0.6 = 1.6
        result = compute_action_priority("MEDIUM", 0.3, False)
        assert result == "MEDIUM"

    def test_low(self):
        # LOW sev(1)*0.5 + importance(0.0)*4*0.5 = 0.5+0.0 = 0.5
        result = compute_action_priority("LOW", 0.0, False)
        assert result == "LOW"

    def test_unknown_severity_defaults_medium(self):
        # defaults to 2
        result = compute_action_priority("UNKNOWN", 0.5, False)
        assert result in ("MEDIUM", "HIGH")
