"""UTF 字符串长度异常容错测试 — Task 5 (#395)

验证 UTF-8 / UTF-16 字符串长度超过文件大小时的容错行为：
- strict 模式：抛出 ParseError（已有行为）
- tolerant 模式：返回空字符串 + 记录诊断
"""
import logging
import struct
import pytest

from uasset_read.archive import FArchive, ByteArchive
from uasset_read.exceptions import ParseError
from uasset_read.constants import MAX_FSTRING_LENGTH


def _make_utf8_fstring(text_bytes: bytes) -> bytes:
    """构造 UTF-8 FString 原始数据（长度前缀 + 内容）。"""
    return struct.pack('<i', len(text_bytes)) + text_bytes


def _make_utf16_fstring(text: str) -> bytes:
    """构造 UTF-16 FString 原始数据（负长度前缀 + 内容）。"""
    encoded = text.encode('utf-16-le')
    char_count = len(encoded) // 2
    return struct.pack('<i', -char_count) + encoded


def _make_utf8_with_length(length: int) -> bytes:
    """构造指定长度前缀的 UTF-8 FString（不填充内容，模拟截断）。"""
    return struct.pack('<i', length)


def _make_utf16_with_length(char_count: int) -> bytes:
    """构造指定字符数前缀的 UTF-16 FString（不填充内容，模拟截断）。"""
    return struct.pack('<i', -char_count)


class TestUTF8LengthExceedsFileSize:
    """UTF-8 字符串长度超过文件大小时的容错测试。"""

    def test_strict_raises_parse_error(self, tmp_path):
        """strict 模式：长度超过文件大小 → ParseError。"""
        # 构造一个 4 字节文件，fstring 声明长度 1000
        data = _make_utf8_with_length(1000)
        archive = FArchive.__new__(FArchive)
        archive._path = str(tmp_path / "test.uasset")
        archive._file = open(archive._path, 'wb')
        archive._file.write(data)
        archive._file.close()
        archive._file = open(archive._path, 'rb')
        archive._file_size = len(data)
        archive._byte_swapping = False
        archive._tolerant = False
        archive._mmap = None
        archive._use_mmap = False
        archive._mmap_warning = None
        archive._logger = logging.getLogger("test")
        archive._name_map = None
        from uasset_read.bounded_events import BoundedEventBuffer
        archive._diagnostics = BoundedEventBuffer(max_entries=10000)
        archive._hex_view_enabled = False
        archive._hex_view_entries = BoundedEventBuffer(max_entries=50000)
        archive._hex_view_context = ""

        with pytest.raises(ParseError, match="exceeds file size|exceeds maximum|expected .* bytes"):
            archive.read_fstring()
        archive.close()

    def test_tolerant_returns_empty_string(self, tmp_path):
        """tolerant 模式：长度超过文件大小 → 返回空字符串。"""
        data = _make_utf8_with_length(1000)
        archive = FArchive.__new__(FArchive)
        archive._path = str(tmp_path / "test.uasset")
        archive._file = open(archive._path, 'wb')
        archive._file.write(data)
        archive._file.close()
        archive._file = open(archive._path, 'rb')
        archive._file_size = len(data)
        archive._byte_swapping = False
        archive._tolerant = True
        archive._mmap = None
        archive._use_mmap = False
        archive._mmap_warning = None
        archive._logger = logging.getLogger("test")
        archive._name_map = None
        from uasset_read.bounded_events import BoundedEventBuffer
        archive._diagnostics = BoundedEventBuffer(max_entries=10000)
        archive._hex_view_enabled = False
        archive._hex_view_entries = BoundedEventBuffer(max_entries=50000)
        archive._hex_view_context = ""

        result = archive.read_fstring()
        assert result == ""
        archive.close()

    def test_tolerant_position_restored(self, tmp_path):
        """tolerant 模式：异常后位置回退到入口点。"""
        data = _make_utf8_with_length(1000)
        archive = FArchive.__new__(FArchive)
        archive._path = str(tmp_path / "test.uasset")
        archive._file = open(archive._path, 'wb')
        archive._file.write(data)
        archive._file.close()
        archive._file = open(archive._path, 'rb')
        archive._file_size = len(data)
        archive._byte_swapping = False
        archive._tolerant = True
        archive._mmap = None
        archive._use_mmap = False
        archive._mmap_warning = None
        archive._logger = logging.getLogger("test")
        archive._name_map = None
        from uasset_read.bounded_events import BoundedEventBuffer
        archive._diagnostics = BoundedEventBuffer(max_entries=10000)
        archive._hex_view_enabled = False
        archive._hex_view_entries = BoundedEventBuffer(max_entries=50000)
        archive._hex_view_context = ""

        pos_before = archive.tell()
        archive.read_fstring()
        # 位置应回退到入口（4 字节长度前缀之后的位置）
        # 实际上由于容忍模式 seek 回退，位置应与读前一致
        assert archive.tell() == pos_before
        archive.close()


