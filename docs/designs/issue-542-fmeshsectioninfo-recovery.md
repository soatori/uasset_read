# FMeshSectionInfo Recovery Design

> Issue #542 — Document UE source evidence for `FMeshSectionInfo` struct layout and `FMeshSectionInfoMap` serialization

## Goal

Record the authoritative UE source definition of `FMeshSectionInfo` and its containing map `FMeshSectionInfoMap`, including the serialization version threshold that governs whether the map is serialized via legacy binary format or UE's automatic UProperty serialization. This evidence supports the implementation task of recovering all fields in `MeshSectionInfoMap` values.

## FMeshSectionInfo Struct Layout

**Source:** `Engine/Source/Runtime/Engine/Classes/Engine/StaticMesh.h:344`

```cpp
USTRUCT()
struct FMeshSectionInfo
{
    GENERATED_USTRUCT_BODY()

    /** Index in to the Materials array on UStaticMesh. */
    UPROPERTY()
    int32 MaterialIndex;

    /** If true, collision is enabled for this section. */
    UPROPERTY()
    bool bEnableCollision;

    /** If true, this section will cast shadows. */
    UPROPERTY()
    bool bCastShadow;

    /** If true, this section will be visible in ray tracing Geometry. */
    UPROPERTY()
    bool bVisibleInRayTracing;

    /** If true, this section will affect lighting methods that use Distance Fields. */
    UPROPERTY()
    bool bAffectDistanceFieldLighting;

    /** If true, this section will always considered opaque in ray tracing Geometry. */
    UPROPERTY()
    bool bForceOpaque;
};
```

### Field Summary

| Field | Type | Default | Description |
|---|---|---|---|
| `MaterialIndex` | `int32` | `0` | Index into the Materials array on UStaticMesh |
| `bEnableCollision` | `bool` | `true` | Whether collision is enabled for this section |
| `bCastShadow` | `bool` | `true` | Whether this section casts shadows |
| `bVisibleInRayTracing` | `bool` | `true` | Whether this section is visible in ray tracing |
| `bAffectDistanceFieldLighting` | `bool` | `true` | Whether this section affects Distance Field lighting |
| `bForceOpaque` | `bool` | `false` | Whether this section is always considered opaque in ray tracing |

### Default Constructor

The default constructor initializes all boolean fields to `true` except `bForceOpaque` which defaults to `false`. An explicit constructor also exists that accepts an `int32 InMaterialIndex` parameter while keeping the same boolean defaults.

## FMeshSectionInfoMap Definition

**Source:** `Engine/Source/Runtime/Engine/Classes/Engine/StaticMesh.h:403`

```cpp
USTRUCT()
struct FMeshSectionInfoMap
{
    GENERATED_USTRUCT_BODY()

    /** Maps an LOD+Section to the material it should render with. */
    UPROPERTY()
    TMap<uint32, FMeshSectionInfo> Map;
};
```

### Key Encoding

The map key is a `uint32` computed from LOD index and section index:

```cpp
// Engine/Source/Runtime/Engine/Private/StaticMesh.cpp:6488
static uint32 GetMeshMaterialKey(int32 LODIndex, int32 SectionIndex)
{
    return ((LODIndex & 0xffff) << 16) | (SectionIndex & 0xffff);
}
```

The high 16 bits store the LOD index; the low 16 bits store the section index.

### Methods

| Method | Signature | Description |
|---|---|---|
| `Clear()` | `void Clear()` | Empties the map |
| `GetSectionNumber()` | `int32 GetSectionNumber(int32 LODIndex) const` | Returns the number of sections for a given LOD |
| `IsValidSection()` | `bool IsValidSection(int32 LODIndex, int32 SectionIndex) const` | Returns whether a given LOD+Section entry exists |
| `Get()` | `FMeshSectionInfo Get(int32 LODIndex, int32 SectionIndex) const` | Retrieves per-section settings; returns default `FMeshSectionInfo(SectionIndex)` if not found |
| `Set()` | `void Set(int32 LODIndex, int32 SectionIndex, FMeshSectionInfo Info)` | Sets per-section settings for a given LOD+Section |
| `Remove()` | `void Remove(int32 LODIndex, int32 SectionIndex)` | Removes the entry for a given LOD+Section |
| `CopyFrom()` | `void CopyFrom(const FMeshSectionInfoMap& Other)` | Copies all entries from another map |
| `AnySectionHasCollision()` | `bool AnySectionHasCollision(int32 LodIndex) const` | Returns true if any section in the given LOD has `bEnableCollision` set |

## Serialization

### Legacy Binary Path (pre-UE 4.15)

**Source:** `Engine/Source/Runtime/Engine/Private/StaticMesh.cpp:6567`

