# #515 Opaque StructProperty Candidates

> Original scan: 2026-08-02 (`temp/scan_opaque_structs.py`)
> Re-scan: 2026-08-05 (`temp/rescan_opaque_structs.py`)
> Re-scan output: `temp/rescan_opaque_2026-08-05.txt`
> B1-pre re-scan: 2026-08-05 (`temp/scan_opaque_structs.py` extended, commit `28725871`)
> B1-pre output: `temp/b1_pre_scan.json`
> Samples scanned: 42 (all files under `tests/samples/` at scan time)
> 2026-08-05 (B1-pre): scan extended to `partial_metadata` exports; counts refreshed.

## Scan Methodology

Three scan generations exist; their counts are NOT interchangeable. Every row
below cites the scan that produced it.

1. **2026-08-02 original scan** (`temp/scan_opaque_structs.py`,
   export-level): listed struct types embedded in exports whose
   `parse_status` was `opaque`. Superseded; its six then-opaque candidates
   are tracked in the "Status change" section below.
2. **2026-08-05 value-level re-scan** (`temp/rescan_opaque_structs.py`,
   output `temp/rescan_opaque_2026-08-05.txt`): records only StructProperty
   values whose **own** `parse_status` is `opaque` in the current parser
   output (JSON, tolerant mode, `output_level="debug"`), recursing into
   export properties and `ArrayProperty` items (not `MapProperty` entries).
   This is the generation that measures remaining value-level opacity.
