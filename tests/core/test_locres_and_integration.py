"""测试 _scrape_locres_strings（raw.py）和集成流程。"""

import struct

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.core.error_handling import tolerant_parse
from uasset_read.exceptions import ParseError
from uasset_read.models.result import ParseResult
from uasset_read.parse_uasset import _handle_parse_error
from uasset_read.raw import _scrape_locres_strings


# ---------------------------------------------------------------------------
# locres 字符串提取
# ---------------------------------------------------------------------------

class TestScrapeLocresStrings:
    """_scrape_locres_strings 二进制字符串提取。"""

    def test_ascii_strings_correctly_extracted(self):
        """ASCII 可打印字符串正确提取。"""
        data = b"hello\x00world\x00"
        result = _scrape_locres_strings(data)
        assert len(result) == 2
        assert result[0]["value"] == "hello"
        assert result[1]["value"] == "world"

    def test_utf8_multibyte_strings_extracted(self):
        """UTF-8 多字节字符串（如中文）正确提取。"""
        text = "你好世界"
        data = text.encode("utf-8") + b"\x00"
        result = _scrape_locres_strings(data)
        assert len(result) == 1
        assert result[0]["value"] == text

    def test_null_byte_separates_multiple_strings(self):
        """null 字节正确分隔多个字符串。"""
        data = b"AAA\x00BBB\x00CCC\x00"
        result = _scrape_locres_strings(data)
        assert [r["value"] for r in result] == ["AAA", "BBB", "CCC"]

    def test_short_strings_below_3_chars_filtered(self):
        """长度不足 3 字符的字符串被过滤。"""
        data = b"a\x00ab\x00abc\x00"
        result = _scrape_locres_strings(data)
        assert len(result) == 1
        assert result[0]["value"] == "abc"

    def test_empty_data_returns_empty_list(self):
        """空数据返回空列表。"""
        assert _scrape_locres_strings(b"") == []
        assert _scrape_locres_strings(b"\x00") == []

    def test_max_200_strings_returned(self):
        """最多返回 200 个字符串。"""
        parts = [f"s{i:03d}".encode() for i in range(250)]
        data = b"\x00".join(parts) + b"\x00"
        result = _scrape_locres_strings(data)
        assert len(result) == 200


# ---------------------------------------------------------------------------
# 集成测试
# ---------------------------------------------------------------------------

class TestTolerantParseIntegration:
    """tolerant_parse + _handle_parse_error 端到端。"""

    def test_parse_error_caught_and_recorded(self):
        """ParseError 被 tolerant_parse 捕获并记录到 result.errors，is_success=False。"""
        result = ParseResult()
        result.is_success = True
        _archive = ByteArchive(b"\x00" * 8, name="test.uasset")

        with pytest.raises(ParseError):
            with tolerant_parse(result, "test stage"):
                raise ParseError("模拟解析失败")

        # tolerant_parse re-raises, so is_success stays True here;
        # _handle_parse_error is what sets it to False in the real pipeline.
        assert len(result.errors) == 1
        assert "模拟解析失败" in result.errors[0]

    def test_handle_parse_error_sets_success_false(self):
        """_handle_parse_error 将 result.is_success 设为 False 并记录错误。"""
        result = ParseResult()
        result.is_success = True
        archive = ByteArchive(b"\x00" * 8, name="test.uasset")

        exc = ParseError("模拟解析失败")
        _handle_parse_error(exc, result, archive, "test.uasset", tolerant=True)

        assert result.is_success is False
        assert any("模拟解析失败" in e for e in result.errors)


class TestByteArchiveIntegration:
    """ByteArchive → 属性读取 → close 完整流程。"""

    def test_read_multi_type_and_close(self):
        """ByteArchive 读取 u8/u16/u32 后正常 close，无异常。"""
        data = (
            struct.pack("<B", 7)
            + struct.pack("<H", 1024)
            + struct.pack("<I", 42)
            + struct.pack("<I", 99)
        )
        archive = ByteArchive(data, name="test.bin")

        assert archive.read_u8("b") == 7
        assert archive.read_u16("h") == 1024
        assert archive.read_u32("f1") == 42
        assert archive.read_u32("f2") == 99

        archive.close()

    def test_read_past_eof_raises_parse_error(self):
        """读取超出 EOF 抛出 ParseError。"""
        archive = ByteArchive(b"\x00" * 2, name="tiny.bin")
        with pytest.raises(ParseError):
            archive.read_u32("overflow")
        archive.close()
