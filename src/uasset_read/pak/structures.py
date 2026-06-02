"""
Pak 文件数据结构

镜像 UE 引擎 IPlatformFilePak.h 中的 FPakInfo、FPakEntry、FPakDirectoryEntry 等结构。
"""
import struct
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, BinaryIO, Dict, Optional

from uasset_read.exceptions import ParseError
from uasset_read.constants import MAX_FSTRING_LENGTH
from uasset_read.pak.constants import (
    PAK_FILE_MAGIC,
    PAK_FILE_MAGICS,
    PakFileVersion,
    PAK_INFO_SIZES,
    Flag_Encrypted,
    Flag_Deleted,
)
from uasset_read.pak.game_versions import detect_game_from_magic, get_game_info, EGame


# ============================================================================
# FString Reader (shared utility)
# ============================================================================

def read_fstring(stream: BinaryIO, version: int = 0) -> str:
    """读取 UE FString（带长度前缀，null-terminated）。

    Args:
        stream: 二进制流
        version: Pak 文件版本（>= 12 可能使用 FUtf8String）

    Returns:
        解码后的字符串

    UE FString 格式：
    - int32 length: 正数=ANSI，负数=UTF-16，0=空字符串
    - length 字节的数据 + 1 字节 null 终止符（ANSI）
    - abs(length)*2 字节数据 + 2 字节 null 终止符（UTF-16）
    - version >= 12: uint32 length（无符号），UTF-8 编码
    """
    if version >= PakFileVersion.Utf8PakDirectory:
        # FUtf8String: uint32 length + UTF-8 bytes + 1 null terminator
        length_bytes = stream.read(4)
        if len(length_bytes) < 4:
            raise ParseError("Unexpected end of stream reading FUtf8String length")
        length = struct.unpack('<I', length_bytes)[0]
        if length == 0:
            # Read null terminator
            stream.read(1)
            return ""
        if length > MAX_FSTRING_LENGTH:
            raise ParseError(
                f"FUtf8String length {length} exceeds maximum {MAX_FSTRING_LENGTH}"
            )
        data = stream.read(length)
        stream.read(1)  # null terminator
        return data.decode('utf-8', errors='replace').rstrip('\x00')

    # Standard FString: int32 length
    length_bytes = stream.read(4)
    if len(length_bytes) < 4:
        raise ParseError("Unexpected end of stream reading FString length")
    length = struct.unpack('<i', length_bytes)[0]

    if length == 0:
        return ""

    if length < 0:
        # UTF-16
        utf16_len = -length * 2
        if utf16_len > MAX_FSTRING_LENGTH:
            raise ParseError(
                f"UTF-16 string length {utf16_len} exceeds maximum {MAX_FSTRING_LENGTH}"
            )
        data = stream.read(utf16_len)
        stream.read(2)  # null terminator (2 bytes for UTF-16)
        return data.decode('utf-16-le', errors='replace').rstrip('\x00')
    else:
        # ANSI / UTF-8
        if length > MAX_FSTRING_LENGTH:
            raise ParseError(
                f"ANSI string length {length} exceeds maximum {MAX_FSTRING_LENGTH}"
            )
        data = stream.read(length)
        stream.read(1)  # null terminator
        return data.decode('ascii', errors='replace').rstrip('\x00')


# ============================================================================
# FPakCompressedBlock
# ============================================================================

@dataclass
class FPakCompressedBlock:
    """压缩块信息。

    compressed_start/compressed_end 在解析后转换为绝对文件偏移。
    对于 version < 5 (RelativeChunkOffsets)，需要在加载后加上 entry.offset。
    """
    compressed_start: int  # int64 — 绝对文件偏移
    compressed_end: int    # int64 — 独占结束偏移


# ============================================================================
# FPakEntry
# ============================================================================

