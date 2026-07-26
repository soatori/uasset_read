"""USkeleton Asset type handler

Parse USkeleton custom serialization data:
- ReferenceSkeleton (reference skeleton)
  - Names: TArray<FName>
  - Parents: TArray<int32>
  - RefLocalPose: TArray<FTransform>
    - UE4: 40 bytes (Rotation 16 + Translation 12 + Scale 12)
    - UE5: 52 bytes (Rotation 16 + Translation 24 + Scale 12)
  - NameToIndexMap: TMap<FName, int32>
- RetargetSources: TMap<FName, FReferencePose>
- VirtualBoneGuid: FGuid (16 bytes)

UPROPERTY section (BoneTree, VirtualBones, SlotGroups, Sockets etc.)
Automatically handled by property parser.

Format reference:
- Engine/Source/Runtime/Engine/Classes/Animation/Skeleton.h
- Engine/Source/Runtime/Engine/Private/Animation/Skeleton.cpp
- Engine/Source/Runtime/Engine/Public/ReferenceSkeleton.h
"""

import logging
import struct
from typing import Any, Dict, List

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)

# Safety limit: prevent garbage bytes from being interpreted as counts
_MAX_SKELETON_COUNT = 100000

# FGuid serialization size (bytes)
FGUID_SIZE = 16


def parse_skeleton(archive: Any, name_map: List[str]) -> Dict[str, Any]:
    """Parse USkeleton asset custom serialization data.

    Handler called after property parsing, archive positioned at export serial_offset.
    Property parser already handled BoneTree/VirtualBoneGuid/VirtualBones/SlotGroups/Sockets and other UPROPERTYs.
    This handler is responsible for:
    1. Skip already-parsed tagged properties (by reading PropertyTag until Name=="None")
    2. Parse custom serialization data (ReferenceSkeleton, RetargetSources, Guid)

    Args:
        archive: FArchive instance (positioned at serial_offset)
        name_map: Name table

    Returns:
        Parse result dictionary, containing reference_skeleton, retarget_sources, guid etc.
    """
    result: Dict[str, Any] = {
        "parse_status": "success",
    }

    # Collect truncation diagnostics: append when sub-functions encounter illegal count, then upgrade parse_status
    _diagnostics: List[str] = []

    try:
        # Step 1: skip tagged properties
        # PropertyTag serialization format:
        #   Name: FName (index + number)
        #   If Name == "None" (index=0), Property list ends
        #   Otherwise continue reading TypeName, Size, ArrayIndex etc. fields and value data
        _skip_tagged_properties(archive, name_map)

        # Step 2: Parse ReferenceSkeleton (custom serialization, not UPROPERTY)
        ref_skeleton = _read_reference_skeleton(archive, name_map, _diagnostics)
        result["reference_skeleton"] = ref_skeleton

        # Step 3: Parse RetargetSources: TMap<FName, FReferencePose>
        retarget_sources = _read_retarget_sources(archive, name_map, _diagnostics)
        result["retarget_sources"] = retarget_sources
        result["retarget_source_count"] = len(retarget_sources)

        # Step 4: Parse Guid: FGuid (16 bytes)
        # Guid serialized after UE4 >= VER_UE4_SKELETON_GUID_SERIALIZATION
        if archive.check_remaining(FGUID_SIZE, "Skeleton.Guid"):
            guid_bytes = archive.read_bytes(FGUID_SIZE, "Skeleton.Guid")
            result["guid"] = _format_guid(guid_bytes)

    except (struct.error, OSError, ValueError, ParseError) as e:
        logger.debug("skeleton handler parse failed: %s", e)
        # When class_index erroneously points to Skeleton but actual data is another type (e.g. SkeletalMesh),
        # handler failing to parse is expected behavior, mark as opaque rather than failed,
        # to avoid the entire package being judged as failed (Issue #321)
        result["parse_status"] = "opaque"
        result["error"] = str(e)

    # When count is illegal, mark as partial with diagnostics
    if _diagnostics:
        result["parse_status"] = "partial"
        result["diagnostics"] = _diagnostics

    return result


