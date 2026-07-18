"""FString / FName 类型测试（archive/types）。

合并自：
- test_fstring_fname.py — FString 全 null 检测、损坏处理、UTF-16 代理对、长度异常容错、FName 索引恢复
"""
import logging
import struct
import pytest
from unittest.mock import MagicMock, patch

from uasset_read.archive import FArchive, ByteArchive
from uasset_read.exceptions import ParseError
from uasset_read.constants import MAX_FSTRING_LENGTH


# ---------------------------------------------------------------------------
# 辅助函数（去重合并）
# ---------------------------------------------------------------------------

def _make_archive(data: bytes, tmp_path, tolerant: bool = True) -> FArchive:
    """创建临时 FArchive 用于测试。"""
    path = tmp_path / "_test_fstring.uasset"
    with open(path, "wb") as f:
        f.write(data)
    return FArchive(str(path), tolerant=tolerant)


def _make_utf8_all_null(byte_count: int) -> bytes:
    """构造 UTF-8 FString 原始数据（长度前缀 + 全零内容）。"""
    return struct.pack('<i', byte_count) + b'\x00' * byte_count


def _make_utf16_all_null(char_count: int) -> bytes:
    """构造 UTF-16 FString 原始数据（负长度前缀 + 全零内容）。"""
    return struct.pack('<i', -char_count) + b'\x00' * (char_count * 2)


def _make_utf8_starts_with_null(null_count: int, suffix: bytes) -> bytes:
    """构造 UTF-8 FString，前 N 字节为 null，后跟实际内容。

    注意：当 nulls 从头开始时，当前代码返回 ""（nulls-from-start 分支）。
    """
    byte_count = null_count + len(suffix)
    return struct.pack('<i', byte_count) + b'\x00' * null_count + suffix


def _encode_utf16(text: str) -> bytes:
    """编码为 UE FString UTF-16-LE 格式（负长度前缀）。"""
    utf16_data = text.encode('utf-16-le') + b'\x00\x00'
    num_code_units = len(utf16_data) // 2
    return struct.pack('<i', -num_code_units) + utf16_data


def _encode_utf8(text: str) -> bytes:
    """编码为 UE FString UTF-8 格式（正长度前缀）。"""
    utf8_data = text.encode('utf-8') + b'\x00'
    return struct.pack('<i', len(utf8_data)) + utf8_data


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


# ===================================================================
# 第一部分：FString 全 null 检测与降噪（#369）
# ===================================================================

class TestFstringAllNullPadding:
    """对齐 padding 的全零字节应记录 debug 而非 warning。"""

    def test_utf16_alignment_padding_downgraded(self, caplog):
        """UTF-16: 4 个空字符，数据位置 4 字节对齐 → debug 级别。"""
        preamble = b'\x01\x02\x03\x04'
        data = preamble + _make_utf16_all_null(4)
        archive = ByteArchive(data, tolerant=True)
        archive.seek(4)
        with caplog.at_level(logging.DEBUG, logger="uasset_read.archive"):
            result = archive.read_fstring()
        assert result == ""
        assert not any(
            r.levelno >= logging.WARNING and "all nulls" in r.message
            for r in caplog.records
        )

    def test_utf16_8_char_padding_downgraded(self, caplog):
        """UTF-16: 8 个空字符，对齐位置 → debug 级别。"""
        preamble = b'\x00' * 16
        data = preamble + _make_utf16_all_null(8)
        archive = ByteArchive(data, tolerant=True)
        archive.seek(16)
        with caplog.at_level(logging.DEBUG, logger="uasset_read.archive"):
            result = archive.read_fstring()
        assert result == ""
        assert not any(
            r.levelno >= logging.WARNING and "all nulls" in r.message
            for r in caplog.records
        )

    def test_utf8_starts_with_null_aligned_downgraded(self, caplog):
        """UTF-8: 开头 4 字节 null + 4 字节内容（总 8 字节），数据位置对齐 → debug 级别。"""
        preamble = b'\x01\x02\x03\x04'
        data = preamble + _make_utf8_starts_with_null(4, b'ABCD')
        archive = ByteArchive(data, tolerant=True)
        archive.seek(4)
        with caplog.at_level(logging.DEBUG, logger="uasset_read.archive"):
            result = archive.read_fstring()
        # nulls-from-start 分支返回 ""
        assert result == ""
        assert not any(
            r.levelno >= logging.WARNING and "all nulls" in r.message
            for r in caplog.records
        )