3. **2026-08-05 B1-pre export-level scan** (`temp/scan_opaque_structs.py`
   extended in commit `28725871` to exports whose `parse_status` is `opaque`
   OR `partial_metadata`; output `temp/b1_pre_scan.json`): records EVERY
   StructProperty entry inside in-scope exports regardless of the value's own
   status, and tags each occurrence with `export_status`. Extending to
   `partial_metadata` was the B1-pre intake fix: all Niagara exports are
   handler-projected `partial_metadata` (#521), so the opaque-only filter
   structurally missed them. Because it does not filter by value status, this
   scan also re-lists struct types that already decode — treat its rows as
   "structs embedded in in-scope exports", not as opacity candidates by
   themselves.

All scans are diagnostic only; they do not modify parsing.

## Scan Summary

### B1-pre export-level scan (2026-08-05, `temp/b1_pre_scan.json`)

| Metric | Value |
|--------|-------|
| Samples scanned | 42 |
| Files with in-scope exports (`opaque` or `partial_metadata`) | 21 |
| Total in-scope exports | 87 |
| Total struct entries recorded | 138 |
| Unique struct types recorded | 22 |

### Value-level re-scan (2026-08-05, `temp/rescan_opaque_2026-08-05.txt`)

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

Status change after the value-level re-scan (2026-08-05, FExpressionInput
slice; commits `242b66e7`, `d8278880`; roadmap Slice Log): the four re-scan
candidates `ExpressionInput` (×22), `ScalarMaterialInput`, `ColorMaterialInput`
and `VectorMaterialInput` are now decoded by dedicated native parsers
(`SerializeExpressionInput` / `SerializeMaterialInput`,
`MaterialShared.cpp:439-487`, UE `5.8.0-release` @ `7deeb413d`) — all 25
family structs in `StarterContent_M_Wood_Walnut.uasset` report
`parse_status: success`. They are no longer opacity candidates.

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

Row status as of B1-pre: rows 1, 3, 4, 5 are decoded (FExpressionInput slice,
see "Status change" above); row 2 (`NiagaraVariable`) remains opaque at value
level and is intaken in the Niagara Intake section below.

### Re-scan traversal caveat: UnknownStruct

`UnknownStruct` does not appear in the script output: the re-scan's `_collect`
recurses into StructProperty values and ArrayProperty items only, not into
MapProperty entries. A separate verification walk over
`CiciToon_SK_Mannequin.uasset` (2026-08-05) found 126 `UnknownStruct` values
(the `AnimCurveMetaData` map values), all with `parse_status: opaque` and
`raw_size: 0`. They remain part of the still-opaque set below. The Niagara
`UnknownStruct` array elements have a separate structural blind spot,
documented in the Niagara Intake section.

### B1-pre export-level frequencies (2026-08-05, `temp/b1_pre_scan.json`)

Export-level scan rows for the Niagara structs (occurrences / unique
(file, property) locations / `export_status`). The B1-pre scan does not
filter by value status, so the deciding column for candidacy is the
value-level status — verified live (debug parse of every instance) and by
byte-level tag walks (`temp/b1_gate_byte_walk.py`) proving exact payload
consumption:

| Struct Type | Occurrences | Unique locations | export_status | Value-level status (verified) |
|---|---|---|---|---|
| Guid | 83 | 23 | mixed | decoded (fast path) — not a candidate |
| NiagaraVariable | 12 | 2 | partial_metadata | **opaque ×12** (raw 111-114) |
| NiagaraVariableMetaData | 11 | 1 | partial_metadata | success ×11 (73/73 bytes consumed) |
| NiagaraVariant | 11 | 1 | partial_metadata | success ×11 (90/90 consumed) |
| NiagaraTypeDefinition | 1 | 1 | partial_metadata | success (37/37 consumed) |
| StaticSwitchTypeData | 1 | 1 | partial_metadata | success (34/34 consumed) |
| NiagaraParameterStore | 1 | 1 | partial_metadata | success (102/102 consumed) |

The `NiagaraVariable` location dedup collapses 11 `NiagaraScriptVariable_*.Variable`
exports (same file + outer path) plus `NiagaraNodeInput_170.Input` into 2 rows.

The pre-existing opaque-only candidates persist unchanged in the B1-pre scan
(`AlphaBlend` ×2, `MeshSectionInfoMap` ×2, `Guid` occurrences inside opaque
exports ×9, `MeshNaniteSettings` ×1, `RawCurveTracks` ×1,
`StaticMeshSourceModel` ×1, `BoxSphereBounds` ×1). All of them already decode
at value level (see "Status change" above), so their re-listing here is the
expected no-value-filter byproduct of the export-level methodology, not new
opacity.

## Still-Opaque Set (status as of B1-pre, 2026-08-05)

### 1. ExpressionInput (22 occurrences) — RESOLVED

- Decoded by the FExpressionInput slice (commits `242b66e7`, `d8278880`;
  roadmap Slice Log 2026-08-05): native layout per `SerializeExpressionInput`
  (`Engine/Source/Runtime/Engine/Private/Materials/MaterialShared.cpp:439-469`,
  UE 5.8.0-release @ `7deeb413d`). All occurrences now `parse_status: success`.
  No longer an opacity candidate.

### 2. NiagaraVariable (12 occurrences) — still opaque, intaken

- **Sample file:** `NM_BPSystemEvent.uasset` (properties: `Input`, `Variable`)
- **Raw size:** 111-114 bytes
- **Rationale:** Niagara script variable declarations. Custom `Serialize`
  (`FNiagaraVariableBase::Serialize`, NiagaraModule.cpp:1732), so the tagged
  fallback cannot decode it. Intaken with full gate evidence in the Niagara
  Intake section below; child issue created under #515. It gates the #521
  parameters path.

### 3. Material input variants (3 occurrences) — RESOLVED

- Decoded together with candidate 1 (same slice): base 36 bytes +
  `bUseConstant` (uint32) + typed `Constant`, per `SerializeMaterialInput`
  (`MaterialShared.cpp:473-487`, UE 5.8.0-release @ `7deeb413d`). All
  occurrences now `parse_status: success`. No longer opacity candidates.

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

## Niagara Intake (B1-pre, from #521 roadmap)

Fixture: `tests/samples/NM_BPSystemEvent.uasset`, SHA-256
`B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF`.
Fixture package: UE5.0-era (legacy file version −8, `FileVersionUE4` 522,
`FileVersionUE5` 1004, `FNiagaraCustomVersion` 70) — the checkout is 5.8, so
every cited code path is version-checked and deltas are recorded below.
UE checkout: `E:/Develop/lib/UnrealEngine` @ `7deeb413d3dc1fc034f48d1aacc0861301829d32`
(5.8.0-release), verified at audit time. Property paths observed in the scan:
`NiagaraScriptVariable_*.Variable` / `.Metadata` / `.DefaultValueVariant`,
`NiagaraNodeInput_170.Input`, `NiagaraNodeSelect_1.SelectorPinType`,
`NiagaraNodeStaticSwitch_1.SwitchTypeData`,
`NM_BPSystemEvent.RapidIterationParameters`. Element identifications:
`docs/designs/issue-521-b0-pin-existence-evidence.md` (B0a byte evidence).

### Selection gate

The gate applies the four Candidate Selection Criteria (fixture / boundary /
source / semantics) plus the candidacy premise of this document: the struct
must still be opaque or under-decoded. Value-level status was verified live
(debug parse of every instance) and, for the tagged structs, by byte-level
tag walks (`temp/b1_gate_byte_walk.py`) that prove exact payload consumption
(absent members are writer-side default skips, not dropped bytes).

| Struct | Source reference (checkout `7deeb413d`) | Gate (fixture / boundary / source / semantics) | Qualifies |
|---|---|---|---|
| NiagaraVariable | `NiagaraTypes.h:1460` (`FNiagaraVariable`), `:1281` (`FNiagaraVariableBase`); custom `Serialize` `NiagaraModule.cpp:1732`/`:1763` | ✓ / ✓ tag.size / ✓ / ✓ (B0a byte evidence: FName `Name` + `FNiagaraTypeDefinition` tagged stream + data blob; exact size arithmetic) | **yes** — value-level opaque ×12; custom Serialize means the tagged fallback never applies |
| NiagaraGraphScriptUsageInfo | `NiagaraEditor/Public/NiagaraGraph.h:87` (struct), `:571` (member `CachedUsageInfo`) | ✓ / ✓ per-element tag size / ✓ / ✓ (B0a: 544/544-byte tagged stream decoded) | **yes** — opaque array element (`UnknownStruct`, raw_size 0) |
| VersionedNiagaraScriptData | `Niagara/Classes/NiagaraScript.h:619` (struct), `:873` (member `VersionData`) | ✓ / ✓ per-element tag size / ✓ / ✓ (B0a: 2038/2038-byte tagged stream decoded) | **yes** — opaque array element (`UnknownStruct`, raw_size 0) |
| NiagaraVariableMetaData | `Niagara/Public/NiagaraVariableMetaData.h:214` | ✓ / ✓ / ✓ / ✓ — but no gap | **no** — tagged fallback already decodes it completely (11/11 instances `success`; 73/73 bytes consumed) |
| NiagaraVariant | `Niagara/Public/NiagaraVariant.h:23` | ✓ / ✓ / ✓ / ✓ — but no gap | **no** — fully decodes (11/11 `success`; 90/90 consumed; absent `Object`/`DataInterface` are null-default skips) |
| NiagaraTypeDefinition | `Niagara/Public/NiagaraTypes.h:664`; `Serialize` `NiagaraModule.cpp:1569` (delegates to tagged properties) | ✓ / ✓ / ✓ / ✓ — but no gap | **no** — fully decodes (`success`; 37/37 consumed; absent `UnderlyingType`/`Flags` are default skips) |
| StaticSwitchTypeData | `NiagaraEditor/Private/NiagaraNodeStaticSwitch.h:20` (`FStaticSwitchTypeData`), member `:58` | ✓ / ✓ / ✓ / ✓ — but no gap | **no** — fully decodes (`success`; 34/34 consumed) |
| NiagaraParameterStore | `Niagara/Public/NiagaraParameterStore.h:161` | ✓ / ✓ / ✓ / ✓ — but no gap | **no** — fully decodes (`success`; 102/102 consumed; confirms the 2026-08-05 "Status change" record) |
| Guid / FGuid | parser fast path | — | excluded — already decoded, including the two `OutputVarGuids` elements (B0a) |

Intake result: `NiagaraVariable` (parameters path, first),
`NiagaraGraphScriptUsageInfo`, and `VersionedNiagaraScriptData` pass the gate
and each receives a #515 child issue. The five "no" structs are recorded here
as verified-decodable (evidence above) and are not intaken; their decode
status is incidental to the generic tagged fallback, so a future fixture whose
non-default members exercise unsupported property types would be a new,
separate observation.

### Array-element caveat (structural scan blind spot)

The identified element structs live in `ArrayProperty` values:
`NiagaraGraph_1.CachedUsageInfo`, `NiagaraNodeOutput_1.Outputs`,
`NiagaraNodeSelect_1.OutputVars`, `NiagaraNodeStaticSwitch_1.OutputVars`,
`NM_BPSystemEvent.VersionData`, plus the two `FGuid` elements in
`OutputVarGuids` (Select/StaticSwitch). The export-level scan structurally
never visits them: its `ArrayProperty` branch expects an `{"items": [...]}`
value shape with per-item `"type"` keys, while the parser emits these arrays
as bare element lists whose entries carry `property_type` instead. Their
intake entries therefore cite the B0a byte evidence, not scan occurrences.
(The roadmap's "(elements of Outputs/OutputVars)" parenthetical was
imprecise: the seven identified element occurrences span five properties —
`CachedUsageInfo`, `Outputs`, `OutputVars`, `OutputVarGuids`, `VersionData` —
on five exports.)

Mechanism (B0a): in the legacy tag format an `ArrayProperty` tag carries only
the inner type (`StructProperty`), not the element struct name; the name is
written inside the array payload as a per-element property tag
(`LoadPropertyTagNoFullType`, `PropertyTag.cpp` at the pinned commit), which
the parser does not currently read — hence `UnknownStruct`, `raw_size: 0`,
`parse_status: opaque`. Decoding these elements requires reading the
per-element tags first.

Version deltas (fixture UE5.0-era vs checkout 5.8), recorded per B0a:
- `FNiagaraGraphScriptUsageInfo`: 5.8 member `ReferenceHashFromGraph` absent
  from the fixture stream.
- `FVersionedNiagaraScriptData`: 5.8 member `InlineOverviewDisplayName`
  absent from the fixture stream.
- `FNiagaraVariable(Base)` (`NiagaraModule.cpp:1732-1776`): the 5.8 writer
  branches on `FNiagaraCustomVersion::VariablesUseTypeDefRegistry` (5.8
  ordinal 64 in `NiagaraCustomVersion.h`). The fixture's stored
  `FNiagaraCustomVersion` is 70, which under 5.8 ordinals would select the
  registry path — but the fixture bytes (B0a) hold the LEGACY layout (FName
  `Name` + nested tagged `FNiagaraTypeDefinition` + `VarData` blob). The
  UE5.0-era enum ordinals differ from 5.8, so the 5.8 version comparison
  cannot be applied to the fixture's version value; the decoder must
  implement the legacy layout as pinned by the B0a byte walk and cite it
  field-by-field.

## Implementation Notes

- All still-opaque candidates above have determinable boundaries (`tag.size` or
  zero-size tagged) except where noted; layouts must be proven against UE source
  before implementation (no format guessing).
- Candidate selection should prioritize types with stable, version-controlled
  sample fixtures in `tests/samples/`.
