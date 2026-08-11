"""Consolidated archive tests — essential regression and safety checks.

Covers: FString safety, bulk array validation, boundary cases,
UTF-16 surrogate pairs, and serialize_bits regressions.
"""
from __future__ import annotations

import struct
import pytest
from io import BytesIO

from uasset_read.archive import ByteArchive, _contains_binary_data
from uasset_read.constants import MAX_ARRAY_COUNT
from uasset_read.exceptions import ParseError


# ---------------------------------------------------------------------------
# 1. FString safety — empty string edge case
# ---------------------------------------------------------------------------

class TestFStringSafety:
    """Verify ByteArchive.read_fstring handles empty strings."""

    def test_empty_fstring(self):
        data = struct.pack("<i", 0)
        ar = ByteArchive(data)
        assert ar.read_fstring() == ""


# ---------------------------------------------------------------------------
# 2. UTF-16 surrogate pairs — supplementary-plane edge cases
# ---------------------------------------------------------------------------

def _encode_utf16(text: str) -> bytes:
    """Encode to UE FString UTF-16-LE format (negative length prefix)."""
    utf16_data = text.encode("utf-16-le") + b"\x00\x00"
    num_code_units = len(utf16_data) // 2
    return struct.pack("<i", -num_code_units) + utf16_data


class TestFStringUTF16EdgeCases:
    """FString UTF-16 decoding with surrogate pairs."""

    def test_emoji_surrogate_pair(self, tmp_path):
        """U+1F600 requires surrogate pair: 0xD83D 0xDE00."""
        text = "\U0001F600"
        path = tmp_path / "test.uasset"
        path.write_bytes(_encode_utf16(text))
        from uasset_read.archive import FArchive
        ar = FArchive(str(path))
        assert ar.read_fstring() == text


# ---------------------------------------------------------------------------
# 3. serialize_bits — bit-level read regressions
# ---------------------------------------------------------------------------

class TestSerializeBitsRegression:
    """Verify serialize_bits byte-count and value correctness (Issue #246)."""

    def test_byte_count_rounds_up(self):
        ar = ByteArchive(b"\x00" * 16)
        assert len(ar.serialize_bits(0xFF, 8)) == 1
        assert len(ar.serialize_bits(0x1FF, 9)) == 2
        assert len(ar.serialize_bits(0xFFFF, 16)) == 2
        assert len(ar.serialize_bits(0xFFFFFFFF, 32)) == 4


# ---------------------------------------------------------------------------
# 4. Boundary seek and overflow — ByteArchive position safety
# ---------------------------------------------------------------------------

class TestBoundarySeekOverflow:
    """ByteArchive seek/read boundary conditions."""

    def test_read_beyond_remaining_raises(self):
        ar = ByteArchive(b"\x00\x01\x02")
        ar.read(2)
        with pytest.raises(ParseError):
            ar.read(2)


# ---------------------------------------------------------------------------
# 5. BulkArray validation — count limits and corrupt headers
# ---------------------------------------------------------------------------

class TestBulkArrayValidation:
    """read_bulk_array defensive checks for sizes and counts."""

    def test_size_mismatch_raises(self):
        data = b"\x00" * 3
        ar = ByteArchive(data)
        with pytest.raises(ParseError, match="Cannot read"):
            ar.read_bulk_array(element_size=4, element_count=2)
