---
title: PAK File Reading
section: pak
---

# PAK File Reading

The PAK module provides complete parsing capabilities for Unreal Engine `.pak` container files, supporting all file formats from v1 to v12, covering index decryption, bitfield-encoded entry parsing, multiple compression algorithms, and AES-ECB encryption.

**Source**: `src/uasset_read/pak/`

## Core API

### PakFileReader

```python
PakFileReader(path: str, aes_key: bytes | None = None, tolerant: bool = False)
  .open() -> None              # Open file and parse FPakInfo + Primary Index
  .close() -> None             # Close file handle
  .list_files() -> list[str]   # Return paths of all non-deleted entries
  .get_entry(path: str) -> FPakEntry | None  # Get entry information
  .extract(path: str) -> bytes | None        # Extract and decompress file data

# Context manager
with PakFileReader("game.pak") as reader:
    info = reader.info           # FPakInfo
    files = reader.list_files()
    data = reader.extract("path/to/file.uasset")
```

### Module Public API

```python
# Constants
PAK_FILE_MAGIC                     # 0x5A6F12E1
PakFileVersion                       # v1~v12 version enum
ECompressionFlags                   # Compression flags (used before v8)
Flag_Encrypted, Flag_Deleted         # Entry flags

# Data structures
FPakInfo                            # PAK trailer info (version, index offset, encryption GUID)
FPakEntry                           # File entry (offset, size, compression blocks, hash)
FPakDirectoryEntry                  # Directory entry (path + filename + entry data)
FPakCompressedBlock                 # Compression block (start/end offset)
read_fstream(stream, version)       # FString deserialization

# Index parsing
parse_primary_index(stream, pak_info, aes_key) -> (mount_point, entries, extra)
parse_path_hash_index(file_stream, offset, size, pak_info) -> dict
parse_directory_index(file_stream, offset, size, pak_info) -> dict

# Compression
decompress_block(data, uncompressed_size, method) -> bytes
decompress_entry(stream, entry, compression_method, encryption_key) -> bytes

# Encryption
decrypt_aes_ecb(data, key) -> bytes
validate_index_hash(decrypted_blob, expected_hash) -> bool
decrypt_index_blob(index_data, key, expected_hash) -> bytes

# Game detection
detect_game_from_magic(magic) -> EGame
get_game_info(game) -> (name, version)
```

## File Structure

### Module Files

| File | Responsibility |
|------|----------------|
| `pak/__init__.py` | Public API exports |
| `pak/constants.py` | Magic numbers, version enums, flags, size constants |
| `pak/structures.py` | FPakInfo, FPakEntry, FPakDirectoryEntry data structures + FString reading |
| `pak/reader.py` | PakFileReader main reader (context manager, entry parsing, decompression dispatch) |
| `pak/index.py` | Primary Index parsing (legacy v<10 and v10+ PathHashIndex) |
| `pak/decompress.py` | Compression block decompression dispatch (Zlib/Gzip/LZ4/Zstd/Oodle) |
| `pak/crypto.py` | AES-ECB decryption, index hash validation |
| `pak/game_versions.py` | Game identity detection (magic number → game → PAK version mapping) |

### Binary Layout

```
┌─────────────────────────────────────────────────────┐
│                     .pak file                        │
├─────────────────────────────────────────────────────┤
│  Mount Point (FString)                              │
│  Index Blob (Primary Index)                          │
│    ├─ v<10: N × (FString path + FPakEntry)           │
│    └─ v10+: PathHashSeed + PathHashIndex             │
│             + DirectoryIndex + Encoded Entries        │
│  ... File data region ...                            │
├─────────────────────────────────────────────────────┤
│  FPakInfo Trailer (file end)                         │
│    ├─ v<7: Magic(4) + Version(4) + IndexOffset(8)    │
│    │         + IndexSize(8) + IndexHash(20)          │
│    ├─ v7:  + EncryptionKeyGuid(16) + bEncrypted(1)   │
│    ├─ v8:  + CompressionMethods(32×5)               │
│    └─ v9:  + FrozenIndex(1)                          │
│    └─ v10+: - FrozenIndex (removed)                  │
└─────────────────────────────────────────────────────┘
```

## Data Structures

### FPakInfo

PAK file trailer information structure, located at the end of the file, detected by reverse scanning from the tail.

```python
@dataclass
class FPakInfo:
    magic: int                      # Magic number (standard or game-specific)
    version: int                    # File format version (1~12)
    index_offset: int               # Primary Index offset in file
    index_size: int                 # Index blob size
    index_hash: bytes               # SHA1 of index blob (20 bytes)
    encryption_key_guid: bytes      # Encryption key GUID (16 bytes, v7+)
    encrypted_index: bool           # Whether index is encrypted (v7+)
    compression_methods: list       # Compression method name table (max 5, v8+)
    index_is_frozen: bool           # FrozenIndex flag (v9 only)
    detected_game: int              # Detected game identity
```

