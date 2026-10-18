# Issue #665 — struct property fallback diagnosis (Vector / Guid / Transform / LinearColor / Box)

Worktree: `issue-665-struct-fallbacks` on `dev-0.6.0` @ cf29b070.
UE source: paths relative to the Unreal Engine source root of the local
`UnrealEngine/` checkout (per AGENTS.md). Peers under `external/` are
corroboration only and are cited by name.

## 1. Reproduction (matches the issue table exactly)

DEBUG-log capture over the five listed samples reproduces every count in the
issue:

```
16  StarterContent_SM_Chair.uasset          StructProperty 'Vector': tag.size=0 does not match float(12) or double(24)
 1  StarterContent_SM_Chair.uasset          StructProperty 'Box': tag.size=49 does not match float(28) or double(52)
 1  StarterContent_SM_Chair.uasset          StructProperty 'Transform': tag.size=235 does not match float(40) or double(80)
 4  B_ControlPointScoring.uasset            StructProperty 'LinearColor': tag.size=0 != expected=16
 3  StarterContent_M_Wood_Walnut.uasset     StructProperty 'Guid': tag.size=0 != expected=16
 2  Lyra_SEQ_LobbyScreen_LevelSequence.uasset StructProperty 'Guid': tag.size=0 != expected=16
 4  Lyra_SEQ_LobbyScreen_LevelSequence.uasset StructProperty 'Transform': tag.size=162/235 ...
 5  BP_UnversionedTest.uasset               Unversioned export ... without mappings, returning opaque block
```

Tracing `parse_struct_property`/`parse_array_property` per call (temp/trace_665.py,
temp/arrays_665.py) shows where each lands:

| Sample | Property | Container | Observed result (before) |
|---|---|---|---|
| chair | `VertexData[0..15]` size=0 ×16 | `TArray<FVector>` in `FKConvexElem` | alternating opaque / empty-"success" StructValue, all X/Y/Z data lost |
| chair | `ElemBox` size=49 | `FKConvexElem.ElemBox` member tag | opaque (tagged loop on native bytes → ParseError → seek end) |
| chair | `Transform` size=235 | `FKConvexElem.Transform` member tag | decoded via tagged loop, but `TRANSFORM_SIZE_INVALID` `recovered_corruption` emitted first |
| B_Control | `RawTeamColors[0..3]` size=0 ×4 | `TArray<FLinearColor>` | opaque ×4 (silent) |
| M_Wood | `ReferencedTextureGuids[0..2]` size=0 ×3 | `TArray<FGuid>` | opaque / empty-"success" (silent) |
| Lyra | `ChildPossessables[0]` ×2, `SpawnTransform` 235 ×2, `InitialCameraCutTransform` 162 ×2 | arrays / member tags | Guid lost; Transform decoded but `TRANSFORM_SIZE_INVALID` `recovered_corruption` downgraded `MovieSceneCameraCutSection_0/2` to `parse=partial` |
| BP_Unversioned | whole export streams | unversioned, no/limited usmap | `UnversionedOpaque` + `PROPERTY_VALUE_READ_FAILED` `schema_required` |

## 2. Classification (exactly one class per fallback, UE-source backed)

### 2.1 Vector — 16× size-0 in `StarterContent_SM_Chair.uasset` → **(a) legal inline/native layout we mis-handle**

- File: inner tag `VertexData/StructProperty/Vector size=384` read after the
  array count; `384/16 = 24` = `FVector3d` native stride. Outer array tag size
  437 = 4 (count) + 49 (inner tag header) + 384 (elements).
- UE source: `Engine/Source/Runtime/CoreUObject/Private/UObject/PropertyArray.cpp:768-777`
  — for `UEVer < PROPERTY_TAG_COMPLETE_TYPE_NAME && >= VER_UE4_INNER_ARRAY_TAG_INFO`
  and struct inner types, the array payload carries **one** inner `FPropertyTag`
  whose `Size` bounds the elements (`PropertyArray.cpp:817` uses it as the
  remaining-size bound on load); each element then serializes via
  `Inner->SerializeItem(...)` (`PropertyArray.cpp:141-197` save path).
- Native element serialization: `Engine/Source/Runtime/Core/Public/Math/Vector.h:1225/1242`
  `operator<<(FArchive&, TVector<float|double>&)` writes `X << Y << Z`
  (12 bytes float / 24 bytes double).
- Our parser read the inner tag (`size=384`) and then threw the size away,
  building `size=0` element tags (`property_types.py` legacy-element path), so
  the size pre-check always rejected the fast path and a `size=0` "validated"
  tagged attempt ran over raw floats — data lost, boundaries only held because
  `read_tag_value_bounded` seeks the outer value end.
- Fix: `_native_struct_elem_size()` derives the stride (`payload/count`) when it
  equals a known native size for the struct type; element tags carry it and the
  existing fast path decodes. `_TAGGED_FALLBACK_STRUCTS` and non-native types
  keep `size=0` (validated None-terminated attempt) unchanged.

