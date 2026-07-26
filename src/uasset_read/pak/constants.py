"""
Pak file constant definitions.

Mirrors magic numbers, version enums, and flag constants from UE engine IPlatformFilePak.h.
"""
from enum import IntEnum, IntFlag

# ============================================================================
# Pak File Magic
# ============================================================================

PAK_FILE_MAGIC = 0x5A6F12E1  # uint32, little-endian

# Game-specific magic numbers (extended support)
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

# Set of all valid magic numbers (for detection)
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

    Version boundary notes:
    - v1: Initial
    - v2: Removed Timestamp field from FPakEntry
    - v3: CompressionEncryption (legacy)
    - v4: IndexEncryption (legacy)
    - v5: Compression block offsets changed to relative values (RelativeChunkOffsets)
    - v6: Added Flag_Deleted support
    - v7: Added EncryptionKeyGuid and bEncryptedIndex
    - v8: Added CompressionMethods table (FName-based)
    - v9: Added FrozenIndex flag (deprecated)
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

    Version >= 8 uses FPakInfo.compression_methods table instead of bit flags.
    """
    NONE = 0
    Zlib = 1
    Gzip = 2
    LZ4 = 4
    Zstd = 8
    Oodle = 16


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
# bEncryptedIndex (1 byte) is unconditionally serialized for ALL versions
PAK_INFO_SIZES = {
    "v1-6": 45,    # Magic(4) + Version(4) + IndexOffset(8) + IndexSize(8) + IndexHash(20) + bEncryptedIndex(1)
    "v7": 61,      # + EncryptionKeyGuid(16)
    "v8": 221,     # + CompressionMethods(32*5=160)
    "v9": 222,     # + FrozenIndex(1)
    "v10+": 221,   # - FrozenIndex (removed in v10)
}
