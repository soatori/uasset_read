# #515 Opaque StructProperty Candidates

> Generated: 2026-08-02
> Scan script: `tests/temp/scan_opaque_structs.py`
> Samples scanned: 41

## Scan Summary

| Metric | Value |
|--------|-------|
| Total samples scanned | 41 |
| Files with opaque exports | 9 |
| Total opaque exports | 39 |
| Total struct entries in opaque | 22 |
| Unique struct types | 8 |

## Candidate Selection Criteria

| Dimension | Evaluation | Weight |
|-----------|-----------|--------|
| Frequency | Occurrence count in tracked samples | High |
| Impact | Importance of user-visible data | High |
| Complexity | Parsing difficulty (tagged fallback vs native) | Medium |
| Evidence | UE source documentation level | High |

A candidate qualifies for implementation only when ALL are met:
1. Stable fixture available (version-controlled in `tests/samples/`)
2. Binary boundaries determinable (tag.size or tagged property loop)
3. UE source code auditable for the matching engine version
4. Field semantics provable from source or tagged property structure

## All Candidates by Frequency

| # | Struct Type | Occurrences | Unique Locations | Raw Size Range | Sample Files |
|---|------------|-------------|-----------------|----------------|--------------|
| 1 | Guid | 13 | 13 | null (fast-path) | ALS_N_FallLoop, FirstPerson_M_FlatCol, FirstPerson_M_PrototypeGrid, IntroToUnreal_M_Plastic, NM_BPSystemEvent, StarterContent_M_Wood_Walnut |
| 2 | AlphaBlend | 2 | 2 | 37-78 | ALS_CLF_GetUp_Back_Montage_Default |
| 3 | MeshSectionInfoMap | 2 | 2 | 228 | StarterContent_SM_Chair |
| 4 | BoxSphereBounds | 1 | 1 | 187 | StarterContent_SM_Chair |
| 5 | MeshNaniteSettings | 1 | 1 | 34 | StarterContent_SM_Chair |
| 6 | NiagaraParameterStore | 1 | 1 | 102 | NM_BPSystemEvent |
| 7 | RawCurveTracks | 1 | 1 | 5258 | ALS_CLF_GetUp_Back_Montage_Default |
| 8 | StaticMeshSourceModel | 1 | 1 | 37 | StarterContent_SM_Chair |

## Top Candidates (Recommended for Implementation)

### 1. AlphaBlend

- **Occurrences:** 2
- **Sample file:** `ALS_CLF_GetUp_Back_Montage_Default.uasset` (properties: `BlendIn`, `BlendOut`)
- **Raw size:** 37-78 bytes
- **Rationale:** Animation montage blending parameters. Variable size suggests tagged property format or LWC precision variants. UE source: `Animation/AlphaBlend.h`. Medium complexity; high impact for animation data extraction.

### 2. MeshSectionInfoMap

- **Occurrences:** 2
- **Sample file:** `StarterContent_SM_Chair.uasset` (properties: `SectionInfoMap`, `OriginalSectionInfoMap`)
- **Raw size:** 228 bytes
- **Rationale:** Static mesh section metadata map. Map type requires careful parsing of key-value pairs. UE source: `Engine/MeshSectionInfo.h`. Medium complexity; medium impact for mesh structure analysis.

### 3. MeshNaniteSettings

- **Occurrences:** 1
- **Sample file:** `StarterContent_SM_Chair.uasset` (property: `NaniteSettings`)
- **Raw size:** 34 bytes
- **Rationale:** Nanite virtual geometry settings. Small fixed size suggests simple binary layout. UE source: `Engine/NaniteVertexFactory.h` and related. Low complexity; emerging importance for UE5+ assets.

### 4. NiagaraParameterStore

- **Occurrences:** 1
- **Sample file:** `NM_BPSystemEvent.uasset` (property: `RapidIterationParameters`)
- **Raw size:** 102 bytes
- **Rationale:** Niagara VFX parameter storage. Variable-size parameter store with internal array structure. UE source: `NiagaraDataInterfaceBase.h` and Niagara module. Medium complexity; high impact for VFX data extraction.

## Deferred Candidates

### StaticMeshSourceModel

- **Occurrences:** 1
- **Reason:** Complex nested structure (LOD settings, build settings, reduction settings). Requires deep UE source analysis of `StaticMeshSourceModel.h` and multiple sub-structures. Low ROI for initial implementation.

### RawCurveTracks

- **Occurrences:** 1
- **Reason:** Very large raw_size (5258 bytes). Contains arrays of rich curve data with nested structures. High parsing complexity; better deferred until simpler candidates are validated.

### Guid (13 occurrences)

- **Reason:** Already handled by `_try_fast_path_struct()` in `property_types.py:628-632`. Not an opaque candidate -- these 13 occurrences appear in the scan because they are embedded in opaque exports, but the StructProperty itself is parsed by the fast-path handler. No implementation needed.

## Excluded Categories

- **Fast-path handled structs:** `Vector`, `Rotator`, `Vector2D`, `Vector4`, `LinearColor`, `Color`, `Quat`, `Plane`, `Guid`, `IntPoint`, `IntVector`, `Box2D`, `Box`, `Sphere`, `TopLevelAssetPath`, `PointerToUberGraphFrame`, `Matrix`, `TwoVectors`, `OrientedBox`, `Transform` -- all handled by `_try_fast_path_struct()` in `property_types.py`.
- **Tagged fallback structs:** `MemberReference`, `SimpleMemberReference`, `FBPVariableDescription`, `BPVariableDescription`, `EdGraphPinType`, `FEdGraphPinType`, `BPVariableDescriptionHelper`, `ComponentOverrideRecord`, `ImplementedInterfaces`, `LastEditedDocuments`, `EditedDocumentInfo`, `CategorySorting`, `FrameRate`, `AnimNotifyTrack`, `FEditorElement`, `BoxSphereBounds` -- handled via `_TAGGED_FALLBACK_STRUCTS` in `property_types.py:197-217`.
- **Zero-boundary false positives:** Opaque exports with no struct data or with `tag.size <= 0` that produce empty `StructValue` objects.

## Implementation Notes

- All candidates with non-null `raw_size` values have determinable binary boundaries via the tagged property size field.
- Candidates 2-5 have variable or complex layouts; tagged fallback parsing may be needed before native fast-path implementation.
- Candidate selection should prioritize types with stable, version-controlled sample fixtures in `tests/samples/`.