When the package version is **below** the `UPropertryForMeshSectionSerialize` threshold in both release and editor object versions, the map uses a manual binary serialization:

```cpp
FArchive& operator<<(FArchive& Ar, FMeshSectionInfo& Info)
{
    Ar << Info.MaterialIndex;
    Ar << Info.bEnableCollision;
    Ar << Info.bCastShadow;
    return Ar;
}
```

The legacy binary format serializes only three fields: `MaterialIndex`, `bEnableCollision`, `bCastShadow`. The remaining three fields (`bVisibleInRayTracing`, `bAffectDistanceFieldLighting`, `bForceOpaque`) are **not serialized** in the legacy path -- they simply hold their default constructor values.

### UProperty Path (post-UE 4.15)

When the version **meets or exceeds** the threshold, `FMeshSectionInfoMap::Serialize` is a no-op (the method body is gated by the version check). Instead, UE's UProperty reflection system automatically serializes the `TMap<uint32, FMeshSectionInfo> Map` member as a UPROPERTY, which means all six fields of `FMeshSectionInfo` are serialized through the standard property serialization pipeline.

**Threshold check** (`StaticMesh.cpp:6580`):

```cpp
void FMeshSectionInfoMap::Serialize(FArchive& Ar)
{
    Ar.UsingCustomVersion(FReleaseObjectVersion::GUID);
    Ar.UsingCustomVersion(FEditorObjectVersion::GUID);

    if ( Ar.CustomVer(FReleaseObjectVersion::GUID) < FReleaseObjectVersion::UPropertryForMeshSectionSerialize
        && Ar.CustomVer(FEditorObjectVersion::GUID) < FEditorObjectVersion::UPropertryForMeshSectionSerialize)
    {
        Ar << Map;
    }
}
```

The condition uses **AND** -- the legacy path fires only when **both** custom versions are below the threshold.

### Version Thresholds

| Enum | Entry | Comment |
|---|---|---|
| `FReleaseObjectVersion` | `UPropertryForMeshSectionSerialize` | Release version, corresponding to UE 4.15 |
| `FEditorObjectVersion` | `UPropertryForMeshSectionSerialize` | Editor version, same semantic threshold |
| `FEditorObjectVersion` | `UPropertryForMeshSection` | Earlier version that gates the initial `SectionInfoMap` UProperty on `UStaticMesh` |

**Source:** `Engine/Source/Runtime/Core/Public/UObject/ReleaseObjectVersion.h:30`, `EditorObjectVersion.h:33,43`

## Instances on UStaticMesh

**Source:** `Engine/Source/Runtime/Engine/Classes/Engine/StaticMesh.h:672-687`

Two `FMeshSectionInfoMap` members exist on `UStaticMesh`:

### SectionInfoMap (line 675)

```cpp
UE_DEPRECATED(5.0, "This must be protected for async build, always use the accessors even internally.")
UPROPERTY()
FMeshSectionInfoMap SectionInfoMap;
```

Primary map of LOD+Section index to per-section info. Deprecated for direct access in UE 5.0 in favor of `GetSectionInfoMap()` / `GetSectionInfoMap() const` accessors. Serialized on `UStaticMesh` at line 7487-7490 for pre-UE5 packages that use the old serialization path.

### OriginalSectionInfoMap (line 687)

```cpp
UE_DEPRECATED(5.0, "This must be protected for async build, always use the accessors even internally.")
UPROPERTY()
FMeshSectionInfoMap OriginalSectionInfoMap;
```

Preserves the original section info map for non-destructive mesh building. Used by the mesh reduction pipeline. Updated only on import/reimport or postload (when the map is empty). Accessible via `GetOriginalSectionInfoMap()` / `GetOriginalSectionInfoMap() const`.

## Implications for uasset_read

1. **Pre-UE4.15 assets:** The legacy binary path serializes only `MaterialIndex`, `bEnableCollision`, `bCastShadow`. The remaining three fields (`bVisibleInRayTracing`, `bAffectDistanceFieldLighting`, `bForceOpaque`) are absent from the serialized data and must be reconstructed from defaults.

2. **Post-UE4.15 assets:** All six fields are serialized through UProperty reflection. The full struct can be reconstructed from the serialized property data.

3. **Key decoding:** The `uint32` key encodes `LODIndex` in the upper 16 bits and `SectionIndex` in the lower 16 bits. Both maps (`SectionInfoMap` and `OriginalSectionInfoMap`) use the same encoding.

4. **Dual maps:** Both maps may be present in editor-saved assets. `OriginalSectionInfoMap` is typically populated from `SectionInfoMap` during postload if empty.
