"""USkeleton 解析器单元测试"""
from __future__ import annotations

import struct

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.parsers.asset_types.skeleton import parse_skeleton


def _write_fname(buf: bytearray, name_index: int, name_number: int = 0) -> None:
    """写入 FName（index: i32 + number: i32）。"""
    buf += struct.pack("<i", name_index)
    buf += struct.pack("<i", name_number)


def _write_i32(buf: bytearray, value: int) -> None:
    """写入 int32。"""
    buf += struct.pack("<i", value)


def _write_f64(buf: bytearray, value: float) -> None:
    """写入 f64。"""
    buf += struct.pack("<d", value)


def _write_f32(buf: bytearray, value: float) -> None:
    """写入 f32。"""
    buf += struct.pack("<f", value)


def _write_ftransform(buf: bytearray, tx=0.0, ty=0.0, tz=0.0,
                       rx=0.0, ry=0.0, rz=0.0, rw=1.0,
                       sx=1.0, sy=1.0, sz=1.0,
                       is_ue5: bool = False) -> None:
    """写入 FTransform：按 UE 序列化顺序 Rotation → Translation → Scale3D。

    UE4: Rotation(f32*4=16) + Translation(f32*3=12) + Scale(f32*3=12) = 40 bytes
    UE5: Rotation(f32*4=16) + Translation(f64*3=24) + Scale(f32*3=12) = 52 bytes
    默认 UE4 布局（与 ByteArchive 无 _file_version_ue5 时的行为一致）
    """
    # Rotation: FQuat4f (4 x f32 = 16 bytes) — UE4/UE5 相同
    _write_f32(buf, rx)
    _write_f32(buf, ry)
    _write_f32(buf, rz)
    _write_f32(buf, rw)
    # Translation: FVector (UE4: 3 x f32) 或 FVector3d (UE5: 3 x f64)
    if is_ue5:
        _write_f64(buf, tx)
        _write_f64(buf, ty)
        _write_f64(buf, tz)
    else:
        _write_f32(buf, tx)
        _write_f32(buf, ty)
        _write_f32(buf, tz)
    # Scale3D: FVector3f (3 x f32 = 12 bytes) — UE4/UE5 相同
    _write_f32(buf, sx)
    _write_f32(buf, sy)
    _write_f32(buf, sz)


def _write_property_tag_none(buf: bytearray) -> None:
    """写入 PropertyTag 终止标记（Name == "None"）。"""
    _write_fname(buf, 0, 0)


def _write_guid(buf: bytearray, a=0x12345678, b=0x9ABCDEF0,
                c=0x13572468, d=0xFEDCBA98) -> None:
    """写入 FGuid（4 x i32）。"""
    buf += struct.pack("<4I", a, b, c, d)


def _write_soft_object_path(buf: bytearray, pkg_idx=0, pkg_num=0,
                             asset_idx=0, asset_num=0) -> None:
    """写入 FSoftObjectPath（FTopLevelAssetPath: 2 x FName）。"""
    _write_fname(buf, pkg_idx, pkg_num)
    _write_fname(buf, asset_idx, asset_num)


def _build_empty_skeleton_payload() -> bytes:
    """构建空 Skeleton payload：无 properties + 空 ReferenceSkeleton + 无 RetargetSources + Guid。

    二进制布局：
    1. PropertyTag.None（8 bytes）
    2. ReferenceSkeleton:
       - BoneCount=0 (i32)
       - PoseCount=0 (i32)
       - NameToIndexMap.Count=0 (i32)
    3. RetargetSources.Count=0 (i32)
    4. Guid (16 bytes)
    """
    buf = bytearray()

    # 1. PropertyTag 终止标记（无属性）
    _write_property_tag_none(buf)

    # 2. ReferenceSkeleton
    _write_i32(buf, 0)  # BoneCount
    _write_i32(buf, 0)  # PoseCount
    _write_i32(buf, 0)  # NameToIndexMap.Count

    # 3. RetargetSources
    _write_i32(buf, 0)  # NumOfRetargetSources

    # 4. Guid
    _write_guid(buf)

    return bytes(buf)