class TestFstringAllNullCorruption:
    """非 padding 位置的全零字节应保持 warning。"""

    def test_utf16_non_aligned_still_warns(self, caplog):
        """UTF-16: 4 个空字符，数据位置未对齐 → 保持 warning。"""
        preamble = b'\x01'
        data = preamble + _make_utf16_all_null(4)
        archive = ByteArchive(data, tolerant=True)
        archive.seek(1)
        with caplog.at_level(logging.DEBUG, logger="uasset_read.archive"):
            result = archive.read_fstring()
        assert result == ""
        assert any(
            r.levelno >= logging.WARNING and "all nulls" in r.message
            for r in caplog.records
        )

    def test_utf16_odd_char_count_still_warns(self, caplog):
        """UTF-16: 3 个空字符（非对齐大小） → 保持 warning。"""
        preamble = b'\x01'
        data = preamble + _make_utf16_all_null(3)
        archive = ByteArchive(data, tolerant=True)
        archive.seek(1)
        with caplog.at_level(logging.DEBUG, logger="uasset_read.archive"):
            result = archive.read_fstring()
        assert result == ""
        assert any(
            r.levelno >= logging.WARNING and "all nulls" in r.message
            for r in caplog.records
        )

    def test_utf8_starts_with_null_non_aligned_still_warns(self, caplog):
        """UTF-8: 开头 null + 内容，位置未对齐 → 保持 warning。"""
        preamble = b'\x01'
        data = preamble + _make_utf8_starts_with_null(4, b'AB')
        archive = ByteArchive(data, tolerant=True)
        archive.seek(1)
        with caplog.at_level(logging.DEBUG, logger="uasset_read.archive"):
            result = archive.read_fstring()
        assert result == ""
        assert any(
            r.levelno >= logging.WARNING and "all nulls" in r.message
            for r in caplog.records
        )

    def test_utf8_odd_null_count_still_warns(self, caplog):
        """UTF-8: 5 字节 null（非对齐大小） + 内容 → 保持 warning。"""
        preamble = b'\x00\x00\x00'
        data = preamble + _make_utf8_starts_with_null(5, b'X')
        archive = ByteArchive(data, tolerant=True)
        archive.seek(3)
        with caplog.at_level(logging.DEBUG, logger="uasset_read.archive"):
            result = archive.read_fstring()
        assert result == ""
        assert any(
            r.levelno >= logging.WARNING and "all nulls" in r.message
            for r in caplog.records
        )


class TestFstringAllNullBehaviorPreserved:
    """验证行为不变性：返回值和位置不受影响。"""

    def test_empty_result_returned_utf16(self):
        """UTF-16 全零 FString 始终返回空字符串。"""
        data = _make_utf16_all_null(4)
        archive = ByteArchive(data, tolerant=True)
        result = archive.read_fstring()
        assert result == ""

    def test_utf8_starts_with_null_returns_empty(self):
        """UTF-8 开头 null（nulls-from-start 分支）返回空字符串。"""
        data = _make_utf8_starts_with_null(4, b'AB')
        archive = ByteArchive(data, tolerant=True)
        result = archive.read_fstring()
        assert result == ""

    def test_utf8_content_before_null_returns_truncated(self):
        """UTF-8 内容在 null 之前时截断返回。"""
        # length=6, "AB\x00\x00\x00\x00" → 截断为 "AB"
        content = b"AB\x00\x00\x00\x00"
        data = struct.pack('<i', len(content)) + content
        archive = ByteArchive(data, tolerant=True)
        result = archive.read_fstring()
        assert result == "AB"

    def test_strict_mode_still_raises_utf16(self):
        """UTF-16 strict 模式下全 null 仍抛出异常。"""
        data = _make_utf16_all_null(4)
        archive = ByteArchive(data, tolerant=False)
        with pytest.raises(Exception, match="all nulls"):
            archive.read_fstring()

    def test_position_advances_after_utf16_padding(self):
        """UTF-16 padding 降噪后位置仍然正确前进。"""
        data = _make_utf16_all_null(4) + b'\xff' * 4
        archive = ByteArchive(data, tolerant=True)
        result = archive.read_fstring()
        assert result == ""
        assert archive.tell() == 12  # 4 (length) + 8 (4 chars * 2 bytes)


