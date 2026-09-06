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
| `MyProject-Windows.ucas` | 259,193,536 B (247.2 MB) | `723302e856eea40c0591936fd03e3c8a6f9ab6dd29d1e6a37726a35ab804787c` | IoStore container archive |

### Secondary container: global

| File | Size | SHA-256 | Description |
|------|------|---------|-------------|
| `global.utoc` | 782 B | `97d7856030734fdff11bc4cddd2619c9142a693f0d37adc2ac3c59f4a4a9df3c` | IoStore TOC (global data) |
| `global.ucas` | 3,209,824 B (3.1 MB) | `989837d42550dcccf3b7332c033f6de6ae4af256778011d9c04ecc71d8782fe8` | IoStore container (global data) |

## IoStore TOC Header (MyProject-Windows.utoc)

| Field | Value | Notes |
| ------- | ------- | ------- |
| Magic | `-==--==--==--==-` (16 bytes) | IoStore TOC magic |
| Version | 8 | UE 5.8 IoStore format |
| Header size | 144 bytes | |
| Entry count | 2,221 | Partitions/segments |
| Compression methods | 6,694 | Registered compression codecs |
| Compression name length | 12 | |
| Platform | Windows (32 chars) | |
| Container ID | 4295002954 | Unique container identifier |

## IoStore TOC Header (global.utoc)

| Field | Value | Notes |
| ------- | ------- | ------- |
| Magic | `-==--==--==--==-` (16 bytes) | IoStore TOC magic |
| Version | 8 | UE 5.8 IoStore format |
| Header size | 144 bytes | |
| Entry count | 1 | Single global partition |
| Compression methods | 49 | |
| Container ID | 4294967296 | |

## Compression

IoStore uses block-level compression. The `.ucas` file contains compressed data blocks referenced by the `.utoc` index. Common UE5 compression methods:

- **None** (method 0): Uncompressed
- **Zlib**: Standard DEFLATE
- **Oodle** (Kraken/Mermaid): Default in UE5 for high-ratio compression

## Redistribution

- Self-generated project assets — no third-party content
- No commercial or licensed dependencies
- Safe for redistribution under project license

## Verification

After parsing, verify:

- `.utoc` magic bytes match `-==--==--==--==-`
- TOC header version is 8
- Package names can be listed from directory index
- At least 5 packages identifiable in the container
- At least 3 Zen package entries cover Blueprint, Material, DataTable types

## Notes

- The `global.utoc/.ucas` pair is a small secondary container for global shader/material data
- The `MyProject-Windows` pair is the primary asset container (247 MB)
- Companion `.pak` file is an IoStore container wrapper (see `ORIGIN-issue-625-pak.md`)

## Related

- Parent issue: #621 (Package-First UAsset Parser Refactor)
- Companion Pak fixture: `ORIGIN-issue-625-pak.md`