def _skip_tagged_properties(archive: Any, name_map: List[str]) -> None:
    """Skip tagged properties until encountering Name=="None" terminator.

    PropertyTag serialization format (refer to UE FPropertyTag::Serialize):
    1. Name: FName (index: i32 + number: i32)
    2. If Name == "None" (index == 0), stop
    3. Otherwise read the complete PropertyTag:
       - TypeName: FName
       - Size: i32
       - ArrayIndex: i32
       - BoolVal: u8 (if TypeName is BoolProperty)
       - EnumName: FName (if TypeName is EnumProperty or ByteProperty)
       - StructName: FName (if TypeName is StructProperty)
       - InnerTypeName: FName (if TypeName is ArrayProperty or SetProperty)
       - KeyType + ValueType: 2 x FName (if TypeName is MapProperty)
       - And other version-dependent fields
    4. Then skip the Value data (Size bytes)

    Reference: Engine/Source/Runtime/CoreUObject/Private/UObject/Class.cpp
    FPropertyTag::Serialize
    """
    max_properties = 10000  # Safety limit
    for _ in range(max_properties):
        current_pos = archive.tell()
        remaining = archive.total_size() - current_pos
        if remaining < 8:
            # Less than one FName, treat as end
            break

        # Read PropertyTag.Name
        name_index = archive.read_i32()
        _name_number = archive.read_i32()  # noqa: F841 - protocol read

        if name_index == 0:
            # Name == "None", Property list ends
            break

        # Read TypeName
        type_index = archive.read_i32()
        _type_number = archive.read_i32()  # noqa: F841 - protocol read

        # Parse type name (to determine if extra fields need skipping)
        type_name = ""
        if 0 <= type_index < len(name_map):
            type_name = name_map[type_index]

        # Read Size: i32
        tag_size = archive.read_i32()

        # Read ArrayIndex: i32
        archive.read_i32()

        # BoolVal: u8 (BoolProperty only)
        if type_name == "BoolProperty":
            archive.read_u8()

        # EnumName: FName (ByteProperty or EnumProperty)
        if type_name in ("ByteProperty", "EnumProperty"):
            archive.read_i32()  # index
            archive.read_i32()  # number

        # StructName: FName (StructProperty)
        if type_name == "StructProperty":
            archive.read_i32()  # index
            archive.read_i32()  # number

        # InnerTypeName: FName (ArrayProperty or SetProperty)
        # Reference: FPropertyTag::Serialize: InnerType.Serialize(Ar)
        if type_name in ("ArrayProperty", "SetProperty"):
            archive.read_i32()  # index
            archive.read_i32()  # number

        # KeyTypeName + ValueTypeName: 2 x FName (MapProperty)
        # Reference: FPropertyTag::Serialize: KeyType.Serialize(Ar) + ValueType.Serialize(Ar)
        if type_name == "MapProperty":
            archive.read_i32()  # key type index
            archive.read_i32()  # key type number
            archive.read_i32()  # value type index
            archive.read_i32()  # value type number

        # Guid (PropertyGuid): bool(i32) + optional FGuid(16)
        has_guid = archive.read_i32()
        if has_guid != 0:
            archive.read_bytes(16)

        # Skip Value data
        if tag_size > 0:
            remaining_after_tag = archive.total_size() - archive.tell()
            if tag_size <= remaining_after_tag:
                archive.seek(archive.tell() + tag_size)
            else:
                # Data truncated, jump to end
                archive.seek(archive.total_size())
                break