# ===================================================================
# 第二部分：FString 损坏数据处理（Task 3）
# ===================================================================

class TestFStringCorruption:
    """验证 FString 在遇到损坏数据时的处理行为。"""

    def test_all_nulls_returns_empty(self, tmp_path):
        """全 null 数据返回空字符串，不崩溃。"""
        # length=5, 后面 5 个 null 字节
        data = b"\x05\x00\x00\x00\x00\x00\x00\x00\x00"
        archive = _make_archive(data, tmp_path)
        result = archive.read_fstring()
        assert result == ""

    def test_partial_content_before_null(self, tmp_path):
        """null 之前有内容时截断返回。"""
        # length=10, "hello\x00..." 在 null 处截断
        content = b"hello\x00\x00\x00\x00\x00"
        data = b"\x0a\x00\x00\x00" + content
        archive = _make_archive(data, tmp_path)
        result = archive.read_fstring()
        assert result == "hello"

    def test_empty_string(self, tmp_path):
        """length=0 返回空字符串。"""
        data = b"\x00\x00\x00\x00"
        archive = _make_archive(data, tmp_path)
        result = archive.read_fstring()
        assert result == ""

    def test_normal_string(self, tmp_path):
        """正常字符串正确读取。"""
        text = b"Hello World\x00"
        data = b"\x0b\x00\x00\x00" + text
        archive = _make_archive(data, tmp_path)
        result = archive.read_fstring()
        assert result == "Hello World"

    def test_position_restored_on_boundary_error_tolerant(self, tmp_path):
        """tolerant 模式：长度异常时返回空字符串并回退位置。"""
        # length=999999 但后面没有足够数据
        data = b"\x3f\x42\x0f\x00"  # 大长度，无后续数据
        archive = _make_archive(data, tmp_path, tolerant=True)
        pos_before = archive.tell()

        result = archive.read_fstring()
        assert result == ""
        # 位置应回退到入口
        assert archive.tell() == pos_before

    def test_position_restored_on_boundary_error_strict(self, tmp_path):
        """strict 模式：长度异常时抛出异常并回退位置。"""
        data = b"\x3f\x42\x0f\x00"  # 大长度，无后续数据
        archive = _make_archive(data, tmp_path, tolerant=False)
        pos_before = archive.tell()

        with pytest.raises(Exception):
            archive.read_fstring()

        # 位置应回退到入口
        assert archive.tell() == pos_before


# ===================================================================
# 第三部分：FString UTF-16 代理对处理（#183）
# ===================================================================

