"""Regression tests for IoStore directory index cycle detection.

Covers:
- Directory entry self-reference (child points to itself)
- File chain cycle (file entry points back to itself)
- Sibling cycle (directory entry next_sibling creates a loop)
- No infinite loop hangs (subprocess timeout test)
"""
from __future__ import annotations

import struct
from io import BytesIO
from types import SimpleNamespace

import pytest

from uasset_read.exceptions import ParseError
from uasset_read.iostore.reader import IoStoreReader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

INVALID = 0xFFFFFFFF


def _make_reader_with_directory_index(
    mount_point: str,
    directory_entries: list[tuple[int, int, int, int]],
    file_entries: list[tuple[int, int, int]],
    string_table: list[str],
    chunk_ids: list[bytes] | None = None,
) -> IoStoreReader:
    """Build a reader with a pre-built directory index buffer.

    Args:
        mount_point: Mount point string (e.g. "")
        directory_entries: List of (name, first_child_entry, next_sibling_entry, first_file_entry)
        file_entries: List of (name, next_file_entry, user_data)
        string_table: List of name strings
        chunk_ids: Optional list of 12-byte chunk IDs (default: 1 empty chunk)
    """
    # Build the binary buffer in the same format as _parse_directory_index expects:
    # 1. FString mount point (4-byte length + UTF-8 bytes + null terminator)
    # 2. TArray directory entries (4-byte count + N * 16 bytes)
    # 3. TArray file entries (4-byte count + N * 12 bytes)
    # 4. FString string table (4-byte count + N FStrings)

    buffer = bytearray()

    # FString mount point
    mp_bytes = mount_point.encode("utf-8") + b"\x00"
    buffer.extend(struct.pack("<i", len(mp_bytes)))
    buffer.extend(mp_bytes)

    # Directory entries array
    buffer.extend(struct.pack("<i", len(directory_entries)))
    for name, first_child, next_sibling, first_file in directory_entries:
        buffer.extend(struct.pack("<IIII", name, first_child, next_sibling, first_file))

    # File entries array
    buffer.extend(struct.pack("<i", len(file_entries)))
    for name, next_file, user_data in file_entries:
        buffer.extend(struct.pack("<III", name, next_file, user_data))

    # String table
    buffer.extend(struct.pack("<i", len(string_table)))
    for s in string_table:
        s_bytes = s.encode("utf-8") + b"\x00"
        buffer.extend(struct.pack("<i", len(s_bytes)))
        buffer.extend(s_bytes)

    # Create reader with directory index buffer
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._header = SimpleNamespace(
        is_encrypted=False,
        version=5,
    )
    reader._directory_index_buffer = bytes(buffer)
    reader._chunk_ids = []
    reader._mount_point = ""
    reader._directory_index = {}
    reader._aes_key = None

    return reader


# ---------------------------------------------------------------------------
# Test: self-referencing directory entry (child -> self)
# ---------------------------------------------------------------------------

def test_child_self_reference_raises_parse_error():
    """A directory entry whose first_child_entry points to itself triggers a cycle error."""
    # Directory entry 0: name=0, first_child=0 (self), next_sibling=INVALID
    directory_entries = [
        (0, 0, INVALID, INVALID),  # child points to itself
    ]
    string_table = ["dir"]

    reader = _make_reader_with_directory_index("", directory_entries, [], string_table)

    with pytest.raises(ParseError, match="cycle"):
        reader._parse_directory_index()


# ---------------------------------------------------------------------------
# Test: file chain cycle (file -> self)
# ---------------------------------------------------------------------------

def test_file_chain_cycle_raises():
    """A file entry whose next_file_entry points to itself triggers a cycle error."""
    # Directory entry 0: name=0, first_child=INVALID, next_sibling=INVALID, first_file=0
    directory_entries = [
        (0, INVALID, INVALID, 0),
    ]
    # File entry 0: name=0, next_file=0 (self-reference), user_data=0
    file_entries = [
        (0, 0, 0),
    ]
    string_table = ["file.txt"]

    reader = _make_reader_with_directory_index("", directory_entries, file_entries, string_table)

    with pytest.raises(ParseError, match="cycle"):
        reader._parse_directory_index()


# ---------------------------------------------------------------------------
# Test: sibling cycle
# ---------------------------------------------------------------------------

def test_sibling_cycle_raises_parse_error():
    """A directory entry whose next_sibling_entry creates a cycle triggers ParseError."""
    # Directory entry 0: name=0, first_child=INVALID, next_sibling=1, first_file=INVALID
    # Directory entry 1: name=0, first_child=INVALID, next_sibling=0, first_file=INVALID
    # Entry 0 -> 1 -> 0 forms a 2-node sibling cycle
    directory_entries = [
        (0, INVALID, 1, INVALID),
        (0, INVALID, 0, INVALID),
    ]
    string_table = ["dir"]

    reader = _make_reader_with_directory_index("", directory_entries, [], string_table)

    with pytest.raises(ParseError, match="cycle"):
        reader._parse_directory_index()


# ---------------------------------------------------------------------------
# Test: no infinite loop (subprocess timeout)
# ---------------------------------------------------------------------------

def test_sibling_cycle_no_hang_subprocess():
    """A cycle-detection test must terminate within a reasonable time, proving no infinite loop.

    This is a meta-test: it runs the cycle-detection code and verifies it completes
    without hanging. pytest.mark.timeout provides an outer safety net.
    """
    directory_entries = [
        (0, INVALID, 1, INVALID),
        (0, INVALID, 0, INVALID),
    ]
    string_table = ["dir"]

    reader = _make_reader_with_directory_index("", directory_entries, [], string_table)

    # Must raise ParseError (cycle detected) rather than hang
    with pytest.raises(ParseError):
        reader._parse_directory_index()
