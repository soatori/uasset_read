"""UTF-8 字符串长度越界验证测试 (#407)

验证 read_utf8_string() 对声明长度超过剩余字节的容错行为：
- tolerant 模式：记录诊断并返回空字符串
- strict 模式：抛出 ParseError
"""
import struct
import pytest
from uasset_read.archive import ByteArchive
from uasset_read.exceptions import ParseError


def test_utf8_length_exceeds_remaining_bytes_tolerant():
    """UTF-8 长度超过剩余字节时，tolerant 模式应返回空字符串"""
    # length=1000, 但只剩 10 字节（不含 length 字段本身的 4 字节）
    # 构造: i32 length (1000) + 10 bytes of padding
    data = struct.pack('<i', 1000) + b'\x00' * 10
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == ""


def test_utf8_length_exceeds_remaining_bytes_strict():
    """UTF-8 长度超过剩余字节时，strict 模式应抛出 ParseError"""
    data = struct.pack('<i', 1000) + b'\x00' * 10
    archive = ByteArchive(data, tolerant=False)
    with pytest.raises(ParseError, match="UTF-8 length 1000 exceeds remaining"):
        archive.read_utf8_string(tolerant=False)


def test_utf8_length_within_remaining_bytes():
    """UTF-8 长度在剩余字节范围内，应正常读取"""
    # length=5, 后跟 5 字节有效数据 + null terminator
    content = b'hello'
    data = struct.pack('<i', len(content) + 1) + content + b'\x00'
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == "hello"


def test_utf8_length_zero():
    """UTF-8 长度为 0，应返回空字符串"""
    data = struct.pack('<i', 0)
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == ""


def test_utf8_length_exactly_matches_remaining():
    """UTF-8 长度恰好等于剩余字节，应正常读取"""
    content = b'test\x00'
    data = struct.pack('<i', len(content)) + content
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == "test"


def test_utf8_length_one_byte_over():
    """UTF-8 长度比剩余字节多 1，应触发越界"""
    data = struct.pack('<i', 11) + b'\x00' * 10
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == ""


def test_utf8_length_records_diagnostic():
    """tolerant 模式下应记录诊断信息"""
    data = struct.pack('<i', 500) + b'\x00' * 5
    archive = ByteArchive(data, tolerant=True)
    archive.read_utf8_string(tolerant=True)
    diagnostics = archive.get_diagnostics()
    assert len(diagnostics) > 0
    assert any("UTF-8 length" in d.error for d in diagnostics)
