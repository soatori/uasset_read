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

Because of that, this file is kept only as the IoStore-wrapper negative case asserted by
`test_iostore_wrapper_is_not_treated_as_traditional_pak()`; it is never counted as the
FPak capability sample. The current manifest marks `pak_container` as `available` because
the compact traditional Pak below was added on 2026-09-27.

## Traditional Pak Format

A traditional FPakFile was not available from the original default build; UE 5.8 defaults
to IoStore packaging. The later UE5.8.2 native `UnrealPak` repack described below is the
current FPak fixture.

Before the compact fixture was generated, the usual alternatives would have been a
deprecated `-iostore=0` build or an older UE project. Neither is needed now: UE4 legacy
versions are explicitly out of scope, and the current fixture was repacked from the
user-owned UE5.8.2 `LooseTagged` ParserFixtures with the native `UnrealPak` tool.

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

## 2026-09-27 intake update

Issue #625 is closed as completed. UE4 legacy versions are not required for
the fixture: the user-owned UE5.8.2 `ParserFixtures 02 Pak Tagged`/native
UnrealPak route produced `ParserFixturesLegacy-Windows.pak`, a compact
traditional FPak containing 25 ParserFixtures files. Its SHA-256 is
`44a1a134aa515734f3d7cb6f7468e654c238d5c3036e1c24720a8abae1927518` and its
footer contains `5a6f12e1`. This closes sample intake only; Pak range-read and
container extraction remain separate implementation work.
