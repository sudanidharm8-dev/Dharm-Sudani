"""
test_security.py — Unit tests for the cryptographic wage proof utilities.

Tests cover: hash generation, tamper detection, and input sanitization.
Run with: pytest tests/test_security.py -v
"""

import pytest

from backend.security import generate_shift_hash, sanitize_text, verify_shift_hash


class TestGenerateShiftHash:
    """Tests for generate_shift_hash."""

    def test_returns_64_char_hex_string(self) -> None:
        """SHA-256 digest must always be exactly 64 hex characters."""
        result = generate_shift_hash("W001", "2026-10-01", 8.0, 450.0)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_inputs_produce_same_hash(self) -> None:
        """Hashing is deterministic — same input always yields same output."""
        h1 = generate_shift_hash("W001", "2026-10-01", 8.0, 450.0)
        h2 = generate_shift_hash("W001", "2026-10-01", 8.0, 450.0)
        assert h1 == h2

    def test_different_wage_produces_different_hash(self) -> None:
        """Changing the wage must change the hash (tamper detection)."""
        h_original = generate_shift_hash("W001", "2026-10-01", 8.0, 450.0)
        h_tampered = generate_shift_hash("W001", "2026-10-01", 8.0, 400.0)
        assert h_original != h_tampered

    def test_different_hours_produces_different_hash(self) -> None:
        """Changing hours worked must change the hash."""
        h1 = generate_shift_hash("W001", "2026-10-01", 8.0, 450.0)
        h2 = generate_shift_hash("W001", "2026-10-01", 6.0, 450.0)
        assert h1 != h2

    def test_different_worker_produces_different_hash(self) -> None:
        """Two different workers with same shift data produce different hashes."""
        h1 = generate_shift_hash("W001", "2026-10-01", 8.0, 450.0)
        h2 = generate_shift_hash("W002", "2026-10-01", 8.0, 450.0)
        assert h1 != h2


class TestVerifyShiftHash:
    """Tests for verify_shift_hash."""

    def test_valid_record_returns_true(self) -> None:
        """Untampered record must pass verification."""
        stored = generate_shift_hash("W001", "2026-10-01", 8.0, 450.0)
        assert verify_shift_hash("W001", "2026-10-01", 8.0, 450.0, stored) is True

    def test_tampered_wage_returns_false(self) -> None:
        """Modified wage must fail verification — fraud detected."""
        stored = generate_shift_hash("W001", "2026-10-01", 8.0, 450.0)
        assert verify_shift_hash("W001", "2026-10-01", 8.0, 400.0, stored) is False

    def test_tampered_hours_returns_false(self) -> None:
        """Modified hours must fail verification."""
        stored = generate_shift_hash("W001", "2026-10-01", 8.0, 450.0)
        assert verify_shift_hash("W001", "2026-10-01", 6.0, 450.0, stored) is False

    def test_wrong_stored_hash_returns_false(self) -> None:
        """A completely wrong stored hash must fail."""
        assert verify_shift_hash("W001", "2026-10-01", 8.0, 450.0, "deadbeef") is False


class TestSanitizeText:
    """Tests for sanitize_text."""

    def test_strips_whitespace(self) -> None:
        assert sanitize_text("  hello  ") == "hello"

    def test_enforces_max_length(self) -> None:
        long_text = "a" * 1000
        result = sanitize_text(long_text, max_length=100)
        assert len(result) == 100

    def test_empty_string_returns_empty(self) -> None:
        assert sanitize_text("") == ""
