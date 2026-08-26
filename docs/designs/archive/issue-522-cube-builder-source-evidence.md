# Issue #522 — CubeBuilder Source Evidence List

> Status: accepted (2026-08-05); issue #522 closed
> Scope: version-pinned UE source evidence for every attribution claim used to
> close #522. All paths are relative to the engine checkout below; all line
> numbers were verified against that exact commit.

## Pinned UE version

| Item | Value |
|------|-------|
| Checkout | `E:/Develop/lib/UnrealEngine` |
| Commit | `7deeb413d3dc1fc034f48d1aacc0861301829d32` |
| Tag | `5.8.0-release` (branch `release`, grafted) |

## 1. Fields owned by CubeBuilder serialization

`UCubeBuilder` inherits `UEditorBrushBuilder` → `UBrushBuilder` → `UObject`.
The complete serialized UPROPERTY inventory of a `CubeBuilder` export:

### UCubeBuilder — `Engine/Source/Editor/UnrealEd/Classes/Builders/CubeBuilder.h:17-64`

| Field | Type | Line |
|-------|------|------|
| `X` | `float` | 27-28 |
| `Y` | `float` | 31-32 |
| `Z` | `float` | 35-36 |
| `WallThickness` | `float` | 39-40 |
| `GroupName` | `FName` | 42-43 |
| `Hollow` | `uint32:1` | 46-47 |
| `Tessellated` | `uint32:1` | 50-51 |

Constructor defaults — `Engine/Source/Editor/UnrealEd/Private/EditorBrushBuilder.cpp:395-418`:
`X = Y = Z = 200.0`, `WallThickness = 10.0`, `GroupName = "Cube"`,
`Hollow = false`, `Tessellated = false`, `BitmapFilename = "Btn_Box"`,
`ToolTip = "BrushBuilderName_Cube"`.

### UEditorBrushBuilder — `Engine/Source/Editor/UnrealEd/Classes/Builders/EditorBrushBuilder.h:13-40`

Adds **no** serialized UPROPERTYs; only interface overrides.

### UBrushBuilder — `Engine/Source/Runtime/Engine/Classes/Engine/BrushBuilder.h:51-80`

| Field | Type | Line | Serialized? |
|-------|------|------|-------------|
| `BitmapFilename` | `FString` | 57-58 | yes (delta) |
| `ToolTip` | `FString` | 61-62 | yes (delta) |
| `NotifyBadParams` | `uint32:1` | 65-66 | **never** — `UPROPERTY(Transient)` |
| `Vertices` | `TArray<FVector>` | 70-71 | yes (delta) |
| `Polys` | `TArray<FBuilderPoly>` | 73-74 | yes (delta) |
| `Layer` | `FName` | 76-77 | yes (delta) |
| `MergeCoplanars` | `uint32:1` | 79-80 | yes (delta) |

### FBuilderPoly — `Engine/Source/Runtime/Engine/Classes/Engine/BrushBuilder.h:13-33`

Exactly four UPROPERTYs, in serialization order:

1. `VertexIndices` — `TArray<int32>` (line 18-19)
2. `Direction` — `int32` (line 21-22)
3. `ItemName` — `FName` (line 24-25)
4. `PolyFlags` — `int32` (line 27-28)

**No material field exists on `FBuilderPoly`.**

### Why CubeBuilder exports exist only in editor-saved maps

`ABrush::BrushBuilder` is `UPROPERTY(VisibleAnywhere, Instanced)` inside
`WITH_EDITORONLY_DATA` — `Engine/Source/Runtime/Engine/Classes/Engine/Brush.h:114-116`.
The builder is an instanced editor-only subobject of the brush actor; baked
content has it stripped.

## 2. Fields NOT owned by CubeBuilder (attribution chains)

### Material → `FBspSurf.Material` on `UModel`

- `FBspSurf::Material` — `TObjectPtr<UMaterialInterface>`,
  `Engine/Source/Runtime/Engine/Public/Model.h:215`.
- Linked back to the editor polygon via `FBspSurf::iBrushPoly`
  (`Model.h:221`) and owning actor via `FBspSurf::Actor` (`Model.h:223`).
- The `FBspSurf` array lives in `UModel`; `ABrush` holds it as
  `UPROPERTY(Instanced) TObjectPtr<UModel> Brush`
  (`Engine/Source/Runtime/Engine/Classes/Engine/Brush.h:106-107`).

### Collision → `UBrushComponent.BrushBodySetup`

- `UBrushComponent::BrushBodySetup` — `TObjectPtr<UBodySetup>`,
  `Engine/Source/Runtime/Engine/Classes/Components/BrushComponent.h:30`
  (class declaration line 21, `GetBodySetup()` line 56).
- `ABrush::BrushComponent` — `Brush.h:110-111`.

### LOD → StaticMesh build system

- LODs live in `UStaticMesh::RenderData`
  (`TUniquePtr<FStaticMeshRenderData>`, which owns
  `FStaticMeshLODResources`) —
  `Engine/Source/Runtime/Engine/Classes/Engine/StaticMesh.h:602` (class),
  `633` (RenderData member).
- Neither `UCubeBuilder`, `UEditorBrushBuilder`, nor `UBrushBuilder` declares
  any LOD-related UPROPERTY (full headers verified, see §1).

