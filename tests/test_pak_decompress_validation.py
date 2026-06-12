"""Pak 解压缩块校验回归测试"""
from __future__ import annotations

import io
import pytest

from uasset_read.pak.decompress import decompress_entry
from uasset_read.pak.structures import FPakEntry, FPakCompressedBlock
from uasset_read.exceptions import ParseError


def _make_entry(blocks, uncompressed_size=1024):
    """构造一个最小 FPakEntry。"""
    entry = FPakEntry.__new__(FPakEntry)
    entry.compression_blocks = blocks
    entry.compression_block_size = 65536
    entry.is_encrypted = False
    entry.is_compressed = True
    entry.uncompressed_size = uncompressed_size
    entry.compression_method_index = 1
    entry.offset = 0
    entry.size = sum(b.compressed_end - b.compressed_start for b in blocks)
    entry.compression_method = "Zlib"
    entry.hash = b"\x00" * 20
    return entry


def test_compressed_end_before_start_raises():
    """compressed_end < compressed_start 应抛 ParseError。"""
    block = FPakCompressedBlock(compressed_start=100, compressed_end=50)
    entry = _make_entry([block])

    stream = io.BytesIO(b"\x00" * 200)
    with pytest.raises(ParseError, match="compressed_end.*compressed_start"):
        decompress_entry(stream, entry, compression_method="Zlib")


def test_short_read_raises():
    """块读取不足时应抛 ParseError。"""
    block = FPakCompressedBlock(compressed_start=0, compressed_end=100)
    entry = _make_entry([block])

    stream = io.BytesIO(b"\x00" * 10)  # 只有 10 字节，期望 100
    with pytest.raises(ParseError, match="读取不足"):
        decompress_entry(stream, entry, compression_method="Zlib")


def test_uncompressed_short_read_raises():
    """非压缩 entry 读取不足时应抛 ParseError。"""
    entry = FPakEntry.__new__(FPakEntry)
    entry.is_compressed = False
    entry.is_encrypted = False
    entry.offset = 0
    entry.uncompressed_size = 100
    entry.compression_blocks = []

    stream = io.BytesIO(b"\x00" * 10)  # 只有 10 字节，期望 100
    with pytest.raises(ParseError, match="非压缩短读"):
        decompress_entry(stream, entry, compression_method="None")


def test_uncompressed_normal_read():
    """非压缩 entry 正常读取应返回完整数据。"""
    entry = FPakEntry.__new__(FPakEntry)
    entry.is_compressed = False
    entry.is_encrypted = False
    entry.offset = 0
    entry.uncompressed_size = 5
    entry.compression_blocks = []

    data = b"hello"
    stream = io.BytesIO(data)
    result = decompress_entry(stream, entry, compression_method="None")
    assert result == data


def test_uncompressed_encrypted_short_read_at_aligned_size():
    """加密非压缩 entry：读取不足 aligned raw_size 时应抛错。"""
    entry = FPakEntry.__new__(FPakEntry)
    entry.is_compressed = False
    entry.is_encrypted = True
    entry.offset = 0
    entry.uncompressed_size = 13  # 不是 16 的倍数 → aligned 为 16
    entry.compression_blocks = []

    # 只提供 13 字节，不够 16 字节 aligned raw_size
    stream = io.BytesIO(b"x" * 13)
    dummy_key = b"\x00" * 32
    with pytest.raises(ParseError, match="Pak 非压缩短读"):
        decompress_entry(stream, entry, compression_method="None", encryption_key=dummy_key)


def test_compressed_result_truncated_to_expected_size():
    """压缩结果超过预期大小时应截断到 uncompressed_size。"""
    # 构造一个返回过多数据的压缩块
    import zlib
    original = b"x" * 100
    compressed = zlib.compress(original)

    block = FPakCompressedBlock(compressed_start=0, compressed_end=len(compressed))
    entry = _make_entry([block], uncompressed_size=50)  # 预期 50 字节

    stream = io.BytesIO(compressed)
    result = decompress_entry(stream, entry, compression_method="Zlib")
    assert len(result) == 50
    assert result == original[:50]