def _read_reference_skeleton(
    archive: Any, name_map: List[str], _diagnostics: List[str] | None = None,
) -> Dict[str, Any]:
    """Read FReferenceSkeleton custom serialization.

    FReferenceSkeleton serialization format (ReferenceSkeleton.cpp:941):
    1. RawRefBoneInfo: TArray<FMeshBoneInfo>
       - FMeshBoneInfo: FName (8 bytes) + int32 ParentIndex
    2. RawRefBonePose: TArray<FTransform>
       - Each FTransform: Translation(FVector3d: 3*8=24) + Rotation(FQuat4f: 4*4=16) + Scale(FVector3f: 3*4=12) = 52 bytes
       Note: FTransform is not bulk-serialized, actual layout depends on UE version
    3. RawNameToIndexMap: TMap<FName, int32>

    Args:
        _diagnostics: Optional diagnostic collection list, append entries when truncating illegal counts

    Returns:
        Dictionary containing names, parents, transforms
    """
    ref_skeleton: Dict[str, Any] = {}

    # Read BoneInfo count (TArray count)
    bone_count = archive.read_i32("RefSkel.BoneCount")

    if bone_count < 0 or bone_count > 10000:
        logger.debug(
            "ReferenceSkeleton: abnormal bone count %d, skipping parse",
            bone_count,
        )
        return {"bone_count": bone_count, "error": "invalid bone count"}

    # Read BoneInfo array
    names: List[str] = []
    parents: List[int] = []
    for i in range(bone_count):
        # FName: Index (int32) + Number (int32)
        name_index = archive.read_i32(f"RefSkel.BoneInfo[{i}].Name.Index")
        name_number = archive.read_i32(f"RefSkel.BoneInfo[{i}].Name.Number")

        # Parse name
        bone_name = _resolve_fname(name_index, name_number, name_map)

        # ParentIndex: int32 (INDEX_NONE = -1 indicates root bone)
        parent_index = archive.read_i32(f"RefSkel.BoneInfo[{i}].ParentIndex")

        names.append(bone_name)
        parents.append(parent_index)

    ref_skeleton["names"] = names
    ref_skeleton["parents"] = parents
    ref_skeleton["bone_count"] = bone_count

    # Read BonePose array (TArray<FTransform>)
    pose_count = archive.read_i32("RefSkel.PoseCount")
    if pose_count < 0 or pose_count > _MAX_SKELETON_COUNT:
        logger.debug(
            "ReferenceSkeleton: abnormal PoseCount %d (bone_count=%d), truncated to 0",
            pose_count, bone_count,
        )
        if _diagnostics is not None:
            _diagnostics.append(
                f"ReferenceSkeleton.PoseCount truncated: {pose_count} -> 0"
            )
        pose_count = 0
    if pose_count != bone_count:
        logger.debug(
            "ReferenceSkeleton: PoseCount(%d) != BoneCount(%d)",
            pose_count, bone_count,
        )

    transforms: List[Dict[str, Any]] = []
    is_ue5 = getattr(archive, '_file_version_ue5', 0) > 0
    for i in range(min(pose_count, bone_count)):
        transform = _read_ftransform(archive, is_ue5=is_ue5)
        transforms.append(transform)

    ref_skeleton["transforms"] = transforms
    ref_skeleton["pose_count"] = pose_count

    # Read NameToIndexMap: TMap<FName, int32>
    # TMap serialized as count + entries, each entry = Key(FName) + Value(int32)
    map_count = archive.read_i32("RefSkel.NameToIndexMap.Count")
    if map_count < 0 or map_count > _MAX_SKELETON_COUNT:
        logger.debug(
            "ReferenceSkeleton: abnormal NameToIndexMap.Count %d, skipping parse",
            map_count,
        )
        if _diagnostics is not None:
            _diagnostics.append(
                f"ReferenceSkeleton.NameToIndexMap.Count truncated: {map_count} -> 0"
            )
        map_count = 0
    name_to_index: Dict[str, int] = {}
    for _ in range(map_count):
        key_index = archive.read_i32("RefSkel.NameToIndexMap.Key.Index")
        key_number = archive.read_i32("RefSkel.NameToIndexMap.Key.Number")
        value = archive.read_i32("RefSkel.NameToIndexMap.Value")

        key_name = _resolve_fname(key_index, key_number, name_map)
        name_to_index[key_name] = value

    ref_skeleton["name_to_index"] = name_to_index

    return ref_skeleton


