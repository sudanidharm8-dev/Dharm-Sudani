from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
from backend.database import hazards
from backend.gemini_helper import get_gemini_response

router = APIRouter()

class HazardRequest(BaseModel):
    description: str    # What the hazard is
    location: str       # Where it is
    industry: str       # Which industry sector

@router.post("/report-hazard")
def report_hazard(data: HazardRequest):
    """Worker reports a safety hazard. Gemini classifies the severity."""

    # Ask Gemini to classify severity
    prompt = f"""
    A worker reported this safety hazard: "{data.description}" at "{data.location}".
    Classify the severity as one of: LOW, MEDIUM, CRITICAL.
    Give a one-line reason. Reply in this format only:
    SEVERITY: <level>
    REASON: <one sentence>
    """
    ai_response = get_gemini_response(prompt)

    record = {
        "id": len(hazards) + 1,
        "description": data.description,
        "location": data.location,
        "industry": data.industry,
        "reported_at": datetime.now().isoformat(),
        "ai_classification": ai_response,
        "status": "open"
    }
    hazards.append(record)

    return {
        "message": f"🛡️ Hazard report #{record['id']} submitted. Thank you for keeping everyone safe!",
        "ticket_id": record["id"],
        "ai_severity": ai_response
    }

@router.get("/hazards")
def get_all_hazards():
    """Admin: Get all hazard reports."""
    return {"total": len(hazards), "hazards": hazards}
