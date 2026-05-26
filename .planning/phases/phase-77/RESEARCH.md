# Phase 77: Pak File Parsing - Research

**Researched:** 2026-05-26
**Domain:** Unreal Engine .pak file format (FPakInfo, FPakEntry, directory index, AES encryption, compression dispatch)
**Confidence:** HIGH

## Summary

This research covers the complete .pak file format as implemented in Unreal Engine source (UE 5.x from `E:\Develop\lib\UnrealEngine`) and the CUE4Parse C# library (FabianFG/CUE4Parse, GitHub master branch as of 2026-05-26). The .pak format is a trailer-indexed archive: the FPakInfo header sits at the end of the file, pointing to an index region that contains file entries, mount points, and directory structures. Each file entry (FPakEntry) describes offset, size, compression, encryption, and hash of a single packed file.

**Primary recommendation:** Follow the UE engine serialization order exactly as documented in `IPlatformFilePak.h` and `PakFile.cpp`. Use CUE4Parse as a reference for game-specific format deviations (custom magic numbers, XOR obfuscation, bitfield-encoded entries). For Python implementation, use `struct` module for binary reads, `cryptography` library for AES-ECB decryption, and `zstandard`/`lz4`/`zlib` for decompression.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Binary file reading (FArchive emulation) | API / Backend | — | Stream-based byte reading with position/seek |
| FPakInfo header parsing | API / Backend | — | Trailer deserialization at file end |
| FPakEntry deserialization | API / Backend | — | Per-entry binary structure parsing |
| Index decryption (AES-ECB) | API / Backend | — | Block cipher applied to index blob |
| Compression dispatch | API / Backend | — | Decompress per-block using method from FPakInfo table |
| Directory tree building | API / Backend | — | In-memory map from path hash / directory name to entries |
| File content extraction | API / Backend | — | Read + decrypt + decompress pipeline |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `struct` | Python stdlib | Binary unpacking of FPakInfo/FPakEntry fields | Zero dependency, precise control over byte order |
| `hashlib` | Python stdlib | SHA1 hash computation for index validation | Standard library, matches UE's FSHA1 |
| `cryptography` | >=41.0 | AES-ECB decryption for encrypted indexes | Industry standard, supports ECB mode with no padding |
| `zlib` | Python stdlib | Zlib decompression | Built-in, matches UE's Zlib handler |
| `lz4` | >=4.3 (PyPI: `lz4`) | LZ4 block decompression | Fast LZ4 binding, matches UE's LZ4 handler |
| `zstandard` | >=0.21 (PyPI: `zstandard`) | Zstd decompression | Official Zstd Python binding |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `mmap` | Python stdlib | Memory-mapped file access for large .pak files | Files > 100MB where random access is frequent |
| `enum` | Python stdlib | Compression method and version enums | Clean state machine for version-dependent parsing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `cryptography` AES | `pycryptodome` | pycryptodome is broader but cryptography is more actively maintained |
| `lz4` PyPI package | `lz4ffi` | lz4ffi requires Cython build; pure `lz4` package has wheels |
| `zstandard` | `zstd` (unofficial PyPI) | `zstandard` is the official binding from Facebook |

**Installation:**
```bash
pip install cryptography lz4 zstandard
```

**Version verification:**
```bash
npm view is not applicable — Python packages
pip index versions cryptography   # confirms current version
pip index versions lz4
pip index versions zstandard
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `cryptography` | PyPI | 10+ yrs | 50M+/wk | [github.com/pyca/cryptography](https://github.com/pyca/cryptography) | [ASSUMED] | Approved — well-known security library |
| `lz4` | PyPI | 8+ yrs | 5M+/wk | [github.com/python-lz4/python-lz4](https://github.com/python-lz4/python-lz4) | [ASSUMED] | Approved — standard LZ4 binding |
| `zstandard` | PyPI | 8+ yrs | 20M+/wk | [github.com/indygreg/python-zstandard](https://github.com/indygreg/python-zstandard) | [ASSUMED] | Approved — official Zstd binding |

*slopcheck was not available at research time — all packages tagged [ASSUMED]. Planner should gate each install behind checkpoint:human-verify.*

## Architecture Patterns

### System Architecture Diagram

```
.pak file
  |
  v
