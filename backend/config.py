"""
config.py — All settings loaded from environment variables.
No secrets are ever hardcoded here.
"""

import os


class Settings:
    """Application settings loaded exclusively from environment variables."""

    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    APP_ENV: str = os.environ.get("APP_ENV", "development")
    APP_VERSION: str = os.environ.get("APP_VERSION", "1.0.0")

    # Rate limiting
    AI_RATE_LIMIT: str = "5/minute"
    API_RATE_LIMIT: str = "30/minute"

    # Fairness score weights (must sum to 1.0)
    WEIGHT_PAY: float = 0.30
    WEIGHT_HAZARD: float = 0.25
    WEIGHT_OVERTIME: float = 0.25
    WEIGHT_MOOD: float = 0.20

    # Supported industries
    INDUSTRIES: list[str] = ["construction", "college"]

    # Admin API key — set ADMIN_API_KEY env var to any non-empty secret
    ADMIN_API_KEY: str = os.environ.get("ADMIN_API_KEY", "")

    # Mood options
    MOOD_OPTIONS: list[str] = ["great", "okay", "tired", "unhappy"]

    # Near-miss icon types
    NEAR_MISS_TYPES: list[str] = [
        "slipped",
        "falling_object",
        "spark",
        "chemical_smell",
        "electrical",
        "blocked_exit",
    ]


settings = Settings()
