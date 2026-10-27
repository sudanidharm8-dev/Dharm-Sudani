"""
test_routes.py — Integration tests for all API endpoints.

Uses FastAPI's TestClient — no real server needed.
Run with: pytest tests/test_routes.py -v
"""

import pytest
from fastapi.testclient import TestClient

from backend import database as db
from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_db():
    """Reset the in-memory database before every test for isolation."""
    db.reset_all()
    yield
    db.reset_all()


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_health_returns_200(self) -> None:
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_health_returns_version(self) -> None:
        res = client.get("/health")
        assert "version" in res.json()


# ---------------------------------------------------------------------------
# Check-In
# ---------------------------------------------------------------------------

class TestCheckIn:
    def test_valid_checkin_returns_201(self) -> None:
        res = client.post("/api/checkin", json={
            "worker_id": "W001",
            "industry": "construction",
            "zone": "A",
            "shift_type": "morning",
            "daily_wage_inr": 450.0,
        })
        assert res.status_code == 201
        assert "Check-in successful" in res.json()["message"]

    def test_checkin_invalid_industry_rejected(self) -> None:
        res = client.post("/api/checkin", json={
            "worker_id": "W001",
            "industry": "mining",   # Not a valid Literal
            "zone": "A",
            "shift_type": "morning",
            "daily_wage_inr": 450.0,
        })
        assert res.status_code == 422

    def test_checkin_invalid_worker_id_rejected(self) -> None:
        """Worker IDs with special characters must be rejected."""
        res = client.post("/api/checkin", json={
            "worker_id": "w001!",
            "industry": "construction",
            "zone": "A",
            "shift_type": "morning",
            "daily_wage_inr": 450.0,
        })
        assert res.status_code == 422

    def test_checkin_negative_wage_rejected(self) -> None:
        """Negative daily wage must be rejected by Pydantic gt=0."""
        res = client.post("/api/checkin", json={
            "worker_id": "W001",
            "industry": "construction",
            "zone": "A",
            "shift_type": "morning",
            "daily_wage_inr": -100.0,
        })
        assert res.status_code == 422

    def test_list_checkins_returns_200(self) -> None:
        client.post("/api/checkin", json={
            "worker_id": "W002", "industry": "college",
            "zone": "B", "shift_type": "afternoon", "daily_wage_inr": 350.0,
        })
        res = client.get("/api/checkins")
        assert res.status_code == 200
        assert res.json()["total"] == 1


# ---------------------------------------------------------------------------
# Near-Miss
# ---------------------------------------------------------------------------

class TestNearMiss:
    def test_valid_near_miss_returns_201(self) -> None:
        res = client.post("/api/near-miss", json={
            "icon_type": "slipped",
            "zone": "B",
            "industry": "construction",
        })
        assert res.status_code == 201
        assert "ticket_id" in res.json()

    def test_invalid_icon_type_rejected(self) -> None:
        res = client.post("/api/near-miss", json={
            "icon_type": "explosion",   # Not in Literal list
            "zone": "A",
            "industry": "construction",
        })
        assert res.status_code == 422

    def test_list_near_misses_returns_correct_count(self) -> None:
        client.post("/api/near-miss", json={"icon_type": "spark", "zone": "A", "industry": "college"})
        client.post("/api/near-miss", json={"icon_type": "slipped", "zone": "B", "industry": "construction"})
        res = client.get("/api/near-misses")
        assert res.json()["total"] == 2

    def test_near_miss_response_has_ai_classification(self) -> None:
        """Response must include the ai_classification field."""
        res = client.post("/api/near-miss", json={
            "icon_type": "electrical", "zone": "C", "industry": "college"
        })
        assert res.status_code == 201
        assert "ai_classification" in res.json()


# ---------------------------------------------------------------------------
# Mood Pulse
# ---------------------------------------------------------------------------

