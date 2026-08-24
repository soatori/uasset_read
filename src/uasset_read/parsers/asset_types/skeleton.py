"""USkeleton 资产类型处理器

解析 USkeleton 的 custom serialization 数据：
- ReferenceSkeleton（参考骨架）
  - Names: TArray<FName>
  - Parents: TArray<int32>
  - RefLocalPose: TArray<FTransform>
    - UE4: 40 bytes (Rotation 16 + Translation 12 + Scale 12)
    - UE5: 52 bytes (Rotation 16 + Translation 24 + Scale 12)
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

import logging
import struct
from typing import Any, Dict, List

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)

# 安全上限：防止将垃圾字节解释为计数
_MAX_SKELETON_COUNT = 100000

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

    # 收集截断诊断：子函数遇到非法 count 时追加，最后统一升级 parse_status
    _diagnostics: List[str] = []

    try:
        # 第一步：跳过 tagged properties
        # PropertyTag 序列化格式：
        #   Name: FName（index + number）
        #   如果 Name == "None"（index=0），属性列表结束
        #   否则继续读取 TypeName、Size、ArrayIndex 等字段和值数据
        _skip_tagged_properties(archive, name_map)

        # 第二步：解析 ReferenceSkeleton（custom serialization，非 UPROPERTY）
        ref_skeleton = _read_reference_skeleton(archive, name_map, _diagnostics)
        result["reference_skeleton"] = ref_skeleton

        # 第三步：解析 RetargetSources: TMap<FName, FReferencePose>
        retarget_sources = _read_retarget_sources(archive, name_map, _diagnostics)
        result["retarget_sources"] = retarget_sources
        result["retarget_source_count"] = len(retarget_sources)

        # 第四步：解析 Guid: FGuid（16 bytes）
        # Guid 在 UE4 >= VER_UE4_SKELETON_GUID_SERIALIZATION 后序列化
        if archive.check_remaining(FGUID_SIZE, "Skeleton.Guid"):
            guid_bytes = archive.read_bytes(FGUID_SIZE, "Skeleton.Guid")
            result["guid"] = _format_guid(guid_bytes)

    except (struct.error, OSError, ValueError, ParseError) as e:
        logger.debug("skeleton handler 解析失败: %s", e)
        # 当 class_index 错误指向 Skeleton 但实际数据为其他类型（如 SkeletalMesh）时，
        # handler 无法解析是预期行为，标记为 opaque 而非 failed，
        # 避免整个 package 被判定为 failed（Issue #321）
        result["parse_status"] = "opaque"
        result["error"] = str(e)

    # 骨骼层级验证：检查 parent index 合法性和环检测
    ref_skeleton = result.get("reference_skeleton")
    if ref_skeleton and "parents" in ref_skeleton:
        hierarchy_diags = _validate_hierarchy(ref_skeleton)
        if hierarchy_diags:
            result["valid_hierarchy"] = False
            result["hierarchy_diagnostics"] = hierarchy_diags
            # 层级错误升级为 partial（除非已经是 opaque/failed）
            if result["parse_status"] == "success":
                result["parse_status"] = "partial"
        else:
            result["valid_hierarchy"] = True

    # 非法 count 截断时，标记为 partial 并附带诊断
    if _diagnostics:
        result["parse_status"] = "partial"
        if "diagnostics" in result:
            result["diagnostics"].extend(_diagnostics)
        else:
            result["diagnostics"] = _diagnostics

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
       - InnerTypeName: FName（如果 TypeName 是 ArrayProperty 或 SetProperty）
       - KeyType + ValueType: 2 x FName（如果 TypeName 是 MapProperty）
       - 以及其他版本相关字段
    4. 然后跳过 Value 数据（Size 字节）

    参照 Engine/Source/Runtime/CoreUObject/Private/UObject/Class.cpp
    FPropertyTag::Serialize
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
        _name_number = archive.read_i32()  # noqa: F841 - protocol read

        if name_index == 0:
            # Name == "None"，属性列表结束
            break

        # 读取 TypeName
        type_index = archive.read_i32()
        _type_number = archive.read_i32()  # noqa: F841 - protocol read

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

        # InnerTypeName: FName（ArrayProperty 或 SetProperty）
        # 参照 FPropertyTag::Serialize: InnerType.Serialize(Ar)
        if type_name in ("ArrayProperty", "SetProperty"):
            archive.read_i32()  # index
            archive.read_i32()  # number

        # KeyTypeName + ValueTypeName: 2 x FName（MapProperty）
        # 参照 FPropertyTag::Serialize: KeyType.Serialize(Ar) + ValueType.Serialize(Ar)
        if type_name == "MapProperty":
            archive.read_i32()  # key type index
            archive.read_i32()  # key type number
            archive.read_i32()  # value type index
            archive.read_i32()  # value type number

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


_MAX_EXAMPLES = 5


def _validate_hierarchy(ref_skeleton: Dict[str, Any]) -> List[Dict[str, Any]]:
    """验证骨骼层级结构的合法性。

    检查项：
    1. parent_index 在 [-1, bone_count) 范围内（-1 = INDEX_NONE，表示根骨骼）
    2. 无环（DFS 检测）
    3. 根骨骼数量信息

    Args:
        ref_skeleton: 包含 names、parents、bone_count 的字典

    Returns:
        聚合的诊断条目列表，空列表表示层级合法。
        每条目: {"code": str, "count": int, "examples": list}
    """
    names = ref_skeleton.get("names", [])
    parents = ref_skeleton.get("parents", [])
    bone_count = ref_skeleton.get("bone_count", 0)

    if not parents or bone_count <= 0:
        return []

    diagnostics: List[Dict[str, Any]] = []

    # 1. 检查 parent index 范围
    invalid_examples: List[Dict[str, int]] = []
    invalid_count = 0
    for i, p in enumerate(parents):
        if p < -1 or p >= bone_count:
            invalid_count += 1
            if len(invalid_examples) < _MAX_EXAMPLES:
                invalid_examples.append({"bone_index": i, "parent_index": p})
    if invalid_count > 0:
        diagnostics.append({
            "code": "SKELETON_INVALID_PARENT_INDEX",
            "count": invalid_count,
            "examples": invalid_examples,
        })

    # 2. 环检测（仅在 parent index 范围合法时执行，否则跳过）
    if invalid_count == 0:
        cycle_examples: List[Dict[str, Any]] = []
        cycle_count = 0
        visited = [0] * bone_count  # 0=unvisited, 1=visiting, 2=done

        def _dfs(node: int, path: List[int]) -> bool:
            """DFS 检测环。返回 True 表示发现环。"""
            nonlocal cycle_count
            if visited[node] == 1:
                # 发现环：path 中从 node 到末尾构成环
                cycle_start = path.index(node)
                cycle_path = path[cycle_start:] + [node]
                cycle_count += 1
                if len(cycle_examples) < _MAX_EXAMPLES:
                    cycle_examples.append({
                        "cycle": cycle_path,
                        "names": [names[idx] if idx < len(names) else f"bone_{idx}" for idx in cycle_path],
                    })
                return True
            if visited[node] == 2:
                return False
            visited[node] = 1
            path.append(node)
            parent = parents[node]
            if parent >= 0 and parent < bone_count:
                _dfs(parent, path)
            path.pop()
            visited[node] = 2
            return False

        for i in range(bone_count):
            if visited[i] == 0:
                _dfs(i, [])

        if cycle_count > 0:
            diagnostics.append({
                "code": "SKELETON_HIERARCHY_CYCLE",
                "count": cycle_count,
                "examples": cycle_examples,
            })

    # 3. 多根骨骼信息（informational，不升级为 partial）
    root_count = sum(1 for p in parents if p == -1)
    if root_count > 1:
        root_examples = [
            {"bone_index": i, "name": names[i] if i < len(names) else f"bone_{i}"}
            for i, p in enumerate(parents) if p == -1
        ][:_MAX_EXAMPLES]
        diagnostics.append({
            "code": "SKELETON_MULTIPLE_ROOTS",
            "count": root_count,
            "examples": root_examples,
        })

    return diagnostics


def _read_reference_skeleton(
    archive: Any, name_map: List[str], _diagnostics: List[str] | None = None,
) -> Dict[str, Any]:
    """读取 FReferenceSkeleton custom serialization。

    FReferenceSkeleton 序列化格式（ReferenceSkeleton.cpp:941）：
    1. RawRefBoneInfo: TArray<FMeshBoneInfo>
       - FMeshBoneInfo: FName (8 bytes) + int32 ParentIndex
    2. RawRefBonePose: TArray<FTransform>
       - 每个 FTransform: Translation(FVector3d: 3*8=24) + Rotation(FQuat4f: 4*4=16) + Scale(FVector3f: 3*4=12) = 52 bytes
       注意：FTransform 不是 bulk-serialize，实际布局取决于 UE 版本
    3. RawNameToIndexMap: TMap<FName, int32>

    Args:
        _diagnostics: 可选的诊断收集列表，截断非法 count 时追加条目

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
    if pose_count < 0 or pose_count > _MAX_SKELETON_COUNT:
        logger.debug(
            "ReferenceSkeleton: 异常的 PoseCount %d（bone_count=%d），截断为 0",
            pose_count, bone_count,
        )
        if _diagnostics is not None:
            _diagnostics.append(
                f"ReferenceSkeleton.PoseCount 截断: {pose_count} -> 0"
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

    # 读取 NameToIndexMap: TMap<FName, int32>
    # TMap 序列化为 count + entries，每个 entry = Key(FName) + Value(int32)
    map_count = archive.read_i32("RefSkel.NameToIndexMap.Count")
    if map_count < 0 or map_count > _MAX_SKELETON_COUNT:
        logger.debug(
            "ReferenceSkeleton: 异常的 NameToIndexMap.Count %d，跳过解析",
            map_count,
        )
        if _diagnostics is not None:
            _diagnostics.append(
                f"ReferenceSkeleton.NameToIndexMap.Count 截断: {map_count} -> 0"
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
    is_ue5 = getattr(archive, '_file_version_ue5', 0) > 0

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
        if pose_count < 0 or pose_count > _MAX_SKELETON_COUNT:
            logger.debug(
                "RetargetSources[%d]: 异常的 PoseCount %d，截断为 0",
                i, pose_count,
            )
            if _diagnostics is not None:
                _diagnostics.append(
                    f"RetargetSources[{i}].PoseCount 截断: {pose_count} -> 0"
                )
            pose_count = 0
        transforms: List[Dict[str, Any]] = []
        for _ in range(pose_count):
            transform = _read_ftransform(archive, is_ue5=is_ue5)
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


def _read_ftransform(archive: Any, is_ue5: bool = True) -> Dict[str, Any]:
    """读取 FTransform，支持 UE4/UE5 不同布局。

    序列化顺序（参照 TransformVectorized.h operator<<）：
    Rotation → Translation → Scale3D

    UE4 布局（40 bytes）：
    - Rotation: FQuat4f (4 x f32 = 16 bytes)
    - Translation: FVector (3 x f32 = 12 bytes)
    - Scale3D: FVector (3 x f32 = 12 bytes)

    UE5 布局（52 bytes）：
    - Rotation: FQuat4f (4 x f32 = 16 bytes)
    - Translation: FVector3d (3 x f64 = 24 bytes)
    - Scale3D: FVector3f (3 x f32 = 12 bytes)

    Args:
        archive: FArchive 实例
        is_ue5: True 表示 UE5 布局（默认），False 表示 UE4 布局
    """
    # Rotation: FQuat4f (4 x f32 = 16 bytes) — UE4/UE5 相同
    rx = archive.read_f32("Transform.Rotation.X")
    ry = archive.read_f32("Transform.Rotation.Y")
    rz = archive.read_f32("Transform.Rotation.Z")
    rw = archive.read_f32("Transform.Rotation.W")

    # Translation: FVector (UE4: 3 x f32 = 12 bytes) 或 FVector3d (UE5: 3 x f64 = 24 bytes)
    if is_ue5:
        tx = archive.read_f64("Transform.Translation.X")
        ty = archive.read_f64("Transform.Translation.Y")
        tz = archive.read_f64("Transform.Translation.Z")
    else:
        tx = archive.read_f32("Transform.Translation.X")
        ty = archive.read_f32("Transform.Translation.Y")
        tz = archive.read_f32("Transform.Translation.Z")

    # Scale3D: FVector3f (3 x f32 = 12 bytes) — UE4/UE5 相同
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
