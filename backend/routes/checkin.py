"""
checkin.py — Worker shift check-in endpoint.

Workers register the start of their shift with their zone and industry.
Each check-in is timestamped and stored for payroll and fatigue tracking.
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
# Request / Response schemas
# ---------------------------------------------------------------------------

class CheckInRequest(BaseModel):
    """Validated request body for a worker shift check-in."""

    worker_id: str = Field(
        ...,
        min_length=3,
        max_length=20,
        pattern=r"^[A-Z0-9]+$",
        description="Anonymous worker ID — uppercase letters and digits only.",
        examples=["W001", "WRK42"],
    )
    industry: Literal["construction", "college"] = Field(
        ..., description="Sector the worker belongs to."
    )
    zone: Literal["A", "B", "C", "D"] = Field(
        ..., description="Work zone within the site."
    )
    shift_type: Literal["morning", "afternoon", "night"] = Field(
        ..., description="Shift slot for the day."
    )
    daily_wage_inr: float = Field(
        ..., gt=0, le=10000, description="Agreed daily wage in Indian Rupees."
    )


class CheckInResponse(BaseModel):
    """Response returned after a successful check-in."""

    message: str
    record_id: int
    checked_in_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/checkin",
    response_model=CheckInResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Worker shift check-in",
)
def check_in(payload: CheckInRequest) -> CheckInResponse:
    """
    Record the start of a worker's shift.

    Stores the worker ID, industry, zone, shift type, and timestamp.
    No personally identifiable information beyond the anonymous worker ID
    is collected or stored.
    """
    record: dict = {
        "id": len(db.checkins) + 1,
        "worker_id": payload.worker_id,
        "industry": payload.industry,
        "zone": payload.zone,
        "shift_type": payload.shift_type,
        "daily_wage_inr": payload.daily_wage_inr,
        "checked_in_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    }
    db.checkins.append(record)
    logger.info("Check-in: worker=%s zone=%s", payload.worker_id, payload.zone)

    return CheckInResponse(
        message=f"Check-in successful. Welcome to Zone {payload.zone}!",
        record_id=record["id"],
        checked_in_at=record["checked_in_at"],
    )


@router.get("/checkins", summary="List all check-ins (admin)")
def list_checkins() -> dict:
    """Return all shift check-ins for the admin dashboard."""
    return {"total": len(db.checkins), "checkins": db.checkins}
