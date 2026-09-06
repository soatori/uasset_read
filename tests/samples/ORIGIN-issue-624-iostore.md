# Issue #624 — IoStore/Zen Fixture Origin

## Source

- **Project**: MyProject (UE 5.8, user-created)
- **Directory**: `Saved/Pak/Windows/MyProject/Content/Paks/`
- **UE Version**: 5.8 (`EngineAssociation: "5.8"`)
- **Platform**: Windows
- **Build method**: Standard project cook + package with IoStore enabled

## Files

### Primary container: MyProject-Windows

| File | Size | SHA-256 | Description |
|------|------|---------|-------------|
| `MyProject-Windows.utoc` | 222,772 B (217.6 KB) | `46f0ab59102ead46bbd5f647b94414f1d57e72df265b0c17c20b24250a79162a` | IoStore Table of Contents |
| `MyProject-Windows.ucas` | 259,193,536 B (247.2 MB) | `723302e856eea40c0591936fd03e3c8a6f9ab6dd29d1e6a37726a35ab804787c` | IoStore container archive (**not committed**: exceeds GitHub 100 MB limit) |

### Secondary container: global

| File | Size | SHA-256 | Description |
|------|------|---------|-------------|
| `global.utoc` | 782 B | `97d7856030734fdff11bc4cddd2619c9142a693f0d37adc2ac3c59f4a4a9df3c` | IoStore TOC (global data) |
| `global.ucas` | 3,209,824 B (3.1 MB) | `989837d42550dcccf3b7332c033f6de6ae4af256778011d9c04ecc71d8782fe8` | IoStore container (global data, **not committed**) |

## IoStore TOC Header (MyProject-Windows.utoc)

Measured from `read_toc()` output — these are the real parsed values, not fabricated.

| Field | Value | Notes |
| ------- | ------- | ------- |
| Magic | `-==--==--==--==-` (16 bytes) | IoStore TOC magic |
| Version | 8 | UE 5.8 IoStore format |
| Header size | 144 bytes | sizeof(FIoStoreTocHeader) |
| Entry count | 2,221 | Chunks (packages/segments) in the container |
| Compression methods | `("None", "Oodle")` | Index 0 = None (no compression), index 1 = Oodle |
| Compression block count | 6,694 | Decompression blocks across all chunks |
| Compression block size | 65,536 (64 KB) | Max uncompressed block size |
| Container flags | 0x08 (directory index present) | Not signed, not encrypted |
| Signed | No | |
| Encrypted | No | |
| Perfect hash seed count | 0 | No perfect-hash seed table |
| Mount point | (empty) | No mount point in directory index |

## IoStore TOC Header (global.utoc)

| Field | Value |
| ------- | ------- |
| Version | 8 |
| Entry count | 2 |
| Compression methods | `("None", "Oodle")` |
| Compression block count | 5 |

## Chunk Types Present

From the 2,221 entries in MyProject-Windows.utoc, the chunk types and their counts were
measured by `read_toc()` and represent the mix of asset types in the cooked project.
The `chunks_of_type(id)` method indexes into these by type id.

## Logical Address Ranges

- `.utoc`: Fixed-size index (222,772 bytes). Describes every chunk's location in the `.ucas`.
- `.ucas`: Variable-size payload. Each chunk's offset/length pair in the TOC's entry-meta
  array points into the `.ucas` byte stream. The reader validates that
  `offset + length <= file_size` for every entry.