@dataclass
class FPakEntry:
    """Pak 文件条目。

    描述 pak 中单个文件的偏移、大小、压缩、加密和哈希信息。
    对应 UE IPlatformFilePak.h 中的 FPakEntry 结构。
    """
    offset: int = 0                      # int64 — 条目数据起始偏移
    uncompressed_size: int = 0           # int64 — 解压后大小
    size: int = 0                        # int64 — 压缩大小（未压缩时 == uncompressed_size）
    compression_method_index: int = 0    # uint32 — 在 FPakInfo.compression_methods 中的索引
    is_encrypted: bool = False           # 是否加密
    is_compressed: bool = False          # 是否压缩（derived from compression_method_index > 0）
    compression_block_count: int = 0     # uint16/uint32 取决于版本
    compression_block_size: int = 0      # uint32 — 每个压缩块的大小（未压缩）
    compression_blocks: list = field(default_factory=list)  # list[FPakCompressedBlock]
    hash: bytes = b""                    # 20 bytes — SHA1 of uncompressed data
    flags: int = 0                       # 原始标志位
    is_deleted: bool = False             # 是否已删除（derived from flags）
    serialized_size: int = 0             # v10+ bitfield 编码时的条目大小

    @classmethod
    def deserialize_legacy(cls, stream: BinaryIO, version: int) -> "FPakEntry":
        """从流中反序列化完整 FPakEntry（version < 10 的旧格式）。

        序列化顺序（UE FPakEntry::Serialize）：
        - Offset (int64)
        - UncompressedSize (int64)
        - Size (int64)
        - CompressionMethodIndex (uint32)
        - [Timestamp (int64) — version < 2 only, removed in v2]
        - CompressionBlockCount (uint16 if v<8 else uint32)
        - CompressionBlockSize (uint32)
        - CompressionBlocks [array]
        - Hash [20 bytes]
        """
        entry = cls()

        entry.offset = struct.unpack('<q', stream.read(8))[0]
        entry.uncompressed_size = struct.unpack('<q', stream.read(8))[0]
        entry.size = struct.unpack('<q', stream.read(8))[0]
        entry.compression_method_index = struct.unpack('<I', stream.read(4))[0]

        # Timestamp removed in version 2 (PakFile_Version_NoTimestamps)
        if version < PakFileVersion.NoTimestamps:
            stream.read(8)

        if version < PakFileVersion.FNameBasedCompressionMethod:
            entry.compression_block_count = struct.unpack('<H', stream.read(2))[0]
        else:
            entry.compression_block_count = struct.unpack('<I', stream.read(4))[0]

        entry.compression_block_size = struct.unpack('<I', stream.read(4))[0]

        # Compression blocks
        for _ in range(entry.compression_block_count):
            block_start = struct.unpack('<q', stream.read(8))[0]
            block_end = struct.unpack('<q', stream.read(8))[0]
            entry.compression_blocks.append(
                FPakCompressedBlock(compressed_start=block_start, compressed_end=block_end)
            )

        # SHA1 hash
        entry.hash = stream.read(20)

        entry.is_compressed = entry.compression_method_index > 0
        return entry

    @classmethod
    def decode_bitfield(cls, data: bytes, offset: int, pak_info: "FPakInfo") -> tuple["FPakEntry", int]:
        """解码 v10+ bitfield 编码的 FPakEntry。

        Bitfield 布局（UE PakFile.cpp DecodePakEntry）：
        - Bit 31: Offset fits in 32-bit
        - Bit 30: UncompressedSize fits in 32-bit
        - Bit 29: Size fits in 32-bit
        - Bits 23-28: Compression method index (6 bits)
        - Bit 22: Encrypted flag
        - Bits 6-21: Compression block count (16 bits)
        - Bits 0-5: Compression block size index (6 bits, 0x3F=read from stream)

        Args:
            data: 包含 bitfield 的字节流
            offset: bitfield 在 data 中的起始偏移
            pak_info: FPakInfo 实例，提供压缩方法表

        Returns:
            (FPakEntry, bytes_consumed)
        """
        entry = cls()
        start_offset = offset

        # Read bitfield (4 bytes, little-endian)
        bitfield = struct.unpack_from('<I', data, offset)[0]
        offset += 4

        # Decode fields from bitfield
        offset_fits_32 = bool(bitfield & (1 << 31))
        uncompressed_size_fits_32 = bool(bitfield & (1 << 30))
        size_fits_32 = bool(bitfield & (1 << 29))
        entry.compression_method_index = (bitfield >> 23) & 0x3F
        entry.is_encrypted = bool(bitfield & (1 << 22))
        entry.compression_block_count = (bitfield >> 6) & 0xFFFF
        block_size_index = bitfield & 0x3F

        # Read actual values for fields that don't fit in 32-bit
        if offset_fits_32:
            entry.offset = struct.unpack_from('<I', data, offset)[0]
            offset += 4
        else:
            entry.offset = struct.unpack_from('<q', data, offset)[0]
            offset += 8

        # Read UncompressedSize
        if uncompressed_size_fits_32:
            entry.uncompressed_size = struct.unpack_from('<I', data, offset)[0]
            offset += 4
        else:
            entry.uncompressed_size = struct.unpack_from('<q', data, offset)[0]
            offset += 8

        # Size defaults to UncompressedSize
        entry.size = entry.uncompressed_size

        # Read CompressedSize only if entry is compressed
        if entry.compression_method_index > 0:
            if size_fits_32:
                entry.size = struct.unpack_from('<I', data, offset)[0]
                offset += 4
            else:
                entry.size = struct.unpack_from('<q', data, offset)[0]
                offset += 8

        # Block size: 0x3F means read from stream
        if block_size_index == 0x3F:
            entry.compression_block_size = struct.unpack_from('<I', data, offset)[0]
            offset += 4
        else:
            # Block size index maps to actual size
            # UE 源码: (bitfield & 0x3f) << 11 = index * 2048
            entry.compression_block_size = block_size_index << 11

        entry.is_compressed = entry.compression_method_index > 0
        entry.flags = Flag_Encrypted if entry.is_encrypted else 0
        entry.serialized_size = offset - start_offset

        return entry, entry.serialized_size

    def encode_bitfield(self) -> bytes:
        """编码 v10+ bitfield 格式的 FPakEntry。

        与 decode_bitfield 对称的编码方法，用于序列化写入。

        Returns:
            编码后的字节数据
        """
        result = bytearray()

        # 构建 bitfield (4 bytes)
        bitfield = 0

        # 判断是否适合 32 位
        offset_fits_32 = self.offset <= 0xFFFFFFFF
        uncompressed_size_fits_32 = self.uncompressed_size <= 0xFFFFFFFF
        size_fits_32 = self.size <= 0xFFFFFFFF

        if offset_fits_32:
            bitfield |= (1 << 31)
        if uncompressed_size_fits_32:
            bitfield |= (1 << 30)
        if size_fits_32:
            bitfield |= (1 << 29)

        # 压缩方法索引 (6 bits)
        bitfield |= (self.compression_method_index & 0x3F) << 23

        # 加密标志
        if self.is_encrypted:
            bitfield |= (1 << 22)

        # 压缩块数量 (16 bits)
        bitfield |= (self.compression_block_count & 0xFFFF) << 6

        # 压缩块大小索引 (6 bits)
        # 如果大小是 2048 的倍数且 <= 131072，使用索引；否则使用 0x3F 并在后面写入实际大小
        if self.compression_block_size > 0 and self.compression_block_size % 2048 == 0:
            block_size_index = self.compression_block_size >> 11
            if block_size_index <= 0x3E:  # 0x3F 保留给 "read from stream"
                bitfield |= block_size_index
            else:
                bitfield |= 0x3F
        else:
            bitfield |= 0x3F

        result.extend(struct.pack('<I', bitfield))

        # 写入 Offset
        if offset_fits_32:
            result.extend(struct.pack('<I', self.offset))
        else:
            result.extend(struct.pack('<q', self.offset))

        # 写入 UncompressedSize
        if uncompressed_size_fits_32:
            result.extend(struct.pack('<I', self.uncompressed_size))
        else:
            result.extend(struct.pack('<q', self.uncompressed_size))

        # 写入 Size（仅压缩时）
        if self.compression_method_index > 0:
            if size_fits_32:
                result.extend(struct.pack('<I', self.size))
            else:
                result.extend(struct.pack('<q', self.size))

        # 写入 BlockSize（如果使用 0x3F 标记）
        if (bitfield & 0x3F) == 0x3F and self.compression_block_size > 0:
            result.extend(struct.pack('<I', self.compression_block_size))

        self.serialized_size = len(result)
        return bytes(result)