class TestFStringUTF16:
    """验证 FString UTF-16 解码，重点测试代理对处理。"""

    def test_ascii_utf8(self, tmp_path):
        archive = _make_archive(_encode_utf8("Hello"), tmp_path)
        assert archive.read_fstring() == "Hello"

    def test_ascii_utf16(self, tmp_path):
        archive = _make_archive(_encode_utf16("Hello"), tmp_path)
        assert archive.read_fstring() == "Hello"

    def test_chinese_bmp(self, tmp_path):
        text = "你好世界"
        archive = _make_archive(_encode_utf16(text), tmp_path)
        assert archive.read_fstring() == text

    def test_japanese_bmp(self, tmp_path):
        text = "こんにちは"
        archive = _make_archive(_encode_utf16(text), tmp_path)
        assert archive.read_fstring() == text

    def test_emoji_surrogate_pair(self, tmp_path):
        """U+1F600 (😀) 需要代理对：0xD83D 0xDE00"""
        text = "\U0001F600"
        archive = _make_archive(_encode_utf16(text), tmp_path)
        assert archive.read_fstring() == text

    def test_multiple_emoji_surrogate_pairs(self, tmp_path):
        text = "\U0001F600\U0001F601\U0001F602"
        archive = _make_archive(_encode_utf16(text), tmp_path)
        assert archive.read_fstring() == text

    def test_mixed_bmp_and_supplementary(self, tmp_path):
        """BMP 字符和补充平面字符混合。"""
        text = "Hello你好\U0001F600World"
        archive = _make_archive(_encode_utf16(text), tmp_path)
        assert archive.read_fstring() == text

    def test_supplementary_plane_math_symbols(self, tmp_path):
        """U+1D400-1D7FF 数学字母符号（代理对范围）。"""
        text = "\U0001D400\U0001D401"  # 𝐀𝐁
        archive = _make_archive(_encode_utf16(text), tmp_path)
        assert archive.read_fstring() == text

    def test_supplementary_cjk(self, tmp_path):
        """U+20000 CJK 扩展 B（代理对）。"""
        text = "\U00020000"  # 𠀀
        archive = _make_archive(_encode_utf16(text), tmp_path)
        assert archive.read_fstring() == text

    def test_empty_string(self, tmp_path):
        data = b'\x00\x00\x00\x00'
        archive = _make_archive(data, tmp_path)
        assert archive.read_fstring() == ""

    def test_utf16_null_terminator_stripped(self, tmp_path):
        """null 终止符被正确去除。"""
        text = "Test"
        archive = _make_archive(_encode_utf16(text), tmp_path)
        result = archive.read_fstring()
        assert result == "Test"
        assert '\x00' not in result

    def test_position_advances_correctly(self, tmp_path):
        """读取后文件位置正确推进。"""
        text = "你好"
        data = _encode_utf16(text)
        archive = _make_archive(data, tmp_path)
        pos_before = archive.tell()
        archive.read_fstring()
        pos_after = archive.tell()
        # 4 (length) + len(text)*2 + 2 (null) = 4 + 4 + 2 = 10
        assert pos_after - pos_before == len(data)

    def test_boundary_error_restores_position(self, tmp_path):
        """数据不足时位置回退（strict 模式）。"""
        # length=-100 but no data
        data = struct.pack('<i', -100)
        archive = _make_archive(data, tmp_path, tolerant=False)
        pos_before = archive.tell()
        with pytest.raises(Exception):
            archive.read_fstring()
        assert archive.tell() == pos_before

    def test_two_consecutive_reads(self, tmp_path):
        """连续读取两个 UTF-16 字符串。"""
        data = _encode_utf16("你好") + _encode_utf16("世界")
        archive = _make_archive(data, tmp_path)
        assert archive.read_fstring() == "你好"
        assert archive.read_fstring() == "世界"

    def test_two_consecutive_mixed_encoding(self, tmp_path):
        """先 UTF-8 后 UTF-16 连续读取。"""
        data = _encode_utf8("Hello") + _encode_utf16("你好")
        archive = _make_archive(data, tmp_path)
        assert archive.read_fstring() == "Hello"
        assert archive.read_fstring() == "你好"


# ===================================================================
# 第四部分：UTF 字符串长度异常容错（#395）
# ===================================================================

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


# ===================================================================
# 第五部分：FName 索引越界恢复
# ===================================================================

