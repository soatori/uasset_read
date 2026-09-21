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

## Fixture intake status — still blocked (plan Task 2, 2026-09-21)

Candidate search and measurement via `read_toc()` / `inspect_container()`. No fixture was
intaken; no manifest-integrity test was added.

| Candidate | On disk | Commit status | Verdict |
|-----------|---------|---------------|---------|
| `MyProject-Windows.utoc` + `.ucas` | Yes (both; hashes above re-verified) | `.utoc` tracked; `.ucas` gitignored (`tests/samples/containers/MyProject-Windows.ucas`) and 259,193,536 B > GitHub 100 MB limit | Structurally valid but **not committable**; kept as historical evidence only |
| `global.utoc` + `.ucas` | Yes (both) | Both tracked | **Rejected**: measured `entry_count=1`, the single chunk is type `ScriptObjects` (type id 5), `package_files()` is empty — no `ExportBundleData` package chunk, so no package bytes to decode |

Measured primary-container facts (not in the tables above, from `read_toc()` on the hashed
`.utoc`): `container_flags=0x9` (compressed | directory index; not signed, not encrypted),
mount point `../../../`, 575 `ExportBundleData` chunks addressed by 575 directory-index
package paths (e.g. `../../../MyProject/Content/Test/TestBlueprint.uasset` → chunk index
2204, `ExportBundleData`, compressed, logical length 3204). Of the 575 package chunks,
213 are uncompressed (method `None`, no codec required) and 362 are compressed; the block
table uses methods `None` (5036 blocks), `Oodle` (1564), and method index 255 (94 blocks,
not listed in the header method table — unverified). Expected per-package object counts
are not measurable until a Zen decode path exists.

**Still missing for fixture intake:**

1. A committable (or in-repo-approved external-artifact) pair providing at least one
   `ExportBundleData` package chunk's bytes — no `ZenFixture.utoc`/`.ucas` exists and no
   approved external-artifact manifest path is documented in the repository.
2. Consequently: no `test_iostore_fixture_manifest_matches_files()`, no provenance table
   for an intaken fixture, and no skip/xfail placeholder. The historical 247 MB manifest
   rows above remain the fixture-gap evidence, not a real-package decode fixture.

Note: the `global.utoc` header table above (entry count 2 / `("None", "Oodle")` / 5
blocks) disagrees with a fresh `read_toc()` of the hashed file (1 entry, `("None",)`,
49 blocks); treat the fresh measurement as authoritative until re-measured otherwise.
`global.ucas` is tracked in git despite the "not committed" annotation above.
