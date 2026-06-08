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