class TestFnameIndexRecoveryLogging:
    """验证 _try_recover_fname 恢复成功/失败时的日志级别。"""

    @patch("uasset_read.archive.logger")
    def test_recovery_success_is_debug(self, mock_logger):
        """恢复成功时应记录 debug 而非 warning。"""
        archive = MagicMock(spec=FArchive)
        archive._name_map = ["ValidName1", "ValidName2"]
        archive._name_count = 2
        archive._source_hint = "test.uasset"
        archive._tolerant = True
        archive._file_size = 100
        archive._recovery_attempts = 0
        archive._recovery_successes = 0
        archive._recovery_failures = 0

        # 模拟 read_u32 返回超阈值索引，然后恢复成功
        original_pos = 10
        archive.tell.return_value = original_pos
        archive.read_u32.side_effect = [1500, 0]  # index=1500 (>1000), number=0

        # 模拟 _try_recover_fname 成功恢复
        archive._try_recover_fname.return_value = "ValidName1"

        # 调用 read_name
        result = FArchive.read_name(archive)

        assert result == "ValidName1"
        # 恢复成功时应记录 debug，不应记录 warning
        mock_logger.debug.assert_called()
        mock_logger.warning.assert_not_called()

    @patch("uasset_read.archive.logger")
    def test_recovery_failure_still_warns(self, mock_logger):
        """恢复失败时应保持 warning。"""
        archive = MagicMock(spec=FArchive)
        archive._name_map = []
        archive._name_count = 0
        archive._source_hint = "test.uasset"
        archive._tolerant = True
        archive._file_size = 100
        archive._recovery_attempts = 0
        archive._recovery_successes = 0
        archive._recovery_failures = 0
        archive._name_warnings_seen = set()  # #411 去重追踪

        # 模拟 read_u32 返回超阈值索引
        original_pos = 10
        archive.tell.return_value = original_pos
        archive.read_u32.side_effect = [1500, 0]  # index=1500, number=0

        # 模拟 _try_recover_fname 恢复失败
        archive._try_recover_fname.return_value = None

        # 恢复失败后 tell 返回原始+8 位置
        archive.tell.return_value = original_pos + 8

        # 调用 read_name
        result = FArchive.read_name(archive)

        assert result == "None"
        # 恢复失败且索引越界时应记录 warning
        mock_logger.warning.assert_called()

    @patch("uasset_read.archive.logger")
    def test_normal_index_no_recovery_no_warning(self, mock_logger):
        """正常索引不应触发恢复，也不应记录 warning。"""
        archive = MagicMock(spec=FArchive)
        archive._name_map = ["Name0", "Name1", "Name2"]
        archive._name_count = 3
        archive._source_hint = "test.uasset"
        archive._tolerant = True
        archive._file_size = 100

        # 模拟 read_u32 返回正常索引
        archive.tell.return_value = 10
        archive.read_u32.side_effect = [1, 0]  # index=1, number=0

        result = FArchive.read_name(archive)

        assert result == "Name1"
        # 正常索引不应触发恢复逻辑
        archive._try_recover_fname.assert_not_called()
        mock_logger.warning.assert_not_called()

    @patch("uasset_read.archive.logger")
    def test_recovery_success_with_number(self, mock_logger):
        """恢复成功且 number > 0 时应返回 Name_number 格式。"""
        archive = MagicMock(spec=FArchive)
        archive._name_map = ["ValidName"]
        archive._name_count = 1
        archive._source_hint = "test.uasset"
        archive._tolerant = True
        archive._file_size = 100
        archive._recovery_attempts = 0
        archive._recovery_successes = 0
        archive._recovery_failures = 0

        original_pos = 10
        archive.tell.return_value = original_pos
        archive.read_u32.side_effect = [2000, 3]  # index=2000, number=3

        # _try_recover_fname 返回带 number 的名称
        archive._try_recover_fname.return_value = "ValidName_3"

        result = FArchive.read_name(archive)

        assert result == "ValidName_3"
        mock_logger.debug.assert_called()
        mock_logger.warning.assert_not_called()
