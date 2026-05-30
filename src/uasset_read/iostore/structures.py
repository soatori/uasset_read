"""IoStore 核心数据结构 — 镜像 CUE4Parse IoStore 结构"""
from __future__ import annotations
from dataclasses import dataclass
from typing import BinaryIO
import struct


@dataclass
class FIoChunkId:
    """IoStore Chunk 标识符（12 字节）"""
    bytes: bytes  # 12 bytes

    @staticmethod
    def from_hash(chunk_hash: int) -> FIoChunkId:
        """从 64 位哈希创建（低 12 字节）"""
        data = struct.pack('<Q', chunk_hash) + b'\x00' * 4
        return FIoChunkId(bytes=data[:12])

    @property
    def id(self) -> int:
        """返回 64 位 ID（低 8 字节）"""
        return struct.unpack('<Q', self.bytes[:8])[0]


@dataclass
class FIoOffsetAndSize:
    """偏移和大小（打包为 40 位偏移 + 24 位大小）"""
    offset: int
    size: int

    def pack(self) -> bytes:
        """打包为 8 字节"""
        # 40 位偏移 + 24 位大小
        value = (self.offset << 24) | (self.size & 0xFFFFFF)
        return struct.pack('<Q', value)

    @staticmethod
    def unpack(data: bytes) -> FIoOffsetAndSize:
        """从 8 字节解包"""
        value = struct.unpack('<Q', data)[0]
        offset = value >> 24
        size = value & 0xFFFFFF
        return FIoOffsetAndSize(offset=offset, size=size)


@dataclass
class FIoDirectoryIndexEntry:
    """目录索引条目"""
    name_offset: int
    next_index: int
    child_index: int
    chunk_id_index: int
    size: int
    flags: int

    @staticmethod
    def deserialize(stream: BinaryIO) -> FIoDirectoryIndexEntry:
        """从流反序列化"""
        data = stream.read(24)
        if len(data) < 24:
            raise ValueError("Unexpected end of stream")

        name_offset, next_index, child_index, chunk_id_index, size, flags = \
            struct.unpack('<IIIIII', data)

        return FIoDirectoryIndexEntry(
            name_offset=name_offset,
            next_index=next_index,
            child_index=child_index,
            chunk_id_index=chunk_id_index,
            size=size,
            flags=flags
        )
