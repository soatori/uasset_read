"""IoStore Reader 分区读取不足回归测试"""
from __future__ import annotations

import io
import pytest

from uasset_read.iostore.reader import IoStoreReader
from uasset_read.iostore.structures import FIoStoreTocHeader, FIoStoreTocCompressedBlockEntry
from uasset_read.exceptions import ParseError


def _make_reader_with_short_partition(data: bytes, length: int) -> IoStoreReader:
    """构造一个 UCAS 分区数据不足的 IoStoreReader。"""
    reader = IoStoreReader.__new__(IoStoreReader)
    # 模拟一个只有 data 长度的分区流
    reader._ucas_files = [io.BytesIO(data)]
    reader._header = FIoStoreTocHeader.__new__(FIoStoreTocHeader)
    reader._header.partition_size = 0  # 不限分区大小
    reader._header.container_flags = 0  # 无加密
    return reader


def _make_reader_with_compressed_block(
    block_data: bytes, uncompressed_size: int, method_index: int = 1
) -> IoStoreReader:
    """构造一个压缩块数据不足的 IoStoreReader。"""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._ucas_files = [io.BytesIO(block_data)]
    reader._header = FIoStoreTocHeader.__new__(FIoStoreTocHeader)
    reader._header.container_flags = 0
    reader._header.partition_size = len(block_data) + 100  # 确保块在第一个分区内
    reader._compression_blocks = [
        FIoStoreTocCompressedBlockEntry(
            offset=0,
            compressed_size=len(block_data) + 50,  # 声称比实际数据大
            uncompressed_size=uncompressed_size,
            compression_method_index=method_index,
        )
    ]
    reader._compression_methods = ["None", "Zlib"]
    reader._compression_block_size = 64 * 1024 * 1024  # 64MB
    return reader


def test_uncompressed_partition_short_read_raises():
    """分区读取不足时应抛 ParseError 而非静默返回短数据。"""
    reader = _make_reader_with_short_partition(b"ab", length=10)
    with pytest.raises(ParseError, match="分区读取不足"):
        reader._read_uncompressed_partitions(
            partition_index=0, partition_offset=0, length=10
        )


def test_uncompressed_partition_normal_read():
    """正常分区读取应返回完整数据。"""
    data = b"hello world"
    reader = _make_reader_with_short_partition(data, length=len(data))
    result = reader._read_uncompressed_partitions(
        partition_index=0, partition_offset=0, length=len(data)
    )
    assert result == data


def test_compressed_block_short_read_raises():
    """压缩块读取不足时应抛 ParseError 而非静默返回短数据。"""
    # TOC 声称 compressed_size=52，但实际只有 2 字节
    reader = _make_reader_with_compressed_block(b"ab", uncompressed_size=10)
    with pytest.raises(ParseError, match="压缩块.*读取不足"):
        reader._read_data(0, 2)  # 读取 2 字节触发块加载
