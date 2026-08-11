"""Consolidated IoStore tests — cycle detection, resource limits, and security bounds."""
import io
import struct
import pytest

from uasset_read.iostore.reader import IoStoreReader, MAX_TOC_ENTRIES, MAX_PARTITION_COUNT
from uasset_read.exceptions import ParseError


def _build_cyclic_directory_index() -> bytes:
    """Build a directory index buffer with a child-entry cycle.

    Structure: mount_point + directory_entries + file_entries + string_table
    Cycle: entry 0's first_child_entry = 0 (points to itself).
    """
    buf = bytearray()

    # mount_point: FString "Test/"
    mount = b"Test/\x00"
    buf += struct.pack("<i", len(mount))
    buf += mount

    # directory_entries: 1 entry
    buf += struct.pack("<i", 1)
    # FIoDirectoryIndexEntry: name(4) + first_child_entry(4) + next_sibling_entry(4) + first_file_entry(4)
    buf += struct.pack("<i", 0)   # name = string_table[0]
    buf += struct.pack("<i", 0)   # first_child_entry = 0 -> cycle!
    buf += struct.pack("<i", -1)  # next_sibling_entry = invalid
    buf += struct.pack("<i", -1)  # first_file_entry = invalid

    # file_entries: 0 entries
    buf += struct.pack("<i", 0)

    # string_table: 1 entry
    buf += struct.pack("<i", 1)
    name = b"dir\x00"
    buf += struct.pack("<i", len(name))
    buf += name

    return bytes(buf)


def _make_reader(**attrs) -> IoStoreReader:
    """Create an IoStoreReader with specified attributes for testing."""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._header = None
    reader._aes_key = None
    reader._chunk_ids = []
    reader._directory_index = {}
    reader._mount_point = ""
    for k, v in attrs.items():
        setattr(reader, k, v)
    return reader


# ---------------------------------------------------------------------------
# Cycle detection tests
# ---------------------------------------------------------------------------

class TestDirectoryIndexCycleDetection:
    """Directory index cycle detection — child entry self-cycle."""

    def test_child_entry_self_cycle(self):
        """first_child_entry pointing to itself should raise ParseError."""
        reader = _make_reader(_directory_index_buffer=_build_cyclic_directory_index())
        with pytest.raises(ParseError):
            reader._parse_directory_index()


# ---------------------------------------------------------------------------
# Resource limit tests
# ---------------------------------------------------------------------------

class TestResourceLimits:
    """Header resource limits — TOC entries and partition count."""

    def test_toc_entry_count_too_large(self):
        """toc_entry_count exceeding MAX_TOC_ENTRIES should be rejected."""
        reader = IoStoreReader.__new__(IoStoreReader)
        reader._utoc_file = io.BytesIO(b"\x00" * 100)
        reader._header = type("FakeHeader", (), {
            "toc_entry_count": MAX_TOC_ENTRIES + 1,
            "version": 8,
        })()
        reader._chunk_ids = []

        with pytest.raises(ParseError, match="limit|上限"):
            reader._load_chunk_ids()

    def test_partition_count_too_large(self):
        """partition_count exceeding MAX_PARTITION_COUNT should be rejected."""
        reader = IoStoreReader.__new__(IoStoreReader)
        reader._header = type("FakeHeader", (), {
            "partition_count": MAX_PARTITION_COUNT + 1,
            "version": 8,
        })()
        reader._ucas_files = []
        reader.utoc_path = "dummy/path.utoc"
        reader._ucas_path_override = None

        with pytest.raises(ParseError, match="limit|上限"):
            reader._open_container_files()