[1] Seek to end - read FPakInfo trailer (variable offset)
  |  Magic: 0x5A6F12E1
  |  Version, IndexOffset, IndexSize, IndexHash
  |  bEncryptedIndex, EncryptionKeyGuid, CompressionMethods[]
  v
[2] Decrypt index blob (if bEncryptedIndex)
  |  AES-ECB, 16-byte aligned, no padding
  |  Key from user or embedded
  v
[3] Validate index: SHA1(index_blob) == IndexHash
  |
  v
[4] Parse Primary Index
  |  MountPoint (FString)
  |  NumEntries (int32)
  |  PathHashSeed (uint64) [version >= 10]
  |  bHasPathHashIndex + offsets [version >= 10]
  |  bHasDirectoryIndex + offsets [version >= 10]
  |  EncodedPakEntries[] (bitfield-encoded entries)
  |  NonEncodedEntries[] (full FPakEntry serialization)
  v
[5] For version >= 10: Parse PathHashIndex / DirectoryIndex
    |  PathHashIndex: TMap<uint64, FPakEntryLocation>
    |  DirectoryIndex: TMap<FString, TMap<FString, FPakEntryLocation>>
    v
[6] For version < 10 (legacy): flat entry list
    |  MountPoint + NumEntries
    |  For each: FString path + FPakEntry
    v
[7] File extraction: seek to entry.Offset + entry.StructSize
    |  If encrypted: AES-ECB decrypt blocks
    |  If compressed: dispatch to Zlib/LZ4/Zstd/Oodle per block
    v
  Raw file bytes
```

### Recommended Project Structure
```
src/uasset_read/
├── pak/                    # Pak file parsing module
│   ├── __init__.py         # Public API exports
│   ├── models.py           # FPakInfo, FPakEntry, FPakCompressedBlock dataclasses
│   ├── reader.py           # PakFileReader — main entry point
│   ├── index.py            # Index parsing (PrimaryIndex, PathHashIndex, DirectoryIndex)
│   ├── crypto.py           # AES decryption for encrypted indexes
│   ├── decompress.py       # Compression dispatch (Zlib/LZ4/Zstd/Oodle)
│   └── constants.py        # Magic numbers, version enums, flag constants
└── ...
```

### Pattern 1: Trailer-Indexed Archive Parsing
**What:** Read the file header from the END of the file, not the beginning. The FPakInfo struct is serialized at the file tail.
**When to use:** Any UE .pak file parsing.
**Example:**
```python
# UE engine approach: try versions from latest to earliest
# Source: PakFile.cpp line 284-304 (Initialize function)
def read_pak_info(stream: io.BytesIO, file_size: int) -> FPakInfo:
    for version in reversed(range(PakFile_Version_Initial, PakFile_Version_Latest + 1)):
        info_size = get_serialized_size(version)
        pos = file_size - info_size
        if pos < 0:
            continue
        stream.seek(pos)
        info = FPakInfo.deserialize(stream, version)
        if info.magic == PAK_FILE_MAGIC:
            return info
    raise ValueError("Unknown .pak format")
```

### Pattern 2: Bitfield-Encoded Pak Entries (UE5 / version >= 10)
**What:** FPakEntry data in the index is encoded into a compact bitfield to save memory, not serialized as full structs.
**When to use:** When Info.Version >= PakFile_Version_PathHashIndex (10).
**Example:**
```python
# Source: PakFile.cpp lines 1734-1869 (DecodePakEntry)
# Bitfield layout:
# Bit 31     = Offset fits in 32-bit
# Bit 30     = UncompressedSize fits in 32-bit
# Bit 29     = Size fits in 32-bit
# Bits 23-28 = Compression method index (6 bits)
# Bit 22     = Encrypted flag
# Bits 6-21  = Compression block count (16 bits)
# Bits 0-5   = Compression block size (6 bits, or 0x3F = read from stream)
def decode_pak_entry(data: bytes, offset: int, pak_info: FPakInfo) -> FPakEntry:
    bitfield = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    # ... decode fields based on bit flags
