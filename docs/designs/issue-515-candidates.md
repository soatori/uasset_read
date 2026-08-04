# #515 Opaque StructProperty Candidates

> Original scan: 2026-08-02 (`tests/temp/scan_opaque_structs.py`)
> Re-scan: 2026-08-05 (`tests/temp/rescan_opaque_structs.py`)
> Re-scan output: `temp/rescan_opaque_2026-08-05.txt`
> Samples scanned: 42 (all files under `tests/samples/` at scan time)

## Scan Methodology

The 2026-08-02 scan listed struct types embedded in opaque **exports**. The
2026-08-05 re-scan records only StructProperty values whose **own**
`parse_status` is `opaque` in the current parser output (JSON, tolerant mode,
`output_level="debug"`), recursing into export properties and `ArrayProperty`
items. The re-scan is diagnostic only; it does not modify parsing.

## Scan Summary

| Metric | Value |
|--------|-------|
| Samples scanned | 42 |
| Parse errors | 0 |
| Opaque struct values found by the script | 37 |
| Unique opaque struct types found by the script | 5 |
| Additional opaque values verified outside the script traversal | 126 (`UnknownStruct`; see traversal caveat below) |

## Status change since 2026-08-02

The six 2026-08-02 candidates are now `success` via the generic tagged-fallback
loop in `parse_struct_property` (`parsers/property_types.py`). They are no
longer opacity candidates:

| 2026-08-02 candidate | Current status | Verified location |
|---|---|---|
| `AlphaBlend` | success (`BlendIn`/`BlendOut`, 37/78 bytes) | `ALS_CLF_GetUp_Back_Montage_Default.uasset` |
| `MeshSectionInfoMap` | success (`SectionInfoMap`/`OriginalSectionInfoMap`, 228 bytes) | `StarterContent_SM_Chair.uasset` |
| `MeshNaniteSettings` | success (`NaniteSettings`, 34 bytes) | `StarterContent_SM_Chair.uasset` |
| `BoxSphereBounds` | success (`ExtendedBounds`, 187 bytes) | `StarterContent_SM_Chair.uasset` |
| `NiagaraParameterStore` | success (`RapidIterationParameters`, 102 bytes) | `NM_BPSystemEvent.uasset` |
| `StaticMeshSourceModel` | success (`HiResSourceModel`, 37 bytes) | `StarterContent_SM_Chair.uasset` |

Other 2026-08-02 list entries: `RawCurveTracks` also decodes as `success` at
the struct-value level now (its containing export remains `opaque` at export
level, which is why the export-based 2026-08-02 scan listed it); `Guid` was
already a fast-path false positive in the old scan.

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

## All Candidates by Frequency (re-scan 2026-08-05)

From `temp/rescan_opaque_2026-08-05.txt`:

| # | Struct Type | Occurrences | Raw Size | Sample Files |
|---|------------|-------------|----------|--------------|
| 1 | ExpressionInput | 22 | 36 | StarterContent_M_Wood_Walnut |
| 2 | NiagaraVariable | 12 | 111-114 | NM_BPSystemEvent |
| 3 | ColorMaterialInput | 1 | 44 | StarterContent_M_Wood_Walnut |
| 4 | ScalarMaterialInput | 1 | 44 | StarterContent_M_Wood_Walnut |
| 5 | VectorMaterialInput | 1 | 52 | StarterContent_M_Wood_Walnut |

### Re-scan traversal caveat: UnknownStruct

`UnknownStruct` does not appear in the script output: the re-scan's `_collect`
recurses into StructProperty values and ArrayProperty items only, not into
MapProperty entries. A separate verification walk over
`CiciToon_SK_Mannequin.uasset` (2026-08-05) found 126 `UnknownStruct` values
(the `AnimCurveMetaData` map values), all with `parse_status: opaque` and
`raw_size: 0`. They remain part of the still-opaque set below.

## Still-Opaque Set (recommended next slices)

### 1. ExpressionInput (22 occurrences)

- **Sample file:** `StarterContent_M_Wood_Walnut.uasset` (material expression inputs such as `A`, `B`, `Alpha`)
- **Raw size:** 36 bytes
- **Rationale:** Material graph input references. Native (non-tagged) layout per
  `SerializeExpressionInput` (`Engine/Source/Runtime/Engine/Private/Materials/MaterialShared.cpp:439-469`,
  UE 5.8.0-release), which is why the tagged fallback cannot decode it. Highest
  frequency in the current corpus; stable fixture available.

### 2. NiagaraVariable (12 occurrences)

- **Sample file:** `NM_BPSystemEvent.uasset` (properties: `Input`, `Variable`)
- **Raw size:** 111-114 bytes
- **Rationale:** Niagara script variable declarations with offset-based embedded
  data. Requires its own evidence-backed slice (adjacent to #521 work).

### 3. Material input variants (3 occurrences)

- **Types:** `ScalarMaterialInput` (44 bytes), `ColorMaterialInput` (44 bytes),
  `VectorMaterialInput` (52 bytes)
- **Sample file:** `StarterContent_M_Wood_Walnut.uasset` (properties: `Roughness`, `BaseColor`, `Normal`)
- **Rationale:** Same native family as `ExpressionInput`: base 36 bytes +
  `bUseConstant` (uint32) + typed `Constant`, per `SerializeMaterialInput`
  (`MaterialShared.cpp:473-487`, UE 5.8.0-release). Best implemented together
  with candidate 1.

### 4. UnknownStruct -- CurveMetaData values (126 occurrences)

- **Sample file:** `CiciToon_SK_Mannequin.uasset` (values of the `AnimCurveMetaData` map entries)
- **Raw size:** 0
- **Rationale:** Zero-size tagged struct values whose type name is not resolved
  (reported as `UnknownStruct`). Not visible to the re-scan script (MapProperty
  entries); verified separately as still opaque. Type-name resolution needs its
  own evidence-backed slice.

## Follow-up: MeshSectionInfoMap value correctness (not opacity)

`MeshSectionInfoMap` now decodes as a `MapProperty`, but its value type resolves
to `IntProperty` with a single entry (`{0: 77}`) -- the `FMeshSectionInfo`
fields are not decoded. That is a **correctness gap**, not an opacity gap, and
is tracked as a follow-up rather than in the opaque candidate list above.

## Implementation Notes

- All still-opaque candidates above have determinable boundaries (`tag.size` or
  zero-size tagged) except where noted; layouts must be proven against UE source
  before implementation (no format guessing).
- Candidate selection should prioritize types with stable, version-controlled
  sample fixtures in `tests/samples/`.
