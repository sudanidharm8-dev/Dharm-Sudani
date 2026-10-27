"""
test_fairness.py — Unit tests for the Fairness Score calculator.

Tests cover: boundary values, grade assignment, and weight correctness.
Run with: pytest tests/test_fairness.py -v
"""

import pytest

from backend.routes.dashboard import calculate_fairness_score


class TestCalculateFairnessScore:
    """Tests for the pure Fairness Score computation function."""

    def test_perfect_conditions_returns_100(self) -> None:
        """All-optimal inputs must yield 100/100 with grade A."""
        result = calculate_fairness_score(
            pay_accuracy=1.0,
            hazard_resolution_hours=0.0,
            overtime_rate=0.0,
            avg_mood=1.0,
        )
        assert result["score"] == 100.0
        assert result["grade"] == "A"

    def test_worst_conditions_returns_low_score(self) -> None:
        """All-worst inputs must yield a failing score."""
        result = calculate_fairness_score(
            pay_accuracy=0.0,
            hazard_resolution_hours=72.0,
            overtime_rate=1.0,
            avg_mood=0.0,
        )
        assert result["score"] == 0.0
        assert result["grade"] == "F"

    def test_grade_a_threshold(self) -> None:
        """Score >= 90 must return grade A."""
        result = calculate_fairness_score(1.0, 0.0, 0.0, 1.0)
        assert result["grade"] == "A"

    def test_grade_f_threshold(self) -> None:
        """Score < 45 must return grade F."""
        result = calculate_fairness_score(0.0, 72.0, 1.0, 0.0)
        assert result["grade"] == "F"

    def test_breakdown_keys_present(self) -> None:
        """Result must always include all breakdown fields."""
        result = calculate_fairness_score(0.85, 24.0, 0.2, 0.7)
        keys = result["breakdown"].keys()
        assert "pay_accuracy_pct" in keys
        assert "hazard_resolution_hours" in keys
        assert "overtime_rate_pct" in keys
        assert "avg_mood_score" in keys

    def test_hazard_resolution_capped_at_72h(self) -> None:
        """Hazard resolution beyond 72 hours should not drop below 0."""
        result_72 = calculate_fairness_score(0.5, 72.0, 0.5, 0.5)
        result_100 = calculate_fairness_score(0.5, 100.0, 0.5, 0.5)
        # Both should be equal — score capped at 0 for hazard component
        assert result_72["score"] == result_100["score"]

    def test_score_is_between_0_and_100(self) -> None:
        """Score must always be in [0, 100] range."""
        for pay in [0.0, 0.5, 1.0]:
            for hazard in [0.0, 36.0, 72.0]:
                result = calculate_fairness_score(pay, hazard, 0.5, 0.5)
                assert 0.0 <= result["score"] <= 100.0