```

### Anti-Patterns to Avoid
- **Reading from file start:** The FPakInfo is at the END. Do not parse from offset 0.
- **Assuming fixed header size:** FPakInfo size varies by version (new fields are prepended before Magic for backward compatibility).
- **Ignoring alignment for encrypted entries:** Encrypted compressed blocks must be 16-byte aligned (AES block size).
- **Treating CompressionBlocks as absolute offsets:** For version < 5 (RelativeChunkOffsets), compressed block offsets are relative to the entry's file offset, not absolute file positions.
- **Hardcoding compression methods:** The compression method table is stored in FPakInfo and varies per .pak file. Do not assume ["None", "Zlib", "Oodle"] — read the table.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AES-ECB decryption | Custom AES implementation | `cryptography.hazmat.primitives.ciphers` | AES is subtle; ECB mode with no padding is standard |
| SHA1 hashing | Custom SHA1 | `hashlib.sha1` | Battle-tested, matches UE's FSHA1 output exactly |
| LZ4 decompression | Port C LZ4 code | `lz4.block.decompress` | Native C binding via wheels, handles all edge cases |
| Zstd decompression | Port libzstd | `zstandard.ZstdDecompressor` | Official binding, streaming support |
| FNV-64 hash for path hashing | Custom implementation | Must match UE's `FFnv::MemFnv64` exactly | Path hash must match UE's output byte-for-byte; bug in pre-UE5.0 version (swapped offset/primer) |

**Key insight:** The .pak format has 12+ version variants with game-specific deviations. Hand-rolling binary parsing without exhaustive version testing will miss edge cases like XOR-obfuscated offsets (Snowbreak), swapped fields (Wild Assault), or custom magic numbers (Outlast Trials, Game for Peace).

## Common Pitfalls

### Pitfall 1: FPakInfo Size Miscalculation
**What goes wrong:** Computing the wrong position for the FPakInfo trailer, leading to reading garbage as the header.
**Why it happens:** FPakInfo.GetSerializedSize() is version-dependent. New fields are prepended before the Magic field. The total size at version 12 is: FGuid(16) + bEncryptedIndex(1) + Magic(4) + Version(4) + IndexOffset(8) + IndexSize(8) + IndexHash(20) + CompressionMethods(32*5=160) = 221 bytes, but game-specific variants add extra fields.
**How to avoid:** Follow CUE4Parse's approach: read the maximum possible trailer size from end of file, then try each known offset variant and check for magic match.
**Warning signs:** Magic number doesn't match 0x5A6F12E1 on first try — don't fail immediately, iterate through version/offset variants.

### Pitfall 2: Encrypted Index vs Encrypted Files
**What goes wrong:** Confusing `bEncryptedIndex` (the index blob is AES-encrypted) with individual file entry encryption (`Flag_Encrypted`).
**Why it happens:** Both use AES-ECB but at different stages. The index is decrypted before parsing entries; individual files are decrypted during extraction.
**How to avoid:** Treat them as separate concerns. `bEncryptedIndex` affects index parsing. `FPakEntry.Flags & 0x01` affects file extraction.
**Warning signs:** Index parsing produces garbage strings for mount point or file count.

### Pitfall 3: Legacy vs Updated Index Format (version 10 boundary)
**What goes wrong:** Using the legacy flat-entry-list parser on a version >= 10 .pak, or vice versa.
**Why it happens:** Version 10 (PathHashIndex) introduced a completely different index structure with PathHashIndex, DirectoryIndex, EncodedPakEntries, and NonEncodedEntries. The legacy format simply has MountPoint + NumEntries + (path, FPakEntry) pairs.
**How to avoid:** Check `Info.Version >= PakFile_Version_PathHashIndex (10)` and branch to the correct parser.
**Warning signs:** File count is negative or mount point is garbage.

### Pitfall 4: Compression Block Offset Calculation
**What goes wrong:** Reading compressed data from the wrong file offset, producing decompression failures.
**Why it happens:** For version >= 5 (RelativeChunkOffsets), CompressionBlocks store offsets relative to the entry's file offset. For version < 5, they are absolute. CUE4Parse converts relative to absolute after loading. Also, encrypted entries require 16-byte alignment padding between blocks.
**How to avoid:** Always convert to absolute offsets: `block.CompressedStart += entry.Offset` for relative versions. Apply AES alignment: `aligned_size = (size + 15) & ~15`.
**Warning signs:** LZ4/Zstd decompression returns wrong size or fails with corrupted data errors.

### Pitfall 5: FString Serialization
**What goes wrong:** Incorrectly parsing UE's FString format in the index.
**Why it happens:** UE FString is: int32 length (negative for UTF-16, positive for ANSI), followed by length bytes of data, followed by a null terminator byte. Length = 0 means empty string. CUE4Parse handles this in `ReadFString()`.
**How to avoid:** Read int32 length. If length > 0, read `length` ANSI bytes + 1 null terminator. If length < 0, read `abs(length) * 2` UTF-16 bytes + 2 null terminator bytes.
**Warning signs:** Mount point contains null bytes or non-printable characters.

## Code Examples

### FPakInfo Deserialization (UE engine order)
```python
# Source: UE IPlatformFilePak.h lines 231-319 (FPakInfo::Serialize)
# and CUE4Parse FPakInfo.cs lines 142-149 (ReadFPakInfo)
import struct

