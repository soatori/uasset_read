"""IoStore security integration tests -- covering adversarial input scenarios."""
import io
import struct
import pytest

from uasset_read.iostore.reader import IoStoreReader, MAX_TOC_ENTRIES, MAX_PARTITION_COUNT
from uasset_read.exceptions import ParseError


class TestIoStoreResourceLimits:
    """Header resource limit integration tests."""

    def test_max_toc_entries_respected(self):
        """toc_entry_count = 10 should be handled normally (small-scale boundary value)."""
        reader = IoStoreReader.__new__(IoStoreReader)
        reader._utoc_file = io.BytesIO(b"\x00" * 12 * 10)
        reader._header = type("H", (), {"toc_entry_count": 10, "version": 8})()
        reader._chunk_ids = []
        # Should not throw exception
        reader._load_chunk_ids()
        assert len(reader._chunk_ids) == 10

    def test_toc_entries_exactly_at_limit(self):
        """toc_entry_count exactly equal to 100 should pass."""
        reader = IoStoreReader.__new__(IoStoreReader)
        # Need sufficient data
        data = b"\x00" * (12 * 100)
        reader._utoc_file = io.BytesIO(data)
        reader._header = type("H", (), {"toc_entry_count": 100, "version": 8})()
        reader._chunk_ids = []
        reader._load_chunk_ids()
        assert len(reader._chunk_ids) == 100

    def test_partition_count_limit(self):
        """Partition count exceeding limit should be rejected."""
        reader = IoStoreReader.__new__(IoStoreReader)
        reader._header = type("H", (), {
            "partition_count": MAX_PARTITION_COUNT + 1,
            "version": 8,
        })()
        reader._ucas_files = []
        reader.utoc_path = "/fake/test.utoc"
        reader._ucas_path_override = None

        with pytest.raises(ParseError, match="limit|exceeds"):
            reader._open_container_files()


class TestDirectoryIndexSafety:
    """Directory index safety tests."""

    def _build_sibling_cycle_index(self) -> bytes:
        """Build a directory index buffer with a sibling chain cycle.

        Two directory entries point to each other as next_sibling, forming a cycle.
        """
        buf = bytearray()

        # mount_point: FString "/"
        mount = b"/\x00"
        buf += struct.pack("<i", len(mount))
        buf += mount

        # directory_entries: 2 entries
        buf += struct.pack("<i", 2)
        # entry 0
        buf += struct.pack("<i", 0)    # name
        buf += struct.pack("<i", -1)   # first_child
        buf += struct.pack("<i", 1)    # next_sibling = 1
        buf += struct.pack("<i", -1)   # first_file
        # entry 1
        buf += struct.pack("<i", 1)    # name
        buf += struct.pack("<i", -1)   # first_child
        buf += struct.pack("<i", 0)    # next_sibling = 0 -> cycle!
        buf += struct.pack("<i", -1)   # first_file

        # file_entries
        buf += struct.pack("<i", 0)

        # string_table
        buf += struct.pack("<i", 2)
        for name in [b"a\x00", b"b\x00"]:
            buf += struct.pack("<i", len(name))
            buf += name

        return bytes(buf)

    def test_sibling_chain_cycle(self):
        """sibling chain cycle should be detected."""
        reader = IoStoreReader.__new__(IoStoreReader)
        reader._directory_index_buffer = self._build_sibling_cycle_index()
        reader._header = None
        reader._aes_key = None
        reader._chunk_ids = []
        reader._directory_index = {}
        reader._mount_point = ""

        with pytest.raises(ParseError, match="cycle|depth"):
            reader._parse_directory_index()

    def test_file_chain_cycle(self):
        """file chain cycle should be detected."""
        buf = bytearray()
        # mount_point
        mount = b"/\x00"
        buf += struct.pack("<i", len(mount))
        buf += mount

        # directory_entries: 1 entry (no subdirectories)
        buf += struct.pack("<i", 1)
        buf += struct.pack("<i", -1)  # name = invalid
        buf += struct.pack("<i", -1)  # first_child_entry = invalid
        buf += struct.pack("<i", -1)  # next_sibling_entry = invalid
        buf += struct.pack("<i", 0)   # first_file_entry = 0

        # file_entries: 1 entry, next_file_entry = 0 (cycle)
        buf += struct.pack("<i", 1)
        buf += struct.pack("<i", 0)   # name
        buf += struct.pack("<i", 0)   # user_data
        buf += struct.pack("<i", 0)   # next_file_entry = 0 -> cycle!

        # string_table
        buf += struct.pack("<i", 1)
        fname = b"test.uasset\x00"
        buf += struct.pack("<i", len(fname))
        buf += fname

        reader = IoStoreReader.__new__(IoStoreReader)
        reader._directory_index_buffer = bytes(buf)
        reader._header = None
        reader._aes_key = None
        reader._chunk_ids = []
        reader._directory_index = {}
        reader._mount_point = ""

        with pytest.raises(ParseError, match="cycle|depth"):
            reader._parse_directory_index()

    def test_self_referencing_child_cycle(self):
        """first_child_entry self-referencing cycle should be detected."""
        buf = bytearray()
        # mount_point
        mount = b"/\x00"
        buf += struct.pack("<i", len(mount))
        buf += mount

        # directory_entries: 1 entry, first_child = self
        buf += struct.pack("<i", 1)
        buf += struct.pack("<i", 0)   # name
        buf += struct.pack("<i", 0)   # first_child = 0 -> self-referencing!
        buf += struct.pack("<i", -1)  # next_sibling = invalid
        buf += struct.pack("<i", -1)  # first_file = invalid

        # file_entries: 0
        buf += struct.pack("<i", 0)

        # string_table: 1
        buf += struct.pack("<i", 1)
        name = b"dir\x00"
        buf += struct.pack("<i", len(name))
        buf += name

        reader = IoStoreReader.__new__(IoStoreReader)
        reader._directory_index_buffer = bytes(buf)
        reader._header = None
        reader._aes_key = None
        reader._chunk_ids = []
        reader._directory_index = {}
        reader._mount_point = ""

        with pytest.raises(ParseError, match="cycle|depth"):
            reader._parse_directory_index()
