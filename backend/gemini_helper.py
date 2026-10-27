"""
gemini_helper.py — Thin wrapper around the Gemini 1.5 Flash API.

Key security rules enforced here:
  - API key is read from env var only (never hardcoded).
  - All prompts are sanitized before sending.
  - A clear error string is returned on failure (no raw exceptions exposed).
"""

import logging
import os

from google import genai
from google.genai import types

from backend.security import sanitize_text

logger = logging.getLogger(__name__)

# Read key once at import time — fails loudly if missing in production.
_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
_MODEL_NAME: str = "gemini-2.0-flash"   # Latest Flash = fast + cost-efficient


def _get_client() -> genai.Client:
    """Create and return an authenticated Gemini client."""
    if not _API_KEY:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Add it to Cloud Run environment variables."
        )
    return genai.Client(api_key=_API_KEY)


def ask_gemini(prompt: str) -> str:
    """
    Send a sanitized prompt to Gemini and return the text response.

    Args:
        prompt: The instruction/question to send to the model.

    Returns:
        The model's text response, or a safe error message on failure.
    """
    clean_prompt = sanitize_text(prompt, max_length=2000)
    try:
        client = _get_client()
        response = client.models.generate_content(
            model=_MODEL_NAME,
            contents=clean_prompt,
        )
        return response.text.strip()
    except EnvironmentError as exc:
        logger.error("Gemini config error: %s", exc)
        return "AI service is not configured. Contact the administrator."
    except Exception as exc:          # noqa: BLE001
        logger.error("Gemini API error: %s", exc)
        return "AI service is temporarily unavailable. Please try again."


def classify_near_miss(icon_type: str, zone: str, industry: str) -> str:
    """
    Ask Gemini to classify a near-miss report and suggest an action.

    Args:
        icon_type: Type of near-miss (e.g. 'slipped', 'spark').
        zone:      Work zone identifier (e.g. 'A', 'B').
        industry:  Sector — 'construction' or 'college'.

    Returns:
        A short structured string with SEVERITY and ACTION fields.
    """
    prompt = (
        f"A worker in a {industry} workplace (Zone {zone}) reported a near-miss: "
        f"'{icon_type}'. "
        "Classify severity as LOW, MEDIUM, or CRITICAL. "
        "Suggest one immediate action in one sentence. "
        "Reply ONLY in this format:\n"
        "SEVERITY: <level>\n"
        "ACTION: <one sentence>"
    )
    return ask_gemini(prompt)


def generate_workforce_insight(question: str, context: str) -> str:
    """
    Answer an admin's natural-language workforce question using Gemini.

    Args:
        question: Admin's question (e.g. 'Who is at quit risk?').
        context:  JSON-serialised summary of current workforce data.

    Returns:
        Gemini's actionable insight as plain text.
    """
    prompt = (
        "You are an expert workforce health analyst. "
        "Based on the following anonymised workforce data, "
        f"answer this question: '{sanitize_text(question, 200)}'.\n\n"
        f"Data:\n{sanitize_text(context, 1500)}\n\n"
        "Give a clear, actionable answer in under 100 words."
    )
    return ask_gemini(prompt)