### 2.2 Guid — 3× size-0 in `StarterContent_M_Wood_Walnut.uasset`, 2× in Lyra → **(a)**

- File: inner tags `size=48` (3×16) and `size=16` (1×16); stride = 16 = `FGuid`.
- UE source: `Engine/Source/Runtime/Core/Private/Misc/Guid.cpp:637-639`
  `operator<<` writes `G.A << G.B << G.C << G.D` (4×uint32 = 16 bytes).
- Same root cause and same fix as Vector. One Lyra case
  (`ReferencedTextureGuids[1]` pattern) even reported a *false* `success` with
  empty fields when the raw GUID bytes happened to read as a `None` tag; the
  sized decode removes that path.

### 2.3 LinearColor — 4× size-0 in `B_ControlPointScoring.uasset` → **(a)**

- File: inner tag `RawTeamColors/StructProperty/LinearColor size=64` = 4×16.
- UE source: `Engine/Source/Runtime/Core/Public/Math/Color.h:150`
  `friend FArchive& operator<<(FArchive& Ar, FLinearColor& Color)` — four
  floats (16 bytes).
- Same root cause and fix; the fast path (R/G/B/A) now runs.

### 2.4 Box — tag size 49 in chair + `FirstPersonC_Variant_Shooter_CubeBuilder_4` → **(d) parser defect**

