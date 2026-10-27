"""
database.py — In-memory data store for the hackathon.

NOTE: For production, replace these lists with Firebase Firestore calls.
The interface (append / read) stays the same — only the storage layer changes.
"""

from typing import Any


# ---------------------------------------------------------------------------
# In-memory collections (acts like Firestore documents for the hackathon)
# ---------------------------------------------------------------------------

checkins: list[dict[str, Any]] = []
near_misses: list[dict[str, Any]] = []
mood_entries: list[dict[str, Any]] = []
shift_hashes: dict[str, str] = {}   # shift_id → SHA-256 hash
wage_records: list[dict[str, Any]] = []


def reset_all() -> None:
    """Clear all collections — used in unit tests only."""
    checkins.clear()
    near_misses.clear()
    mood_entries.clear()
    shift_hashes.clear()
    wage_records.clear()
