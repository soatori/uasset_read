"""USkeleton 资产类型处理器

解析 USkeleton 的 custom serialization 数据：
- ReferenceSkeleton（参考骨架）
  - Names: TArray<FName>
  - Parents: TArray<int32>
  - RefLocalPose: TArray<FTransform>（每 transform 48 bytes）
  - NameToIndexMap: TMap<FName, int32>
- RetargetSources: TMap<FName, FReferencePose>
- VirtualBoneGuid: FGuid（16 bytes）

UPROPERTY 部分（BoneTree、VirtualBones、SlotGroups、Sockets 等）
由属性解析器自动处理。

格式参考：
- Engine/Source/Runtime/Engine/Classes/Animation/Skeleton.h
- Engine/Source/Runtime/Engine/Private/Animation/Skeleton.cpp
- Engine/Source/Runtime/Engine/Public/ReferenceSkeleton.h
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# FGuid 序列化大小（字节）
FGUID_SIZE = 16


def parse_skeleton(archive: Any, name_map: List[str]) -> Dict[str, Any]:
    """解析 USkeleton 资产的 custom serialization 数据。

    Handler 在属性解析完成后调用，archive 定位到 export 的 serial_offset。
    属性解析器已处理 BoneTree/VirtualBoneGuid/VirtualBones/SlotGroups/Sockets 等 UPROPERTY。
    此 handler 负责：
    1. 跳过已解析的 tagged properties（通过读取 PropertyTag 直到 Name=="None"）
    2. 解析 custom serialization 数据（ReferenceSkeleton、RetargetSources、Guid）

    Args:
        archive: FArchive 实例（定位到 serial_offset）
        name_map: 名称表

    Returns:
        解析结果字典，包含 reference_skeleton、retarget_sources、guid 等
    """
    result: Dict[str, Any] = {
        "parse_status": "success",
    }

    try:
        # 第一步：跳过 tagged properties
        # PropertyTag 序列化格式：
        #   Name: FName（index + number）
        #   如果 Name == "None"（index=0），属性列表结束
        #   否则继续读取 TypeName、Size、ArrayIndex 等字段和值数据
        _skip_tagged_properties(archive, name_map)

        # 第二步：解析 ReferenceSkeleton（custom serialization，非 UPROPERTY）
        ref_skeleton = _read_reference_skeleton(archive, name_map)
        result["reference_skeleton"] = ref_skeleton

        # 第三步：解析 RetargetSources: TMap<FName, FReferencePose>
        retarget_sources = _read_retarget_sources(archive, name_map)
        result["retarget_sources"] = retarget_sources
        result["retarget_source_count"] = len(retarget_sources)

        # 第四步：解析 Guid: FGuid（16 bytes）
        # Guid 在 UE4 >= VER_UE4_SKELETON_GUID_SERIALIZATION 后序列化
        if archive.check_remaining(FGUID_SIZE, "Skeleton.Guid"):
            guid_bytes = archive.read_bytes(FGUID_SIZE, "Skeleton.Guid")
            result["guid"] = _format_guid(guid_bytes)

    except Exception as e:
        logger.debug("skeleton handler 解析失败: %s", e)
        result["parse_status"] = "failed"
        result["error"] = str(e)

    return result


def _skip_tagged_properties(archive: Any, name_map: List[str]) -> None:
    """跳过 tagged properties 直到遇到 Name=="None" 终止标记。

    PropertyTag 序列化格式（参照 UE FPropertyTag::Serialize）：
    1. Name: FName (index: i32 + number: i32)
    2. 如果 Name == "None"（index == 0），停止
    3. 否则读取完整的 PropertyTag：
       - TypeName: FName
       - Size: i32
       - ArrayIndex: i32
       - BoolVal: u8（如果 TypeName 是 BoolProperty）
       - EnumName: FName（如果 TypeName 是 EnumProperty 或 ByteProperty）
       - StructName: FName（如果 TypeName 是 StructProperty）
       - 以及其他版本相关字段
    4. 然后跳过 Value 数据（Size 字节）
    """
    max_properties = 10000  # 安全上限
    for _ in range(max_properties):
        current_pos = archive.tell()
        remaining = archive.total_size() - current_pos
        if remaining < 8:
            # 不足一个 FName，视为结束
            break

        # 读取 PropertyTag.Name
        name_index = archive.read_i32()
        name_number = archive.read_i32()

        if name_index == 0:
            # Name == "None"，属性列表结束
            break

        # 读取 TypeName
        type_index = archive.read_i32()
        type_number = archive.read_i32()

        # 解析类型名（用于判断是否需要跳过额外字段）
        type_name = ""
        if 0 <= type_index < len(name_map):
            type_name = name_map[type_index]

        # 读取 Size: i32
        tag_size = archive.read_i32()

        # 读取 ArrayIndex: i32
        archive.read_i32()

        # BoolVal: u8（仅 BoolProperty）
        if type_name == "BoolProperty":
            archive.read_u8()

        # EnumName: FName（ByteProperty 或 EnumProperty）
        if type_name in ("ByteProperty", "EnumProperty"):
            archive.read_i32()  # index
            archive.read_i32()  # number

        # StructName: FName（StructProperty）
        if type_name == "StructProperty":
            archive.read_i32()  # index
            archive.read_i32()  # number

        # Guid（PropertyGuid）: bool(i32) + optional FGuid(16)
        has_guid = archive.read_i32()
        if has_guid != 0:
            archive.read_bytes(16)

        # 跳过 Value 数据
        if tag_size > 0:
            remaining_after_tag = archive.total_size() - archive.tell()
            if tag_size <= remaining_after_tag:
                archive.seek(archive.tell() + tag_size)
            else:
                # 数据截断，跳到末尾
                archive.seek(archive.total_size())
                break


def _read_reference_skeleton(archive: Any, name_map: List[str]) -> Dict[str, Any]:
    """读取 FReferenceSkeleton custom serialization。

    FReferenceSkeleton 序列化格式（ReferenceSkeleton.cpp:941）：
    1. RawRefBoneInfo: TArray<FMeshBoneInfo>
       - FMeshBoneInfo: FName (8 bytes) + int32 ParentIndex
    2. RawRefBonePose: TArray<FTransform>
       - 每个 FTransform: Translation(FVector3d: 3*8=24) + Rotation(FQuat4f: 4*4=16) + Scale(FVector3f: 3*4=12) = 52 bytes
       注意：FTransform 不是 bulk-serialize，实际布局取决于 UE 版本
    3. RawNameToIndexMap: TMap<FName, int32>

    Returns:
        包含 names、parents、transforms 的字典
    """
    ref_skeleton: Dict[str, Any] = {}

    # 读取 BoneInfo 数量（TArray count）
    bone_count = archive.read_i32("RefSkel.BoneCount")

    if bone_count < 0 or bone_count > 10000:
        logger.debug(
            "ReferenceSkeleton: 异常的骨骼数量 %d，跳过解析",
            bone_count,
        )
        return {"bone_count": bone_count, "error": "invalid bone count"}

    # 读取 BoneInfo 数组
    names: List[str] = []
    parents: List[int] = []
    for i in range(bone_count):
        # FName: Index (int32) + Number (int32)
        name_index = archive.read_i32(f"RefSkel.BoneInfo[{i}].Name.Index")
        name_number = archive.read_i32(f"RefSkel.BoneInfo[{i}].Name.Number")

        # 解析名称
        bone_name = _resolve_fname(name_index, name_number, name_map)

        # ParentIndex: int32（INDEX_NONE = -1 表示根骨骼）
        parent_index = archive.read_i32(f"RefSkel.BoneInfo[{i}].ParentIndex")

        names.append(bone_name)
        parents.append(parent_index)

    ref_skeleton["names"] = names
    ref_skeleton["parents"] = parents
    ref_skeleton["bone_count"] = bone_count

    # 读取 BonePose 数组（TArray<FTransform>）
    pose_count = archive.read_i32("RefSkel.PoseCount")
    if pose_count != bone_count:
        logger.debug(
            "ReferenceSkeleton: PoseCount(%d) != BoneCount(%d)",
            pose_count, bone_count,
        )

    transforms: List[Dict[str, Any]] = []
    for i in range(min(pose_count, bone_count)):
        transform = _read_ftransform(archive)
        transforms.append(transform)

    ref_skeleton["transforms"] = transforms
    ref_skeleton["pose_count"] = pose_count

    # 读取 NameToIndexMap: TMap<FName, int32>
    # TMap 序列化为 count + entries，每个 entry = Key(FName) + Value(int32)
    map_count = archive.read_i32("RefSkel.NameToIndexMap.Count")
    name_to_index: Dict[str, int] = {}
    for _ in range(map_count):
        key_index = archive.read_i32("RefSkel.NameToIndexMap.Key.Index")
        key_number = archive.read_i32("RefSkel.NameToIndexMap.Key.Number")
        value = archive.read_i32("RefSkel.NameToIndexMap.Value")

        key_name = _resolve_fname(key_index, key_number, name_map)
        name_to_index[key_name] = value

    ref_skeleton["name_to_index"] = name_to_index

    return ref_skeleton


def _read_retarget_sources(archive: Any, name_map: List[str]) -> List[Dict[str, Any]]:
    """读取 RetargetSources: TMap<FName, FReferencePose>。

    格式（Skeleton.cpp:419-448）：
    1. int32 NumOfRetargetSources
    2. 每个 source:
       - FName RetargetSourceName
       - SerializeReferencePose:
         - FName PoseName
         - TArray<FTransform> ReferencePose
         - FSoftObjectPath SourceReferenceMesh（editor only，非 cooking 时序列化）

    Returns:
        RetargetSource 列表
    """
    sources: List[Dict[str, Any]] = []

    num_sources = archive.read_i32("RetargetSources.Count")
    if num_sources < 0 or num_sources > 1000:
        logger.debug(
            "RetargetSources: 异常的 source 数量 %d，跳过解析",
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
        transforms: List[Dict[str, Any]] = []
        for _ in range(pose_count):
            transform = _read_ftransform(archive)
            transforms.append(transform)
        source["transforms"] = transforms
        source["transform_count"] = len(transforms)

        # 3. SourceReferenceMesh: FSoftObjectPath（editor only）
        # FSoftObjectPath 序列化为 FTopLevelAssetPath: PackageName(FName) + AssetName(FName)
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


def _read_ftransform(archive: Any) -> Dict[str, Any]:
    """读取 FTransform。

    UE5 FTransform 序列化顺序（property_types.py 参考）：
    - Translation: 3 x f64 = 24 bytes
    - Rotation: 4 x f32 = 16 bytes
    - Scale3D: 3 x f32 = 12 bytes
    """
    # Translation: FVector3d (3 x f64 = 24 bytes)
    tx = archive.read_f64("Transform.Translation.X")
    ty = archive.read_f64("Transform.Translation.Y")
    tz = archive.read_f64("Transform.Translation.Z")

    # Rotation: FQuat (4 x f32 = 16 bytes)
    rx = archive.read_f32("Transform.Rotation.X")
    ry = archive.read_f32("Transform.Rotation.Y")
    rz = archive.read_f32("Transform.Rotation.Z")
    rw = archive.read_f32("Transform.Rotation.W")

    # Scale3D: FVector3f (3 x f32 = 12 bytes)
    sx = archive.read_f32("Transform.Scale.X")
    sy = archive.read_f32("Transform.Scale.Y")
    sz = archive.read_f32("Transform.Scale.Z")

    return {
        "translation": {"x": tx, "y": ty, "z": tz},
        "rotation": {"x": rx, "y": ry, "z": rz, "w": rw},
        "scale": {"x": sx, "y": sy, "z": sz},
    }


def _format_guid(guid_bytes: bytes) -> str:
    """将 16 字节 FGuid 格式化为字符串。"""
    import struct
    if len(guid_bytes) < 16:
        return ""
    # FGuid 序列化顺序: A(i32) B(i32) C(i32) D(i32)
    a, b, c, d = struct.unpack('<4I', guid_bytes[:16])
    return f"{a:08X}-{b:08X}-{c:08X}-{d:08X}"


def _resolve_fname(index: int, number: int, name_map: List[str]) -> str:
    """解析 FName（index + number）到字符串。"""
    if 0 <= index < len(name_map):
        base_name = name_map[index]
        if number > 0:
            return f"{base_name}_{number}"
        return base_name
    return f"<invalid_index_{index}>"
