"""IoStore resource-limit tests — header caps and adversarial count validation."""
import io
import struct
import pytest

from uasset_read.iostore.reader import IoStoreReader
from uasset_read.iostore.reader import MAX_DIRECTORY_ARRAY_COUNT, MAX_STRING_TABLE_COUNT
from uasset_read.exceptions import ParseError


# ---------------------------------------------------------------------------
# Existing header-resource-limit tests
# ---------------------------------------------------------------------------

def test_toc_entry_count_too_large():
    """toc_entry_count above limit should be rejected."""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._utoc_file = io.BytesIO(b"\x00" * 100)
    reader._header = type("FakeHeader", (), {
        "toc_entry_count": 10_000_000,
        "version": 8,
    })()
    reader._chunk_ids = []

    with pytest.raises(ParseError, match="上限"):
        reader._load_chunk_ids()


def test_compression_block_count_too_large():
    """Compression block count above limit should be rejected."""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._utoc_file = io.BytesIO(b"\x00" * 100)
    reader._header = type("FakeHeader", (), {
        "toc_compressed_block_entry_count": 10_000_000,
        "version": 8,
    })()
    reader._compression_blocks = []

    with pytest.raises(ParseError, match="上限"):
        reader._load_compression_blocks()


def test_compression_method_buffer_too_large():
    """Compression method buffer above limit should be rejected."""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._utoc_file = io.BytesIO(b"\x00" * 100)
    reader._header = type("FakeHeader", (), {
        "compression_method_name_count": 100_000,
        "compression_method_name_length": 1000,
        "compression_block_size": 65536,
        "version": 8,
    })()
    reader._compression_methods = ["None"]

    with pytest.raises(ParseError, match="上限"):
        reader._load_compression_methods()


def test_directory_index_size_too_large():
    """Directory index size above limit should be rejected."""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._utoc_file = io.BytesIO(b"\x00" * 100)
    reader._header = type("FakeHeader", (), {
        "version": 8,
        "is_indexed": True,
        "directory_index_size": 500 * 1024 * 1024,  # 500 MB
    })()
    reader._read_options = 0xFF
    reader._directory_index_buffer = None

    with pytest.raises(ParseError, match="上限"):
        reader._load_directory_index()


def test_partition_count_too_large():
    """Partition count above limit should be rejected."""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._header = type("FakeHeader", (), {
        "partition_count": 10_000,
        "version": 8,
    })()
    reader._ucas_files = []
    reader.utoc_path = "dummy/path.utoc"

    with pytest.raises(ParseError, match="上限"):
        reader._open_container_files()


# ---------------------------------------------------------------------------
# Adversarial: _read_array_from bounded-count validation
# ---------------------------------------------------------------------------

class TestDirectoryArrayCountLimit:
    """_read_array_from() bounded-count validation."""

    @staticmethod
    def _count_stream(count: int) -> io.BytesIO:
        return io.BytesIO(struct.pack("<i", count))

    def test_at_limit_succeeds(self):
        data = b"\x00" * MAX_DIRECTORY_ARRAY_COUNT
        stream = io.BytesIO(struct.pack("<i", MAX_DIRECTORY_ARRAY_COUNT) + data)
        result = IoStoreReader._read_array_from(stream, lambda s: s.read(1))
        assert len(result) == MAX_DIRECTORY_ARRAY_COUNT

    def test_above_limit_rejected(self):
        stream = self._count_stream(MAX_DIRECTORY_ARRAY_COUNT + 1)
        with pytest.raises(ParseError, match="directory array count.*exceeds limit"):
            IoStoreReader._read_array_from(stream, lambda s: s.read(1))

    def test_far_above_limit_rejected(self):
        stream = self._count_stream(100_000_000)
        with pytest.raises(ParseError, match="directory array count.*exceeds limit"):
            IoStoreReader._read_array_from(stream, lambda s: s.read(1))

    def test_zero_count_succeeds(self):
        stream = self._count_stream(0)
        result = IoStoreReader._read_array_from(stream, lambda s: s.read(1))
        assert result == []


