# Issue #625 — Pak Container Fixture Origin

## Source

- **Project**: MyProject (UE 5.8, user-created)
- **Directory**: `Saved/Pak/Windows/MyProject/Content/Paks/`
- **UE Version**: 5.8 (`EngineAssociation: "5.8"`)
- **Platform**: Windows
- **Build method**: Standard project cook + package

## Files

| File | Size | SHA-256 | Description |
|------|------|---------|-------------|
| `MyProject-Windows.pak` | 11,450,886 B (10.9 MB) | `1c5e7bb264810f197480d124434acaf56af8452c48df583708c25c14a019b478` | IoStore container pak |

## Format Notes

⚠️ **This is an IoStore-based container pak, NOT a traditional FPakFile.**

In UE5 with IoStore enabled (default in UE 5.4+), the `.pak` file is a container wrapper:

- First 8 bytes: zero-filled header
- Byte 8: partition/version marker (`0x4D` = 77)
- Contains embedded IoStore `.ucas`/`.utoc` data
- No traditional FPakFile index or magic (`5a6f12e1`)

The actual asset data lives in the companion `.ucas` file (see `iostore/` directory). The `.pak` serves as a mountable container for backward compatibility.

## Traditional Pak Format

A traditional FPakFile (with magic `5a6f12e1`, version 11/12, embedded index) is **not available** from this project. UE 5.8 defaults to IoStore packaging.

To obtain a traditional pak, one would need to:

1. Build with `-iostore=0` flag (deprecated in UE 5.4+)
2. Or use an older UE project (UE 4.x)

## Mount Point

Default: `/Game/` (project content root)

## Package Count

The companion IoStore container holds the actual package index. See `ORIGIN-issue-624-iostore.md` for package count details.

## Redistribution

- Self-generated project assets — no third-party content
- No commercial or licensed dependencies
- Safe for redistribution under project license

## Verification

After parsing, verify:

- Container header parses correctly (zero-filled magic, version/partition at offset 8)
- Companion `.ucas`/`.utoc` files are co-located
- Extracted packages parse correctly with PackageDocument

## Related

- Parent issue: #621 (Package-First UAsset Parser Refactor)
- Companion IoStore fixture: `ORIGIN-issue-624-iostore.md`
