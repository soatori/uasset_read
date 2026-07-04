"""ByteArchive 单元测试 — 验证内存数据读取器功能。"""
from __future__ import annotations

import struct

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.exceptions import ParseError


class TestByteArchiveFromBytes:
    """从 bytes 创建 ByteArchive 的测试。"""

    def test_basic_read(self):
        """从 bytes 创建并读取数据。"""
        data = b'\x01\x02\x03\x04'
        archive = ByteArchive(data)
        assert archive.total_size() == 4
        assert archive.read(2) == b'\x01\x02'
        assert archive.read(2) == b'\x03\x04'

    def test_read_u32(self):
        """读取 u32 值。"""
        value = 0x04030201
        data = struct.pack('<I', value)
        archive = ByteArchive(data)
        assert archive.read_u32() == value

    def test_read_i32(self):
        """读取 i32 值。"""
        value = -12345
        data = struct.pack('<i', value)
        archive = ByteArchive(data)
        assert archive.read_i32() == value

    def test_read_fstring(self):
        """读取 FString。"""
        text = "Hello"
        encoded = text.encode('utf-8') + b'\x00'
        length = len(encoded)
        data = struct.pack('<i', length) + encoded
        archive = ByteArchive(data)
        assert archive.read_fstring() == "Hello"

    def test_empty_data(self):
        """空数据创建。"""
        archive = ByteArchive(b'')
        assert archive.total_size() == 0
        assert archive.tell() == 0


class TestByteArchiveFromMemoryview:
    """从 memoryview 创建 ByteArchive 的测试。"""

    def test_basic_read(self):
        """从 memoryview 创建并读取数据。"""
        raw = bytearray(b'\x0a\x0b\x0c\x0d')
        mv = memoryview(raw)
        archive = ByteArchive(mv)
        assert archive.total_size() == 4
        assert archive.read(2) == b'\x0a\x0b'
        assert archive.read(2) == b'\x0c\x0d'

    def test_read_u64(self):
        """从 memoryview 读取 u64。"""
        raw = bytearray(struct.pack('<Q', 0xDEADBEEFCAFEBABE))
        mv = memoryview(raw)
        archive = ByteArchive(mv)
        assert archive.read_u64() == 0xDEADBEEFCAFEBABE

    def test_read_bool(self):
        """从 memoryview 读取 bool（4-byte uint32）。"""
        raw = bytearray(struct.pack('<I', 1))
        mv = memoryview(raw)
        archive = ByteArchive(mv)
        assert archive.read_bool() is True


class TestByteArchiveSeek:
    """seek/tell 操作测试。"""

    def test_tell_after_read(self):
        """读取后 tell 返回正确位置。"""
        archive = ByteArchive(b'\x00\x01\x02\x03\x04')
        assert archive.tell() == 0
        archive.read(2)
        assert archive.tell() == 2
        archive.read(3)
        assert archive.tell() == 5

    def test_seek_forward(self):
        """向前 seek。"""
        archive = ByteArchive(b'\x00\x01\x02\x03\x04')
        archive.seek(3)
        assert archive.tell() == 3
        assert archive.read(2) == b'\x03\x04'

    def test_seek_backward(self):
        """向后 seek 回退。"""
        archive = ByteArchive(b'\x00\x01\x02\x03\x04')
        archive.read(3)
        archive.seek(1)
        assert archive.tell() == 1
        assert archive.read(2) == b'\x01\x02'

    def test_seek_to_start(self):
        """seek 回起始位置。"""
        archive = ByteArchive(b'\x0a\x0b\x0c')
        archive.read(3)
        archive.seek(0)
        assert archive.tell() == 0
        assert archive.read(1) == b'\x0a'

    def test_seek_to_end(self):
        """seek 到末尾。"""
        archive = ByteArchive(b'\x0a\x0b\x0c')
        archive.seek(3)
        assert archive.tell() == 3
        with pytest.raises(ParseError):
            archive.read(1)

    def test_seek_negative_raises(self):
        """负偏移抛出 ParseError。"""
        archive = ByteArchive(b'\x00\x01\x02')
        with pytest.raises(ParseError):
            archive.seek(-1)

    def test_seek_beyond_end_raises(self):
        """超出范围偏移抛出 ParseError。"""
        archive = ByteArchive(b'\x00\x01\x02')
        with pytest.raises(ParseError):
            archive.seek(10)

    def test_read_beyond_end_raises(self):
        """读取超出剩余数据抛出 ParseError。"""
        archive = ByteArchive(b'\x00\x01\x02')
        archive.read(2)
        with pytest.raises(ParseError):
            archive.read(2)

    def test_repeated_seek_read(self):
        """反复 seek + read 验证稳定性。"""
        data = bytes(range(256))
        archive = ByteArchive(data)
        for i in range(0, 256, 17):
            archive.seek(i)
            assert archive.tell() == i
            val = archive.read(1)
            assert val == bytes([i])