class TestMood:
    def test_valid_mood_returns_201(self) -> None:
        res = client.post("/api/mood", json={
            "mood": "great", "industry": "construction", "zone": "A"
        })
        assert res.status_code == 201
        assert res.json()["recorded"] is True

    def test_invalid_mood_rejected(self) -> None:
        res = client.post("/api/mood", json={
            "mood": "angry",   # Not in Literal list
            "industry": "college", "zone": "B"
        })
        assert res.status_code == 422

    def test_mood_summary_aggregates_correctly(self) -> None:
        client.post("/api/mood", json={"mood": "great", "industry": "construction", "zone": "A"})
        client.post("/api/mood", json={"mood": "tired", "industry": "construction", "zone": "A"})
        res = client.get("/api/moods")
        assert res.json()["total_responses"] == 2

    def test_mood_summary_groups_by_zone(self) -> None:
        """Mood summary must group responses by industry|zone key."""
        client.post("/api/mood", json={"mood": "okay", "industry": "construction", "zone": "A"})
        client.post("/api/mood", json={"mood": "unhappy", "industry": "college", "zone": "B"})
        res = client.get("/api/moods")
        data = res.json()
        assert "construction|A" in data["by_zone"]
        assert "college|B" in data["by_zone"]

    def test_mood_no_worker_id_stored(self) -> None:
        """Mood entries must not contain worker_id (privacy by design)."""
        client.post("/api/mood", json={"mood": "great", "industry": "construction", "zone": "A"})
        for entry in db.mood_entries:
            assert "worker_id" not in entry


# ---------------------------------------------------------------------------
# Wage Proof
# ---------------------------------------------------------------------------

class TestWageProof:
    def test_log_wage_record_returns_hash(self) -> None:
        res = client.post("/api/wage-record", json={
            "worker_id": "W001",
            "date": "2026-10-01",
            "hours_worked": 8.0,
            "wage_paid_inr": 450.0,
            "industry": "construction",
        })
        assert res.status_code == 201
        assert len(res.json()["hash_fingerprint"]) == 64

    def test_verify_wage_no_mismatch(self) -> None:
        client.post("/api/wage-record", json={
            "worker_id": "W001", "date": "2026-10-01",
            "hours_worked": 8.0, "wage_paid_inr": 450.0, "industry": "construction",
        })
        res = client.post("/api/verify-wages", json={
            "worker_id": "W001", "claimed_total_inr": 450.0
        })
        assert res.status_code == 200
        assert res.json()["status"] == "VERIFIED_OK"

    def test_verify_wage_detects_mismatch(self) -> None:
        client.post("/api/wage-record", json={
            "worker_id": "W002", "date": "2026-10-01",
            "hours_worked": 8.0, "wage_paid_inr": 450.0, "industry": "college",
        })
        res = client.post("/api/verify-wages", json={
            "worker_id": "W002", "claimed_total_inr": 300.0
        })
        assert res.status_code == 200
        assert res.json()["shortfall_inr"] > 0

    def test_verify_unknown_worker_returns_404(self) -> None:
        res = client.post("/api/verify-wages", json={
            "worker_id": "W999", "claimed_total_inr": 450.0
        })
        assert res.status_code == 404

    def test_pdf_download_returns_pdf(self) -> None:
        """PDF endpoint must return Content-Type: application/pdf."""
        client.post("/api/wage-record", json={
            "worker_id": "W001", "date": "2026-10-01",
            "hours_worked": 8.0, "wage_paid_inr": 450.0, "industry": "construction",
        })
        res = client.get("/api/wage-dispute-pdf/W001")
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"

    def test_pdf_download_no_records_returns_404(self) -> None:
        """PDF for a worker with no records must return 404."""
        res = client.get("/api/wage-dispute-pdf/W999")
        assert res.status_code == 404

    def test_pdf_invalid_worker_id_rejected(self) -> None:
        """Path param with invalid characters must be rejected."""
        res = client.get("/api/wage-dispute-pdf/../../etc")
        assert res.status_code in (404, 422)

    def test_hours_exceeding_24_rejected(self) -> None:
        """Hours worked > 24 must be rejected by Pydantic le=24."""
        res = client.post("/api/wage-record", json={
            "worker_id": "W001", "date": "2026-10-01",
            "hours_worked": 25.0, "wage_paid_inr": 450.0, "industry": "construction",
        })
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_dashboard_returns_200(self) -> None:
        res = client.get("/api/dashboard")
        assert res.status_code == 200

    def test_dashboard_has_all_required_keys(self) -> None:
        """Dashboard must expose all expected top-level keys."""
        res = client.get("/api/dashboard")
        data = res.json()
        required_keys = [
            "total_checkins", "checkins_by_industry",
            "total_near_misses", "open_near_misses",
            "total_mood_responses", "total_wage_records",
            "fairness_scores", "recent_near_misses", "recent_checkins",
        ]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"

    def test_dashboard_fairness_scores_both_industries(self) -> None:
        """Fairness scores must be returned for both industries."""
        res = client.get("/api/dashboard")
        fs = res.json()["fairness_scores"]
        assert "construction" in fs
        assert "college" in fs

    def test_dashboard_counts_update_after_checkin(self) -> None:
        """total_checkins must increase after a new check-in."""
        before = client.get("/api/dashboard").json()["total_checkins"]
        client.post("/api/checkin", json={
            "worker_id": "W001", "industry": "construction",
            "zone": "A", "shift_type": "morning", "daily_wage_inr": 450.0,
        })
        after = client.get("/api/dashboard").json()["total_checkins"]
        assert after == before + 1

    def test_dashboard_fairness_pay_accuracy_from_real_data(self) -> None:
        """Pay accuracy in fairness score must reflect actual wage records."""
        # Log a valid wage record for construction
        client.post("/api/wage-record", json={
            "worker_id": "W001", "date": "2026-10-01",
            "hours_worked": 8.0, "wage_paid_inr": 450.0, "industry": "construction",
        })
        res = client.get("/api/dashboard")
        # With one valid record, pay_accuracy should be 1.0 (100%)
        breakdown = res.json()["fairness_scores"]["construction"]["breakdown"]
        assert breakdown["pay_accuracy_pct"] == 100.0


