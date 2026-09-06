# Issue #627 — Loose Sidecar Fixture Origin (.uexp / .ubulk)

Every number below was read back from the files on disk. Nothing is asserted from a filename.

## Source

- **Project**: MyProject (user-created, self-generated content — redistributable)
- **Editor build**: `5.8.2-56702186`, compatible `5.8.0-55116800`
- **Directory**: `Saved/Cooked/Windows/MyProject/Content/ParserFixtures/` (Windows cook)
- **Package state**: cooked — `PKG_Cooked (0x200)` set, `LegacyFileVersion -9`,
  `FileVersionUE4 522`, `FileVersionUE5 1018`; `engine_version` in the summary is `0.0.0.0`
  because the cook did not embed a changelist.

## Files (main + declared sidecars, all hash-pinned in `manifest.json`)

| File | Size | SHA-256 | Role |
| --- | --- | --- | --- |
| `T_ParserBulk.uasset` | 1,487 B | `4f518bc6fbcd20308a8a8927296f461fa03cb37cb35ec14220078be74f74f847` | Texture2D package header + export map |
| `T_ParserBulk.uexp` | 22,308 B | `f3408c6168a9f6ff0934eda13026d7d9ed65345a7661afda43d82e2eae7c95bd` | export serial data (tagged properties) |
| `T_ParserBulk.ubulk` | 5,570,560 B | `750386e56a90b3d3073fabb34ba525054b6beda7c6ef1376abac3b4cc200e96c` | bulk mip bytes, addressed from 0 of this file |
| `DT_ParserWeapon.uasset` | 1,066 B | `d3fae6faed554ca98d2d02c517669272ef39df770ab13e7baacd8a093f880c36` | DataTable header |
| `DT_ParserWeapon.uexp` | 230 B | `57b6a2e0e2688ac4ee18c000b745a06c844f699959dac7e427951793ae2d1f4c` | export data (row block decodes to `EmptyWeaponA`, `EmptyWeaponB`) |
| `TestBlueprint.uasset` | 3,565 B | `70806823d99cd8c07ff972794042f513dd6cb7b99b951faba3081897424770d6` | BlueprintGeneratedClass header, 7 exports / 1 asset |
| `TestBlueprint.uexp` | 1,894 B | `dda43e54fb72c0d7bc525ce4cb235782a2030d02649fa002fd67163b113bee76` | export data |
| `TestDataRow.uasset` | 981 B | `35ab689138b67e42a2358ba3a65db0debf315f5a370c55348b3c5f3174aae82c` | UserDefinedStruct header |
| `TestDataRow.uexp` | 359 B | `2cfd726ca5ae49d0e4b047ac46d46c476b1ca197d1680df271296363dc18e50e` | export data |
| `TestDataTable.uasset` | 1,046 B | `18f243bef71eab64976fc51de2bcabab35e7c70cad5d5b7334d1322439815a86` | DataTable header |
| `TestDataTable.uexp` | 206 B | `ac0621233b8417ea692e177634fee91c102b4479b263ce985280e898cdae7d6d` | export data (rows `Test.Tag`, `Test.Tag.2`) |
| `TestMaterial.uasset` | 2,803 B | `0d949b49fedd9f2dc78f66bac03145c0b50ddddee8400394406a02b2b59cdebd` | Material header |
| `TestMaterial.uexp` | 124,909 B | `0a8b81380608c5fe354c650f020e69069d822377c5029921c5b06929342dca88` | export data (largest of the group) |

## Split-file invariant (why these are the real thing)

For all six groups `size(.uasset) == Summary.TotalHeaderSize`, which is UE's own condition for
addressing `.uasset` + `.uexp` as one stream:

- `SavePackage2.cpp:3767` — `Export.SerialOffset += Linker.Summary.TotalHeaderSize`
- `FilePackageWriterUtil.cpp:164-176` — the merged buffer is cut at `TotalHeaderSize`
- `AsyncLoading.cpp:605-611` — the engine detects a split package by the same equality

Measured per group: `serial_size` of all exports summed equals `size(.uexp) - 4`, so the export
regions are contiguous inside `.uexp` and four bytes sit past the last export.

**Observed, not UE-symbol-resolved:** each of the six `.uexp` files ends with the 8-byte tail
`00 00 00 00 C1 83 2A 9E` (a zero int32 followed by `PACKAGE_FILE_TAG`). It is reproducible on
6/6 files here but has not been traced to a writer symbol yet, so no reader behaviour depends
on it. Do not treat it as a spec claim until it is traced.

`.ubulk` addresses restart at 0 for that file (`LinkerSave.cpp:678/697` take the bulk archive's
`Tell()`, `:664` sets `BULKDATA_NoOffsetFixUp`), which is why an "整文件 ubulk 描述符" with
`offset = main_size` was retracted earlier. First bytes of `T_ParserBulk.ubulk` are
`00 00 00 ff 00 00 01 ff …` — 32-bit RGBA mip data with an opaque alpha channel.

## What v2 consumes today

- `.uexp` is spliced into the address space by `PackageBundle`/`PackageArchive` and the tagged
  property stream is read across the boundary. Proof on this fixture: `DT_ParserWeapon` and
  `TestDataTable` decode their row blocks (`EmptyWeaponA/EmptyWeaponB`, `Test.Tag/Test.Tag.2`)
  from data that exists only in `.uexp`.
- `.ubulk` is **discovered and hash-pinned but not yet mapped**: `doc.payloads == []` and
  `extract_payload` returns `PAYLOAD_EXTRACTION_DEFERRED`. Per-export bulk descriptors still need
  the `FTexture2DResource`/`FByteBulkData` mapping against this file; that is the remaining work
  item of #627, not a fixture gap.

## Verification / gate

- `manifest.json` declares the pairing: each main entry lists its sidecars by name, SHA-256 and
  size, and `test_manifest_matches_every_real_sample` fails if a declared sidecar is missing, if
  an on-disk sidecar is undeclared, or if any hash/size drifts.
- Missing-sidecar acceptance: a main file whose `SerialOffset`s resolve past
  `TotalHeaderSize` with no `.uexp` present must not silently truncate — it must report a
  structured diagnostic and degrade `status.parse`. That check is tracked in #627 and is not yet
  satisfied by the reader.

## Related

- Parent issue: #621, Phases 1 and 4 (bounded sidecar source, payload descriptors)
- Also unblocks the Texture payload descriptor half of #602 (see that issue's closure notes)
- CurveTable fixtures: `ORIGIN-issue-626-curve-table.md`