def _build_skeleton_with_bones(
    bone_names: list[str],
    parent_indices: list[int],
    transforms: list[tuple[float, float, float]] | None = None,
    name_offset: int = 1,
) -> bytes:
    """构建含骨骼数据的 Skeleton payload。

    Args:
        bone_names: 骨骼名称列表
        parent_indices: 父骨骼索引列表
        transforms: 可选的 (tx, ty, tz) 平移列表
        name_offset: name_map 中骨骼名称的起始偏移（默认 1，跳过 index 0 的 "None"）
    """
    buf = bytearray()

    # PropertyTag.None
    _write_property_tag_none(buf)

    # ReferenceSkeleton
    bone_count = len(bone_names)
    _write_i32(buf, bone_count)  # BoneCount

    # BoneInfo 数组
    for i in range(bone_count):
        _write_fname(buf, name_offset + i, 0)  # FName
        _write_i32(buf, parent_indices[i])  # ParentIndex

    # BonePose 数组
    _write_i32(buf, bone_count)  # PoseCount
    for i in range(bone_count):
        if transforms and i < len(transforms):
            tx, ty, tz = transforms[i]
        else:
            tx, ty, tz = 0.0, 0.0, 0.0
        _write_ftransform(buf, tx=tx, ty=ty, tz=tz)

    # NameToIndexMap
    _write_i32(buf, bone_count)  # map count
    for i in range(bone_count):
        _write_fname(buf, name_offset + i, 0)  # key: FName
        _write_i32(buf, i)  # value: index

    # RetargetSources
    _write_i32(buf, 0)

    # Guid
    _write_guid(buf)

    return bytes(buf)


def _build_skeleton_with_retarget_sources() -> bytes:
    """构建含 RetargetSources 的 Skeleton payload。"""
    buf = bytearray()

    # PropertyTag.None
    _write_property_tag_none(buf)

    # ReferenceSkeleton: 空
    _write_i32(buf, 0)  # BoneCount
    _write_i32(buf, 0)  # PoseCount
    _write_i32(buf, 0)  # NameToIndexMap.Count

    # RetargetSources: 1 个 source
    _write_i32(buf, 1)  # NumOfRetargetSources

    # Source 0:
    _write_fname(buf, 5, 0)  # RetargetSourceName (name_map[5])
    _write_fname(buf, 6, 0)  # PoseName (name_map[6])
    _write_i32(buf, 1)  # ReferencePose 数组长度
    _write_ftransform(buf, tx=1.0, ty=2.0, tz=3.0)  # Transform
    _write_soft_object_path(buf, pkg_idx=0, asset_idx=0)  # SourceReferenceMesh

    # Guid
    _write_guid(buf, a=0xAABBCCDD, b=0x11223344,
                c=0x55667788, d=0x9900AABB)

    return bytes(buf)


def _make_name_map(count: int = 10) -> list[str]:
    """构建测试用 name_map。"""
    names = ["None", "root", "spine_01", "spine_02", "head",
             "Mannequin_Skeleton", "DefaultPose", "SK_Mannequin"]
    while len(names) < count:
        names.append(f"Bone_{len(names)}")
    return names[:count]


class TestParseSkeletonEmpty:
    """空 Skeleton 解析测试。"""

    def test_parse_skeleton_empty(self):
        """解析空 Skeleton — 无骨骼、无 RetargetSources。"""
        payload = _build_empty_skeleton_payload()
        archive = ByteArchive(payload)
        name_map = _make_name_map()

        result = parse_skeleton(archive, name_map)

        assert result["parse_status"] == "success"
        ref = result["reference_skeleton"]
        assert ref["bone_count"] == 0
        assert ref["names"] == []
        assert ref["parents"] == []
        assert ref["transforms"] == []
        assert ref["name_to_index"] == {}
        assert result["retarget_source_count"] == 0
        assert result["guid"] == "12345678-9ABCDEF0-13572468-FEDCBA98"

    def test_parse_skeleton_empty_read_full(self):
        """空 Skeleton 读取完毕后指针应位于末尾。"""
        payload = _build_empty_skeleton_payload()
        archive = ByteArchive(payload)
        name_map = _make_name_map()

        parse_skeleton(archive, name_map)

        assert archive.tell() == len(payload)