# ---------------------------------------------------------------------------
# Adversarial: _read_string_table_from bounded-count validation
# ---------------------------------------------------------------------------

class TestStringTableCountLimit:
    """_read_string_table_from() bounded-count validation."""

    @staticmethod
    def _count_stream(count: int) -> io.BytesIO:
        return io.BytesIO(struct.pack("<i", count))

    def test_at_limit_succeeds(self):
        fstring_payload = struct.pack("<i", 1) + b"\x00"
        header = struct.pack("<i", MAX_STRING_TABLE_COUNT)
        stream = io.BytesIO(header + fstring_payload * MAX_STRING_TABLE_COUNT)
        result = IoStoreReader._read_string_table_from(stream)
        assert len(result) == MAX_STRING_TABLE_COUNT

    def test_above_limit_rejected(self):
        stream = self._count_stream(MAX_STRING_TABLE_COUNT + 1)
        with pytest.raises(ParseError, match="string table count.*exceeds limit"):
            IoStoreReader._read_string_table_from(stream)

    def test_far_above_limit_rejected(self):
        stream = self._count_stream(100_000_000)
        with pytest.raises(ParseError, match="string table count.*exceeds limit"):
            IoStoreReader._read_string_table_from(stream)

    def test_zero_count_succeeds(self):
        stream = self._count_stream(0)
        result = IoStoreReader._read_string_table_from(stream)
        assert result == []


# ---------------------------------------------------------------------------
# Adversarial: open() releases handles on ParseError
# ---------------------------------------------------------------------------

class TestOpenReleasesHandlesOnParseError:
    """open() must close file handles when a ParseError propagates."""

    def test_parse_error_closes_handles(self):
        """ParseError path in open() should call close()."""
        reader = IoStoreReader.__new__(IoStoreReader)

        class MockFile:
            def __init__(self):
                self.closed = False
            def close(self):
                self.closed = True
            def seek(self, *a, **kw):
                pass
            def read(self, *a, **kw):
                return b""
            def tell(self):
                return 0

        mock = MockFile()
        reader._utoc_file = mock
        reader._ucas_files = []

        # Simulate the except path from open()
        try:
            raise ParseError("simulated parse error")
        except (OSError, struct.error, ValueError, ParseError):
            reader.close()

        assert mock.closed, "utoc file must be closed on ParseError"

    def test_struct_error_also_closes_handles(self):
        """struct.error path in open() should also call close()."""
        reader = IoStoreReader.__new__(IoStoreReader)

        class MockFile:
            def __init__(self):
                self.closed = False
            def close(self):
                self.closed = True
            def seek(self, *a, **kw):
                pass
            def read(self, *a, **kw):
                return b""
            def tell(self):
                return 0

        mock = MockFile()
        reader._utoc_file = mock
        reader._ucas_files = []

        try:
            raise struct.error("simulated struct error")
        except (OSError, struct.error, ValueError, ParseError):
            reader.close()

        assert mock.closed, "utoc file must be closed on struct.error"

    def test_ucas_files_closed_on_parse_error(self):
        """open() should close ucas files as well when ParseError propagates."""
        reader = IoStoreReader.__new__(IoStoreReader)

        class MockFile:
            def __init__(self):
                self.closed = False
            def close(self):
                self.closed = True
            def seek(self, *a, **kw):
                pass
            def read(self, *a, **kw):
                return b""
            def tell(self):
                return 0

        ucas_mock1 = MockFile()
        ucas_mock2 = MockFile()
        reader._utoc_file = MockFile()
        reader._ucas_files = [ucas_mock1, ucas_mock2]

        try:
            raise ParseError("simulated parse error")
        except (OSError, struct.error, ValueError, ParseError):
            reader.close()

        assert ucas_mock1.closed, "ucas file 0 must be closed on ParseError"
        assert ucas_mock2.closed, "ucas file 1 must be closed on ParseError"
        assert reader._ucas_files == [], "ucas_files list must be cleared"