# ============================================================================
# FPakInfo
# ============================================================================

@dataclass
class FPakInfo:
    """Pak 文件尾部信息结构。

    FPakInfo 位于文件末尾，通过从尾部反向扫描不同大小的版本来检测。
    新字段 prepend 在 Magic 之前以保持向后兼容。

    对应 UE IPlatformFilePak.h 中的 FPakInfo::Serialize。
    """
    magic: int = PAK_FILE_MAGIC
    version: int = 0
    index_offset: int = 0          # int64 — Primary Index 在文件中的偏移
    index_size: int = 0            # int64 — Index blob 大小
    index_hash: bytes = b""        # 20 bytes — SHA1 of index blob
    encryption_key_guid: bytes = b""  # 16 bytes, version >= 7
    encrypted_index: bool = False     # version >= 7
    compression_methods: list = field(default_factory=list)  # up to 5 names, version >= 8
    index_is_frozen: bool = False   # version 9 only
    detected_game: int = EGame.UNKNOWN  # 检测到的游戏标识

    @classmethod
    def _serialized_size(cls, version: int) -> int:
        """返回指定版本的 FPakInfo 序列化大小。"""
        if version <= 6:
            return PAK_INFO_SIZES["v1-6"]
        elif version == 7:
            return PAK_INFO_SIZES["v7"]
        elif version == 8:
            return PAK_INFO_SIZES["v8"]
        elif version == 9:
            return PAK_INFO_SIZES["v9"]
        else:
            return PAK_INFO_SIZES["v10+"]

    @classmethod
    def deserialize(cls, stream: BinaryIO, file_size: int) -> "FPakInfo":
        """从文件尾部检测并反序列化 FPakInfo。

        算法：从最新版本 (12) 到最早版本 (1) 迭代，
        计算 pos = file_size - serialized_size，seek 到 pos，
        读取 4 字节检查 magic 是否匹配。

        Args:
            stream: 文件流
            file_size: 文件总大小

        Returns:
            解析后的 FPakInfo 实例

        Raises:
            ParseError: 如果没有版本匹配
        """
        # Version groups by serialized size, ordered latest first within each size
        version_groups = [
            (12, 11, 10),  # 221 bytes
            (9,),           # 222 bytes
            (8,),           # 221 bytes (same size as v10+, but different structure)
            (7,),           # 61 bytes
            (6, 5, 4, 3, 2, 1),  # 44 bytes
        ]

        for group in version_groups:
            info_size = cls._serialized_size(group[0])
            pos = file_size - info_size
            if pos < 0:
                continue

            # For v7+, the magic is at offset 17 (after EncryptionKeyGuid[16] + bEncryptedIndex[1])
            # For v1-6, magic is at offset 0
            magic_offset_in_trailer = 17 if group[0] >= PakFileVersion.EncryptionKeyGuid else 0

            stream.seek(pos + magic_offset_in_trailer)
            raw = stream.read(4)
            if len(raw) < 4:
                continue

            magic = struct.unpack('<I', raw)[0]
            # 检查标准魔数和游戏特定魔数
            if magic not in PAK_FILE_MAGICS:
                continue

            # 检测游戏标识
            detected_game = detect_game_from_magic(magic)

            # Magic matched — read version field to determine exact version
            version_field = struct.unpack('<i', stream.read(4))[0]

            # Find matching version in this group
            matched_version = None
            for v in group:
                if v >= PakFileVersion.PathHashIndex:
                    if version_field >= PakFileVersion.PathHashIndex:
                        matched_version = v
                        break
                elif version_field == v:
                    matched_version = v
                    break

            if matched_version is None:
                continue

            version = matched_version

            # Deserialize from the beginning of the trailer
            stream.seek(pos)
            info = cls()
            info.version = version
            info.detected_game = detected_game

            # New fields (version >= 7): prepended before Magic
            if version >= PakFileVersion.EncryptionKeyGuid:
                info.encryption_key_guid = stream.read(16)
                info.encrypted_index = struct.unpack('<B', stream.read(1))[0] != 0

            # Core fields (always present)
            info.magic = struct.unpack('<I', stream.read(4))[0]
            info.version = struct.unpack('<i', stream.read(4))[0]
            info.index_offset = struct.unpack('<q', stream.read(8))[0]
            info.index_size = struct.unpack('<q', stream.read(8))[0]
            info.index_hash = stream.read(20)

            # FrozenIndex (version 9 only)
            if version == 9:
                info.index_is_frozen = struct.unpack('<B', stream.read(1))[0] != 0

            # Compression methods (version >= 8)
            if version >= PakFileVersion.FNameBasedCompressionMethod:
                info.compression_methods = []
                for _ in range(5):
                    name_bytes = stream.read(32)
                    name_str = name_bytes.split(b'\x00')[0].decode('ascii', errors='replace')
                    if name_str:
                        info.compression_methods.append(name_str)

            return info

        raise ParseError("Unknown .pak format — no valid FPakInfo trailer found")


