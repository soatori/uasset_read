# Issue #626 — CurveTable Fixture Origin

Every number below was read back from the files on disk by the v2 reader or by a
struct decode against UE 5.8 source. Nothing here is asserted from the asset's name.

## Source

- **Project**: MyProject (user-created, self-generated content — redistributable)
- **Editor build**: `EngineVersion 5.8.2-56702186`, `CompatibleEngineVersion 5.8.0-55116800`
- **Directory**: `Content/ParserFixtures/` (editor-saved, not cooked — `PackageFlags == 0x0`,
  each package carries an `AssetImportData` export and an `/Game/ParserFixtures/...` package name)
- **Platform recorded in the file**: UE5 legacy layout, `LegacyFileVersion -9`,
  `FileVersionUE4 522`, `FileVersionUE5 1018` (`IMPORT_TYPE_HIERARCHIES`)

## Files

| File | Size | SHA-256 | Export class | exports/assets |
| --- | --- | --- | --- | --- |
| `TestSimpleCurveTable.uasset` | 2,796 B | `2d98adad5f156e26d7efabaf6954755ae564a5e88954ec9980a123a3c6e29f20` | CurveTable | 2 / 1 |
| `TestRichCurveTable.uasset` | 2,746 B | `be08b1b889ed9f421cc4f1f3a9f4bd70d4a7b1b14d0813361472340675ebe64f` | CurveTable | 2 / 1 |
| `testrCurveTable.uasset` | 2,669 B | `4d8581b9f4a05026edd2a9ab021b1bbd0a5d5b85bbd86a2812e3bac7c8c576f7` | CurveTable | 2 / 1 |
| `testCurveBase.uasset` | 4,757 B | `0f99372dafcff15a6e49cb964d92a3e3ca59906e6a9c78fbae3fe22eb2db6069` | CurveFloat | 2 / 1 |

`testCurveBase.uasset` is a **`UCurveFloat`, not a `UCurveTable`**. It is registered as the
negative control for the handler contract: an asset whose name contains "Curve" must not be
routed to the CurveTable row block.

## Row block layout (UE basis)

`Engine/Source/Runtime/Engine/Private/CurveTable.cpp:102` `UCurveTable::Serialize`:

1. `Super::Serialize(Ar)` — the tagged property stream (`AssetImportData`,
   `ImportCurveInterpMode`), which ends at the `NAME_None` tag.
2. Save branch at `:201-235`: `int32 NumRows`, then `ECurveTableMode` (one byte), then per row
   an `FName RowName` followed by `FSimpleCurve::StaticStruct()->SerializeTaggedProperties`
   (mode 1) or `FRichCurve::...` (mode 2). There is **no** `RowMap` tagged property: the rows
   are native bytes after the property stream.

`ECurveTableMode`: `0 Empty`, `1 SimpleCurves`, `2 RichCurves`.

## Deterministic expectations (measured from the fixtures)

| Asset | Mode | Rows | Row names |
| --- | --- | --- | --- |
| `TestSimpleCurveTable` | `SimpleCurves` | 2 | `RowA`, `RowB` |
| `TestRichCurveTable` | `RichCurves` | 2 | `RowA`, `RowB` |
| `testrCurveTable` | `SimpleCurves` | 3 | `Curve`, `Curve_0`, `Curve_1` |

`testrCurveTable` is the case that proves row names are FNames, not strings: the three rows
share the `Curve` name index and differ only in the on-disk `Number`, so the display instance
is `Number - 1` (`NAME_INTERNAL_TO_EXTERNAL`, `LinkerLoad.h`) — the same rule `FArchive.read_name`
applies everywhere else. Reading the index alone yields three identical `Curve` names, which is
structurally impossible for a `TMap<FName, ...>` and is therefore a detectable bug, not data.

## The `.uexp` files that came with these assets are not companions

The copy that arrived also contained `testCurveBase.uexp`, `testCurveBase1.uexp`,
`testrCurveTable.uexp`, `TestRichCurveTable.uexp` and `TestSimpleCurveTable.uexp`. They do
**not** pair with the `.uasset` files above: every one of those `.uasset` files is longer than
its `TotalHeaderSize` (e.g. 4,757 vs 4,467), which fails the UE split-file condition
(`main_size == Summary.TotalHeaderSize`, `SavePackage2.cpp:3767` +
`FilePackageWriterUtil.cpp:164-176`), and one has no matching `.uasset` at all. They were cooked
exports of the same-named assets taken from a different directory, so they are kept out of the
corpus (`temp/fixtures-orphan-uexp/`, untracked) and are **not** registered in `manifest.json`.
Real cooked `.uasset`/`.uexp`/`.ubulk` companions with the split invariant intact are in
`ORIGIN-issue-627-sidecar.md`.

## Verification / gate

- `tests/samples/manifest.json` → `samples[]` entries carry SHA-256, size, real export counts and
  the observed diagnostic set; `fixture_gaps.curve_table.status = "available"`.
- `tests/test_samples.py::test_manifest_matches_every_real_sample` fails on a missing file,
  a size change or a hash mismatch.
- `tests/test_samples.py::test_real_sample_proves_claimed_capability` pins the mode + row names
  above (`SimpleCurves` / `RichCurves`, `RowA`/`RowB`) as the complete-sample assertion.
- `tests/test_core.py` `test_curve_table_mode_byte_is_consumed`,
  `test_table_payload_residue_is_disclosed_not_complete` and
  `test_fname_instance_number_renders_in_row_name` are the partial/residue assertions: a row
  block that does not exhaust its payload downgrades coverage to `partial` and emits
  `TABLE_PAYLOAD_RESIDUE` instead of claiming decoded rows.

## Related

- Parent issue: #621 (Package-First UAsset Parser Refactor), Phase 4.1
- Companion sidecar fixture: `ORIGIN-issue-627-sidecar.md`
- Historical issue: #497
