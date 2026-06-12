"""IoStore 核心数据结构 — 镜像 IoStore 结构"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import BinaryIO, List, Optional
import struct


# ============================================================================
# 枚举定义
# ============================================================================

class EIoStoreTocVersion(IntEnum):
    """IoStore TOC 版本枚举"""
    Invalid = 0
    Initial = 1
    DirectoryIndex = 2
    PartitionSize = 3
    PerfectHash = 4
    PerfectHashWithOverflow = 5
    OnDemandMetaData = 6
    RemovedOnDemandMetaData = 7
    ReplaceIoChunkHashWithIoHash = 8
    LatestPlusOne = 9
    Latest = LatestPlusOne - 1


class EIoContainerFlags(IntFlag):
    """IoStore 容器标志"""
    None_ = 0
    Compressed = 1 << 0
    Encrypted = 1 << 1
    Signed = 1 << 2
    Indexed = 1 << 3
    OnDemand = 1 << 4


class EIoChunkType(IntEnum):
    """IoStore 数据块类型

    UE5 IoStore 专用类型。UE4 使用不同的存储机制。
    类型 0-6 在 UE5.0+ 中定义，类型 7+ 在后续版本中添加。
    """
    Invalid = 0
    ExportBundleData = 1       # UE5.0+: 导出包数据
    BulkData = 2               # UE5.0+: 批量数据
    OptionalBulkData = 3       # UE5.0+: 可选批量数据
    MemoryMappedBulkData = 4   # UE5.0+: 内存映射批量数据
    ScriptObjects = 5          # UE5.0+: 脚本对象
    ContainerHeader = 6        # UE5.0+: 容器头部
    ExternalFile = 7           # UE5.1+: 外部文件引用
    ShaderCodeLibrary = 8      # UE5.1+: 着色器代码库
    ShaderCode = 9             # UE5.1+: 着色器代码
    PackageStoreEntry = 10     # UE5.2+: 包存储条目
    DerivedData = 11           # UE5.3+: 派生数据
    EditorDerivedData = 12     # UE5.4+: 编辑器派生数据
    PackageResource = 13       # UE5.5+: 包资源


class EIoStoreTocEntryMetaFlags(IntEnum):
    """IoStore TOC 条目元数据标志"""
    None_ = 0
    Compressed = 1 << 0
    MemoryMapped = 1 << 1


class EIoStoreTocReadOptions(IntFlag):
    """IoStore TOC 读取选项"""
    Default = 0
    ReadDirectoryIndex = 1 << 0
    ReadTocMeta = 1 << 1
    ReadAll = ReadDirectoryIndex | ReadTocMeta


# ============================================================================
# 核心数据结构
# ============================================================================

@dataclass
class FIoChunkId:
    """IoStore Chunk 标识符（12 字节）。

    结构布局（UE FIoChunkId）：
    - 字节 0-7: ChunkId (uint64, little-endian)
    - 字节 8-9: ChunkIndex (uint16, big-endian)
    - 字节 10: ChunkGroup (uint8)
    - 字节 11: ChunkType (uint8, EIoChunkType)

    比较使用完整 12 字节，与 UE 源码一致。
    """
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

    @property
    def chunk_index(self) -> int:
        """返回 ChunkIndex（字节 8-9，大端序）"""
        return (self.bytes[8] << 8) | self.bytes[9]

    @property
    def chunk_group(self) -> int:
        """返回 ChunkGroup（字节 10）"""
        return self.bytes[10]

    @property
    def chunk_type(self) -> int:
        """返回 ChunkType（字节 11）"""
        return self.bytes[11]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FIoChunkId):
            return NotImplemented
        return self.bytes == other.bytes

    def __hash__(self) -> int:
        return hash(self.bytes)


@dataclass
class FIoOffsetAndSize:
    """偏移和大小（打包为 40 位偏移 + 24 位大小）— 旧版兼容"""
    offset: int
    size: int

    def pack(self) -> bytes:
        """打包为 8 字节"""
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
class FIoOffsetAndLength:
    """偏移和长度（10 字节大端编码，5 字节偏移 + 5 字节长度）

    FIoOffsetAndLength — IoStore 标准格式
    """
    offset: int
    length: int

    @staticmethod
    def from_bytes(data: bytes) -> FIoOffsetAndLength:
        """从 10 字节解包（大端序）"""
        if len(data) < 10:
            raise ValueError("FIoOffsetAndLength 需要至少 10 字节")
        # 偏移：字节 0-4，大端序
        offset = (data[0] << 32) | (data[1] << 24) | (data[2] << 16) | (data[3] << 8) | data[4]
        # 长度：字节 5-9，大端序
        length = (data[5] << 32) | (data[6] << 24) | (data[7] << 16) | (data[8] << 8) | data[9]
        return FIoOffsetAndLength(offset=offset, length=length)

    @staticmethod
    def from_stream(stream: BinaryIO) -> FIoOffsetAndLength:
        """从流中读取 10 字节"""
        data = stream.read(10)
        return FIoOffsetAndLength.from_bytes(data)


@dataclass
class FIoDirectoryIndexEntry:
    """目录索引条目"""
    name: int
    first_child_entry: int
    next_sibling_entry: int
    first_file_entry: int

    @staticmethod
    def deserialize(stream: BinaryIO) -> FIoDirectoryIndexEntry:
        """从流反序列化"""
        data = stream.read(16)
        if len(data) < 16:
            raise ValueError("Unexpected end of stream")

        name, first_child_entry, next_sibling_entry, first_file_entry = \
            struct.unpack('<IIII', data)

        return FIoDirectoryIndexEntry(
            name=name,
            first_child_entry=first_child_entry,
            next_sibling_entry=next_sibling_entry,
            first_file_entry=first_file_entry,
        )


@dataclass
class FIoFileIndexEntry:
    """IoStore file index entry."""
    name: int
    next_file_entry: int
    user_data: int

    @staticmethod
    def deserialize(stream: BinaryIO) -> FIoFileIndexEntry:
        data = stream.read(12)
        if len(data) < 12:
            raise ValueError("Unexpected end of stream")
        name, next_file_entry, user_data = struct.unpack('<III', data)
        return FIoFileIndexEntry(
            name=name,
            next_file_entry=next_file_entry,
            user_data=user_data,
        )


# ============================================================================
# IoStore TOC 结构（144 字节头部）
# ============================================================================

# IoStore TOC 魔数："-==--==--==--==-" (16 字节)
TOC_MAGIC = b'-==--==--==--==-'

# FIoStoreTocHeader 大小
TOC_HEADER_SIZE = 144


@dataclass
class FIoStoreTocHeader:
    """IoStore TOC 头部结构（144 字节）

    镜像 FIoStoreTocHeader
    """
    toc_magic: bytes  # 16 bytes
    version: int  # uint8
    reserved0: int  # uint8
    reserved1: int  # uint16
    toc_header_size: int  # uint32
    toc_entry_count: int  # uint32
    toc_compressed_block_entry_count: int  # uint32
    toc_compressed_block_entry_size: int  # uint32
    compression_method_name_count: int  # uint32
    compression_method_name_length: int  # uint32
    compression_block_size: int  # uint32
    directory_index_size: int  # uint32
    partition_count: int  # uint32
    container_id: int  # uint64 (FIoContainerId)
    encryption_key_guid: bytes  # 16 bytes (FGuid)
    container_flags: int  # uint32 (EIoContainerFlags)
    toc_chunk_perfect_hash_seeds_count: int  # uint32
    partition_size: int  # uint64
    toc_chunks_without_perfect_hash_count: int  # uint32
    reserved7: int  # uint32
    reserved8: List[int] = field(default_factory=lambda: [0] * 5)  # 5 x uint64

    @staticmethod
    def from_stream(stream: BinaryIO) -> FIoStoreTocHeader:
        """从流中读取 TOC 头部"""
        header_data = stream.read(TOC_HEADER_SIZE)
        if len(header_data) < TOC_HEADER_SIZE:
            raise ValueError(
                f"TOC 头部数据不足：需要 {TOC_HEADER_SIZE} 字节，实际 {len(header_data)} 字节"
            )

        toc_magic = header_data[0:16]
        if toc_magic != TOC_MAGIC:
            raise ValueError(f"无效的 IoStore TOC 魔数: {toc_magic!r}")

        # 解析头部字段（小端序）
        (version, reserved0, reserved1,
         toc_header_size, toc_entry_count,
         toc_compressed_block_entry_count, toc_compressed_block_entry_size,
         compression_method_name_count, compression_method_name_length,
         compression_block_size, directory_index_size,
         partition_count) = struct.unpack_from('<BBHIIIIIIIIII', header_data, 16)

        # container_id (8 bytes) + encryption_key_guid (16 bytes) + container_flags (4 bytes)
        container_id = struct.unpack_from('<Q', header_data, 64)[0]
        encryption_key_guid = header_data[72:88]
        container_flags = struct.unpack_from('<I', header_data, 88)[0]

        # toc_chunk_perfect_hash_seeds_count (4 bytes) + partition_size (8 bytes)
        toc_chunk_perfect_hash_seeds_count = struct.unpack_from('<I', header_data, 92)[0]
        partition_size = struct.unpack_from('<Q', header_data, 96)[0]

        # toc_chunks_without_perfect_hash_count (4 bytes) + reserved7 (4 bytes)
        toc_chunks_without_perfect_hash_count = struct.unpack_from('<I', header_data, 104)[0]
        reserved7 = struct.unpack_from('<I', header_data, 108)[0]

        # reserved8 (5 bytes in header, padded to 32 bytes)
        reserved8_raw = header_data[112:144]
        reserved8 = list(reserved8_raw[:5])

        return FIoStoreTocHeader(
            toc_magic=toc_magic,
            version=version,
            reserved0=reserved0,
            reserved1=reserved1,
            toc_header_size=toc_header_size,
            toc_entry_count=toc_entry_count,
            toc_compressed_block_entry_count=toc_compressed_block_entry_count,
            toc_compressed_block_entry_size=toc_compressed_block_entry_size,
            compression_method_name_count=compression_method_name_count,
            compression_method_name_length=compression_method_name_length,
            compression_block_size=compression_block_size,
            directory_index_size=directory_index_size,
            partition_count=partition_count,
            container_id=container_id,
            encryption_key_guid=encryption_key_guid,
            container_flags=container_flags,
            toc_chunk_perfect_hash_seeds_count=toc_chunk_perfect_hash_seeds_count,
            partition_size=partition_size,
            toc_chunks_without_perfect_hash_count=toc_chunks_without_perfect_hash_count,
            reserved7=reserved7,
            reserved8=reserved8,
        )

    @property
    def is_encrypted(self) -> bool:
        """容器是否加密"""
        return bool(self.container_flags & EIoContainerFlags.Encrypted)

    @property
    def is_compressed(self) -> bool:
        """容器是否压缩"""
        return bool(self.container_flags & EIoContainerFlags.Compressed)

    @property
    def is_signed(self) -> bool:
        """容器是否签名"""
        return bool(self.container_flags & EIoContainerFlags.Signed)

    @property
    def is_indexed(self) -> bool:
        """容器是否有目录索引"""
        return bool(self.container_flags & EIoContainerFlags.Indexed)


@dataclass
class FIoStoreTocCompressedBlockEntry:
    """IoStore TOC 压缩块条目（12 字节）

    位分布：
    - Offset: 5 字节（位 0-39）
    - CompressedSize: 3 字节（位 40-63）
    - UncompressedSize: 3 字节（位 64-87）
    - CompressionMethodIndex: 1 字节（位 88-95）
    """
    offset: int  # 5 bytes
    compressed_size: int  # 3 bytes
    uncompressed_size: int  # 3 bytes
    compression_method_index: int  # 1 byte

    SIZE = 12  # 字节大小

    @staticmethod
    def from_stream(stream: BinaryIO) -> FIoStoreTocCompressedBlockEntry:
        """从流中读取"""
        data = stream.read(12)
        if len(data) < 12:
            raise ValueError("压缩块条目数据不足")

        # 12 字节小端解析
        # 字节 0-4: Offset (5 bytes, little-endian)
        offset = data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24) | ((data[4] & 0xFF) << 32)

        # 字节 5-7: CompressedSize (3 bytes)
        compressed_size = data[5] | (data[6] << 8) | (data[7] << 16)

        # 字节 8-10: UncompressedSize (3 bytes)
        uncompressed_size = data[8] | (data[9] << 8) | (data[10] << 16)

        # 字节 11: CompressionMethodIndex (1 byte)
        compression_method_index = data[11]

        return FIoStoreTocCompressedBlockEntry(
            offset=offset,
            compressed_size=compressed_size,
            uncompressed_size=uncompressed_size,
            compression_method_index=compression_method_index,
        )


@dataclass
class FIoStoreTocEntryMeta:
    """IoStore TOC 条目元数据

    包含哈希（20 字节）和标志（1 字节）
    """
    chunk_hash: bytes  # 20 bytes (FSHAHash / FIoHash)
    flags: int  # 1 byte (FIoStoreTocEntryMetaFlags)

    SIZE = 24  # 20 + 1 + 3 (padding)

    @staticmethod
    def from_stream(stream: BinaryIO, use_io_hash: bool = False) -> FIoStoreTocEntryMeta:
        """从流中读取

        Args:
            stream: 输入流
            use_io_hash: 是否使用 FIoHash (20 bytes) 替代 FIoChunkHash (20 bytes)
        """
        chunk_hash = stream.read(20)
        if len(chunk_hash) < 20:
            raise ValueError("条目元数据哈希数据不足")

        flags_data = stream.read(1)
        if len(flags_data) < 1:
            raise ValueError("条目元数据标志数据不足")
        flags = flags_data[0]

        # 3 字节填充（对齐到 24 字节）
        if use_io_hash:
            stream.read(3)

        return FIoStoreTocEntryMeta(chunk_hash=chunk_hash, flags=flags)


@dataclass
class FIoContainerHeader:
    """IoStore 容器头部

    读取 ContainerHeader chunk 后解析
    """
    # 简化版本，仅存储原始数据
    data: bytes = b''

    @staticmethod
    def from_bytes(data: bytes) -> FIoContainerHeader:
        """从字节数据创建"""
        return FIoContainerHeader(data=data)
