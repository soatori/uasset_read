"""FString 全 null 检测与降噪测试（#369）。"""
import logging
import struct
import pytest

from uasset_read.archive import ByteArchive


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
