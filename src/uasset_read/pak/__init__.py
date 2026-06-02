"""
Pak 文件解析模块

Public API:
- PakFileReader: Main orchestrator for .pak file parsing
- FPakInfo, FPakEntry, FPakDirectoryEntry, FPakCompressedBlock: Data models
- PAK_FILE_MAGIC: Magic constant for format detection
- read_fstring: FString deserialization utility
- parse_primary_index: Index blob parsing
- decompress_block, decompress_entry: Compression dispatch
- decrypt_aes_ecb, decrypt_index_blob: AES-ECB decryption
"""

# Constants
from uasset_read.pak.constants import (
    PAK_FILE_MAGIC,
    PakFileVersion,
    ECompressionFlags,
    Flag_Encrypted,
    Flag_Deleted,
    MaxNumCompressionMethods,
    PAK_INFO_SIZES,
)

# Data models
from uasset_read.pak.structures import (
    FPakCompressedBlock,
    FPakEntry,
    FPakInfo,
    FPakDirectoryEntry,
    read_fstring,
)

# Compression
from uasset_read.pak.decompress import (
    decompress_block,
    decompress_entry,
)

# Crypto helpers import without optional dependencies; cryptography is loaded
# lazily inside decrypt_aes_ecb() when decryption is actually requested.
from uasset_read.pak.crypto import (
    decrypt_aes_ecb,
    validate_index_hash,
    decrypt_index_blob,
)

# Index parsing
from uasset_read.pak.index import (
    parse_primary_index,
)

# Reader
from uasset_read.pak.reader import (
    PakFileReader,
)

__all__ = [
    # Constants
    "PAK_FILE_MAGIC",
    "PakFileVersion",
    "ECompressionFlags",
    "Flag_Encrypted",
    "Flag_Deleted",
    "MaxNumCompressionMethods",
    "PAK_INFO_SIZES",
    # Data models
    "FPakCompressedBlock",
    "FPakEntry",
    "FPakInfo",
    "FPakDirectoryEntry",
    "read_fstring",
    # Compression
    "decompress_block",
    "decompress_entry",
    # Crypto
    "decrypt_aes_ecb",
    "validate_index_hash",
    "decrypt_index_blob",
    # Index
    "parse_primary_index",
    # Reader
    "PakFileReader",
]