# ---------------------------------------------------------------------------
# AI Insight (chatbot)
# ---------------------------------------------------------------------------

class TestAIInsight:
    def test_ai_insight_returns_200(self) -> None:
        """AI insight endpoint must respond — Gemini returns safe error if no key."""
        res = client.post("/api/ai-insight", json={
            "question": "How many workers checked in today?",
            "industry": "all",
        })
        assert res.status_code == 200
        data = res.json()
        assert "question" in data
        assert "insight" in data

    def test_ai_insight_too_short_question_rejected(self) -> None:
        """Questions under 5 characters must be rejected."""
        res = client.post("/api/ai-insight", json={
            "question": "Hi",
            "industry": "all",
        })
        assert res.status_code == 422

    def test_ai_insight_too_long_question_rejected(self) -> None:
        """Questions over 200 characters must be rejected."""
        res = client.post("/api/ai-insight", json={
            "question": "A" * 201,
            "industry": "all",
        })
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# Admin API Key Authentication
# ---------------------------------------------------------------------------

class TestAdminAuth:
    """Verify that X-Admin-Key header protection works correctly."""

    def test_dashboard_accessible_without_key_when_not_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        When ADMIN_API_KEY is empty (dev default), the dashboard must be
        accessible without any header — so local testing always works.
        """
        from backend.config import settings
        monkeypatch.setattr(settings, "ADMIN_API_KEY", "")
        res = client.get("/api/dashboard")
        assert res.status_code == 200

    def test_dashboard_returns_401_with_wrong_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        When ADMIN_API_KEY is configured, the wrong key must return 401.
        """
        from backend.config import settings
        monkeypatch.setattr(settings, "ADMIN_API_KEY", "secret123")
        res = client.get("/api/dashboard", headers={"X-Admin-Key": "wrongkey"})
        assert res.status_code == 401

    def test_dashboard_returns_200_with_correct_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        When ADMIN_API_KEY is configured, the correct key must grant access.
        """
        from backend.config import settings
        monkeypatch.setattr(settings, "ADMIN_API_KEY", "secret123")
        res = client.get("/api/dashboard", headers={"X-Admin-Key": "secret123"})
        assert res.status_code == 200

    def test_dashboard_returns_401_with_missing_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        When ADMIN_API_KEY is configured, omitting the header must return 401.
        """
        from backend.config import settings
        monkeypatch.setattr(settings, "ADMIN_API_KEY", "secret123")
        res = client.get("/api/dashboard")
        assert res.status_code == 401

    def test_ai_insight_returns_401_with_wrong_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        AI insight must also enforce the admin key when configured.
        """
        from backend.config import settings
        monkeypatch.setattr(settings, "ADMIN_API_KEY", "secret123")
        res = client.post(
            "/api/ai-insight",
            json={"question": "Who is at risk of quitting?", "industry": "all"},
            headers={"X-Admin-Key": "badkey"},
        )
        assert res.status_code == 401
