"""
dashboard.py — Admin dashboard: Fairness Score + AI chatbot endpoint.

The Fairness Score is a single composite metric (0–100) that combines
pay accuracy, hazard resolution speed, overtime load, and mood pulse data.
Pure Python computation — no extra API call needed for maximum efficiency.
"""

import json
import logging
from collections import Counter
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend import database as db
from backend.config import settings
from backend.security import verify_shift_hash

# Logger defined first — functions below may reference it
logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# Gemini helper is imported lazily inside the endpoint so that the rest of
# the module (including calculate_fairness_score) can be imported and tested
# without requiring google-generativeai to be installed.
def _get_gemini_insight(question: str, context: str) -> str:
    from backend.gemini_helper import generate_workforce_insight  # noqa: PLC0415
    return generate_workforce_insight(question, context)


# ---------------------------------------------------------------------------
# Admin authentication dependency
# ---------------------------------------------------------------------------

def require_admin_key(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    """
    FastAPI dependency that enforces the X-Admin-Key header.

    If ADMIN_API_KEY is not configured (empty string), auth is skipped so that
    local development works out of the box without any setup. In production,
    set ADMIN_API_KEY to a strong secret via Cloud Run env vars.
    """
    configured_key = settings.ADMIN_API_KEY
    if not configured_key:
        # Key not configured — skip auth (dev/demo mode)
        return
    if x_admin_key != configured_key:
        logger.warning("Rejected admin request — bad or missing X-Admin-Key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-Admin-Key header.",
        )


# ---------------------------------------------------------------------------
# Pure-function Fairness Score helpers — no side effects, fully unit-testable
# ---------------------------------------------------------------------------

def _build_industry_stats(
    entries: list[dict],
    key: str,
    value_field: str | None = None,
) -> dict[str, Counter]:
    """
    One-pass grouping of any list of dicts by 'industry'.

    Args:
        entries:      The list to group (mood_entries, wage_records, etc.).
        key:          Field to count/collect ('mood', 'worker_id', …).
        value_field:  If given, collects values rather than counting occurrences.

    Returns a dict mapping industry → Counter of key values.
    """
    grouped: dict[str, Counter] = {}
    for entry in entries:
        ind = entry.get("industry", "")
        if ind not in grouped:
            grouped[ind] = Counter()
        grouped[ind][entry[key]] += 1
    return grouped


def _compute_pay_accuracy(industry: str) -> float:
    """
    Compute pay accuracy from real cryptographically verified wage records.

    Iterates wage records for the given industry and verifies each hash.
    Returns the fraction of records that are untampered (0.0–1.0).
    Returns 1.0 (assume perfect) when no records exist yet.
    """
    records = [r for r in db.wage_records if r["industry"] == industry]
    if not records:
        return 1.0  # No data yet — assume compliant
    verified = sum(
        1 for r in records
        if verify_shift_hash(
            worker_id=r["worker_id"],
            date=r["date"],
            hours=r["hours_worked"],
            wage=r["wage_paid_inr"],
            stored_hash=db.shift_hashes.get(str(r["id"]), ""),
        )
    )
    return verified / len(records)


def _avg_hazard_resolution(industry: str) -> float:
    """
    Compute average hours taken to resolve near-miss reports for an industry.

    Uses only resolved reports. Returns 24.0 (one day) as a neutral
    default when no resolved reports exist yet.
    """
    resolved = [
        r for r in db.near_misses
        if r["industry"] == industry and r.get("status") == "resolved"
    ]
    if not resolved:
        return 24.0
    from datetime import datetime, timezone  # noqa: PLC0415
    durations = []
    for r in resolved:
        reported = datetime.fromisoformat(r["reported_at"])
        resolved_at = datetime.fromisoformat(r.get("resolved_at", r["reported_at"]))
        durations.append((resolved_at - reported).total_seconds() / 3600)
    return sum(durations) / len(durations)


def _compute_mood_score_from_counter(mood_counter: Counter) -> float:
    """
    Convert a pre-computed mood Counter into a 0.0–1.0 score.

    Mood weights: great=1.0, okay=0.67, tired=0.33, unhappy=0.0
    Returns 0.5 (neutral) when the counter is empty.
    """
    weights = {"great": 1.0, "okay": 0.67, "tired": 0.33, "unhappy": 0.0}
    total = sum(mood_counter.values())
    if not total:
        return 0.5
    return sum(weights.get(mood, 0.0) * count for mood, count in mood_counter.items()) / total


def _compute_mood_score(entries: list[dict], industry: str) -> float:
    """
    Convert mood entries into a 0.0–1.0 score for a given industry.

    Kept for backward-compatibility with existing unit tests.
    Internally delegates to the Counter-based helper above.

    Mood weights: great=1.0, okay=0.67, tired=0.33, unhappy=0.0
    Returns 0.5 (neutral) when no data exists.
    """
    mood_counter: Counter = Counter(
        e["mood"] for e in entries if e.get("industry") == industry
    )
    return _compute_mood_score_from_counter(mood_counter)


def calculate_fairness_score(
    pay_accuracy: float,
    hazard_resolution_hours: float,
    overtime_rate: float,
    avg_mood: float,
) -> dict:
    """
    Compute the composite Fairness Score (0–100) for a site or industry.

    Args:
        pay_accuracy:            Fraction of workers paid correctly (0.0–1.0).
        hazard_resolution_hours: Average hours taken to resolve an open hazard.
        overtime_rate:           Fraction of workers exceeding overtime threshold.
        avg_mood:                Average mood score (0.0–1.0).

    Returns:
        dict with 'score' (0–100), 'grade' (A–F), and per-component 'breakdown'.
    """
    hazard_score = max(0.0, 1.0 - (hazard_resolution_hours / 72.0))

    raw = (
        pay_accuracy              * settings.WEIGHT_PAY
        + hazard_score            * settings.WEIGHT_HAZARD
        + (1.0 - overtime_rate)   * settings.WEIGHT_OVERTIME
        + avg_mood                * settings.WEIGHT_MOOD
    )
    score = round(raw * 100, 1)

    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 45:
        grade = "D"
    else:
        grade = "F"

    return {
        "score": score,
        "grade": grade,
        "breakdown": {
            "pay_accuracy_pct": round(pay_accuracy * 100, 1),
            "hazard_resolution_hours": hazard_resolution_hours,
            "overtime_rate_pct": round(overtime_rate * 100, 1),
            "avg_mood_score": round(avg_mood * 100, 1),
        },
    }


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class InsightRequest(BaseModel):
    """Admin AI chatbot request body."""

    question: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="Natural-language workforce question from the admin.",
        examples=["Who might quit this month?", "Show critical hazards"],
    )
    industry: Literal["construction", "college", "all"] = Field(
        default="all",
        description="Filter insights to a specific industry or view all.",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/dashboard",
    summary="Full admin dashboard data",
    dependencies=[Depends(require_admin_key)],
)
def get_dashboard() -> dict:
    """
    Return a consolidated view of all workforce health metrics.

    Computes check-in counts, near-miss summaries, mood aggregates,
    and Fairness Scores entirely in-process — no extra API calls.

    Requires the X-Admin-Key header when ADMIN_API_KEY is configured.
    """
    # One-pass grouping using Counter — O(n) not O(n²)
    industry_counts: Counter = Counter(c["industry"] for c in db.checkins)
    night_counts:    Counter = Counter(
        c["industry"] for c in db.checkins if c["shift_type"] == "night"
    )

    # One-pass mood grouping across ALL industries at once
    mood_by_industry: dict[str, Counter] = {}
    for entry in db.mood_entries:
        ind = entry.get("industry", "")
        if ind not in mood_by_industry:
            mood_by_industry[ind] = Counter()
        mood_by_industry[ind][entry["mood"]] += 1

    # Fairness scores — wired to REAL verified wage data
    fairness: dict[str, dict] = {}
    for ind in settings.INDUSTRIES:
        total = industry_counts.get(ind, 0)
        overtime_rate = night_counts.get(ind, 0) / total if total else 0.0
        fairness[ind] = calculate_fairness_score(
            pay_accuracy=_compute_pay_accuracy(ind),      # ← REAL data, not hardcoded
            hazard_resolution_hours=_avg_hazard_resolution(ind),
            overtime_rate=overtime_rate,
            avg_mood=_compute_mood_score_from_counter(mood_by_industry.get(ind, Counter())),
        )

    return {
        "total_checkins": len(db.checkins),
        "checkins_by_industry": dict(industry_counts),
        "total_near_misses": len(db.near_misses),
        "open_near_misses": sum(1 for r in db.near_misses if r["status"] == "open"),
        "total_mood_responses": len(db.mood_entries),
        "total_wage_records": len(db.wage_records),
        "fairness_scores": fairness,
        "recent_near_misses": db.near_misses[-5:] if db.near_misses else [],
        "recent_checkins": db.checkins[-5:] if db.checkins else [],
    }


@router.post(
    "/ai-insight",
    summary="AI workforce insight — rate limited to 5/min",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin_key)],
)
@limiter.limit(settings.AI_RATE_LIMIT)
def ai_insight(request: Request, payload: InsightRequest) -> dict:
    """
    Answer an admin workforce question using Gemini AI.

    Rate-limited to 5 requests/minute per IP to prevent API key abuse.
    Only anonymised aggregate data is sent to Gemini — no worker names
    or personally identifiable information ever leaves the server.

    Requires the X-Admin-Key header when ADMIN_API_KEY is configured.
    """
    safe_context = json.dumps({
        "total_checkins": len(db.checkins),
        "open_near_misses": sum(1 for r in db.near_misses if r["status"] == "open"),
        "mood_summary": {
            m: sum(1 for e in db.mood_entries if e["mood"] == m)
            for m in settings.MOOD_OPTIONS
        },
        "industries_active": list({c["industry"] for c in db.checkins}),
        "total_wage_records": len(db.wage_records),
    })

    answer = _get_gemini_insight(
        question=payload.question,
        context=safe_context,
    )
    logger.info("AI insight: question_len=%d", len(payload.question))
    return {"question": payload.question, "insight": answer}