class TestUTF16LengthExceedsFileSize:
    """UTF-16 字符串长度超过文件大小时的容错测试。"""

    def test_strict_raises_parse_error(self, tmp_path):
        """strict 模式：UTF-16 长度超过文件大小 → ParseError。"""
        data = _make_utf16_with_length(500)
        archive = FArchive.__new__(FArchive)
        archive._path = str(tmp_path / "test.uasset")
        archive._file = open(archive._path, 'wb')
        archive._file.write(data)
        archive._file.close()
        archive._file = open(archive._path, 'rb')
        archive._file_size = len(data)
        archive._byte_swapping = False
        archive._tolerant = False
        archive._mmap = None
        archive._use_mmap = False
        archive._mmap_warning = None
        archive._logger = logging.getLogger("test")
        archive._name_map = None
        from uasset_read.bounded_events import BoundedEventBuffer
        archive._diagnostics = BoundedEventBuffer(max_entries=10000)
        archive._hex_view_enabled = False
        archive._hex_view_entries = BoundedEventBuffer(max_entries=50000)
        archive._hex_view_context = ""

        with pytest.raises(ParseError, match="exceeds file size|exceeds maximum|expected .* bytes"):
            archive.read_fstring()
        archive.close()

    def test_tolerant_returns_empty_string(self, tmp_path):
        """tolerant 模式：UTF-16 长度超过文件大小 → 返回空字符串。"""
        data = _make_utf16_with_length(500)
        archive = FArchive.__new__(FArchive)
        archive._path = str(tmp_path / "test.uasset")
        archive._file = open(archive._path, 'wb')
        archive._file.write(data)
        archive._file.close()
        archive._file = open(archive._path, 'rb')
        archive._file_size = len(data)
        archive._byte_swapping = False
        archive._tolerant = True
        archive._mmap = None
        archive._use_mmap = False
        archive._mmap_warning = None
        archive._logger = logging.getLogger("test")
        archive._name_map = None
        from uasset_read.bounded_events import BoundedEventBuffer
        archive._diagnostics = BoundedEventBuffer(max_entries=10000)
        archive._hex_view_enabled = False
        archive._hex_view_entries = BoundedEventBuffer(max_entries=50000)
        archive._hex_view_context = ""

        result = archive.read_fstring()
        assert result == ""
        archive.close()


class TestMAXFStringLengthExceeded:
    """长度超过 MAX_FSTRING_LENGTH 的容错测试。"""

    def test_utf8_strict_raises(self):
        """UTF-8: 超过 MAX_FSTRING_LENGTH → strict 模式 ParseError。"""
        length = MAX_FSTRING_LENGTH + 1
        data = _make_utf8_with_length(length)
        archive = ByteArchive(data, tolerant=False)
        with pytest.raises(ParseError, match="exceeds maximum"):
            archive.read_fstring()

    def test_utf8_tolerant_returns_empty(self):
        """UTF-8: 超过 MAX_FSTRING_LENGTH → tolerant 模式返回空字符串。"""
        length = MAX_FSTRING_LENGTH + 1
        data = _make_utf8_with_length(length)
        archive = ByteArchive(data, tolerant=True)
        result = archive.read_fstring()
        assert result == ""

    def test_utf16_strict_raises(self):
        """UTF-16: 超过 MAX_FSTRING_LENGTH → strict 模式 ParseError。"""
        char_count = MAX_FSTRING_LENGTH // 2 + 1
        data = _make_utf16_with_length(char_count)
        archive = ByteArchive(data, tolerant=False)
        with pytest.raises(ParseError, match="exceeds maximum"):
            archive.read_fstring()

    def test_utf16_tolerant_returns_empty(self):
        """UTF-16: 超过 MAX_FSTRING_LENGTH → tolerant 模式返回空字符串。"""
        char_count = MAX_FSTRING_LENGTH // 2 + 1
        data = _make_utf16_with_length(char_count)
        archive = ByteArchive(data, tolerant=True)
        result = archive.read_fstring()
        assert result == ""


class TestTolerantDiagnostic:
    """tolerant 模式下诊断信息记录测试。"""

    def test_utf8_length_exceeds_logs_warning(self, caplog):
        """UTF-8 长度超限时记录 warning 诊断。"""
        data = _make_utf8_with_length(9999)
        archive = ByteArchive(data, tolerant=True)
        with caplog.at_level(logging.WARNING, logger="uasset_read.archive"):
            result = archive.read_fstring()
        assert result == ""
        assert any("returning empty string" in r.message.lower()
                    or "tolerant" in r.message.lower()
                    for r in caplog.records if r.levelno >= logging.WARNING)

    def test_utf16_length_exceeds_logs_warning(self, caplog):
        """UTF-16 长度超限时记录 warning 诊断。"""
        data = _make_utf16_with_length(5000)
        archive = ByteArchive(data, tolerant=True)
        with caplog.at_level(logging.WARNING, logger="uasset_read.archive"):
            result = archive.read_fstring()
        assert result == ""
        assert any("returning empty string" in r.message.lower()
                    or "tolerant" in r.message.lower()
                    for r in caplog.records if r.levelno >= logging.WARNING)


class TestNormalStringsUnaffected:
    """正常字符串不受容错逻辑影响。"""

    def test_normal_utf8_string(self):
        """正常 UTF-8 字符串正确读取。"""
        data = _make_utf8_fstring(b"Hello World")
        archive = ByteArchive(data, tolerant=True)
        assert archive.read_fstring() == "Hello World"

    def test_normal_utf16_string(self):
        """正常 UTF-16 字符串正确读取。"""
        data = _make_utf16_fstring("Hello World")
        archive = ByteArchive(data, tolerant=True)
        assert archive.read_fstring() == "Hello World"

    def test_empty_string(self):
        """空字符串正确返回。"""
        data = b"\x00\x00\x00\x00"
        archive = ByteArchive(data, tolerant=True)
        assert archive.read_fstring() == ""
