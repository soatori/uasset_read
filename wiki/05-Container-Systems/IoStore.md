---
title: IoStore Container
section: iostore
---

# IoStore Container

A new container format introduced in UE5.3+, using a dual-file structure of `.utoc` (table of contents) + `.ucas` (data container) to replace the traditional PAK format. IoStore provides O(1) Chunk lookup capability (Perfect Hash), multi-partition support, optional compression/encryption/signing, and directory indexing (path-based lookup).

> [!NOTE]
> IoStore is only available in UE5.0+. UE4 uses a different storage mechanism. Unbaked/editor-saved assets may still use the traditional PAK format.

## Core API

```python
# Using context manager (recommended)
with IoStoreReader("game.utoc", "game.ucas") as reader:
    data = reader.read_chunk(FIoChunkId(bytes=chunk_id_bytes))

# Extract by path (requires directory index)
data = reader.extract_path("/Game/Maps/Level1.uasset")

# List all files
files = reader.list_files()
```

### IoStoreReader

```python
IoStoreReader(
    utoc_path: str,          # .utoc file path (required)
    ucas_path: str | None,   # .ucas file path (optional, auto-derived)
    aes_key: bytes | None,   # AES decryption key (optional)
    tolerant: bool = False,  # Tolerant mode
    read_options: int = EIoStoreTocReadOptions.Default,
)

# Methods
.open()           -> None    # Open container, parse TOC header, chunk array, compressed blocks, directory index
.close()          -> None    # Close all file handles
.list_files()     -> List[str]          # List all file paths (requires directory index)
.does_chunk_exist(chunk_id) -> bool     # Check if a chunk exists
.try_resolve(chunk_id) -> Optional[Tuple[int, int]]  # Resolve chunk -> (offset, length)
.extract(chunk_id_bytes) -> bytes        # Extract data by 12-byte ChunkId
.extract_path(path: str) -> Optional[bytes]  # Extract data by path
.read_chunk(chunk_id) -> bytes           # Read decompressed data by FIoChunkId
```

### IoStoreInfo

Parsed TOC summary information:

```python
info.version                    # TOC version (1-8)
info.toc_entry_count            # Number of chunks
info.compressed_block_count     # Number of compressed blocks
info.compression_method_count   # Number of compression methods
info.compression_block_size     # Compressed block size (bytes)
info.directory_index_size       # Directory index size
info.partition_count            # Number of partitions
info.partition_size             # Partition size
info.container_flags            # Container flags (EIoContainerFlags)
info.is_encrypted               # Whether encrypted
info.is_compressed              # Whether compressed
info.chunk_ids                  # List[FIoChunkId]
info.chunk_offsets              # List[FIoOffsetAndLength]
```

## Core Structures

### FIoChunkId (12 bytes)

Chunk identifier, consistent with UE source code `FIoChunkId`:

| Byte Range | Field | Description |
|------------|-------|-------------|
| 0-7 | ChunkId (uint64 LE) | 64-bit ID |
| 8-9 | ChunkIndex (uint16 BE) | Chunk index (big-endian) |
| 10 | ChunkGroup (uint8) | Chunk group |
| 11 | ChunkType (uint8) | EIoChunkType |

```python
chunk_id = FIoChunkId(bytes=chunk_id_bytes)
chunk_id.id           # 64-bit ID
chunk_id.chunk_index  # Chunk index
chunk_id.chunk_group  # Chunk group
chunk_id.chunk_type   # Chunk type
```

### FIoOffsetAndLength (10 bytes)

Standard IoStore offset/length combination format, 10-byte big-endian encoded:

| Byte Range | Field | Description |
|------------|-------|-------------|
| 0-4 | Offset (big-endian) | 40-bit offset |
| 5-9 | Length (big-endian) | 40-bit length |

```python
offset_length = FIoOffsetAndLength.from_bytes(data)  # 10 bytes
offset_length.offset  # Offset
offset_length.length  # Length
```

### FIoOffsetAndSize (8 bytes, legacy compatibility)

40-bit offset + 24-bit size, little-endian packed:

```python
packed = FIoOffsetAndSize(offset=xxx, size=xxx).pack()   # 8 bytes
ofs = FIoOffsetAndSize.unpack(data)                       # Unpack
```

## Enums

### EIoStoreTocVersion (TOC Version)

