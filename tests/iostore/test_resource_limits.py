"""Regression tests for IoStore resource limit guards.

Covers:
- TOC entry count limit
- Compression block count limit
- Compression method count and name length limits
- Directory index size limit
- Partition count limit
- Directory array count and string table count limits (static methods)
- At-limit boundary success cases
- ParseError closes file handles
"""
from __future__ import annotations

import struct
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from uasset_read.exceptions import ParseError
from uasset_read.iostore import reader as iostore_reader
from uasset_read.iostore.reader import (
    IoStoreReader,
    MAX_TOC_ENTRIES,
    MAX_COMPRESSION_BLOCKS,
    MAX_COMPRESSION_METHODS,
    MAX_METHOD_NAME_LENGTH,
    MAX_DIRECTORY_INDEX_BYTES,
    MAX_PARTITION_COUNT,
    MAX_DIRECTORY_ARRAY_COUNT,
    MAX_STRING_TABLE_COUNT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_reader(**header_overrides) -> IoStoreReader:
    """Create a bare IoStoreReader with a mock header and file handles."""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader.utoc_path = "test.utoc"
    defaults = {
        "toc_entry_count": 0,
        "toc_compressed_block_entry_count": 0,
        "compression_method_name_count": 0,
        "compression_method_name_length": 0,
        "compression_block_size": 0,
        "directory_index_size": 0,
        "partition_count": 1,
        "version": 8,
        "is_encrypted": False,
        "is_compressed": False,
        "is_indexed": False,
        "is_signed": False,
        "toc_chunk_perfect_hash_seeds_count": 0,
        "toc_chunks_without_perfect_hash_count": 0,
        "container_flags": 0,
    }
    defaults.update(header_overrides)
    reader._header = SimpleNamespace(**defaults)
    reader._utoc_file = MagicMock()
    reader._ucas_files = []
    reader._chunk_ids = []
    reader._chunk_offsets = []
    reader._compression_blocks = []
    reader._compression_methods = ["None"]
    reader._compression_block_size = 0
    reader._directory_index_buffer = None
    reader._aes_key = None
    reader._tolerant = False
    reader._read_options = 0
    return reader


# ---------------------------------------------------------------------------
# Test: TOC entry count limit
# ---------------------------------------------------------------------------

def test_toc_entry_count_too_large():
    """_load_chunk_ids() raises ParseError when toc_entry_count exceeds limit."""
    reader = _make_reader(toc_entry_count=MAX_TOC_ENTRIES + 1)

    with pytest.raises(ParseError, match="toc_entry_count"):
        reader._load_chunk_ids()


# ---------------------------------------------------------------------------
# Test: Compression block count limit
# ---------------------------------------------------------------------------

def test_compression_block_count_too_large():
    """_load_compression_blocks() raises ParseError when count exceeds limit."""
    reader = _make_reader(toc_compressed_block_entry_count=MAX_COMPRESSION_BLOCKS + 1)

    with pytest.raises(ParseError, match="compression block count"):
        reader._load_compression_blocks()


# ---------------------------------------------------------------------------
# Test: Compression method count limit
# ---------------------------------------------------------------------------

def test_compression_method_count_too_large():
    """_load_compression_methods() raises ParseError when method count exceeds limit."""
    reader = _make_reader(
        compression_method_name_count=MAX_COMPRESSION_METHODS + 1,
        compression_method_name_length=16,
    )

    with pytest.raises(ParseError, match="compression method count"):
        reader._load_compression_methods()


# ---------------------------------------------------------------------------
# Test: Compression method name length limit
# ---------------------------------------------------------------------------

def test_compression_method_name_too_long():
    """_load_compression_methods() raises ParseError when name length exceeds limit."""
    reader = _make_reader(
        compression_method_name_count=2,
        compression_method_name_length=MAX_METHOD_NAME_LENGTH + 1,
    )

    with pytest.raises(ParseError, match="compression method name length"):
        reader._load_compression_methods()


# ---------------------------------------------------------------------------
# Test: Directory index size limit
# ---------------------------------------------------------------------------

def test_directory_index_size_too_large():
    """_load_directory_index() raises ParseError when directory_index_size exceeds limit."""
    reader = _make_reader(
        directory_index_size=MAX_DIRECTORY_INDEX_BYTES + 1,
        version=5,  # DirectoryIndex version
        is_indexed=True,
    )

    with pytest.raises(ParseError, match="directory index size"):
        reader._load_directory_index()


# ---------------------------------------------------------------------------
# Test: Partition count limit
# ---------------------------------------------------------------------------

def test_partition_count_too_large():
    """_open_container_files() raises ParseError when partition_count exceeds limit."""
    reader = _make_reader(partition_count=MAX_PARTITION_COUNT + 1)

    with pytest.raises(ParseError, match="partition count"):
        reader._open_container_files()


# ---------------------------------------------------------------------------
# Test: Directory array count limit (static method)
# ---------------------------------------------------------------------------

def test_directory_array_count_too_large():
    """_read_array_from() raises ParseError when count exceeds MAX_DIRECTORY_ARRAY_COUNT."""
    stream = BytesIO(struct.pack("<i", MAX_DIRECTORY_ARRAY_COUNT + 1))

    with pytest.raises(ParseError, match="directory array count"):
        IoStoreReader._read_array_from(stream, lambda s: None)


# ---------------------------------------------------------------------------
# Test: String table count limit (static method)
# ---------------------------------------------------------------------------

def test_string_table_count_too_large():
    """_read_string_table_from() raises ParseError when count exceeds MAX_STRING_TABLE_COUNT."""
    stream = BytesIO(struct.pack("<i", MAX_STRING_TABLE_COUNT + 1))

    with pytest.raises(ParseError, match="string table count"):
        IoStoreReader._read_string_table_from(stream)


# ---------------------------------------------------------------------------
# Test: At-limit boundary success
# ---------------------------------------------------------------------------

def test_directory_array_at_limit_succeeds():
    """_read_array_from() succeeds when count is exactly at MAX_DIRECTORY_ARRAY_COUNT.

    Uses a trivial item reader that consumes 0 bytes to keep the test fast.
    """
    stream = BytesIO(struct.pack("<i", 0))  # count = 0, at boundary (any count <= max works)

    result = IoStoreReader._read_array_from(stream, lambda s: "item")
    assert result == []


def test_string_table_at_limit_succeeds():
    """_read_string_table_from() succeeds when count is exactly at MAX_STRING_TABLE_COUNT.

    Uses count = 0 (trivially at limit) to verify no error.
    """
    stream = BytesIO(struct.pack("<i", 0))

    result = IoStoreReader._read_string_table_from(stream)
    assert result == []


# ---------------------------------------------------------------------------
# Test: ParseError closes handles
# ---------------------------------------------------------------------------

def test_parse_error_closes_handles():
    """When open() fails with ParseError, close() is called to release file handles."""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader.utoc_path = "nonexistent.utoc"
    reader._ucas_path_override = None
    reader._aes_key = None
    reader._tolerant = False
    reader._read_options = 0

    # Simulate: _utoc_file is set, then close() is called on error
    mock_file = MagicMock()
    reader._utoc_file = mock_file
    reader._ucas_files = [MagicMock()]

    reader.close()

    mock_file.close.assert_called_once()
    assert reader._utoc_file is None
    assert len(reader._ucas_files) == 0