### Transform → ABrush actor (AActor/USceneComponent), not the builder

- `ABrush : AActor` — `Brush.h:75-77`.
- Transform is serialized on `USceneComponent`:
  `RelativeLocation` / `RelativeRotation` / `RelativeScale3D` —
  `Engine/Source/Runtime/Engine/Classes/Components/SceneComponent.h:139-150`,
  reached through the actor's root component.
- `UCubeBuilder` declares no transform UPROPERTY (full header verified).
- Note: cube builder *vertices* span `±X/2, ±Y/2, ±Z/2` around the builder
  origin, so the actor transform and the builder dimensions compose; the
  builder parameters cannot be recovered from a vertex bounding box in the
  general case (hollow, tessellated, scaled, or non-centered builds).

## 3. Serialization semantics: archetype-delta skipping

Tagged property save skips any property identical to the archetype (CDO)
value:

- `UStruct::SerializeVersionedTaggedProperties` save path —
  `Engine/Source/Runtime/CoreUObject/Private/UObject/Class.cpp:1992`
  (`bDoDeltaSerialization = Ar.DoDelta() && !Ar.IsTransacting() && (Defaults || bIsUClass)`)
  and `Class.cpp:2018`
  (`bSerializeValue = … !Property->Identical(DataPtr, DefaultValue, …)`).

Consequences observed in fixtures:

- Default-valued `X`/`Y`/`Z` (200.0) are absent from the tag stream.
- `BitmapFilename`/`ToolTip` are absent even though non-empty, because they
  equal their CDO defaults (`"Btn_Box"`, `"BrushBuilderName_Cube"`).
- `NotifyBadParams` is never serialized (`Transient`).

No native payload exists after the tagged properties: no class in the
builder chain overrides `Serialize` (`BrushBuilder.h`, `EditorBrushBuilder.h`,
`CubeBuilder.h` declarations and `EditorBrushBuilder.cpp` verified).

## 4. Adjudication of the 4-byte tail

Facts:

1. In the reference fixture (`CubeBuilder_3`,
   `tests/samples/FirstPerson_Lvl_FirstPerson.umap`) the property list ends
   with the `None` FName terminator (name index 58) at absolute offset 9158;
   the terminator consumes 8 bytes and the export's serial data ends at 9170,
   leaving a 4-byte tail `[9166, 9170)` = `00 00 00 00`.
2. Corpus-wide scan (`tests/temp/scan_cube_builder_tails.py`, report in
   `temp/issue522_cube_builder_tail_report.json`): **964 / 964** CubeBuilder
   exports across 936 packages have exactly a 4-byte all-zero tail. Zero
   parse failures.
3. The same zero tail appears after the `None` terminator of unrelated
   classes in the same package (BookMark, ContentBundleManager,
   NavigationSystemConfig, WorldThumbnailInfo, …), while classes with real
   native payloads (Level, Model, World) carry larger, content-bearing tails.
4. No class in the CubeBuilder chain overrides `Serialize` (§3), so nothing
   class-semantic can be written after the terminator.

Verdict: the 4 bytes are a **writer-side version residual / alignment
artifact, not CubeBuilder data**. They are universal, all-zero, and
unexplained by any `CubeBuilder`/`UBrushBuilder` serialization code. They
must not be interpreted as fields; the parser keeps exposing them as
`tail_offset` / `tail_size` and keeps `parse_status: partial_metadata` until
a future UE-source trace proves the writer that emits them.

## 5. Corpus recount (replaces the unverifiable "350 files")

Scan script: `tests/temp/scan_cube_builder_corpus.py` (byte scan) +
`tests/temp/scan_cube_builder_tails.py` (parse verification).

| Metric | Value |
|--------|-------|
| Corpus root | `E:\Develop\lib\Samples` (107 GB) |
| `.uasset`/`.umap` files scanned | 238,602 |
| Files containing the name `CubeBuilder` | 936 (50 `.umap`, 886 `.uasset`) |
| Packages with a `CubeBuilder` export (parse-verified) | 933 |
| `CubeBuilder` exports found | 964 |
| Exports with 4-byte zero tail | 964 / 964 |
| Exports serializing non-default dimensions (`X`/`Y`/`Z`/`WallThickness`) | 141 |

The original issue's "350 files" claim had no reproducible command and does
not match the current corpus; the table above is the reproducible recount.

## 6. Fixture ledger

| Fixture | SHA-256 | Role |
|---------|---------|------|
| `tests/samples/FirstPerson_Lvl_FirstPerson.umap` (`CubeBuilder_3`) | `3D476154…32D258` | baseline metadata + geometry contract; default dimensions (X/Y/Z absent) |
| `tests/samples/FirstPersonC_Variant_Shooter_CubeBuilder_4.uasset` (`CubeBuilder_4`) | `958456CB…53C80` | dimension acceptance: `X=2936.5227…`, `Y=3349.4956…`, `Z=682.7445…`; also contains `BrushComponent0`, `BodySetup_1`, `Model_2` demonstrating the §2 attribution chains in one package |

Source of the dimension fixture:
`E:\Develop\lib\Samples\FirstPersonC\Content\__ExternalActors__\Variant_Shooter\Lvl_Shooter\4\4A\VTCLSHIX2YXQ8FSREY3I5O.uasset`.