| Version | Name | New Features |
|---------|------|--------------|
| 1 | Initial | Initial version |
| 2 | DirectoryIndex | Directory index |
| 3 | PartitionSize | Multi-partition support |
| 4 | PerfectHash | Perfect Hash optimization |
| 5 | PerfectHashWithOverflow | Perfect Hash + overflow handling |
| 6 | OnDemandMetaData | On-demand metadata |
| 7 | RemovedOnDemandMetaData | Removed on-demand metadata |
| 8 | ReplaceIoChunkHashWithIoHash | Use FIoHash instead of FIoChunkHash |

### EIoChunkType (Chunk Data Type)

| Type Value | Name | Description | Minimum Version |
|------------|------|-------------|-----------------|
| 0 | Invalid | Invalid | — |
| 1 | ExportBundleData | Export bundle data | UE5.0 |
| 2 | BulkData | Bulk data | UE5.0 |
| 3 | OptionalBulkData | Optional bulk data | UE5.0 |
| 4 | MemoryMappedBulkData | Memory-mapped bulk data | UE5.0 |
| 5 | ScriptObjects | Script objects | UE5.0 |
| 6 | ContainerHeader | Container header | UE5.0 |
| 7 | ExternalFile | External file reference | UE5.1 |
| 8 | ShaderCodeLibrary | Shader code library | UE5.1 |
| 9 | ShaderCode | Shader code | UE5.1 |
| 10 | PackageStoreEntry | Package store entry | UE5.2 |
| 11 | DerivedData | Derived data | UE5.3 |
| 12 | EditorDerivedData | Editor derived data | UE5.4 |
| 13 | PackageResource | Package resource | UE5.5 |

### EIoContainerFlags (Container Flags)

| Flag | Value | Description |
|------|-------|-------------|
| None_ | 0 | No flags |
| Compressed | 1 << 0 | Container uses compression |
| Encrypted | 1 << 1 | Container uses encryption |
| Signed | 1 << 2 | Container uses signing |
| Indexed | 1 << 3 | Container has a directory index |
| OnDemand | 1 << 4 | On-demand loading |

## TOC File Structure

Complete layout of the `.utoc` file (read top-to-bottom):

```
+───────────────────────────────────+
│ FIoStoreTocHeader (144 bytes)     │  ← Magic number + version + counts + flags
+───────────────────────────────────+
│ Aligned to 4-byte boundary        │
+───────────────────────────────────+
│ ChunkId array (12 bytes × N)      │  ← N = toc_entry_count
+───────────────────────────────────+
│ OffsetAndLength array (10 bytes × N)│
+───────────────────────────────────+
│ Perfect Hash seeds (Version 4+)   │  ← 4 bytes × seed_count
+───────────────────────────────────+
│ Non-Perfect Hash indices (V5+)    │  ← 4 bytes × count
+───────────────────────────────────+
│ Compressed block entries (12 bytes × M)│  ← M = compressed_block_count
+───────────────────────────────────+
│ Compression method names (name_count × length)│  ← Fixed-length ASCII strings
+───────────────────────────────────+
│ Signature data (if Signed)        │  ← Optional, skipped
+───────────────────────────────────+
│ Directory index buffer (if Indexed)│  ← Variable length
+───────────────────────────────────+
```

### FIoStoreTocHeader (144 bytes)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 16 | toc_magic | Magic number `-==--==--==--==-` |
| 16 | 1 | version | TOC version (EIoStoreTocVersion) |
| 17 | 1 | reserved0 | Reserved |
| 18 | 2 | reserved1 | Reserved |
| 20 | 4 | toc_header_size | Header size |
| 24 | 4 | toc_entry_count | Number of chunk entries |
| 28 | 4 | toc_compressed_block_entry_count | Number of compressed blocks |
| 32 | 4 | toc_compressed_block_entry_size | Compressed block size |
| 36 | 4 | compression_method_name_count | Number of compression method names |
| 40 | 4 | compression_method_name_length | Compression method name length |
| 44 | 4 | compression_block_size | Compressed block size (bytes) |
| 48 | 4 | directory_index_size | Directory index size |
| 52 | 4 | partition_count | Number of partitions |
| 64 | 8 | container_id (FIoContainerId) | Container ID |
| 72 | 16 | encryption_key_guid (FGuid) | Encryption key GUID |
| 88 | 4 | container_flags (EIoContainerFlags) | Container flags |
| 92 | 4 | toc_chunk_perfect_hash_seeds_count | Number of Perfect Hash seeds |
| 96 | 8 | partition_size | Partition size |
| 104 | 4 | toc_chunks_without_perfect_hash_count | Number of chunks without Perfect Hash |

> [!NOTE]
> Before version 3, there was no partition support. `partition_count` is forced to 1, and `partition_size` is set to `ulong.MaxValue`.

