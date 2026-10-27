"""
test_live.py — Full end-to-end verification using FastAPI TestClient.
Covers every endpoint + HTML pages + security + accessibility markers.
Run: python -m pytest tests/test_live.py -v
"""

import pytest
from fastapi.testclient import TestClient

from backend import database as db
from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset():
    db.reset_all()
    yield
    db.reset_all()


# ── Health ──────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "version" in r.json()


# ── HTML pages + WCAG markers ────────────────────────────────────────────────

def test_worker_html_served():
    r = client.get("/worker.html")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]

def test_worker_html_skip_link():
    r = client.get("/worker.html")
    assert "Skip to main content" in r.text

def test_worker_html_role_main():
    r = client.get("/worker.html")
    assert 'role="main"' in r.text

def test_worker_html_toast_5000ms():
    r = client.get("/worker.html")
    assert "5000" in r.text

def test_worker_html_aria_hidden_emojis():
    r = client.get("/worker.html")
    assert 'aria-hidden="true"' in r.text

def test_admin_html_served():
    r = client.get("/admin.html")
    assert r.status_code == 200

def test_admin_html_skip_link():
    r = client.get("/admin.html")
    assert "Skip to main content" in r.text

def test_admin_html_role_main():
    r = client.get("/admin.html")
    assert 'role="main"' in r.text

def test_root_redirects_to_worker():
    r = client.get("/")
    assert r.status_code == 200

def test_admin_route_served():
    r = client.get("/admin")
    assert r.status_code == 200


# ── Check-In ─────────────────────────────────────────────────────────────────

def _checkin(**kw):
    defaults = dict(worker_id="W001", industry="construction", zone="A",
                    shift_type="morning", daily_wage_inr=500.0)
    defaults.update(kw)
    return client.post("/api/checkin", json=defaults)

def test_checkin_ok():
    r = _checkin()
    assert r.status_code == 201
    assert "Check-in" in r.json()["message"]

def test_checkin_night_college():
    r = _checkin(worker_id="W002", industry="college", shift_type="night")
    assert r.status_code == 201

def test_checkin_bad_industry():
    assert _checkin(industry="mining").status_code == 422

def test_checkin_bad_worker_id():
    assert _checkin(worker_id="w-001!").status_code == 422

def test_checkin_negative_wage():
    assert _checkin(daily_wage_inr=-1).status_code == 422


# ── Near-Miss ────────────────────────────────────────────────────────────────

def _nm(**kw):
    defaults = dict(icon_type="slipped", zone="A", industry="construction")
    defaults.update(kw)
    return client.post("/api/near-miss", json=defaults)

def test_near_miss_ok():
    r = _nm()
    assert r.status_code == 201
    assert r.json()["ticket_id"] > 0

def test_near_miss_has_ai_classification():
    r = _nm()
    assert "ai_classification" in r.json()

def test_near_miss_bad_type():
    assert _nm(icon_type="explosion").status_code == 422


# ── Mood ─────────────────────────────────────────────────────────────────────

def _mood(**kw):
    defaults = dict(mood="great", industry="construction", zone="A")
    defaults.update(kw)
    return client.post("/api/mood", json=defaults)

def test_mood_recorded():
    r = _mood()
    assert r.status_code == 201
    assert r.json()["recorded"] is True

def test_mood_no_worker_id_stored():
    r = _mood()
    assert "worker_id" not in r.json()

def test_mood_bad_value():
    assert _mood(mood="angry").status_code == 422

def test_mood_summary():
    _mood(mood="great"); _mood(mood="tired")
    r = client.get("/api/moods")
    assert r.status_code == 200
    data = r.json()
    assert data["total_responses"] >= 2
    # Check great count in construction zone A
    assert data["by_zone"]["construction|A"]["great"] >= 1


# ── Wage Proof ───────────────────────────────────────────────────────────────

def _wage(**kw):
    defaults = dict(worker_id="W001", date="2026-10-27",
                    hours_worked=8.0, wage_paid_inr=500.0, industry="construction")
    defaults.update(kw)
    return client.post("/api/wage-record", json=defaults)

def test_wage_sealed_hash_64():
    r = _wage()
    assert r.status_code == 201
    assert len(r.json()["hash_fingerprint"]) == 64

def test_wage_negative_rejected():
    assert _wage(wage_paid_inr=-1).status_code == 422

def test_wage_hours_over_24_rejected():
    assert _wage(hours_worked=25).status_code == 422

def test_wage_verify_ok():
    _wage()
    r = client.post("/api/verify-wages", json={"worker_id":"W001","claimed_total_inr":500})
    assert r.status_code == 200
    assert r.json()["tampered_records"] == 0
    assert r.json()["status"] == "VERIFIED_OK"

def test_wage_verify_unknown_404():
    r = client.post("/api/verify-wages", json={"worker_id":"ZZZZ","claimed_total_inr":100})
    assert r.status_code == 404

def test_wage_pdf_ok():
    _wage()
    r = client.get("/api/wage-dispute-pdf/W001")
    assert r.status_code == 200
    assert "pdf" in r.headers["content-type"]
    assert len(r.content) > 200

def test_wage_pdf_no_records_404():
    r = client.get("/api/wage-dispute-pdf/UNKNOWN")
    assert r.status_code == 404

def test_wage_pdf_path_traversal_blocked():
    # TestClient normalises path before routing, so /../../etc becomes a 404.
    # The real protection is the regex pattern=r"^[A-Z0-9]{3,20}$" which
    # rejects lowercase letters, dots and slashes — 422 via a real HTTP client.
    # We test the pattern enforcement with a clearly invalid ID here.
    r = client.get("/api/wage-dispute-pdf/lowercase")
    assert r.status_code == 422


# ── Dashboard ────────────────────────────────────────────────────────────────

def test_dashboard_all_keys():
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    for k in ("total_checkins","total_near_misses","fairness_scores","total_mood_responses"):
        assert k in r.json()

def test_dashboard_fairness_score_range():
    _checkin(); _wage()
    r = client.get("/api/dashboard")
    score = r.json()["fairness_scores"]["construction"]["score"]
    assert 0 <= score <= 100

def test_dashboard_pay_accuracy_from_real_data():
    _checkin(); _wage()
    r = client.get("/api/dashboard")
    assert r.json()["fairness_scores"]["construction"]["breakdown"]["pay_accuracy_pct"] == 100.0


# ── AI Insight ───────────────────────────────────────────────────────────────

def test_ai_insight_ok():
    r = client.post("/api/ai-insight", json={"question":"How many workers are active today?","industry":"all"})
    assert r.status_code == 200
    assert "insight" in r.json()

def test_ai_insight_too_short():
    r = client.post("/api/ai-insight", json={"question":"Hi","industry":"all"})
    assert r.status_code == 422

def test_ai_insight_too_long():
    r = client.post("/api/ai-insight", json={"question":"A"*201,"industry":"all"})
    assert r.status_code == 422


# ── Admin Auth ────────────────────────────────────────────────────────────────

def test_auth_no_key_dev_mode(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "")
    assert client.get("/api/dashboard").status_code == 200

def test_auth_wrong_key_401(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "secret123")
    r = client.get("/api/dashboard", headers={"X-Admin-Key": "wrong"})
    assert r.status_code == 401

def test_auth_correct_key_200(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "secret123")
    r = client.get("/api/dashboard", headers={"X-Admin-Key": "secret123"})
    assert r.status_code == 200

def test_auth_missing_key_401(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "secret123")
    assert client.get("/api/dashboard").status_code == 401