**Serialized Size by Version**:

| Version Range | Size | Fields |
|---------------|------|--------|
| v1~6 | 44 bytes | Magic + Version + IndexOffset + IndexSize + IndexHash |
| v7 | 61 bytes | + EncryptionKeyGuid(16) + bEncryptedIndex(1) |
| v8 | 221 bytes | + CompressionMethods(32×5=160) |
| v9 | 222 bytes | + FrozenIndex(1) |
| v10+ | 221 bytes | - FrozenIndex (removed) |

### FPakEntry

Describes offset, size, compression, encryption, and hash information for a single file in the PAK.

```python
@dataclass
class FPakEntry:
    offset: int                     # Entry data start offset (int64)
    uncompressed_size: int          # Uncompressed size (int64)
    size: int                       # Compressed size (int64, equals uncompressed_size when not compressed)
    compression_method_index: int   # Index in FPakInfo.compression_methods (uint32)
    is_encrypted: bool              # Whether encrypted
    is_compressed: bool             # Whether compressed (derived)
    compression_block_count: int    # Number of compression blocks
    compression_block_size: int     # Size of each compression block (uint32)
    compression_blocks: list        # list[FPakCompressedBlock]
    hash: bytes                     # SHA1 of uncompressed data (20 bytes)
    flags: int                      # Raw flags
    is_deleted: bool                # Whether deleted (derived from flags)
    serialized_size: int            # Entry size in v10+ bitfield encoding
```

**v10+ Bitfield Encoding Layout**:

| Bit | Field | Description |
|-----|-------|-------------|
| 31 | Offset fits 32-bit | When 1, Offset stored as uint32 |
| 30 | UncompressedSize fits 32-bit | When 1, stored as uint32 |
| 29 | Size fits 32-bit | When 1, stored as uint32 |
| 23~28 | Compression method index | 6 bits, index value |
| 22 | Encrypted flag | 1 bit |
| 6~21 | Compression block count | 16 bits |
| 0~5 | Compression block size index | 6 bits, 0x3F means read from stream |

### FPakCompressedBlock

```python
@dataclass
class FPakCompressedBlock:
    compressed_start: int     # Absolute file offset (int64)
    compressed_end: int       # Exclusive end offset (int64)
```

### FPakDirectoryEntry

```python
@dataclass
class FPakDirectoryEntry:
    path: str             # Directory path
    filename: str         # Filename
    entry: FPakEntry      # Entry data
```

## File Versions

```
v1   Initial — Initial version
v2   NoTimestamps — Removed Timestamp field from FPakEntry
v3   CompressionEncryption — Compression encryption support (legacy format)
v4   IndexEncryption — Index encryption support (legacy format)
v5   RelativeChunkOffsets — Compression block offsets changed to relative values
v6   DeleteRecords — Added Flag_Deleted support
v7   EncryptionKeyGuid — Added EncryptionKeyGuid and bEncryptedIndex
v8   FNameBasedCompressionMethod — Added CompressionMethods name table (replaces bit flags)
v9   FrozenIndex — Added FrozenIndex flag (deprecated)
v10  PathHashIndex — Introduced PathHashIndex, DirectoryIndex, bitfield-encoded entries
v11  Fnv64BugFix — FNV64 hash collision fix (Frostbite game-specific)
v12  Utf8PakDirectory — Directory names use FUtf8String (uint32 length + UTF-8)
```

## Compression and Encryption

### Compression Methods

| Method | Description | Dependency |
|--------|-------------|------------|
| None | No compression | None |
| Zlib | raw deflate (wbits=-15) | None (stdlib) |
| Gzip | gzip format | None (stdlib) |
| LZ4 | LZ4 block compression | `lz4` (optional) |
| Zstd | Zstandard compression | `zstandard` (optional) |
| Oodle | Oodle compression (proprietary) | `oo2core` (not supported) |

**Compression Method Mapping**:

| Index | Name |
|-------|------|
| 0 | None |
| 1 | Zlib |
| 2 | Gzip |
| 3 | Oodle |
| 4 | LZ4 |
| 5 | Zstd |

### AES Encryption

- **Algorithm**: AES-ECB (no padding)
- **Key Length**: 16 bytes (128-bit)
- **Alignment**: 16-byte aligned
- **Dependency**: `cryptography` (optional)
- **Scope**: File entry data + index blob (v7+)

### Magic Numbers

Standard magic number: `0x5A6F12E1`

Game-specific magic numbers:

| Magic Number | Game | PAK Version |
|--------------|------|-------------|
| `0x5A6F12E1` | Standard (default) | v12 |
| `0xA590ED1E` | Outlast Trials | v10 |
| `0x6B2A56B8` | Torchlight Infinite | v10 |
| `0xA4CCD123` | Wild Assault | v10 |
| `0x5A6F12EC` | Gameloop Undawn | v10 |
| `0x65617441` | Friday the 13th | v5 |
| `0x1B6A32F1` | Dream Star | v10 |
| `0xFF67FF70` | Game for Peace | v8 |
| `0x81C4B35B` | KartRider Drift | v10 |
| `0x9A51DA3F` | Racing Master | v10 |
| `0x22CE976A` | Crystal of Atlan | v10 |
| `0x11ADDE11` | Promise Mascot Agency | v10 |
| `0x53647586` | Arena Breakout Infinite | v10 |
| `0x4F6FAE86` | Assault Fire Future | v10 |

## Index Format

### Legacy Format (v<10)

```
Mount Point (FString)
Entry Count (int32)
├─ For each entry:
│  ├─ Path (FString)
│  └─ FPakEntry (legacy deserialization)
```

### v10+ Format

```
Mount Point (FString)
Entry Count (int32)
PathHashSeed (uint64)
bHasPathHashIndex (bool)
├─ If true:
│  ├─ PathHashIndexOffset (int64)
│  └─ PathHashIndexSize (int64)
bHasDirectoryIndex (bool)
├─ If true:
│  ├─ DirectoryIndexOffset (int64)
│  └─ DirectoryIndexSize (int64)
EncodedPakEntries: Count (uint32) + N × (serialized_size + bitfield data)
NonEncodedEntries: Count (uint32) + N × (FString path + serialized_size + bitfield data)
```

### PathHashIndex

```
Entry Count (uint32)
├─ For each entry:
│  ├─ PathHash (uint64)
│  ├─ FileOffset (int64)
│  └─ EntrySize (int64)
```

Mapping: `path_hash -> (file_offset, size)`

### DirectoryIndex

```
Directory Count (uint32)
├─ For each directory:
│  ├─ DirName (FString)
│  ├─ File Count (uint32)
│  └─ For each file:
│     ├─ FileName (FString)
│     ├─ FileOffset (int64)
│     └─ FileSize (int64)
```

Mapping: `directory -> {filename -> (file_offset, size)}`

## FString Reading

UE FString format (length-prefixed, null-terminated):

| Length Value | Encoding | Data Length | Terminator |
|--------------|----------|-------------|------------|
| 0 | Empty string | — | — |
| >0 | ANSI/UTF-8 | length bytes | 1 byte `\x00` |
| <0 | UTF-16LE | abs(length) × 2 bytes | 2 bytes `\x00\x00` |
| v12+ uint32 | UTF-8 | length bytes | 1 byte `\x00` |

**Safety Limit**: String length does not exceed `MAX_FSTRING_LENGTH`.

## Usage Examples

### Basic Reading

```python
from uasset_read.pak import PakFileReader

with PakFileReader("game.pak") as reader:
    # View PAK info
    print(f"Version: {reader.info.version}")
    print(f"Mount point: {reader.mount_point}")
    print(f"Entries: {len(reader.entries)}")

    # List all files
    for path in reader.list_files():
        print(path)

    # Extract a file
    data = reader.extract("Game/Content/MyBlueprint.uasset")
    if data:
        with open("MyBlueprint.uasset", "wb") as f:
            f.write(data)
```

### Encrypted PAK Reading

```python
aes_key = bytes.fromhex("0123456789abcdef0123456789abcdef")

with PakFileReader("encrypted.pak", aes_key=aes_key) as reader:
    if reader.info.encrypted_index:
        print("Index is encrypted")
        print(f"Encryption Key GUID: {reader.info.encryption_key_guid.hex()}")

    data = reader.extract("Game/Content/EncryptedAsset.uasset")
```

### Manual FPakInfo Parsing

```python
from uasset_read.pak import FPakInfo

with open("game.pak", "rb") as f:
    f.seek(0, 2)
    file_size = f.tell()
    f.seek(0)

    info = FPakInfo.deserialize(f, file_size)
    print(f"Magic: 0x{info.magic:08X}")
    print(f"Version: {info.version}")
    print(f"Game: {info.detected_game}")
    print(f"Index offset: {info.index_offset}")
    print(f"Methods: {info.compression_methods}")
```

## Dependencies

| Feature | Package | Required |
|---------|---------|----------|
| Basic parsing | Python stdlib | Yes |
| LZ4 decompression | `lz4` | Optional |
| Zstd decompression | `zstandard` | Optional |
| AES decryption | `cryptography` | Optional |
| Oodle decompression | `oo2core` | Not supported (proprietary) |

## Related Sections

[[Package Management]] · [[IoStore Containers]] · [[Raw File Parsing]]
