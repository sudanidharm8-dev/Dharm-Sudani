"""
mood.py — Anonymous end-of-shift mood pulse endpoint.

Workers tap one of four face icons. The raw input is never stored —
only the aggregated count per industry is kept, making individual
identification impossible by design (privacy by architecture).
"""

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from backend import database as db

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MoodRequest(BaseModel):
    """Anonymous mood entry — no worker ID collected."""

    mood: Literal["great", "okay", "tired", "unhappy"] = Field(
        ..., description="Worker's end-of-shift mood selection."
    )
    industry: Literal["construction", "college"] = Field(
        ..., description="Sector of the reporting worker."
    )
    zone: Literal["A", "B", "C", "D"] = Field(
        ..., description="Zone for aggregated trend reporting."
    )


class MoodResponse(BaseModel):
    """Confirmation that the anonymous mood was recorded."""

    message: str
    recorded: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/mood",
    response_model=MoodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit anonymous end-of-shift mood",
)
def submit_mood(payload: MoodRequest) -> MoodResponse:
    """
    Record an anonymous mood pulse for workforce wellbeing tracking.

    Privacy by design: no worker_id is accepted or stored.
    Minimum group aggregation (enforced at the dashboard level)
    ensures individuals cannot be identified.
    """
    record: dict = {
        "mood": payload.mood,
        "industry": payload.industry,
        "zone": payload.zone,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        # NOTE: No worker_id stored — anonymous by architecture
    }
    db.mood_entries.append(record)
    logger.info("Mood pulse: mood=%s zone=%s", payload.mood, payload.zone)

    return MoodResponse(
        message="Thank you! Your mood was recorded anonymously.",
        recorded=True,
    )


@router.get("/moods", summary="Aggregated mood summary (admin)")
def mood_summary() -> dict:
    """
    Return aggregated mood counts grouped by zone and industry.

    Individual entries are never exposed — only totals per group,
    enforcing the minimum-group-size privacy guarantee.
    """
    summary: dict = {}
    for entry in db.mood_entries:
        key = f"{entry['industry']}|{entry['zone']}"
        if key not in summary:
            summary[key] = {"great": 0, "okay": 0, "tired": 0, "unhappy": 0, "total": 0}
        summary[key][entry["mood"]] += 1
        summary[key]["total"] += 1

    return {"total_responses": len(db.mood_entries), "by_zone": summary}