PAK_FILE_MAGIC = 0x5A6F12E1

def deserialize_fpak_info(data: bytes, version: int) -> dict:
    """Deserialize FPakInfo from raw bytes at given version."""
    offset = 0
    result = {}

    # New fields (prepended for backward compatibility)
    if version >= 7:  # PakFile_Version_EncryptionKeyGuid
        result['encryption_key_guid'] = data[offset:offset+16]
        offset += 16
        result['encrypted_index'] = bool(data[offset])
        offset += 1

    # Core fields (always present)
    result['magic'] = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    if result['magic'] != PAK_FILE_MAGIC:
        return None  # Wrong version/offset

    result['version'] = struct.unpack_from('<i', data, offset)[0]
    offset += 4
    result['index_offset'] = struct.unpack_from('<q', data, offset)[0]
    offset += 8
    result['index_size'] = struct.unpack_from('<q', data, offset)[0]
    offset += 8
    result['index_hash'] = data[offset:offset+20]
    offset += 20

    # FrozenIndex flag (version 9 only, removed in version 10)
    if 9 <= version < 10:
        result['index_is_frozen'] = bool(data[offset])
        offset += 1

    # Compression methods table (version >= 8)
    if version >= 8:  # PakFile_Version_FNameBasedCompressionMethod
        result['compression_methods'] = []
        for i in range(5):  # MaxNumCompressionMethods
            name = data[offset + i*32 : offset + (i+1)*32]
            name_str = name.split(b'\x00')[0].decode('ascii', errors='replace')
            if name_str:
                result['compression_methods'].append(name_str)
        offset += 32 * 5

    return result
```

### AES Index Decryption
```python
# Source: CUE4Parse Encryption/Aes/Aes.cs (AES-ECB, no padding, 16-byte block)
# and UE PakFile.cpp line 899 (DecryptData call)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.backends import default_backend

