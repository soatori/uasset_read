"""Regression tests for archive.validate_size() (#302).

Verifies that validate_size() does not produce false positives on small
files with reasonable property sizes.  The old heuristic used
max(file_size // 10, 1024) as a hard cap, which broke real assets with
legitimately large properties relative to file size.
"""
import pytest
from uasset_read.archive import ByteArchive


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _archive_at(data_len: int, pos: int = 0) -> ByteArchive:
    """Create a zero-filled ByteArchive of *data_len* bytes with cursor at *pos*."""
    archive = ByteArchive(b'\x00' * data_len, tolerant=False)
    archive.seek(pos)
    return archive


# ---------------------------------------------------------------------------
# Strict mode — negative sizes
# ---------------------------------------------------------------------------

class TestValidateSizeStrictNegative:
    def test_negative_size_raises(self):
        archive = _archive_at(256)
        with pytest.raises(Exception, match="negative"):
            archive.validate_size(-1, context="test")

    def test_zero_size_passes(self):
        archive = _archive_at(256)
        assert archive.validate_size(0, context="test") is True


# ---------------------------------------------------------------------------
# Strict mode — size exceeding remaining bytes
# ---------------------------------------------------------------------------

class TestValidateSizeStrictRemaining:
    def test_size_exactly_remaining_passes(self):
        archive = _archive_at(256)
        assert archive.validate_size(256, context="test") is True

    def test_size_one_over_remaining_raises(self):
        archive = _archive_at(256)
        with pytest.raises(Exception, match="exceeds remaining"):
            archive.validate_size(257, context="test")

    def test_size_after_seek_partial_remaining(self):
        archive = _archive_at(256, pos=200)
        assert archive.validate_size(56, context="test") is True
        with pytest.raises(Exception, match="exceeds remaining"):
            archive.validate_size(57, context="test")


# ---------------------------------------------------------------------------
# Strict mode — reasonable cap (no file-size percentage heuristic, #302)
# ---------------------------------------------------------------------------

class TestValidateSizeStrictReasonableCap:
    def test_size_fills_entire_small_file_passes(self):
        """Property filling entire small file is valid."""
        archive = _archive_at(1_024)
        assert archive.validate_size(1_024, context="test") is True

    def test_size_matches_remaining_after_seek(self):
        """Size exactly matching remaining bytes after partial read passes."""
        archive = _archive_at(10_000, pos=5_000)
        assert archive.validate_size(5_000, context="test") is True

    def test_size_at_max_reasonable_cap_passes(self):
        """100 MB is the default cap."""
        cap = 100 * 1024 * 1024
        archive = _archive_at(cap)
        assert archive.validate_size(cap, context="test") is True

    def test_size_above_max_reasonable_cap_raises(self):
        cap = 100 * 1024 * 1024
        archive = _archive_at(cap + 1_000_000)
        archive.seek(0)
        with pytest.raises(Exception, match="max_reasonable"):
            archive.validate_size(cap + 1, context="test")

    def test_size_exceeding_remaining_raises_before_reasonable_check(self):
        """Remaining-bytes check takes priority over reasonable cap (#302)."""
        archive = _archive_at(10_000)
        # 50 KB exceeds 10 KB remaining — caught by remaining check, not cap
        with pytest.raises(Exception, match="exceeds remaining"):
            archive.validate_size(50_000, context="test")


# ---------------------------------------------------------------------------
# Tolerant mode — returns False instead of raising
# ---------------------------------------------------------------------------

class TestValidateSizeTolerant:
    def test_negative_returns_false(self):
        archive = ByteArchive(b'\x00' * 256, tolerant=True)
        assert archive.validate_size(-1, context="test") is False

    def test_exceeds_remaining_returns_false(self):
        archive = ByteArchive(b'\x00' * 256, tolerant=True)
        assert archive.validate_size(257, context="test") is False

    def test_exceeds_max_reasonable_returns_false(self):
        cap = 100 * 1024 * 1024
        archive = ByteArchive(b'\x00' * (cap + 1_000_000), tolerant=True)
        assert archive.validate_size(cap + 1, context="test") is False

    def test_valid_size_returns_true(self):
        archive = ByteArchive(b'\x00' * 10_000, tolerant=True)
        assert archive.validate_size(5_000, context="test") is True


# ---------------------------------------------------------------------------
# Diagnostics are recorded in tolerant mode
# ---------------------------------------------------------------------------

class TestValidateSizeDiagnostics:
    def test_negative_records_diagnostic(self):
        archive = ByteArchive(b'\x00' * 256, tolerant=True)
        archive.validate_size(-1, context="test")
        diags = archive.get_diagnostics()
        assert any("negative" in d.error for d in diags)

    def test_exceeds_remaining_records_diagnostic(self):
        archive = ByteArchive(b'\x00' * 256, tolerant=True)
        archive.validate_size(257, context="test")
        diags = archive.get_diagnostics()
        assert any("exceeds remaining" in d.error for d in diags)

    def test_exceeds_max_reasonable_records_diagnostic(self):
        cap = 100 * 1024 * 1024
        archive = ByteArchive(b'\x00' * (cap + 1_000_000), tolerant=True)
        archive.validate_size(cap + 1, context="test")
        diags = archive.get_diagnostics()
        assert any("max_reasonable" in d.error for d in diags)