def _read_retarget_sources(
    archive: Any, name_map: List[str], _diagnostics: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """Read RetargetSources: TMap<FName, FReferencePose>.

    Format (Skeleton.cpp:419-448):
    1. int32 NumOfRetargetSources
    2. Each source:
       - FName RetargetSourceName
       - SerializeReferencePose:
         - FName PoseName
         - TArray<FTransform> ReferencePose
         - FSoftObjectPath SourceReferenceMesh (editor only, serialized when not cooking)

    Returns:
        RetargetSource list
    """
    sources: List[Dict[str, Any]] = []
    is_ue5 = getattr(archive, '_file_version_ue5', 0) > 0

    num_sources = archive.read_i32("RetargetSources.Count")
    if num_sources < 0 or num_sources > 1000:
        logger.debug(
            "RetargetSources: abnormal source count %d, skipping parse",
            num_sources,
        )
        return sources

    for i in range(num_sources):
        source: Dict[str, Any] = {}

        # RetargetSourceName: FName
        name_index = archive.read_i32(f"RetargetSources[{i}].Name.Index")
        name_number = archive.read_i32(f"RetargetSources[{i}].Name.Number")
        source["name"] = _resolve_fname(name_index, name_number, name_map)

        # SerializeReferencePose:
        # 1. PoseName: FName
        pose_name_index = archive.read_i32(f"RetargetSources[{i}].PoseName.Index")
        pose_name_number = archive.read_i32(f"RetargetSources[{i}].PoseName.Number")
        source["pose_name"] = _resolve_fname(pose_name_index, pose_name_number, name_map)

        # 2. ReferencePose: TArray<FTransform>
        pose_count = archive.read_i32(f"RetargetSources[{i}].PoseCount")
        if pose_count < 0 or pose_count > _MAX_SKELETON_COUNT:
            logger.debug(
                "RetargetSources[%d]: abnormal PoseCount %d, truncated to 0",
                i, pose_count,
            )
            if _diagnostics is not None:
                _diagnostics.append(
                    f"RetargetSources[{i}].PoseCount truncated: {pose_count} -> 0"
                )
            pose_count = 0
        transforms: List[Dict[str, Any]] = []
        for _ in range(pose_count):
            transform = _read_ftransform(archive, is_ue5=is_ue5)
            transforms.append(transform)
        source["transforms"] = transforms
        source["transform_count"] = len(transforms)

        # 3. SourceReferenceMesh: FSoftObjectPath (editor only)
        # FSoftObjectPath serialized as FTopLevelAssetPath: PackageName(FName) + AssetName(FName)
        pkg_index = archive.read_i32(f"RetargetSources[{i}].SourceMesh.Pkg.Index")
        pkg_number = archive.read_i32(f"RetargetSources[{i}].SourceMesh.Pkg.Number")
        asset_index = archive.read_i32(f"RetargetSources[{i}].SourceMesh.Asset.Index")
        asset_number = archive.read_i32(f"RetargetSources[{i}].SourceMesh.Asset.Number")

        pkg_name = _resolve_fname(pkg_index, pkg_number, name_map)
        asset_name = _resolve_fname(asset_index, asset_number, name_map)
        if pkg_name and asset_name:
            source["source_mesh"] = f"{pkg_name}/{asset_name}"
        else:
            source["source_mesh"] = None

        sources.append(source)

    return sources


def _read_ftransform(archive: Any, is_ue5: bool = True) -> Dict[str, Any]:
    """Read FTransform, supports UE4/UE5 different layouts.

    Serialization order (refer to TransformVectorized.h operator<<):
    Rotation -> Translation -> Scale3D

    UE4 layout (40 bytes):
    - Rotation: FQuat4f (4 x f32 = 16 bytes)
    - Translation: FVector (3 x f32 = 12 bytes)
    - Scale3D: FVector (3 x f32 = 12 bytes)

    UE5 layout (52 bytes):
    - Rotation: FQuat4f (4 x f32 = 16 bytes)
    - Translation: FVector3d (3 x f64 = 24 bytes)
    - Scale3D: FVector3f (3 x f32 = 12 bytes)

    Args:
        archive: FArchive instance
        is_ue5: True for UE5 layout (default), False for UE4 layout
    """
    # Rotation: FQuat4f (4 x f32 = 16 bytes) -- same for UE4/UE5
    rx = archive.read_f32("Transform.Rotation.X")
    ry = archive.read_f32("Transform.Rotation.Y")
    rz = archive.read_f32("Transform.Rotation.Z")
    rw = archive.read_f32("Transform.Rotation.W")

    # Translation: FVector (UE4: 3 x f32 = 12 bytes) or FVector3d (UE5: 3 x f64 = 24 bytes)
    if is_ue5:
        tx = archive.read_f64("Transform.Translation.X")
        ty = archive.read_f64("Transform.Translation.Y")
        tz = archive.read_f64("Transform.Translation.Z")
    else:
        tx = archive.read_f32("Transform.Translation.X")
        ty = archive.read_f32("Transform.Translation.Y")
        tz = archive.read_f32("Transform.Translation.Z")

    # Scale3D: FVector3f (3 x f32 = 12 bytes) -- same for UE4/UE5
    sx = archive.read_f32("Transform.Scale.X")
    sy = archive.read_f32("Transform.Scale.Y")
    sz = archive.read_f32("Transform.Scale.Z")

    return {
        "translation": {"x": tx, "y": ty, "z": tz},
        "rotation": {"x": rx, "y": ry, "z": rz, "w": rw},
        "scale": {"x": sx, "y": sy, "z": sz},
    }


def _format_guid(guid_bytes: bytes) -> str:
    """Format 16-byte FGuid as string."""
    import struct
    if len(guid_bytes) < 16:
        return ""
    # FGuid serialization order: A(i32) B(i32) C(i32) D(i32)
    a, b, c, d = struct.unpack('<4I', guid_bytes[:16])
    return f"{a:08X}-{b:08X}-{c:08X}-{d:08X}"


def _resolve_fname(index: int, number: int, name_map: List[str]) -> str:
    """Parse FName (index + number) to string."""
    if 0 <= index < len(name_map):
        base_name = name_map[index]
        if number > 0:
            return f"{base_name}_{number}"
        return base_name
    return f"<invalid_index_{index}>"
