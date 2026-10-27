from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
from backend.database import feedbacks
from backend.gemini_helper import get_gemini_response

router = APIRouter()

class FeedbackRequest(BaseModel):
    feedback_text: str
    industry: str

@router.post("/feedback")
def submit_feedback(data: FeedbackRequest):
    """Worker submits anonymous feedback. Gemini does sentiment analysis."""

    prompt = f"""
    Analyze the sentiment of this anonymous worker feedback: "{data.feedback_text}"
    Classify as: POSITIVE, NEUTRAL, or NEGATIVE.
    Extract the main theme in 3 words or less (e.g., "Overtime pressure", "Good management").
    Reply in this format only:
    SENTIMENT: <label>
    THEME: <3 words>
    """
    ai_response = get_gemini_response(prompt)

    record = {
        "id": len(feedbacks) + 1,
        "industry": data.industry,
        "submitted_at": datetime.now().isoformat(),
        "ai_analysis": ai_response
        # NOTE: We do NOT store the original feedback_text to protect anonymity
    }
    feedbacks.append(record)

    return {
        "message": "💬 Feedback submitted anonymously. Your voice matters!",
        "ticket_id": record["id"]
    }

@router.get("/feedbacks")
def get_all_feedbacks():
    """Admin: Get anonymized feedback analysis (no raw text stored)."""
    return {"total": len(feedbacks), "feedbacks": feedbacks}
