"""
security.py — Cryptographic utilities for tamper-proof wage records.

Uses only Python's built-in hashlib — zero extra dependencies.
SHA-256 is used to generate an immutable fingerprint for every shift record.
"""

import hashlib
import logging

logger = logging.getLogger(__name__)


def generate_shift_hash(worker_id: str, date: str, hours: float, wage: float) -> str:
    """
    Generate a SHA-256 fingerprint for a single shift record.

    The hash encodes worker_id, date, hours worked, and wage paid.
    Any tampering with these values will produce a different hash,
    making falsification instantly detectable.

    Args:
        worker_id: Anonymous worker identifier (not a real name).
        date:      Shift date in ISO format (YYYY-MM-DD).
        hours:     Total hours worked in this shift.
        wage:      Wage paid for this shift in INR.

    Returns:
        A 64-character hexadecimal SHA-256 hash string.
    """
    raw = f"{worker_id}|{date}|{hours}|{wage}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    logger.debug("Generated hash for worker %s on %s", worker_id, date)
    return digest


def verify_shift_hash(
    worker_id: str,
    date: str,
    hours: float,
    wage: float,
    stored_hash: str,
) -> bool:
    """
    Verify that a stored hash still matches the current record values.

    Returns True if the record is intact, False if tampering is detected.

    Args:
        worker_id:   Anonymous worker identifier.
        date:        Shift date in ISO format.
        hours:       Hours worked.
        wage:        Wage paid.
        stored_hash: The hash saved at the time the record was created.

    Returns:
        True if hashes match (record is untampered), False otherwise.
    """
    computed = generate_shift_hash(worker_id, date, hours, wage)
    return computed == stored_hash


def sanitize_text(text: str, max_length: int = 500) -> str:
    """
    Strip leading/trailing whitespace and enforce a maximum length.

    Prevents oversized payloads from reaching the Gemini API.

    Args:
        text:       Raw input string.
        max_length: Maximum allowed character count.

    Returns:
        Cleaned, length-limited string.
    """
    return text.strip()[:max_length]
