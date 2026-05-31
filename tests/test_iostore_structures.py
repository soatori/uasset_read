"""IoStore 核心数据结构测试"""
import struct
import pytest
from io import BytesIO


def test_fio_chunk_id_creation():
    """测试 FIoChunkId 创建"""
    from uasset_read.iostore.structures import FIoChunkId

    chunk_id = FIoChunkId(b'\x00' * 12)
    assert chunk_id.bytes == b'\x00' * 12
    assert chunk_id.id == 0


def test_fio_chunk_id_from_hash():
    """测试从哈希创建 FIoChunkId"""
    from uasset_read.iostore.structures import FIoChunkId

    chunk_id = FIoChunkId.from_hash(0x12345678)
    assert chunk_id.id == 0x12345678


def test_fio_offset_and_size_creation():
    """测试 FIoOffsetAndSize 创建"""
    from uasset_read.iostore.structures import FIoOffsetAndSize

    offset_size = FIoOffsetAndSize(offset=1024, size=2048)
    assert offset_size.offset == 1024
    assert offset_size.size == 2048


def test_fio_directory_index_entry_creation():
    """测试 FIoDirectoryIndexEntry 创建"""
    from uasset_read.iostore.structures import FIoDirectoryIndexEntry

    entry = FIoDirectoryIndexEntry(
        name_offset=100,
        next_index=200,
        child_index=300,
        chunk_id_index=400,
        size=500,
        flags=600
    )
    assert entry.name_offset == 100
    assert entry.child_index == 300