# ============================================================================
# FPakDirectoryEntry
# ============================================================================

@dataclass
class FPakDirectoryEntry:
    """目录树节点。

    表示目录路径下的一个文件条目。
    """
    path: str                    # 目录路径
    filename: str                # 文件名
    entry: FPakEntry             # 实际的条目数据

def decode_encoded_pak_entry(data: bytes, is_enabled: bool) -> Optional[Dict[str, Any]]:
    """解码 v10+ 编码 Pak 条目
    
    等价实现 FPakEntry 的编码条目解码逻辑
    
    Args:
        data: 编码的条目数据
        is_enabled: 是否启用编码
        
    Returns:
        解码后的条目信息字典，或 None
    """
    if not is_enabled or len(data) < 4:
        return None
    
    value = struct.unpack('<I', data[:4])[0]
    
    # 解析位域
    compression_method_index = value & 0x3F  # 6 位
    is_encrypted = bool((value >> 6) & 1)  # 1 位
    is_compressed = bool((value >> 7) & 1)  # 1 位
    compression_block_count = (value >> 8) & 0x3FF  # 10 位
    
    # 检查 64 位大小标志
    has_64bit_size = bool((value >> 22) & 1)
    
    return {
        'compression_method_index': compression_method_index,
        'is_encrypted': is_encrypted,
        'is_compressed': is_compressed,
        'compression_block_count': compression_block_count,
        'has_64bit_size': has_64bit_size,
    }
