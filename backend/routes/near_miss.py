"""
near_miss.py — Near-miss safety incident reporting endpoint.

Workers tap a single icon to report something that almost went wrong.
Gemini AI classifies the severity and suggests an immediate action.
No free-text input → no injection risk, no PII exposure.
"""

import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from backend import database as db

def _classify(icon_type: str, zone: str, industry: str) -> str:
    from backend.gemini_helper import classify_near_miss  # noqa: PLC0415
    return classify_near_miss(icon_type, zone, industry)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class NearMissRequest(BaseModel):
    """Strictly enumerated near-miss report — no free text allowed."""

    icon_type: Literal[
        "slipped",
        "falling_object",
        "spark",
        "chemical_smell",
        "electrical",
        "blocked_exit",
    ] = Field(..., description="The type of near-miss that occurred.")
    zone: Literal["A", "B", "C", "D"] = Field(
        ..., description="Zone where the near-miss happened."
    )
    industry: Literal["construction", "college"] = Field(
        ..., description="Sector of the reporting worker."
    )


class NearMissResponse(BaseModel):
    """Response with ticket ID and AI classification."""

    message: str
    ticket_id: int
    ai_classification: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/near-miss",
    response_model=NearMissResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a near-miss safety report",
)
def report_near_miss(payload: NearMissRequest) -> NearMissResponse:
    """
    Accept an icon-based near-miss report and classify it with Gemini AI.

    Because input is strictly enumerated (Literal types), there is zero
    risk of injection attacks or oversized payloads reaching the AI.
    """
    ai_result: str = _classify(
        icon_type=payload.icon_type,
        zone=payload.zone,
        industry=payload.industry,
    )

    record: dict = {
        "id": len(db.near_misses) + 1,
        "icon_type": payload.icon_type,
        "zone": payload.zone,
        "industry": payload.industry,
        "reported_at": datetime.now(timezone.utc).isoformat(),
        "ai_classification": ai_result,
        "status": "open",
    }
    db.near_misses.append(record)
    logger.info(
        "Near-miss reported: type=%s zone=%s industry=%s",
        payload.icon_type, payload.zone, payload.industry,
    )

    return NearMissResponse(
        message=f"Safety report #{record['id']} submitted. Thank you!",
        ticket_id=record["id"],
        ai_classification=ai_result,
    )


@router.get("/near-misses", summary="List all near-miss reports (admin)")
def list_near_misses() -> dict:
    """Return all near-miss reports for the admin safety dashboard."""
    open_count = sum(1 for r in db.near_misses if r["status"] == "open")
    return {
        "total": len(db.near_misses),
        "open": open_count,
        "reports": db.near_misses,
    }