def decrypt_index(encrypted_data: bytes, aes_key: bytes) -> bytes:
    """Decrypt pak index using AES-ECB (matching UE's FAES::DecryptData)."""
    # Align to 16-byte boundary
    aligned_size = (len(encrypted_data) + 15) & ~15
    if len(encrypted_data) < aligned_size:
        encrypted_data = encrypted_data + b'\x00' * (aligned_size - len(encrypted_data))

    cipher = Cipher(algorithms.AES(aes_key), None, backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(encrypted_data) + decryptor.finalize()
    return decrypted[:len(encrypted_data)]  # Trim to original size
```

### Compression Dispatch
```python
# Source: CUE4Parse Compression/Compression.cs lines 33-74
# Maps to UE's FCompression::CompressMemory / FCompression::UncompressMemory

def decompress_block(data: bytes, uncompressed_size: int, method: str) -> bytes:
    """Decompress a single compression block."""
    if method == 'None' or method == '':
        return data[:uncompressed_size]
    elif method == 'Zlib':
        import zlib
        return zlib.decompress(data, wbits=-15)  # raw deflate, no header
    elif method == 'Gzip':
        import gzip, io
        return gzip.decompress(data)
    elif method == 'LZ4':
        import lz4.block
        # LZ4_compressBound for safety
        return lz4.block.decompress(data, uncompressed_size=uncompressed_size)
    elif method == 'Zstd':
        import zstandard
        return zstandard.decompress(data, uncompressed_size)
    elif method == 'Oodle':
        # Oodle requires proprietary library (oo2core)
        # Not available as open-source Python package
        raise NotImplementedError("Oodle decompression requires oo2core library")
    else:
        raise ValueError(f"Unknown compression method: {method}")
```

### Multi-Block Decompression with Alignment
```python
# Source: CUE4Parse PakFileReader.cs Extract() method, lines 64-105
def extract_file_content(pak_stream, entry: dict, aes_key: bytes = None) -> bytes:
    """Extract and decompress a file entry from the pak stream."""
    if not entry.get('is_compressed', False):
        # Uncompressed: read directly
        read_offset = entry['offset'] + entry['struct_size']
        pak_stream.seek(read_offset)
        return pak_stream.read(entry['uncompressed_size'])

    # Compressed: process block by block
    alignment = 16 if entry.get('is_encrypted', False) else 1
    compression_block_size = entry['compression_block_size']
    blocks = entry['compression_blocks']
    method = entry['compression_method']

    result = bytearray()
    for block in blocks:
        pak_stream.seek(block['compressed_start'])
        block_size = block['compressed_end'] - block['compressed_start']
        aligned_size = (block_size + alignment - 1) & ~(alignment - 1)
        raw = pak_stream.read(aligned_size)

        if entry.get('is_encrypted', False) and aes_key:
            raw = decrypt_index(raw, aes_key)

        decompressed = decompress_block(raw[:block_size], compression_block_size, method)
        result.extend(decompressed)

    return bytes(result)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Flat entry list (MountPoint + N entries) | PrimaryIndex + PathHashIndex + DirectoryIndex | UE 4.25 (version 10) | Faster lookups via hash, memory-efficient directory pruning |
| Legacy compression flags (bitmask) | FName-based compression method table | UE 4.23 (version 8) | Extensible compression methods without hardcoded enums |
| Absolute compressed offsets | Relative compressed offsets | UE 4.19 (version 5) | Smaller entry size, delta-patchable |
| No encryption | Index encryption + per-file encryption | UE 4.17 (version 3-4) | Content protection for shipped games |
| No delete records | Flag_Deleted in FPakEntry.Flags | UE 4.20 (version 6) | Patch-based file removal without rewriting entire pak |
| FString (ANSI/UTF-16) directory names | FUtf8String directory names | UE 5.x (version 12) | Better Unicode support, smaller footprint for ASCII paths |

**Deprecated/outdated:**
- **Timestamps in FPakEntry:** Removed in version 2 (PakFile_Version_NoTimestamps). Legacy .pak files have 8-byte timestamp after compression method.
- **Legacy compression flags:** Pre-version 8 used bit flags (COMPRESS_ZLIB_DEPRECATED=256, COMPRESS_GZIP_DEPRECATED=512). Mapped to index-based method lookup.
- **FrozenIndex format:** Version 9 was deprecated; paks frozen with this version must be regenerated.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `cryptography`, `lz4`, `zstandard` are the correct Python packages for AES/LZ4/Zstd | Standard Stack | Wrong package names would cause pip install failures |
| A2 | UE's FSHA1 produces standard SHA1 (20 bytes) | Code Examples | If UE uses a custom variant, hash validation would always fail |
| A3 | Oodle decompression is not available as an open-source Python library | Don't Hand-Roll | If an open-source Oodle decoder exists, we could support it |
| A4 | AES-ECB with no padding is the exact mode used by UE | Code Examples | Wrong cipher mode would produce garbage decrypted indexes |

## Open Questions (RESOLVED)

1. **Oodle decompression in Python** — **RESOLVED:** Defer to follow-up phase. No open-source Python binding for oo2core DLL exists. Plan 02 implements `NotImplementedError` with clear warning. (Phase 77 scope: standard UE format only.)

2. **Custom game-specific formats** — **RESOLVED:** Out of scope for Phase 77. Implement standard UE format only. Game-specific detection can be added as a fallback layer in v15.0.

3. **FString serialization details** — **RESOLVED:** Implement ANSI/UTF-16 FString parsing (UE standard). UTF-8 variant for version 12 Utf8PakDirectory added to scope if encountered during e2e testing.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | Core implementation | To be verified | — | — |
| `cryptography` | AES index decryption | Not yet installed | — | `pycryptodome` as fallback |
| `lz4` | LZ4 decompression | Not yet installed | — | Skip LZ4 files, log warning |
| `zstandard` | Zstd decompression | Not yet installed | — | Skip Zstd files, log warning |
| `zlib` | Zlib decompression | Python stdlib | Built-in | N/A |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pyproject.toml` (pytest section) |
| Quick run command | `python -m pytest tests/test_pak_*.py -x` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PAK-01 | Parse FPakInfo from .pak trailer | unit | `pytest tests/test_pak_info.py -x` | Wave 0 |
| PAK-02 | Deserialize FPakEntry (legacy format) | unit | `pytest tests/test_pak_entry.py -x` | Wave 0 |
| PAK-03 | Deserialize bitfield-encoded FPakEntry (v10+) | unit | `pytest tests/test_pak_encoded_entry.py -x` | Wave 0 |
| PAK-04 | Decrypt encrypted index with AES key | unit | `pytest tests/test_pak_crypto.py -x` | Wave 0 |
| PAK-05 | Decompress Zlib/LZ4/Zstd blocks | unit | `pytest tests/test_pak_decompress.py -x` | Wave 0 |
| PAK-06 | Build directory index from parsed entries | unit | `pytest tests/test_pak_index.py -x` | Wave 0 |
| PAK-07 | End-to-end: open .pak, list files, extract one | integration | `pytest tests/test_pak_reader_e2e.py -x` | Wave 0 |

### Wave 0 Gaps
- [ ] `tests/test_pak_info.py` — PAK-01: FPakInfo parsing with version variants
- [ ] `tests/test_pak_entry.py` — PAK-02: Legacy FPakEntry deserialization
- [ ] `tests/test_pak_encoded_entry.py` — PAK-03: Bitfield-encoded entry decoding
- [ ] `tests/test_pak_crypto.py` — PAK-04: AES-ECB index decryption + hash validation
- [ ] `tests/test_pak_decompress.py` — PAK-05: Compression dispatch tests
- [ ] `tests/test_pak_index.py` — PAK-06: Directory index / path hash index parsing
- [ ] `tests/test_pak_reader_e2e.py` — PAK-07: End-to-end pak reader test
- [ ] Test assets needed: small .pak files (unencrypted, encrypted, various versions)

## Sources

### Primary (HIGH confidence)
- **UE Engine Source:** `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\PakFile\Public\IPlatformFilePak.h` — FPakInfo, FPakEntry, FPakCompressedBlock, FPakEntryLocation struct definitions and Serialize methods (lines 137-593)
- **UE Engine Source:** `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\PakFile\Private\PakFile.cpp` — FPakFile::Initialize, LoadIndex, LoadIndexInternal, EncodePakEntry, DecodePakEntry, DecryptAndValidateIndex (lines 272-1869)
- **CUE4Parse:** `CUE4Parse/UE4/Pak/Objects/FPakInfo.cs` — Full C# implementation with game-specific format handling (via GitHub API, SHA: 6256e2cf)
- **CUE4Parse:** `CUE4Parse/UE4/Pak/Objects/FPakEntry.cs` — Full C# implementation with bitfield decoding and game-specific overrides (via GitHub API, SHA: 2fe2591e)
- **CUE4Parse:** `CUE4Parse/UE4/Pak/PakFileReader.cs` — Main reader class, Mount/Extract/Index loading (via GitHub API, SHA: 4a1c8bd4, 22722 bytes)
- **CUE4Parse:** `CUE4Parse/Compression/Compression.cs` — Compression dispatch implementation
- **CUE4Parse:** `CUE4Parse/Encryption/Aes/Aes.cs` — AES-ECB decryption wrapper

### Secondary (MEDIUM confidence)
- **CUE4Parse:** `CUE4Parse/UE4/Pak/Objects/FPakCompressedBlock.cs` — Simple struct (CompressedStart, CompressedEnd)
- **CUE4Parse:** `CUE4Parse/Compression/CompressionMethod.cs` — Compression method enum

### Tertiary (LOW confidence)
- UE compression flag constants (COMPRESS_ZLIB_DEPRECATED, etc.) — inferred from code context, not explicitly verified in CompressionFlags.h

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages are well-established Python libraries with active maintenance
- Architecture: HIGH — sourced directly from UE engine source code and CUE4Parse implementation
- Pitfalls: HIGH — derived from actual CUE4Parse game-specific workarounds and UE engine validation checks
- Serialization order: HIGH — verified from IPlatformFilePak.h and FPakEntry::Serialize
- Bitfield encoding: HIGH — verified from PakFile.cpp DecodePakEntry/EncodePakEntry
- AES implementation: HIGH — verified from CUE4Parse Aes.cs and UE DecryptData call
- Oodle support: LOW — no open-source Python binding found; requires proprietary oo2core DLL

**Research date:** 2026-05-26
**Valid until:** 30 days (UE pak format is stable; new versions are backward-compatible)