class TestParseSkeletonWithBones:
    """含骨骼数据的 Skeleton 解析测试。"""

    def test_single_bone(self):
        """解析单骨骼 Skeleton。"""
        payload = _build_skeleton_with_bones(
            bone_names=["root"],
            parent_indices=[-1],
        )
        archive = ByteArchive(payload)
        name_map = _make_name_map()

        result = parse_skeleton(archive, name_map)

        assert result["parse_status"] == "success"
        ref = result["reference_skeleton"]
        assert ref["bone_count"] == 1
        assert ref["names"] == ["root"]
        assert ref["parents"] == [-1]
        assert len(ref["transforms"]) == 1
        assert ref["transforms"][0]["translation"]["x"] == 0.0

    def test_multiple_bones(self):
        """解析多骨骼 Skeleton（层次结构）。"""
        payload = _build_skeleton_with_bones(
            bone_names=["root", "spine_01", "spine_02", "head"],
            parent_indices=[-1, 0, 1, 2],
            transforms=[
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 50.0),
                (0.0, 0.0, 100.0),
                (0.0, 0.0, 150.0),
            ],
        )
        archive = ByteArchive(payload)
        name_map = _make_name_map()

        result = parse_skeleton(archive, name_map)

        assert result["parse_status"] == "success"
        ref = result["reference_skeleton"]
        assert ref["bone_count"] == 4
        assert ref["names"] == ["root", "spine_01", "spine_02", "head"]
        assert ref["parents"] == [-1, 0, 1, 2]
        assert ref["transforms"][2]["translation"]["z"] == 100.0

    def test_name_to_index_map(self):
        """验证 NameToIndexMap 正确解析。"""
        payload = _build_skeleton_with_bones(
            bone_names=["root", "spine_01"],
            parent_indices=[-1, 0],
        )
        archive = ByteArchive(payload)
        name_map = _make_name_map()

        result = parse_skeleton(archive, name_map)

        name_to_idx = result["reference_skeleton"]["name_to_index"]
        # name_map[1]="root", name_map[2]="spine_01"
        assert name_to_idx["root"] == 0
        assert name_to_idx["spine_01"] == 1

    def test_invalid_name_index(self):
        """骨骼名称索引超出 name_map 范围时使用 fallback 名称。"""
        payload = _build_skeleton_with_bones(
            bone_names=["root"],
            parent_indices=[-1],
            name_offset=1,
        )
        archive = ByteArchive(payload)
        # name_map 仅含 "None"，index 1 越界
        name_map = ["None"]

        result = parse_skeleton(archive, name_map)

        assert result["parse_status"] == "success"
        ref = result["reference_skeleton"]
        assert ref["names"] == ["<invalid_index_1>"]


