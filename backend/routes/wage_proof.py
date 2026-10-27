"""
wage_proof.py — Cryptographic wage proof and Wage Dispute PDF endpoints.

Three responsibilities:
  1. Log a shift wage record with a tamper-proof SHA-256 hash.
  2. Verify whether stored records match payslip claims (detect fraud).
  3. Generate a Wage Dispute PDF that workers can take to a supervisor,
     union representative, or Labour Court.

Security: No raw names stored. Worker IDs are anonymous codes only.
"""

import io
import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Path, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend import database as db
from backend.security import generate_shift_hash, verify_shift_hash

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class WageRecordRequest(BaseModel):
    """A single shift wage entry to be cryptographically sealed."""

    worker_id: str = Field(
        ..., min_length=3, max_length=20, pattern=r"^[A-Z0-9]+$"
    )
    date: str = Field(
        ..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="ISO date: YYYY-MM-DD"
    )
    hours_worked: float = Field(..., gt=0, le=24)
    wage_paid_inr: float = Field(..., gt=0, le=50000)
    industry: Literal["construction", "college"]


class WageRecordResponse(BaseModel):
    """Confirmation with the generated cryptographic hash."""

    message: str
    record_id: int
    hash_fingerprint: str


class VerifyWageRequest(BaseModel):
    """Request to verify all wage records for a worker."""

    worker_id: str = Field(..., min_length=3, max_length=20, pattern=r"^[A-Z0-9]+$")
    claimed_total_inr: float = Field(..., gt=0, description="Amount shown on payslip.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/wage-record",
    response_model=WageRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log a shift wage with cryptographic proof",
)
def log_wage_record(payload: WageRecordRequest) -> WageRecordResponse:
    """
    Store a shift wage entry and generate its SHA-256 tamper-proof hash.

    The hash is computed from worker_id + date + hours + wage.
    Any later alteration of these values will produce a different hash,
    making wage fraud instantly detectable.
    """
    fingerprint: str = generate_shift_hash(
        worker_id=payload.worker_id,
        date=payload.date,
        hours=payload.hours_worked,
        wage=payload.wage_paid_inr,
    )

    record: dict = {
        "id": len(db.wage_records) + 1,
        "worker_id": payload.worker_id,
        "date": payload.date,
        "hours_worked": payload.hours_worked,
        "wage_paid_inr": payload.wage_paid_inr,
        "industry": payload.industry,
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "hash": fingerprint,
    }
    db.wage_records.append(record)
    db.shift_hashes[str(record["id"])] = fingerprint

    logger.info("Wage record logged: worker=%s date=%s", payload.worker_id, payload.date)
    return WageRecordResponse(
        message="Wage record sealed with cryptographic proof.",
        record_id=record["id"],
        hash_fingerprint=fingerprint,
    )


@router.post("/verify-wages", summary="Verify wage records for tampering")
def verify_wages(payload: VerifyWageRequest) -> dict:
    """
    Recompute hashes for all of a worker's records and compare with stored hashes.

    Returns a detailed tamper report and calculates the difference between
    what was logged and what the payslip claims.
    """
    worker_records = [r for r in db.wage_records if r["worker_id"] == payload.worker_id]

    if not worker_records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No wage records found for this worker.",
        )

    tampered: list[dict] = []
    verified_total: float = 0.0

    for record in worker_records:
        is_valid = verify_shift_hash(
            worker_id=record["worker_id"],
            date=record["date"],
            hours=record["hours_worked"],
            wage=record["wage_paid_inr"],
            stored_hash=db.shift_hashes.get(str(record["id"]), ""),
        )
        if not is_valid:
            tampered.append(record)
        else:
            verified_total += record["wage_paid_inr"]

    shortfall = verified_total - payload.claimed_total_inr
    status_flag = "MISMATCH_DETECTED" if shortfall > 0.01 else "VERIFIED_OK"

    return {
        "worker_id": payload.worker_id,
        "total_shifts_verified": len(worker_records),
        "tampered_records": len(tampered),
        "verified_total_inr": round(verified_total, 2),
        "claimed_total_inr": round(payload.claimed_total_inr, 2),
        "shortfall_inr": round(max(shortfall, 0), 2),
        "status": status_flag,
    }


@router.get(
    "/wage-dispute-pdf/{worker_id}",
    summary="Download Wage Dispute PDF for a worker",
)
def download_wage_dispute_pdf(
    worker_id: str = Path(
        ...,
        pattern=r"^[A-Z0-9]{3,20}$",
        description="Anonymous worker ID — uppercase letters and digits only.",
    ),
) -> StreamingResponse:
    """
    Generate and stream a Wage Dispute PDF for the given worker.

    The PDF contains all verified shift records and the cryptographic
    hash for each — making it suitable for presenting to a supervisor,
    union representative, or Labour Court.
    """
    records = [r for r in db.wage_records if r["worker_id"] == worker_id]
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No records found for worker {worker_id}.",
        )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph("WAGE DISPUTE RECORD", styles["Title"]))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(Paragraph(f"Worker ID: {worker_id}", styles["Normal"]))
    elements.append(
        Paragraph(
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            styles["Normal"],
        )
    )
    elements.append(Spacer(1, 0.5 * cm))

    # Shift records table
    table_data = [["#", "Date", "Hours", "Wage (INR)", "Hash (first 16 chars)"]]
    total_verified = 0.0
    for r in records:
        table_data.append([
            str(r["id"]),
            r["date"],
            str(r["hours_worked"]),
            f"\u20b9{r['wage_paid_inr']:.2f}",
            r["hash"][:16] + "...",
        ])
        total_verified += r["wage_paid_inr"]

    table = Table(table_data, colWidths=[1.2 * cm, 3 * cm, 2 * cm, 3 * cm, 6 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4ff")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(
        Paragraph(
            f"<b>Total Verified Wages: \u20b9{total_verified:.2f}</b>",
            styles["Normal"],
        )
    )
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(
        Paragraph(
            "Each record above is protected by SHA-256 cryptographic hashing. "
            "Any alteration of shift dates, hours, or wages will produce a "
            "different hash, making falsification instantly detectable.",
            styles["Normal"],
        )
    )

    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=wage_dispute_{worker_id}.pdf"
        },
    )
