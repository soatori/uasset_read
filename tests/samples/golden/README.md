# Golden reference tables (issue #633)

Independent parser output used to break the circular verification of package
index tables (name/import/export counts, `DependsMap`, preload dependency
spans). These files are the reference truth: `tests/test_samples.py` compares
the v2 `PackageDocument` against them and fails on drift. They are checked-in
data; pytest needs no network, no dotnet, and no UE install.

## Generator provenance

| | |
|---|---|
| Generator | [UAssetAPI](https://github.com/atenfyr/UAssetAPI) `master` @ `5c22374`, version 2.0.0 |
| Runtime | built and run with .NET SDK 10.0.400 on Windows 11 |
| Produced | 2026-09-01 |
| Dumper | `dumper/Program.cs` (dev-time only; not part of the package or test runtime) |
| Manifest | hashes + per-file provenance mirrored in `tests/samples/manifest.json` → `golden_files` (validated by the sample manifest test) |

## Fixtures

- `ALS_FootstepDataTable.uasset.golden.json` — small DataTable (3 exports)
- `LevelDesign_ABP_Manny.uasset.golden.json` — mid-size AnimBlueprint (155 exports)
- `ALS_AnimBP.uasset.golden.json` — large legacy package (3395 exports)

## File format

Per golden file: `provenance` (generator + runtime + UTC timestamp),
`fixture` (name/sha256/size — pins the exact bytes that were dumped),
`counts` (parsed name/import/export table sizes), `depends_map`
(`total_edges` plus sparse `rows`: export index → raw `FPackageIndex` int32
list; omitted keys mean empty rows), `preload` (`total_entries` plus sparse
`spans`: export index → the four UE preload blocks concatenated in
serialization order).

## Known limitation: preload spans are empty

All 54 corpus fixtures are editor-saved (uncooked) packages; UE only writes the
summary preload dependency table for cooked packages, so every fixture
legitimately has zero preload entries. The golden files and the drift test
still pin this fact against an independent parser, but the preload span
*values* are only meaningfully verified once a cooked fixture is added to the
corpus (manifest gap).

## Regenerating

Requires a onetime dev-time clone (gitignored, never shipped, never used by
pytest):

```bash
git clone https://github.com/atenfyr/UAssetAPI external/UAssetAPI
git -C external/UAssetAPI checkout 5c22374
for f in ALS_FootstepDataTable LevelDesign_ABP_Manny ALS_AnimBP; do
  dotnet run -c Release --project tests/samples/golden/dumper -- \
    "tests/samples/$f.uasset" "tests/samples/golden/$f.uasset.golden.json"
done
```

Then refresh `sha256`/`size_bytes` in `manifest.json` → `golden_files` and
update the commit hash in this README. Any intentional change to golden data
must cite the new generator commit.
