# Issue #662 — UE 5.8.2 User Fixture Origin

Every number below was read back from the files on disk: header facts and structural
facts by the v2 reader, hashes and sizes by independent re-measurement. Nothing here
is asserted from an asset's name.

## Source

- **Author**: the user themselves — first-party, self-authored content (strongest
  provenance: the provider is the author), redistributable.
- **Provider verification**: engine build `5.8.2.56702186` verified on all five files and
  SHA-256 match against the `MyProject Content/ParserFixtures/Issue662/` originals,
  confirmed independently by the re-measured hashes/sizes below.
- **Directory**: `Content/ParserFixtures/Issue662/` (editor-saved, not cooked —
  `PackageFlags == 0x0`, package names `/Game/ParserFixtures/Issue662/...`)
- **Version pin (re-measured per package, all five identical)**: legacy layout,
  `LegacyFileVersion -9`, `FileVersionUE4 522`, `FileVersionUE5 1018`,
  `SavedByEngineVersion 5.8.2.56702186`, `CompatibleWithEngineVersion 5.8.0.55116800`.
  The reader reads these from the package itself, so the engine version is file evidence,
  not a name claim.

## Files

| File | Size | SHA-256 | Asset export class | exports/assets | names/imports |
| --- | --- | --- | --- | --- | --- |
| `Issue662_SkeletalMesh.uasset` | 15,824,430 B | `3747803797e0a2142deb5c07b8cd65a52aa7d5e3a95a156f1a7a757faca03527` | SkeletalMesh | 7 / 1 | 248 / 15 |
| `Issue662_AnimComposite.uasset` | 3,227 B | `3041cf67346a6ed87c1c1df9d54d722cb4edf93672c537eafe612df178d7776e` | AnimComposite | 2 / 1 | 44 / 7 |
| `Issue662_AnimLayerInterface.uasset` | 9,583 B | `da527310c6e10746c326a055e6ee0379a330bc557a0f8f8c4b1497a2ac7918a9` | AnimBlueprint (asset-as-interface) | 6 / 2 | 52 / 12 |
| `Issue662_MaterialFunction.uasset` | 49,543 B | `ee5358ebdc3bd7569a56005754c464c898f900fa8bd88a63f751d3153c4ccb51` | MaterialFunction | 79 / 1 | 153 / 40 |
| `Issue662_MaterialParameterCollection.uasset` | 1,688 B | `512db99f9986a1e5f59ec4868f84aa86be196015c4981e2fb7aa15f07036a71f` | MaterialParameterCollection | 1 / 1 | 21 / 2 |

## Structural verification (measured)

### SkeletalMesh

- Asset export `export:3` (`SkeletalMesh`, `Issue662_SkeletalMesh`); the other exports are
  `FbxSkeletalMeshImportData`, `AnimCurveMetaData`, `SceneThumbnailInfo` and three
  `SkeletalMeshDescriptionBulkData` blocks (one per LOD).
- LODs are reader-proven from the tagged `SourceModels` stream: 3 source models. LOD0
  caches 92,178 triangles / 46,098 vertices; LOD1 reduces to 12.5 % triangles /
  50 % vertices, LOD2 to 6 % / 50 % (LOD1/LOD2 cached counts are zero in the bag).
- **Bone count is not claimed.** Bones and sections are native-stream data, not tagged
  properties: the mesh payload stays an undecoded native tail of 11,942,964 B after the
  property stream (`EXPORT_TRAILING_BYTES_UNCONSUMED/unexpected`), and `WholeMeshBuiltData`
  is retained as 40 raw bytes (`BINARY_OR_NATIVE_PROPERTY_OPAQUE/known_unimplemented`).
  A record-layout probe of the tail against the two known `FMeshBone` encodings failed
  structural validation, so no bone or section number is pinned; the CAPABILITIES row pins
  only the reader-proven facts, and deep mesh decode stays gated on the #657 P-SK rulings.

### AnimComposite

- 1 decoded segment in `AnimationTrack`: `AnimReference` resolves through `import:0` to
  `MM_Idle` (AnimSequence, package `/Game/Characters/Mannequins/Anims/Unarmed/MM_Idle`);
  `StartPos` 0.0, `AnimStartTime` 0.0, `AnimEndTime` 7.566666603088379, play rate 1.0,
  looping count 1. One `AnimNotifyTrack` (`TrackName` "1"). 16 trailing bytes remain
  unclassified (`known_unimplemented`), so `segment_count` is the pinned assertion.

### AnimLayerInterface

- Asset-as-interface save (UE 5.x): the asset-role exports measure `AnimBlueprint`
  (`Issue662_AnimLayerInterface`) and `AnimBlueprintGeneratedClass`
  (`Issue662_AnimLayerInterface_C`) — there is no export class `AnimLayerInterface`, so the
  handler's `Functions` path reports its explicit missing coverage, and the pinned row is
  the measured `anim_blueprint` summary row.
- Function graph proved structurally: `EdGraph` `Issue662Layer`, `Function` `Issue662Layer`,
  one `K2Node_FunctionEntry`; the Kismet summary reports 1 verified function, 2 instructions
  (`EX_Return`, `EX_EndOfScript`), script range 9077–9080.

### MaterialFunction

- 76 `MaterialExpression*` exports, including 7 comments; inputs `TriPlanar` and `TileSize`;
  outputs `Wire` and `Checker`; 4 `MaterialExpressionMaterialFunctionCall` nodes. Plus
  `MaterialFunctionEditorOnlyData` and `SceneThumbnailInfoWithPrimitive`. Zero diagnostics:
  this fixture parses byte-exactly.

### MaterialParameterCollection

- 1 scalar parameter: `Issue662Value`, default 1.0. `VectorParameters` is absent from the
  property bag, so the handler's explicit missing-vector path is pinned as measured.
  Zero diagnostics.

## Verification / gate

- `tests/samples/manifest.json` → `samples[]` entries carry SHA-256, size and real export and
  asset-role counts; the five `fixture_gaps` entries (`skeletal_mesh`, `anim_composite`,
  `anim_layer_interface`, `material_function`, `material_parameter_collection`) are `available`
  only while these fixtures, their CAPABILITIES rows and this file all exist.
- `tests/test_samples.py::test_manifest_matches_every_real_sample` fails on a missing file, a
  size change, a hash mismatch, or an ORIGIN doc quoting a hash the manifest does not track.
- `tests/test_samples.py::test_real_sample_proves_claimed_capability` pins the five measured
  summary-tier rows (`partial` with coverage).
- `tests/test_samples.py::test_quality_baseline_diagnostics` gates the per-fixture observed
  diagnostic sets recorded in `tests/samples/quality_baseline.json`.

## Related

- Issue: #662 (parent: #657 Phase 1; P-SK mesh decode gate)
- Companion #662 origin: `ORIGIN-issue-662-ue4-graph.md`