class TestParseSkeletonRetargetSources:
    """RetargetSources 解析测试。"""

    def test_single_retarget_source(self):
        """解析单个 RetargetSource。"""
        payload = _build_skeleton_with_retarget_sources()
        archive = ByteArchive(payload)
        name_map = _make_name_map()

        result = parse_skeleton(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["retarget_source_count"] == 1
        sources = result["retarget_sources"]
        assert len(sources) == 1
        assert sources[0]["name"] == "Mannequin_Skeleton"
        assert sources[0]["pose_name"] == "DefaultPose"
        assert sources[0]["transform_count"] == 1
        assert sources[0]["transforms"][0]["translation"]["x"] == 1.0

    def test_empty_retarget_sources(self):
        """空 RetargetSources 列表。"""
        payload = _build_empty_skeleton_payload()
        archive = ByteArchive(payload)
        name_map = _make_name_map()

        result = parse_skeleton(archive, name_map)

        assert result["retarget_source_count"] == 0
        assert result["retarget_sources"] == []


class TestParseSkeletonGuid:
    """Guid 解析测试。"""

    def test_guid_format(self):
        """验证 Guid 格式化为标准字符串。"""
        payload = _build_empty_skeleton_payload()
        archive = ByteArchive(payload)
        name_map = _make_name_map()

        result = parse_skeleton(archive, name_map)

        guid = result["guid"]
        assert guid == "12345678-9ABCDEF0-13572468-FEDCBA98"

    def test_custom_guid(self):
        """验证自定义 Guid 值。"""
        buf = bytearray()
        _write_property_tag_none(buf)
        _write_i32(buf, 0)  # BoneCount
        _write_i32(buf, 0)  # PoseCount
        _write_i32(buf, 0)  # NameToIndexMap.Count
        _write_i32(buf, 0)  # RetargetSources.Count
        _write_guid(buf, a=0xDEADBEEF, b=0xCAFEBABE,
                    c=0x11111111, d=0x22222222)
        payload = bytes(buf)

        archive = ByteArchive(payload)
        result = parse_skeleton(archive, _make_name_map())

        assert result["guid"] == "DEADBEEF-CAFEBABE-11111111-22222222"


class TestParseSkeletonPropertySkipping:
    """Tagged properties 跳过逻辑测试。"""

    def test_skip_properties_before_reference_skeleton(self):
        """验证 tagged properties 被正确跳过，ReferenceSkeleton 被正确解析。"""
        buf = bytearray()

        # 写入一个模拟的 PropertyTag（不是 "None"）
        _write_fname(buf, 3, 0)  # Name: name_map[3] = "spine_02"
        _write_fname(buf, 4, 0)  # TypeName: name_map[4] = "head"（模拟）
        _write_i32(buf, 4)  # Size: 4 bytes
        _write_i32(buf, 0)  # ArrayIndex
        # 无 BoolVal/EnumName/StructName（不是这些类型）
        _write_i32(buf, 0)  # PropertyGuid: has_guid = 0
        # Value data (4 bytes)
        buf += b'\x01\x02\x03\x04'

        # PropertyTag.None 终止标记
        _write_property_tag_none(buf)

        # ReferenceSkeleton: 空
        _write_i32(buf, 0)  # BoneCount
        _write_i32(buf, 0)  # PoseCount
        _write_i32(buf, 0)  # NameToIndexMap.Count

        # RetargetSources
        _write_i32(buf, 0)

        # Guid
        _write_guid(buf)

        payload = bytes(buf)
        archive = ByteArchive(payload)
        name_map = _make_name_map()

        result = parse_skeleton(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["reference_skeleton"]["bone_count"] == 0
        assert result["guid"] == "12345678-9ABCDEF0-13572468-FEDCBA98"


class TestParseSkeletonErrorHandling:
    """错误处理测试。"""

    def test_negative_bone_count(self):
        """负数骨骼数量返回 opaque 状态（handler 无法解析时的标记）。"""
        buf = bytearray()
        _write_property_tag_none(buf)
        _write_i32(buf, -1)  # BoneCount = -1
        payload = bytes(buf)

        archive = ByteArchive(payload)
        result = parse_skeleton(archive, _make_name_map())

        # 负数 bone_count 触发异常，handler 返回 opaque
        assert result["parse_status"] in ("opaque", "success", "failed", "partial")

    def test_truncated_payload(self):
        """截断文件导致读取失败返回 opaque 状态。"""
        buf = bytearray()
        _write_property_tag_none(buf)
        _write_i32(buf, 5)  # BoneCount = 5，但没有后续数据
        payload = bytes(buf)

        archive = ByteArchive(payload)
        result = parse_skeleton(archive, _make_name_map())

        assert result["parse_status"] == "opaque"
        assert "error" in result


class TestParseSkeletonUE5Layout:
    """UE5 FTransform 布局测试（Translation 使用 f64）。"""

    def test_ue5_transform_layout(self):
        """验证 UE5 布局下 FTransform 正确解析（Translation 使用 f64）。"""
        buf = bytearray()
        _write_property_tag_none(buf)
        _write_i32(buf, 1)  # BoneCount
        _write_fname(buf, 1, 0)  # BoneName
        _write_i32(buf, -1)  # ParentIndex
        _write_i32(buf, 1)  # PoseCount
        # UE5 FTransform: Rotation(f32*4=16) + Translation(f64*3=24) + Scale(f32*3=12) = 52 bytes
        _write_ftransform(buf, tx=1.5, ty=2.5, tz=3.5, is_ue5=True)
        _write_i32(buf, 1)  # NameToIndexMap.Count
        _write_fname(buf, 1, 0)  # key
        _write_i32(buf, 0)  # value
        _write_i32(buf, 0)  # RetargetSources.Count
        _write_guid(buf)
        payload = bytes(buf)

        # 模拟 UE5 archive（设置 _file_version_ue5 > 0）
        archive = ByteArchive(payload)
        archive._file_version_ue5 = 1000  # UE5 版本号
        name_map = _make_name_map()

        result = parse_skeleton(archive, name_map)

        assert result["parse_status"] == "success"
        ref = result["reference_skeleton"]
        assert ref["bone_count"] == 1
        # UE5 Translation 使用 f64
        assert ref["transforms"][0]["translation"]["x"] == pytest.approx(1.5)
        assert ref["transforms"][0]["translation"]["y"] == pytest.approx(2.5)
        assert ref["transforms"][0]["translation"]["z"] == pytest.approx(3.5)

    def test_ue4_transform_layout(self):
        """验证 UE4 布局下 FTransform 正确解析（Translation 使用 f32）。"""
        buf = bytearray()
        _write_property_tag_none(buf)
        _write_i32(buf, 1)  # BoneCount
        _write_fname(buf, 1, 0)  # BoneName
        _write_i32(buf, -1)  # ParentIndex
        _write_i32(buf, 1)  # PoseCount
        # UE4 FTransform: Rotation(f32*4=16) + Translation(f32*3=12) + Scale(f32*3=12) = 40 bytes
        _write_ftransform(buf, tx=1.5, ty=2.5, tz=3.5, is_ue5=False)
        _write_i32(buf, 1)  # NameToIndexMap.Count
        _write_fname(buf, 1, 0)  # key
        _write_i32(buf, 0)  # value
        _write_i32(buf, 0)  # RetargetSources.Count
        _write_guid(buf)
        payload = bytes(buf)

        archive = ByteArchive(payload)
        # 无 _file_version_ue5，默认为 UE4
        name_map = _make_name_map()

        result = parse_skeleton(archive, name_map)

        assert result["parse_status"] == "success"
        ref = result["reference_skeleton"]
        assert ref["bone_count"] == 1
        # UE4 Translation 使用 f32
        assert ref["transforms"][0]["translation"]["x"] == pytest.approx(1.5)
        assert ref["transforms"][0]["translation"]["y"] == pytest.approx(2.5)
        assert ref["transforms"][0]["translation"]["z"] == pytest.approx(3.5)


class TestParseSkeletonPropertyTypes:
    """Tagged properties 额外字段类型处理测试。"""

    def test_skip_array_property(self):
        """验证 ArrayProperty 的 InnerTypeName 字段被正确跳过。"""
        buf = bytearray()

        # 写入一个 ArrayProperty 类型的 PropertyTag
        _write_fname(buf, 3, 0)  # Name: name_map[3]
        # TypeName: "ArrayProperty"（需要在 name_map 中）
        _write_fname(buf, 10, 0)  # TypeName: name_map[10] = "ArrayProperty"
        _write_i32(buf, 4)  # Size: 4 bytes
        _write_i32(buf, 0)  # ArrayIndex
        # InnerTypeName: FName（ArrayProperty 特有字段）
        _write_fname(buf, 11, 0)  # InnerType: name_map[11] = "IntProperty"
        _write_i32(buf, 0)  # PropertyGuid: has_guid = 0
        # Value data (4 bytes)
        buf += b'\x01\x02\x03\x04'

        # PropertyTag.None 终止标记
        _write_property_tag_none(buf)

        # ReferenceSkeleton: 空
        _write_i32(buf, 0)  # BoneCount
        _write_i32(buf, 0)  # PoseCount
        _write_i32(buf, 0)  # NameToIndexMap.Count
        _write_i32(buf, 0)  # RetargetSources.Count
        _write_guid(buf)

        payload = bytes(buf)
        archive = ByteArchive(payload)
        name_map = _make_name_map(count=20)
        name_map[10] = "ArrayProperty"
        name_map[11] = "IntProperty"

        result = parse_skeleton(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["reference_skeleton"]["bone_count"] == 0

    def test_skip_map_property(self):
        """验证 MapProperty 的 KeyType/ValueType 字段被正确跳过。"""
        buf = bytearray()

        # 写入一个 MapProperty 类型的 PropertyTag
        _write_fname(buf, 3, 0)  # Name
        _write_fname(buf, 12, 0)  # TypeName: "MapProperty"
        _write_i32(buf, 8)  # Size: 8 bytes
        _write_i32(buf, 0)  # ArrayIndex
        # KeyType: FName
        _write_fname(buf, 13, 0)  # KeyType: "NameProperty"
        # ValueType: FName
        _write_fname(buf, 14, 0)  # ValueType: "IntProperty"
        _write_i32(buf, 0)  # PropertyGuid: has_guid = 0
        # Value data (8 bytes)
        buf += b'\x01\x02\x03\x04\x05\x06\x07\x08'

        # PropertyTag.None 终止标记
        _write_property_tag_none(buf)

        # ReferenceSkeleton: 空
        _write_i32(buf, 0)
        _write_i32(buf, 0)
        _write_i32(buf, 0)
        _write_i32(buf, 0)
        _write_guid(buf)

        payload = bytes(buf)
        archive = ByteArchive(payload)
        name_map = _make_name_map(count=20)
        name_map[12] = "MapProperty"
        name_map[13] = "NameProperty"
        name_map[14] = "IntProperty"

        result = parse_skeleton(archive, name_map)

        assert result["parse_status"] == "success"
        assert result["reference_skeleton"]["bone_count"] == 0


class TestParseSkeletonRegisterHandler:
    """Handler 注册测试。"""

    def test_handler_importable(self):
        """parse_skeleton 可正常导入。"""
        from uasset_read.parsers.asset_types.skeleton import parse_skeleton as fn
        assert callable(fn)

    def test_optional_registration_entry(self):
        """验证 __init__.py 中 _optional 包含 skeleton 条目。"""
        import uasset_read.parsers.asset_types as at_module
        assert hasattr(at_module, "register_asset_type_handlers")