- The fast path existed but mis-modeled the layout: it expected 28/52 and read
  `IsValid` as a 4-byte UBOOL (comment claimed "bool as 4-byte UBOOL,
  Archive.h").
- UE source: `Engine/Source/Runtime/Core/Public/Math/Box.h:45` declares
  `uint8 IsValid;` and `Box.h:666-668` `operator<<` writes
  `Ar << Box.Min << Box.Max << Box.IsValid` — **no padding, 1-byte IsValid**:
  float box = 12+12+1 = **25**, double box = 24+24+1 = **49**.
- Peer corroboration (CUE4Parse, by name): `FBox.cs` `IsValid = Ar.Read<byte>()`
  with `Pack=1` layout — reads a byte for every UE4/UE5 version it supports.
- Byte proof: chair `ElemBox` payload 13741..13790 decodes as 6×float64
  `(-41.944, -40.452, -0.5, 40.212, 40.451, 115.344)` + trailing `01` — exactly
  the chair's bounds (`ExtendedBounds` origin -0.866 ± extent 41.08/40.46/57.68),
  and `IsValid=1`.
- Corpus scan (all 67 samples): the only Box tags present are two 49-byte ones;
  no 28/52 tag exists in the corpus, so the 4-byte-IsValid interpretation had no
  evidence behind it. Fix: LWC pair `(28,52)` → `(25,49)`; fast path selects
  f64 for 49 and reads `u8` IsValid.

### 2.5 Transform — 235/162 ×6 (chair, Lyra, CubeBuilder) → **(a) legal inline/native layout we mis-handle**

- The bytes are a genuine `SerializeTaggedProperties` stream, verified
  byte-by-byte: chair payload 13839..14074 = `Rotation` tag (header 49 + 32-byte
  `Quat3d` payload) + `Translation` tag (header 49 + 24) + `Scale3D` tag
  (header 49 + 24) + 8-byte `None` terminator = 81+73+73+8 = **235**; Lyra's
  **162** = Rotation + Translation + None (Scale3D omitted on save, default
  filled on load). Inner payloads decode as the identity transform
  (quaternion 0,0,0,1; translation 0,0,0; scale 1,1,1).
- UE source: `Engine/Source/Runtime/CoreUObject/Private/UObject/PropertyStruct.cpp:508-511`
  — for `NAME_Transform` the engine itself calls
  `Struct->SerializeTaggedProperties(Slot, DestAddress, Struct, nullptr)` with
  the comment "Special case for Transform, as the f/d variants are immutable …",
  gated on `(StructFlags & STRUCT_SerializeNative) == 0`. The generic decision
  tree is `UScriptStruct::SerializeItem`
  (`Engine/Source/Runtime/CoreUObject/Private/UObject/Class.cpp:3350-3420`):
  native (`STRUCT_SerializeNative`, set only when the C++ struct ops declare a
  serializer, `Class.cpp:3177-3181`) → binary → else `SerializeTaggedProperties`
  (`Class.cpp:1476`, `:1577`). Member tags themselves are explained by
  `FKConvexElem`'s reflected members
  (`Engine/Source/Runtime/Engine/Classes/PhysicsEngine/ConvexElem.h:30-49`:
  `UPROPERTY TArray<FVector> VertexData`, `UPROPERTY TArray<int32> IndexData`,
  `UPROPERTY FBox ElemBox`, `UPROPERTY FTransform Transform`).
  FTransform's own `operator<<` exists for the native path
  (`Engine/Source/Runtime/Core/Public/Math/TransformVectorized.h:665-678`,
  Rotation/Translation/Scale3D) and the 40/80 fast path keeps serving it.
  [INFERENCE] The exact UHT property registration of `TTransform` in this
  checkout was not located (native `.gen.cpp` outputs are build-time
  artifacts); the write layout is proven from the sample bytes plus the
  engine call site above.
- Peer corroboration (CUE4Parse, by name): `FTransform.cs` carries
  `[StructFallback]` and a `FTransform(FStructFallback data)` constructor
  reading `Rotation`/`Translation`/`Scale3D` by name.
- What we mis-handled: the pre-check emitted
  `TRANSFORM_SIZE_INVALID` / `reason=recovered_corruption` / `fallback=opaque_value`
  **before attempting** the tagged decode. The decode then succeeded, but the
  recovery-classified diagnostic still downgraded Lyra's
  `MovieSceneCameraCutSection_0/2` to `parse=partial` — a corruption claim for a
  perfectly legal layout. Fix: pre-check now skips the fast path silently
  (same as `_TAGGED_FALLBACK_STRUCTS`); `TRANSFORM_SIZE_INVALID` is deferred to
  the two opaque-outcome paths, so it fires only when both the native fast path
  and the tagged attempt failed (the handcrafted size=4 unit case still emits
  exactly one diagnostic).

### 2.6 BP_UnversionedTest `missing_mapping` row → **(c) uncovered variant (schema boundary), plus one (d) fixed**

- Without mappings: all five exports stay `UnversionedOpaque` with
  `PROPERTY_VALUE_READ_FAILED reason=schema_required` and `parse=partial`.
  That is the designed no-guessing behavior (`property_parser.py`
  `_handle_unversioned_properties`: "Unversioned package with no reliable
  mapping -> output opaque block, do not guess fields") — honest, no change.
- With `tests/samples/UnversionedTest.usmap` (contains schemas for
  `BP_UnversionedTest_C`, `UnversionedTestAsset`, `UnversionedTestStruct`, …):
  - `export:0 BP_UnversionedTest_C` resolved its schema key via
    `resolve_class_name(class_index)` to the **metaclass**
    (`'BlueprintGeneratedClass'`), missing its own schema which the usmap
    carries — a lookup defect (d). Fix: when the resolved name has no schema
    and the export's own name does, use the export's own name. Result:
    `parse=complete`, 2 properties decoded.
  - `export:1 Default__…` already decoded (25 properties) once mappings load.
  - `export:2/3/4` (`SceneComponent`, `SCS_Node`, `SimpleConstructionScript`)
    are **genuinely absent** from the fixture usmap (9 schemas, listed above)
    → stay honest `schema_required` / `parse=partial`. No fix possible without
    new fixture data; not upgraded to complete.

### 2.7 editor_only (b)

No fallback among the five types classified editor-only. The samples do carry
`EXPORT_TRAILING_BYTES_UNCONSUMED reason=editor_only` diagnostics (editor-only
trailing regions of K2Node/MetaData exports) — unrelated to these five struct
types and unchanged.

## 3. Behavior changes (before → after)

| Surface | Before | After |
|---|---|---|
| chair `AggGeom.ConvexElems[0]` | `KConvexElem` fields `{}` (opaque) | full decode: 16 `VertexData` vectors, `ElemBox` Min/Max/bIsValid, `Transform` |
| chair/other `ElemBox` | opaque | decoded (49-byte double layout) |
| B_Control `RawTeamColors` | 4 opaque | 4× LinearColor R/G/B/A |
| M_Wood `ReferencedTextureGuids` | 3 opaque/empty | 3× Guid A/B/C/D |
| Lyra `ChildPossessables[0]` ×2 | empty success / lost | Guid A/B/C/D |
| Lyra `MovieSceneCameraCutSection_0/2` | `parse=partial` + `TRANSFORM_SIZE_INVALID recovered_corruption` ×2 | `parse=complete`, no spurious diagnostic |
| Transform 235/162 | decoded + spurious corruption diagnostic | decoded, silent fast-path skip (DEBUG log only) |
| BP + usmap | export:0 partial (metaclass key miss) | export:0 complete; export:2-4 remain schema_required partial |

`TRANSFORM_SIZE_INVALID` still exists for genuine failures (deferred emission;
unit test in `tests/test_samples.py` keeps asserting it for an undecodable
size). Quality-baseline totals drop and are regenerated with
`tools/gen_quality_baseline.py`.

## 4. Out of scope / not changed

- 5.3+ (`ue5 >= 1012`) struct arrays have no legacy inner tag; element stride is
  derived from `(tag.size - 4) / count` with the same exact-native-size guard,
  but no tracked sample exercises this path (all corpus struct arrays are
  pre-5.3 legacy-inner-tag files) — guarded, not corpus-proven.
- `Box2D` (20 bytes, 4-byte flag fast path) untouched: no observed fallback in
  scope, no evidence gathered.
- `BoxSphereBounds` stays in `_TAGGED_FALLBACK_STRUCTS` (always tagged; its
  fast-path branch is pre-cleared by the tagged-set gate).
- No `docs/` in this worktree (fresh clone per AGENTS.md), so design-doc status
  was not re-verified; implemented behavior was read from `src/`/`tests/`.