### FIoStoreTocCompressedBlockEntry (12 bytes)

| Bytes | Field | Description |
|-------|-------|-------------|
| 0-4 | Offset (5 bytes LE) | Offset |
| 5-7 | CompressedSize (3 bytes) | Compressed size |
| 8-10 | UncompressedSize (3 bytes) | Uncompressed size |
| 11 | CompressionMethodIndex (1 byte) | Compression method index |

## Directory Index

When the container has the `Indexed` flag set, the `.utoc` file contains a directory index buffer at the end, enabling direct Chunk lookup by file path.

### Index Structure

```
+───────────────────────────────────+
│ MountPoint (FString)              │  ← Mount point path
+───────────────────────────────────+
│ DirectoryEntries[] (FString count)│  ← Directory tree
+───────────────────────────────────+
│ FileEntries[] (FString count)     │  ← File entries
+───────────────────────────────────+
│ StringTable[] (FString count)     │  ← String pool
+───────────────────────────────────+
```

### FIoDirectoryIndexEntry (16 bytes)

| Offset | Field | Description |
|--------|-------|-------------|
| 0 | name | Name index (points to StringTable) |
| 4 | first_child_entry | First child directory index |
| 8 | next_sibling_entry | Next sibling directory index |
| 12 | first_file_entry | First file entry index |

### FIoFileIndexEntry (12 bytes)

| Offset | Field | Description |
|--------|-------|-------------|
| 0 | name | File name index |
| 4 | next_file_entry | Next file entry index |
| 8 | user_data | Chunk index (points to ChunkId array) |

> [!TIP]
> The directory index uses recursive tree traversal: starting from the root directory, it first iterates over file entries, then recursively processes child directories, and finally moves to sibling directories.

## Chunk Lookup Mechanism

### Perfect Hash (O(1), Version 4+)

Uses 64-bit FNV-1a hashing with a seed array for O(1) lookup:

1. Look up the seed value by seed index
2. If seed is positive: `slot = hash_with_seed(chunk_id, seed) % chunk_count`
3. If seed is negative: indicates an imperfect hash entry, convert to index fallback
4. If seed is zero: no entry at that position

```python
# FNV-1a hash (consistent with UE source code)
hash_val = 0xcbf29ce484222325 ^ seed  # offset basis
for byte in chunk_id.bytes:
    hash_val ^= byte
    hash_val = (hash_val * 0x00000100000001B3) & 0xFFFFFFFFFFFFFFFF  # FNV prime
```

### Imperfect Hash Fallback

Chunks not covered by Perfect Hash use dictionary fallback or linear search:

```python
# Method 1: Dictionary lookup (pre-built fallback table)
self._toc_imperfect_hash_map.get(chunk_id)

# Method 2: Linear search
for i, cid in enumerate(self._chunk_ids):
    if cid == chunk_id:
        return self._chunk_offsets[i]
```

## Data Reading

### Uncompressed Direct Read

```python
reader.seek(partition_offset)
data = reader.read(length)
```

### Compressed Block Read

1. Calculate the start and end compressed block indices
2. Read each block sequentially -> decrypt (if encrypted) -> decompress
3. Extract the required byte range from the decompressed blocks and concatenate

Supported compression methods are specified by the compression method names in the TOC (e.g., `LZ4`, `Zlib`, `Zstandard`).

### Multi-Partition Read

When `partition_count > 1`:

- Partition file naming: `game.ucas`, `game_s1.ucas`, `game_s2.ucas` ...
- Partition index: `partition_index = offset // partition_size`
- Offset within partition: `partition_offset = offset % partition_size`
- Supports cross-partition sequential reading

## Encryption and Signing

### Encryption

When `EIoContainerFlags.Encrypted` is set:

- Data blocks are decrypted using AES-ECB
- Directory index buffer is decrypted using AES-ECB
- Alignment to 16-byte boundary is required
- AES key must be provided

### Signing

When `EIoContainerFlags.Signed` is set:

- The TOC contains `tocSignature`, `blockSignature`, and an FSHAHash for each compressed block
- Signature data is skipped during parsing

## Comparison with PAK Format

| Feature | PAK | IoStore |
|---------|-----|---------|
| File Structure | Single file | Dual file (.utoc + .ucas) |
| Lookup Method | Dictionary/Linear | Perfect Hash O(1) |
| Compression Granularity | Per entry | Per compressed block (can span chunks) |
| Multi-Partition | Not supported | Supported |
| Directory Index | None | Yes (supports path-based lookup) |
| Version | UE4/UE5 | UE5.0+ |
