"""
Pak 文件常量定义

镜像 UE 引擎 IPlatformFilePak.h 中的魔术数字、版本枚举、标志常量。
"""
from enum import IntEnum, IntFlag

# ============================================================================
# Pak File Magic
# ============================================================================

PAK_FILE_MAGIC = 0x5A6F12E1  # uint32, little-endian

# 游戏特定魔数（扩展支持）
PAK_FILE_MAGIC_OUTLAST_TRIALS = 0xA590ED1E
PAK_FILE_MAGIC_TORCHLIGHT_INFINITE = 0x6B2A56B8
PAK_FILE_MAGIC_WILD_ASSAULT = 0xA4CCD123
PAK_FILE_MAGIC_GAMELOOP_UNDAWN = 0x5A6F12EC
PAK_FILE_MAGIC_FRIDAY_THE_13TH = 0x65617441
PAK_FILE_MAGIC_DREAM_STAR = 0x1B6A32F1
PAK_FILE_MAGIC_GAME_FOR_PEACE = 0xFF67FF70
PAK_FILE_MAGIC_KART_RIDER_DRIFT = 0x81C4B35B
PAK_FILE_MAGIC_RACING_MASTER = 0x9A51DA3F
PAK_FILE_MAGIC_CRYSTAL_OF_ATLAN = 0x22CE976A
PAK_FILE_MAGIC_PROMISE_MASCOT_AGENCY = 0x11ADDE11
PAK_FILE_MAGIC_ARENA_BREAKOUT_INFINITE = 0x53647586
PAK_FILE_MAGIC_ASSAULT_FIRE_FUTURE = 0x4F6FAE86

# 所有有效魔数集合（用于检测）
PAK_FILE_MAGICS = {
    PAK_FILE_MAGIC,
    PAK_FILE_MAGIC_OUTLAST_TRIALS,
    PAK_FILE_MAGIC_TORCHLIGHT_INFINITE,
    PAK_FILE_MAGIC_WILD_ASSAULT,
    PAK_FILE_MAGIC_GAMELOOP_UNDAWN,
    PAK_FILE_MAGIC_FRIDAY_THE_13TH,
    PAK_FILE_MAGIC_DREAM_STAR,
    PAK_FILE_MAGIC_GAME_FOR_PEACE,
    PAK_FILE_MAGIC_KART_RIDER_DRIFT,
    PAK_FILE_MAGIC_RACING_MASTER,
    PAK_FILE_MAGIC_CRYSTAL_OF_ATLAN,
    PAK_FILE_MAGIC_PROMISE_MASCOT_AGENCY,
    PAK_FILE_MAGIC_ARENA_BREAKOUT_INFINITE,
    PAK_FILE_MAGIC_ASSAULT_FIRE_FUTURE,
}

# ============================================================================
# Pak File Version (E PakFileVersion)
# ============================================================================


class PakFileVersion(IntEnum):
    """Pak file format version enum.

    版本边界说明：
    - v1: Initial
    - v2: 移除 FPakEntry 中的 Timestamp 字段
    - v3: CompressionEncryption (legacy)
    - v4: IndexEncryption (legacy)
    - v5: 压缩块偏移改为相对值 (RelativeChunkOffsets)
    - v6: 添加 Flag_Deleted 支持
    - v7: 添加 EncryptionKeyGuid 和 bEncryptedIndex
    - v8: 添加 CompressionMethods 表 (FName-based)
    - v9: 添加 FrozenIndex 标志 (已废弃)
    - v10: PathHashIndex, DirectoryIndex, bitfield-encoded entries
    - v11: Frostbite (game-specific variant) / Fnv64BugFix
    - v12: FUtf8String directory names (Utf8PakDirectory)
    """
    Initial = 1
    NoTimestamps = 2
    CompressionEncryption = 3
    IndexEncryption = 4
    RelativeChunkOffsets = 5
    DeleteRecords = 6
    EncryptionKeyGuid = 7
    FNameBasedCompressionMethod = 8
    FrozenIndex = 9  # deprecated
    PathHashIndex = 10
    Fnv64BugFix = 11
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
