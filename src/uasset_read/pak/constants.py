"""
Pak 文件常量定义

镜像 UE 引擎 IPlatformFilePak.h 中的魔术数字、版本枚举、标志常量。
Phase 77 — PAK-01.
"""
from enum import IntEnum, IntFlag

# ============================================================================
# Pak File Magic
# ============================================================================

PAK_FILE_MAGIC = 0x5A6F12E1  # uint32, little-endian

# ============================================================================
# Pak File Version (E PakFileVersion)
# ============================================================================


class PakFileVersion(IntEnum):
    """Pak file format version enum.

    版本边界说明：
    - v2: 移除 FPakEntry 中的 Timestamp 字段
    - v3-4: 添加文件加密支持
    - v5: 压缩块偏移改为相对值 (RelativeChunkOffsets)
    - v6: 添加 Flag_Deleted 支持
    - v7: 添加 EncryptionKeyGuid 和 bEncryptedIndex
    - v8: 添加 CompressionMethods 表 (FName-based)
    - v9: 添加 FrozenIndex 标志 (已废弃)
    - v10: PathHashIndex, DirectoryIndex, bitfield-encoded entries
    - v11: Frostbite (game-specific variant)
    - v12: FUtf8String directory names (Utf8PakDirectory)
    """
    Initial = 1
    NoTimestamps = 2
    # v3-4: Encryption (legacy)
    EncryptionKeyGuid = 7
    FNameBasedCompressionMethod = 8
    # v9: FrozenIndex (deprecated)
    PathHashIndex = 10
    Frostbite = 11
    Utf8PakDirectory = 12


# ============================================================================
# Compression Flags (legacy, pre-v8)
# ============================================================================


class ECompressionFlags(IntFlag):
    """Legacy compression flags (pre-version 8).

    Version >= 8 使用 FPakInfo.compression_methods 表替代位标志。
    """
    NONE = 0
    Zlib = 1
    Gzip = 2
    LZ4 = 4
    Zstd = 8
    Oodle = 16

    # Deprecated flags (for reference only)
    COMPRESS_ZLIB_DEPRECATED = 256
    COMPRESS_GZIP_DEPRECATED = 512


# ============================================================================
# Pak Entry Flags
# ============================================================================

PAK_ENTRY_FLAGS = {
    "Flag_Encrypted": 0x01,
    "Flag_Deleted": 0x02,
}

Flag_Encrypted = 0x01
Flag_Deleted = 0x02

# ============================================================================
# Other Constants
# ============================================================================

MaxNumCompressionMethods = 5  # UE engine constant

# FPakInfo serialized sizes per version range
# Computed from field sizes in IPlatformFilePak.h
PAK_INFO_SIZES = {
    "v1-6": 44,    # Magic(4) + Version(4) + IndexOffset(8) + IndexSize(8) + IndexHash(20)
    "v7": 61,      # + EncryptionKeyGuid(16) + bEncryptedIndex(1)
    "v8": 221,     # + CompressionMethods(32*5=160)
    "v9": 222,     # + FrozenIndex(1)
    "v10+": 221,   # - FrozenIndex (removed in v10)
}
