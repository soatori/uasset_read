"""测试 FString UTF-16 代理对处理 — Issue #183"""
import pytest
import struct

from uasset_read.archive import FArchive


def _make_archive(data: bytes, tmp_path) -> FArchive:
    path = tmp_path / "_test_fstring_utf16.uasset"
    with open(path, "wb") as f:
        f.write(data)
    return FArchive(str(path))


def _encode_utf16(text: str) -> bytes:
    """编码为 UE FString UTF-16-LE 格式（负长度前缀）。"""
    utf16_data = text.encode('utf-16-le') + b'\x00\x00'
    num_code_units = len(utf16_data) // 2
    return struct.pack('<i', -num_code_units) + utf16_data


def _encode_utf8(text: str) -> bytes:
    """编码为 UE FString UTF-8 格式（正长度前缀）。"""
    utf8_data = text.encode('utf-8') + b'\x00'
    return struct.pack('<i', len(utf8_data)) + utf8_data


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
        """数据不足时位置回退。"""
        # length=-100 but no data
        data = struct.pack('<i', -100)
        archive = _make_archive(data, tmp_path)
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
