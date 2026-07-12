"""FString 全空损坏检测测试 (#330)

验证 read_fstring() 对全空（全 null）数据的检测和容错行为：
- UTF-8: length > 0 但数据全为 null
- UTF-16: length < 0 但数据全为 null
- strict/tolerant 两种模式的表现差异
"""
import pytest
from uasset_read.archive import ByteArchive
from uasset_read.exceptions import ParseError


def test_fstring_all_nulls_utf8_tolerant():
    """UTF-8 FString 全空在 tolerant 模式应返回空字符串。"""
    # length=5 (u32 LE), 5 个 null 字节
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""


def test_fstring_all_nulls_utf16_tolerant():
    """UTF-16 FString 全空在 tolerant 模式应返回空字符串。"""
    # length=-3 (i32 LE) → utf16_len=6, 6 个 null 字节
    data = b'\xfd\xff\xff\xff\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=True)

    result = archive.read_fstring()
    assert result == ""


def test_fstring_all_nulls_utf8_strict():
    """UTF-8 FString 全空在 strict 模式应抛出 ParseError。"""
    data = b'\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=False)

    with pytest.raises(ParseError):
        archive.read_fstring()


def test_fstring_all_nulls_utf16_strict():
    """UTF-16 FString 全空在 strict 模式应抛出 ParseError。"""
    data = b'\xfd\xff\xff\xff\x00\x00\x00\x00\x00\x00'
    archive = ByteArchive(data, tolerant=False)

    with pytest.raises(ParseError):
        archive.read_fstring()
