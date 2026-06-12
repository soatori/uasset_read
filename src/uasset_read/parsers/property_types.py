"""属性类型解析函数 — 14 种 parse_*_property 函数及 TypeName 提取辅助函数。

等价迁移 uasset_read.py 第 5289-6004 行。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Dict, Any, Optional, Tuple, Union
import re

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.versioning import VersionContainer

from uasset_read.models.properties import (
    PropertyTag, PropertyValue,
    StructValue, MapValue, SetValue, EnumValue, TextValue, DelegateValue,
    SoftObjectPathValue,
)
from uasset_read.models.core import FEdGraphPinType
from uasset_read.exceptions import ParseError
from uasset_read.constants import MAX_PROPERTY_COUNT, MAX_ARRAY_COUNT, UE5_LARGE_WORLD_COORDINATES
from uasset_read.parsers.utils import make_enum_value, extract_inner_from_tag, read_validated_count

# FPropertyTypeName 最大节点数（UE 源码限制）
MAX_TYPENODE_NODES = 20

# Expected byte sizes for fixed-layout structs (used for fast-path validation)
_EXPECTED_STRUCT_SIZES: dict[str, int] = {
    "Vector": 12, "Rotator": 12, "Vector2D": 8, "Vector4": 16,
    "LinearColor": 16, "Color": 4, "Quat": 16, "Plane": 16,
    "Guid": 16, "IntPoint": 8, "IntVector": 12,
    "Box2D": 20, "Box": 28, "Sphere": 16, "BoxSphereBounds": 28,
    "Matrix": 64, "TwoVectors": 24, "OrientedBox": 60,
    "Transform": 48,
    "TopLevelAssetPath": 16,
    # 时间/帧类型
    "Timespan": 8,           # int64
    "DateTime": 8,           # uint64
    "FrameNumber": 4,        # int32
    # 整数向量类型
    "IntVector2": 8,         # 2 * int32
    "Int32Vector2": 8,       # 别名
    "IntVector4": 16,        # 4 * int32
    "UintVector": 12,        # 3 * uint32
    "UintVector2": 8,        # 2 * uint32
    "Uint32Point": 8,        # 别名
    "UintVector4": 16,       # 4 * uint32
    # 64 位整数向量类型
    "Int64Vector2": 16,      # 2 * int64
    "Int64Point": 16,        # 别名
    "Int64Vector": 24,       # 3 * int64
    "Int64Vector4": 32,      # 4 * int64
    "UInt64Vector2": 16,     # 2 * uint64
    "UInt64Point": 16,       # 别名
    "UInt64Vector": 24,      # 3 * uint64
    "UInt64Vector4": 32,     # 4 * uint64
    # 别名类型
    "DeprecateSlateVector2D": 16,  # 别名 Vector2D
    "VectorDouble": 24,            # Wuthering Waves 别名 Vector3d
    "Int32Point": 8,               # 别名 IntPoint
    # UE5 LWC 数学类型
    "Vector2f": 8,           # 2 * float32
    "Vector3f": 12,          # 3 * float32
    "Vector3d": 24,          # 3 * float64
    "Vector4f": 16,          # 4 * float32
    "Vector4d": 32,          # 4 * float64
    "Rotator3f": 12,         # 3 * float32
    "Rotator3d": 24,         # 3 * float64
    "Quat4f": 16,            # 4 * float32
    "Quat4d": 32,            # 4 * float64
    "Plane4f": 16,           # 4 * float32
    "Plane4d": 32,           # 4 * float64
    "Sphere3f": 16,          # 4 * float32
    "Sphere3d": 32,          # 4 * float64
    "Box2f": 16,             # 2 * Vector2f(8)
    "Box3f": 24,             # 2 * Vector3f(12)
    "Matrix44f": 64,         # 4 * Plane4f(16)
    "Transform3f": 48,       # Quat4f(16) + Vector3f(12) + Vector3f(4) + padding
    # 动画/混合空间高频结构体（报告补充）
    "FrameRate": 8,          # 紧凑格式：int32 Numerator + int32 Denominator
                             # tagged 格式 size 不固定（实测 37），通过 tagged fallback 静默解析
    "AnimNotifyTrack": 8,    # 紧凑格式大小
                             # tagged 格式 size=0，通过 tagged fallback 静默解析（数据实际存在）
    "GuidProperty": 16,      # FGuid 标准大小
}


# LWC（Large World Coordinates）类型映射
# UE5 UE5_LARGE_WORLD_COORDINATES(1004) 起，数学向量类型使用 double 精度。
# _LWC_TYPE_MAP: 基础类型名 → (float_size, double_size)
# 当 version_container 的 file_version_ue5 >= 1004 时，基础类型使用 double_size。
_LWC_TYPE_MAP: Dict[str, Tuple[int, int]] = {
    "Vector":        (12, 24),   # FVector3f → FVector3d
    "Rotator":       (12, 24),   # FRotator3f → FRotator3d
    "Vector2D":      (8, 16),    # FVector2f → FVector2d
    "Vector4":       (16, 32),   # FVector4f → FVector4d
    "Quat":          (16, 32),   # FQuat4f → FQuat4d
    "Plane":         (16, 32),   # FPlane4f → FPlane4d
    "Sphere":        (16, 32),   # FSphere3f → FSphere3d
    "Box":           (28, 56),   # 2 * FVector + bool (float → double)
    "BoxSphereBounds": (28, 56), # 3 * FVector + float (float → double)
    "Matrix":        (64, 128),  # 4 * FPlane (float → double)
    "TwoVectors":    (24, 48),   # 2 * FVector (float → double)
    "Transform":     (48, 48),   # FQuat + FVector + FVector（Transform 始终混用）
}

# LWC 双精度类型名 → 对应的基础类型名
# e.g. "Vector3d" → "Vector"，用于 get_struct_size 回退查询
_LWC_DOUBLE_TYPE_TO_BASE: Dict[str, str] = {
    "Vector3d":    "Vector",
    "Vector4d":    "Vector4",
    "Rotator3d":   "Rotator",
    "Quat4d":      "Quat",
    "Plane4d":     "Plane",
    "Sphere3d":    "Sphere",
}

# LWC 单精度类型名 → 对应的基础类型名
_LWC_FLOAT_TYPE_TO_BASE: Dict[str, str] = {
    "Vector3f":    "Vector",
    "Vector4f":    "Vector4",
    "Rotator3f":   "Rotator",
    "Quat4f":      "Quat",
    "Plane4f":     "Plane",
    "Sphere3f":    "Sphere",
    "Vector2f":    "Vector2D",
}


def get_struct_size(
    struct_type: str,
    version_container: Optional["VersionContainer"] = None,
) -> Optional[int]:
    """返回固定布局结构体的预期字节大小（版本感知）。

    对于 LWC（Large World Coordinates）类型：
    - 若 version_container 指示 UE5 LWC (file_version_ue5 >= 1004)，返回双精度大小
    - 否则返回单精度大小
    - 若 struct_type 是显式双精度变体（如 "Vector3d"），始终返回双精度大小

    Args:
        struct_type: 结构体类型名（如 "Vector", "Vector3d"）
        version_container: 版本容器（可选）

    Returns:
        预期字节大小，未知类型返回 None
    """
    # 显式双精度变体：直接返回 double 大小，不看版本
    base_for_double = _LWC_DOUBLE_TYPE_TO_BASE.get(struct_type)
    if base_for_double is not None:
        _, double_size = _LWC_TYPE_MAP[base_for_double]
        return double_size

    # 显式单精度变体：直接返回 float 大小，不看版本
    base_for_float = _LWC_FLOAT_TYPE_TO_BASE.get(struct_type)
    if base_for_float is not None:
        float_size, _ = _LWC_TYPE_MAP[base_for_float]
        return float_size

    # LWC 感知的基础类型：根据版本判断
    if struct_type in _LWC_TYPE_MAP:
        float_size, double_size = _LWC_TYPE_MAP[struct_type]
        if version_container is not None and version_container.is_ue5:
            if version_container.file_version_ue5 >= UE5_LARGE_WORLD_COORDINATES:
                return double_size
        return float_size

    # 非 LWC 类型：直接查表
    return _EXPECTED_STRUCT_SIZES.get(struct_type)


_TAGGED_FALLBACK_STRUCTS: set[str] = {
    "MemberReference",
    "SimpleMemberReference",
    # Blueprint 变量描述 struct（ArrayProperty 内层，size=0 时仍需 tagged 解析）
    "FBPVariableDescription",
    "BPVariableDescription",
    "EdGraphPinType",
    "FEdGraphPinType",
    "BPVariableDescriptionHelper",
    # Blueprint 相关 struct
    "ImplementedInterfaces",
    "LastEditedDocuments",
    "CategorySorting",
    # AnimSequence 结构体（部分资产使用 tagged 格式）
    "FrameRate",         # 部分资产 tag.size=37，使用 tagged PropertyTag 格式
    "AnimNotifyTrack",   # 部分资产 tag.size=0，使用 tagged PropertyTag 格式
    # 编辑器结构体
    "FEditorElement",    # 蓝图编辑器组合框选项（DisplayName/Value/bIsDefault）
    "EditorElement",
    # 材质参数结构体（材质实例资产使用 tagged 格式）
    "ScalarParameterValue",
    "FScalarParameterValue",
    "FMaterialParameterInfo",
    # 动画混合空间结构体（部分资产使用 tagged 格式）
    "BlendSample",          # FBlendSample — BlendSpace 采样点（SampleValue/Time/RateScale/bIsValid）
    "FBlendSample",
    # 材质实例参数结构体（MaterialInstanceConstant 资产，tag.size=0 的 tagged 格式）
    "VectorParameterValue",     # FVectorParameterValue — 向量参数（ParameterInfo/ParameterValue）
    "TextureParameterValue",    # FTextureParameterValue — 纹理参数（ParameterInfo/ParameterValue）
    "MaterialTextureInfo",      # FMaterialTextureInfo — 纹理流送信息（UVChannelIndex 等）
}
"""需要 tagged fallback 解析的结构体名称集合。

当结构体属性使用 tagged 格式（PropertyTag 包含类型信息）但无法通过
标准 StructProperty 解析时，使用 _TAGGED_FALLBACK_STRUCT_SCHEMAS 中
定义的字段列表进行回退解析。
"""

_TAGGED_FALLBACK_STRUCT_SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "MemberReference": [("MemberParent", "ObjectProperty"), ("MemberName", "NameProperty"), ("MemberGuid", "GuidProperty")],
    "SimpleMemberReference": [("MemberParent", "ObjectProperty"), ("MemberName", "NameProperty"), ("MemberGuid", "GuidProperty")],
    # 新增 UE5.5 结构体
    "NewVariables": [
        ("VarName", "NameProperty"),
        ("VarGuid", "GuidProperty"),
        ("VarType", "StructProperty"),  # FEdGraphPinType
    ],
    "ImplementedInterfaces": [
        ("InterfaceName", "NameProperty"),
        ("InterfaceGuid", "GuidProperty"),
    ],
    "LastEditedDocuments": [
        ("DocumentName", "NameProperty"),
    ],
    "CategorySorting": [
        ("CategoryName", "NameProperty"),
    ],
    # AnimSequence 结构体 tagged fallback schemas
    "FrameRate": [
        ("Numerator", "IntProperty"),      # UE 源码: int32 Numerator（非 float）
        # Denominator 在部分资产中未被序列化，由 tagged 循环自然处理
    ],
    "AnimNotifyTrack": [
        ("TrackIndex", "Int64Property"),
        ("TrackName", "NameProperty"),
    ],
    # 编辑器结构体
    "FEditorElement": [
        ("DisplayName", "TextProperty"),
        ("Value", "StrProperty"),
        ("bIsDefault", "BoolProperty"),
    ],
    "EditorElement": [
        ("DisplayName", "TextProperty"),
        ("Value", "StrProperty"),
        ("bIsDefault", "BoolProperty"),
    ],
    # 材质参数结构体 tagged fallback schemas
    # FMaterialParameterInfo: FName ParameterName + int32 Index + bool bOverride
    "FMaterialParameterInfo": [
        ("ParameterName", "NameProperty"),
        ("Index", "IntProperty"),
        ("bOverride", "BoolProperty"),
    ],
    # FScalarParameterValue: FMaterialParameterInfo ParameterInfo + float ParameterValue + bool bOverride
    "ScalarParameterValue": [
        ("ParameterInfo", "StructProperty"),   # FMaterialParameterInfo
        ("ParameterValue", "FloatProperty"),
        ("bOverride", "BoolProperty"),
    ],
    "FScalarParameterValue": [
        ("ParameterInfo", "StructProperty"),   # FMaterialParameterInfo
        ("ParameterValue", "FloatProperty"),
        ("bOverride", "BoolProperty"),
    ],
    # 动画混合空间结构体 tagged fallback schemas
    # FBlendSample: FVector SampleValue + float Time + int32 RateScale + bool bIsValid
    # 参考：Engine/Classes/Animation/BlendSpace.h — FBlendSample
    "BlendSample": [
        ("SampleValue", "StructProperty"),   # FVector — 混合空间采样点坐标
        ("Time", "FloatProperty"),            # float — 动画时间值
        ("RateScale", "IntProperty"),         # int32 — 播放速率缩放
        ("bIsValid", "BoolProperty"),         # bool — 采样点是否有效
    ],
    "FBlendSample": [
        ("SampleValue", "StructProperty"),   # FVector — 混合空间采样点坐标
        ("Time", "FloatProperty"),            # float — 动画时间值
        ("RateScale", "IntProperty"),         # int32 — 播放速率缩放
        ("bIsValid", "BoolProperty"),         # bool — 采样点是否有效
    ],
}


# ============================================================================
# Lazy import helpers (avoid circular dependency with property_parser.py)
# ============================================================================

def _get_parse_property_value():
    """Lazy import to avoid circular dependency (parsers <-> property_types)."""
    from uasset_read.parsers.property_parser import parse_property_value
    return parse_property_value


def _get_read_property_tag():
    """Lazy import to avoid circular dependency."""
    from uasset_read.serializers.property_tags import read_property_tag
    return read_property_tag


def _get_read_tag_value_bounded():
    """Lazy import to avoid circular dependency."""
    from uasset_read.serializers.property_tags import read_tag_value_bounded
    return read_tag_value_bounded


def _build_version_container_from_summary(summary: Any) -> Optional["VersionContainer"]:
    """从 summary 构建 VersionContainer（Lazy，避免循环导入）。"""
    if summary is None:
        return None
    # 已缓存则直接返回
    cached = getattr(summary, "_version_container", None)
    if cached is not None:
        return cached
    try:
        from uasset_read.versioning import build_version_container
        vc = build_version_container(summary)
        # 缓存到 summary 上，避免重复构建
        try:
            summary._version_container = vc
        except AttributeError:
            pass
        return vc
    except Exception:
        return None


# ============================================================================
# Basic type parsers (lines 5289-5406 equivalent)
# ============================================================================

def parse_bool_property(tag: PropertyTag, archive: FArchive) -> bool:
    """解析 BoolProperty（PROP-04）。值存储在 tag.bool_val，无额外读取。"""
    return bool(tag.bool_val)


def parse_int_property(tag: PropertyTag, archive: FArchive, name_map: Optional[List[str]] = None) -> Any:
    """解析 IntProperty/Int64Property/Int16Property/Int8Property/ByteProperty（PROP-02）。

    ByteProperty 特殊处理：
    - 无 enum backing：读取 1 byte
    - 有 enum backing (tag.enum_type)：读取 FName (8 bytes)，返回 EnumValue

    参考 ByteProperty/EnumProperty 处理逻辑：
    ByteProperty with enum_type → EnumProperty → ReadFName()
    """
    type_name = tag.type

    # ByteProperty with enum backing: read FName (8 bytes) per
    if type_name == "ByteProperty" and tag.enum_type is not None:
        if name_map is None:
            raise ParseError("ByteProperty with enum backing requires name_map")
        enum_value_name = archive.read_name(name_map)
        return make_enum_value(tag.enum_type, enum_value_name)

    if type_name == "Int64Property":
        return archive.read_i64()
    elif type_name == "Int16Property":
        return archive.read_i16()
    elif type_name in ("Int8Property", "ByteProperty"):
        return archive.read_u8()
    else:  # IntProperty (default)
        return archive.read_i32()


def parse_uint16_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 UInt16Property"""
    return archive.read_u16()


def parse_uint32_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 UInt32Property"""
    return archive.read_u32()


def parse_uint64_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 UInt64Property"""
    return archive.read_u64()


def parse_float_property(tag: PropertyTag, archive: FArchive) -> float:
    """解析 FloatProperty/DoubleProperty（PROP-03）。"""
    type_name = tag.type
    if type_name == "DoubleProperty":
        return archive.read_f64()
    else:  # FloatProperty (default)
        return archive.read_f32()


def parse_str_property(tag: PropertyTag, archive: FArchive) -> str:
    """解析 StrProperty（PROP-05）。"""
    return archive.read_fstring()


def parse_name_property(tag: PropertyTag, archive: FArchive, name_map: List[str]) -> str:
    """解析 NameProperty（PROP-06）。"""
    return archive.read_name(name_map)


def parse_object_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 ObjectProperty（PROP-07）。返回原始 FPackageIndex。"""
    return archive.read_i32()


def parse_soft_object_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    soft_object_path_list: Optional[List[Dict]] = None,
) -> SoftObjectPathValue:
    """解析 SoftObjectProperty（FSoftObjectPath）。

    当 soft_object_path_list 存在时（UE5.7+），读取 int32 索引。
    否则读取 FString 对（传统格式）。
    """
    if soft_object_path_list is not None and len(soft_object_path_list) > 0:
        # UE5.7+ 索引格式
        index = archive.read_i32()
        if 0 <= index < len(soft_object_path_list):
            entry = soft_object_path_list[index]
            return SoftObjectPathValue(
                raw_kind=tag.type,
                asset_path=entry.get('asset_path', ''),
                sub_path=entry.get('sub_path', ''),
                index=index,
            )
        else:
            return SoftObjectPathValue(
                raw_kind=tag.type,
                asset_path='',
                sub_path='',
                index=index,
                error=f"SoftObjectPath index {index} out of bounds (list size {len(soft_object_path_list)})",
            )
    else:
        # 传统 FString 格式
        asset_path = archive.read_fstring()
        sub_path = archive.read_fstring()
        return SoftObjectPathValue(raw_kind=tag.type, asset_path=asset_path, sub_path=sub_path)


def parse_utf8_str_property(tag: PropertyTag, archive: FArchive) -> str:
    """解析 Utf8StrProperty"""
    return archive.read_fstring()


def parse_weak_object_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 WeakObjectProperty"""
    return archive.read_i32()


def parse_lazy_object_property(tag: PropertyTag, archive: FArchive) -> SoftObjectPathValue:
    """解析 LazyObjectProperty"""
    read_size = tag.size if tag.size > 0 else 16
    raw = archive.read_bytes(read_size)
    return SoftObjectPathValue(raw_kind=tag.type, guid=raw.hex())


def parse_class_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 ClassProperty"""
    return archive.read_i32()


def parse_soft_class_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str] = None,
    soft_object_path_list: Optional[List[Dict]] = None,
) -> SoftObjectPathValue:
    """解析 SoftClassProperty — 与 SoftObjectProperty 解析方式相同。"""
    return parse_soft_object_property(tag, archive, name_map or [], soft_object_path_list)


def parse_asset_object_property(tag: PropertyTag, archive: FArchive) -> SoftObjectPathValue:
    """解析 AssetObjectProperty"""
    return SoftObjectPathValue(raw_kind=tag.type, asset_path=archive.read_fstring())


# ============================================================================
# Complex type parsers (lines 5441-6004 equivalent)
# ============================================================================

def parse_array_property(tag: PropertyTag, archive: FArchive, name_map: List[str], export_map: List[Any], summary: Optional[Any] = None, depth: int = 0) -> List[Any]:
    """解析 ArrayProperty（PROP-08, D-16）。

    UE 序列化格式：
      - int32 ArrayCount
      - 对于每个元素，按其类型原生序列化（不是均分 remaining_size）
      - 对于 StructProperty，每个元素都有完整的 FPropertyTag
    """
    MAX_DEPTH = 10

    if depth > MAX_DEPTH:
        raise ParseError(
            f"ArrayProperty nesting depth {depth} exceeds maximum {MAX_DEPTH}"
        )

    count = read_validated_count(archive, MAX_ARRAY_COUNT, "数组数量")
    elements: List[Any] = []
    parse_property_value = _get_parse_property_value()

    if tag.size < 4:
        import logging
        logging.getLogger(__name__).warning(
            "ArrayProperty '%s': tag.size=%d < 4, 无法计算剩余数据大小",
            tag.name, tag.size,
        )
        return elements

    inner_type = getattr(tag, "inner_type", None) or _get_inner_type(tag.type)

    # 对于 StructProperty 类型的数组元素，UE 使用完整的 PropertyTag 序列化
    # 对于其他类型，按类型原生序列化（每个元素大小由类型决定）
    for i in range(count):
        # 创建内部标签，size=0 表示由解析函数自行决定读取多少字节
        inner_tag = PropertyTag(
            name=f"{tag.name}[{i}]",
            type=inner_type,
            size=0  # 让解析函数按类型原生序列化
        )
        # 对于 StructProperty 数组元素，传递 struct_type 使 parse_struct_property 能命中 fast-path
        if inner_type == "StructProperty":
            inner_tag.struct_type = getattr(tag, "inner_type_struct", None)
        inner_value = parse_property_value(inner_tag, archive, name_map, export_map, summary, depth + 1)
        elements.append(inner_value)

    return elements


def parse_struct_property(tag: PropertyTag, archive: FArchive, name_map: List[str], export_map: List[Any], summary: Optional[Any] = None, depth: int = 0) -> StructValue:
    """解析 StructProperty（ADVP-01）。"""
    MAX_DEPTH = 5

    if depth > MAX_DEPTH:
        raise ParseError(
            f"StructProperty nesting depth {depth} exceeds maximum {MAX_DEPTH}"
        )

    struct_type = _extract_struct_type_from_tag(tag)
    declared_struct_type = struct_type

    # Fast-path pre-check: validate tag.size matches expected layout.
    # 使用 get_struct_size 进行版本感知的尺寸验证（支持 LWC 双精度）。
    # 对于 LWC 类型，同时接受 float 和 double 尺寸（fast-path 自行按 tag.size 选择读取精度）。
    version_container = _build_version_container_from_summary(summary)
    expected_size = get_struct_size(struct_type, version_container)
    if expected_size is not None and tag.size != expected_size:
        # Tagged fallback 结构体：size 不匹配是预期行为（tagged 格式 vs 紧凑格式），
        # 静默跳过 fast-path，直接进入 tagged 解析，不产生警告。
        if declared_struct_type in _TAGGED_FALLBACK_STRUCTS:
            struct_type = None  # Skip all fast-path branches
        else:
            # 对于 LWC 类型，检查 tag.size 是否匹配另一种精度
            lwc_entry = _LWC_TYPE_MAP.get(struct_type)
            if lwc_entry is not None:
                float_size, double_size = lwc_entry
                if tag.size not in (float_size, double_size):
                    import logging
                    logging.getLogger(__name__).warning(
                        "StructProperty '%s': tag.size=%d 不匹配 float(%d) 或 double(%d), using fallback",
                        struct_type, tag.size, float_size, double_size,
                    )
                    struct_type = None  # Skip all fast-path branches
            else:
                import logging
                logging.getLogger(__name__).warning(
                    "StructProperty '%s': tag.size=%d != expected=%d, using fallback",
                    struct_type, tag.size, expected_size,
                )
                struct_type = None  # Skip all fast-path branches

    # Handle negative size values gracefully
    if tag.size is not None and tag.size < 0:
        import logging
        logging.getLogger(__name__).warning(
            "StructProperty '%s': negative size %d, treating as unsigned",
            declared_struct_type, tag.size,
        )
        unsigned_size = tag.size & 0xFFFFFFFF
        total = archive.total_size()
        remaining = max(0, total - archive.tell())
        skip_bytes = min(unsigned_size, remaining) if remaining > 0 else 0
        if skip_bytes > 0:
            archive.seek(archive.tell() + skip_bytes)
        return StructValue(
            struct_type=declared_struct_type or "UnknownStruct",
            fields={},
            raw_size=tag.size,
            parse_status="opaque",
        )

    # Fast-path for simple structs (FScriptStruct.cs L174-178)
    # These structs have no PropertyTags loop — just raw float reads.
    if struct_type == "Vector":
        reader = archive.read_f64 if tag.size == 24 else archive.read_f32
        x = reader()
        y = reader()
        z = reader()
        return StructValue(struct_type="Vector", fields={"X": x, "Y": y, "Z": z})

    if struct_type == "Rotator":
        reader = archive.read_f64 if tag.size == 24 else archive.read_f32
        pitch = reader()
        yaw = reader()
        roll = reader()
        return StructValue(struct_type="Rotator", fields={"Pitch": pitch, "Yaw": yaw, "Roll": roll})

    if struct_type == "Vector2D":
        reader = archive.read_f64 if tag.size == 16 else archive.read_f32
        x = reader()
        y = reader()
        return StructValue(struct_type="Vector2D", fields={"X": x, "Y": y})

    # Additional fast-path structs (raw reads, no PropertyTags loop)
    if struct_type == "Vector4":
        if tag.size == 32:
            # UE5.5 LWC: double 精度
            x = archive.read_f64()
            y = archive.read_f64()
            z = archive.read_f64()
            w = archive.read_f64()
        else:
            # 标准 float 精度
            x = archive.read_f32()
            y = archive.read_f32()
            z = archive.read_f32()
            w = archive.read_f32()
        return StructValue(struct_type="Vector4", fields={"X": x, "Y": y, "Z": z, "W": w})

    if struct_type == "LinearColor":
        r = archive.read_f32()
        g = archive.read_f32()
        b = archive.read_f32()
        a = archive.read_f32()
        return StructValue(struct_type="LinearColor", fields={"R": r, "G": g, "B": b, "A": a})

    if struct_type == "Color":
        b = archive.read_u8()
        g = archive.read_u8()
        r = archive.read_u8()
        a = archive.read_u8()
        return StructValue(struct_type="Color", fields={"B": b, "G": g, "R": r, "A": a})

    if struct_type == "Quat":
        reader = archive.read_f64 if tag.size == 32 else archive.read_f32
        x = reader()
        y = reader()
        z = reader()
        w = reader()
        return StructValue(struct_type="Quat", fields={"X": x, "Y": y, "Z": z, "W": w})

    if struct_type == "Plane":
        reader = archive.read_f64 if tag.size == 32 else archive.read_f32
        x = reader()
        y = reader()
        z = reader()
        w = reader()
        return StructValue(struct_type="Plane", fields={"X": x, "Y": y, "Z": z, "W": w})

    if struct_type == "Guid":
        a = archive.read_u32()
        b = archive.read_u32()
        c = archive.read_u32()
        d = archive.read_u32()
        return StructValue(struct_type="Guid", fields={"A": a, "B": b, "C": c, "D": d})

    if struct_type == "IntPoint":
        x = archive.read_i32()
        y = archive.read_i32()
        return StructValue(struct_type="IntPoint", fields={"X": x, "Y": y})

    if struct_type == "IntVector":
        x = archive.read_i32()
        y = archive.read_i32()
        z = archive.read_i32()
        return StructValue(struct_type="IntVector", fields={"X": x, "Y": y, "Z": z})

    if struct_type == "Box2D":
        min_x = archive.read_f32()
        min_y = archive.read_f32()
        max_x = archive.read_f32()
        max_y = archive.read_f32()
        b_valid = archive.read_i32() != 0
        return StructValue(struct_type="Box2D", fields={
            "Min": {"X": min_x, "Y": min_y},
            "Max": {"X": max_x, "Y": max_y},
            "bIsValid": b_valid,
        })

    if struct_type == "Box":
        min_x = archive.read_f32()
        min_y = archive.read_f32()
        min_z = archive.read_f32()
        max_x = archive.read_f32()
        max_y = archive.read_f32()
        max_z = archive.read_f32()
        b_valid = archive.read_i32() != 0
        return StructValue(struct_type="Box", fields={
            "Min": {"X": min_x, "Y": min_y, "Z": min_z},
            "Max": {"X": max_x, "Y": max_y, "Z": max_z},
            "bIsValid": b_valid,
        })

    if struct_type == "Sphere":
        reader = archive.read_f64 if tag.size == 32 else archive.read_f32
        cx = reader()
        cy = reader()
        cz = reader()
        w = reader()
        return StructValue(struct_type="Sphere", fields={
            "Center": {"X": cx, "Y": cy, "Z": cz},
            "W": w,
        })

    if struct_type == "TopLevelAssetPath":
        pkg_name = archive.read_name(name_map)
        asset_name = archive.read_name(name_map)
        return StructValue(struct_type="TopLevelAssetPath", fields={
            "PackageName": pkg_name,
            "AssetName": asset_name,
        })

    if struct_type == "PointerToUberGraphFrame":
        frame_index = archive.read_i64()  # 8 字节 FPackageIndex
        return StructValue(struct_type="PointerToUberGraphFrame", fields={
            "FrameIndex": frame_index,
        })

    if struct_type == "BoxSphereBounds":
        ox = archive.read_f32()
        oy = archive.read_f32()
        oz = archive.read_f32()
        bx = archive.read_f32()
        by = archive.read_f32()
        bz = archive.read_f32()
        sr = archive.read_f32()
        # UE5.5 扩展格式：标准 28 bytes 后可能有额外 padding
        remaining = tag.size - 28
        if remaining > 0:
            archive.read_bytes(remaining)
        return StructValue(struct_type="BoxSphereBounds", fields={
            "Origin": {"X": ox, "Y": oy, "Z": oz},
            "BoxExtent": {"X": bx, "Y": by, "Z": bz},
            "SphereRadius": sr,
        })

    if struct_type == "Matrix":
        matrix = []
        for i in range(4):
            row = [archive.read_f32() for _ in range(4)]
            matrix.append(row)
        return StructValue(struct_type="Matrix", fields={
            "M": matrix,
        })

    if struct_type == "TwoVectors":
        e1_x = archive.read_f32()
        e1_y = archive.read_f32()
        e1_z = archive.read_f32()
        e2_x = archive.read_f32()
        e2_y = archive.read_f32()
        e2_z = archive.read_f32()
        return StructValue(struct_type="TwoVectors", fields={
            "E1": {"X": e1_x, "Y": e1_y, "Z": e1_z},
            "E2": {"X": e2_x, "Y": e2_y, "Z": e2_z},
        })

    if struct_type == "OrientedBox":
        ax_x = archive.read_f32()
        ax_y = archive.read_f32()
        ax_z = archive.read_f32()
        ay_x = archive.read_f32()
        ay_y = archive.read_f32()
        ay_z = archive.read_f32()
        az_x = archive.read_f32()
        az_y = archive.read_f32()
        az_z = archive.read_f32()
        ex = archive.read_f32()
        ey = archive.read_f32()
        ez = archive.read_f32()
        cx = archive.read_f32()
        cy = archive.read_f32()
        cz = archive.read_f32()
        return StructValue(struct_type="OrientedBox", fields={
            "AxisX": {"X": ax_x, "Y": ax_y, "Z": ax_z},
            "AxisY": {"X": ay_x, "Y": ay_y, "Z": ay_z},
            "AxisZ": {"X": az_x, "Y": az_y, "Z": az_z},
            "Extent": {"X": ex, "Y": ey, "Z": ez},
            "Center": {"X": cx, "Y": cy, "Z": cz},
        })

    # Transform: UE5 LWC uses double for FVector components
    if struct_type == "Transform":
        translation_x = archive.read_f64()
        translation_y = archive.read_f64()
        translation_z = archive.read_f64()
        rot_x = archive.read_f32()
        rot_y = archive.read_f32()
        rot_z = archive.read_f32()
        rot_w = archive.read_f32()
        scale_x = archive.read_f32()
        scale_y = archive.read_f32()
        scale_z = archive.read_f32()
        return StructValue(struct_type="Transform", fields={
            "Translation": {"X": translation_x, "Y": translation_y, "Z": translation_z},
            "Rotation": {"X": rot_x, "Y": rot_y, "Z": rot_z, "W": rot_w},
            "Scale3D": {"X": scale_x, "Y": scale_y, "Z": scale_z},
        })

    if declared_struct_type not in _TAGGED_FALLBACK_STRUCTS and tag.size <= 0:
        return StructValue(
            struct_type=declared_struct_type or "UnknownStruct",
            fields={},
            raw_size=tag.size,
            parse_status="opaque",
        )

    # Unknown structs may still be tagged FStructFallback payloads. Try the
    # standard inner PropertyTag loop first, then fall back to opaque bytes.
    fields: Dict[str, Any] = {}
    property_count = 0

    parse_property_value = _get_parse_property_value()
    read_property_tag = _get_read_property_tag()
    read_tag_value_bounded = _get_read_tag_value_bounded()

    # Track expected struct end position for recovery
    struct_start = archive.tell()
    struct_end = struct_start + tag.size if tag.size > 0 else None
    # tag.size=0 的 tagged 格式结构体：无已知边界，使用安全字节上限防止偏移级联
    # （对应 issue #134: PackageIndex out of bounds 的潜在根因之一）
    _MAX_TAGGED_FALLBACK_BYTES = 4096
    tagged_byte_limit = struct_start + _MAX_TAGGED_FALLBACK_BYTES if struct_end is None else None

    try:
        while property_count < MAX_PROPERTY_COUNT:
            property_count += 1

            # 字节安全上限：防止 tag.size=0 时无边界循环吞没后续属性
            if tagged_byte_limit is not None and archive.tell() >= tagged_byte_limit:
                break

            inner_tag = read_property_tag(archive, name_map)

            if inner_tag.name == "None":
                break

            if struct_end is not None and inner_tag.value_end_offset is not None and inner_tag.value_end_offset > struct_end:
                raise ParseError(
                    f"Tagged struct '{declared_struct_type}' field '{inner_tag.name}' "
                    f"size {inner_tag.size} exceeds struct boundary"
                )

            field_value = read_tag_value_bounded(
                archive,
                inner_tag,
                lambda inner_tag=inner_tag: parse_property_value(
                    inner_tag, archive, name_map, export_map, summary, depth + 1
                ),
            )
            fields[inner_tag.name] = field_value
    except Exception:
        if declared_struct_type in _TAGGED_FALLBACK_STRUCTS:
            raise
        if struct_end is not None:
            archive.seek(struct_end)
        elif tag.size > 0:
            archive.seek(struct_start + tag.size)
        return StructValue(
            struct_type=declared_struct_type or "UnknownStruct",
            fields={},
            raw_size=tag.size,
            parse_status="opaque",
        )

    if struct_end is not None and archive.tell() != struct_end:
        archive.seek(struct_end)

    return StructValue(
        struct_type=declared_struct_type,
        fields=fields,
        raw_size=tag.size,
        parse_status="parsed",
    )


def parse_map_property(tag: PropertyTag, archive: FArchive, name_map: List[str], export_map: List[Any], summary: Optional[Any] = None) -> MapValue:
    """解析 MapProperty（ADVP-02）。

    UE 序列化格式：
      - int32 numKeysToRemove（待删除的键数量）
      - int32 numEntries（实际条目数量）
      - 循环读取 key-value 对
    """
    key_type = getattr(tag, "key_type", None)
    value_type = getattr(tag, "value_type", None)
    if not key_type or not value_type:
        key_type, value_type = _extract_map_types_from_tag(tag)

    # 读取待删除的键数量（UE 源码中用于增量更新）
    num_keys_to_remove = read_validated_count(archive, MAX_PROPERTY_COUNT, "MapProperty 待删除键数量")
    # 跳过待删除的键（按 key_type 序列化）
    for _ in range(num_keys_to_remove):
        _dispatch_key_parse(key_type, archive, name_map, export_map, summary)

    # 读取实际条目数量
    num_entries = read_validated_count(archive, MAX_PROPERTY_COUNT, "MapProperty 条目数量")
    entries: List[Dict[str, Any]] = []

    for _ in range(num_entries):
        key = _dispatch_key_parse(key_type, archive, name_map, export_map, summary)
        value = _dispatch_value_parse(value_type, archive, name_map, export_map, summary)
        entries.append({"key": key, "value": value})

    return MapValue(
        key_type=key_type,
        value_type=value_type,
        entries=entries
    )


def parse_set_property(tag: PropertyTag, archive: FArchive, name_map: List[str], export_map: List[Any], summary: Optional[Any] = None) -> SetValue:
    """解析 SetProperty（ADVP-03）。

    UE 序列化格式：
      - int32 numElementsToRemove（待删除元素数量）
      - int32 numElements（实际元素数量）
      - 循环读取元素
    """
    element_type = getattr(tag, "inner_type", None) or _extract_set_type_from_tag(tag)

    # 读取待删除的元素数量（UE 源码中用于增量更新）
    num_elements_to_remove = read_validated_count(archive, MAX_PROPERTY_COUNT, "SetProperty 待删除元素数量")
    # 跳过待删除的元素（按 element_type 序列化）
    parse_property_value = _get_parse_property_value()
    for _ in range(num_elements_to_remove):
        dummy_tag = PropertyTag(name="RemovedElement", type=element_type, size=0)
        parse_property_value(dummy_tag, archive, name_map, export_map, summary, depth=0)

    # 读取实际元素数量
    num_elements = read_validated_count(archive, MAX_PROPERTY_COUNT, "SetProperty 元素数量")
    elements: List[Any] = []

    for _ in range(num_elements):
        dummy_tag = PropertyTag(name="Element", type=element_type, size=0)
        element = parse_property_value(dummy_tag, archive, name_map, export_map, summary, depth=0)
        elements.append(element)

    return SetValue(
        element_type=element_type,
        elements=elements
    )


def parse_enum_property(tag: PropertyTag, archive: FArchive, name_map: List[str], summary: Optional[Any] = None) -> EnumValue:
    """解析 EnumProperty（ADVP-04）。"""
    enum_type = _extract_enum_type_from_tag(tag)
    enum_value_name = archive.read_name(name_map)
    return make_enum_value(enum_type, enum_value_name)


def _read_ftext_base(archive: FArchive) -> tuple[str, str, str]:
    """读取 Base FText: namespace + key + source_string。"""
    namespace = archive.read_fstring()
    key = archive.read_fstring()
    source_string = archive.read_fstring()
    return namespace, key, source_string


def _read_ftext_args(archive: FArchive) -> None:
    """读取 FText 参数字典并丢弃（仅消耗字节）。"""
    from uasset_read.parsers.utils import read_validated_count
    count = read_validated_count(archive, 10_000, "FText args")
    for _ in range(count):
        archive.read_fstring()  # key
        archive.read_fstring()  # value

def parse_text_property(tag: PropertyTag, archive: FArchive) -> TextValue:
    """解析 TextProperty（ADVP-05）。

    UE FText 序列化格式:
      - flags: i32 (4 bytes)
      - history_type: u8 (1 byte) — FTextHistory 类型标识
      - body: 根据 history_type 不同而不同
        - history_type == 0 (Base): namespace + key + source_string
        - history_type == 1 (NamedFormat): namespace + key + args
        - history_type == 2 (OrderedFormat): namespace + key + source_string + args
        - history_type == 3 (ArgumentFormat): namespace + key + source_string + args
        - history_type == 4-9 (AsNumber/AsPercent/AsCurrency/Date/Time/DateTime): namespace + key + source_string + value
        - history_type == 10 (Transform): namespace + key + source_string + transform_type
    """
    _flags = archive.read_i32()       # FText flags (unused)
    history_type = archive.read_u8() # FTextHistory type

    if history_type == 0:  # Base
        namespace, key, source_string = _read_ftext_base(archive)
    elif history_type == 1:  # NamedFormat
        namespace = archive.read_fstring()
        key = archive.read_fstring()
        _read_ftext_args(archive)
        source_string = ""
    elif history_type == 2:  # OrderedFormat
        namespace, key, source_string = _read_ftext_base(archive)
        _read_ftext_args(archive)
    elif history_type == 3:  # ArgumentFormat
        namespace, key, source_string = _read_ftext_base(archive)
        _read_ftext_args(archive)
    elif history_type == 4:  # AsNumber
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # target_number
    elif history_type == 5:  # AsPercent
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # target_value
    elif history_type == 6:  # AsCurrency
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # currency_code
        archive.read_fstring()  # target_amount
    elif history_type == 7:  # DateString
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # date
    elif history_type == 8:  # TimeString
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # time
    elif history_type == 9:  # DateTimeString
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # datetime
    elif history_type == 10:  # Transform
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # transform_type
    else:
        # Unknown history type: skip remaining data
        remaining = tag.size - 5  # 5 = flags(4) + history_type(1)
        if remaining > 0:
            archive.read(remaining)
        namespace = ""
        key = ""
        source_string = ""

    return TextValue(
        namespace=namespace or "",
        key=key or "",
        source_string=source_string or ""
    )


def parse_delegate_property(tag: PropertyTag, archive: FArchive, name_map: List[str]) -> DelegateValue:
    """解析 DelegateProperty（ADVP-06）。"""
    object_ref = archive.read_i32()
    function_name = archive.read_name(name_map)

    return DelegateValue(
        object_ref=object_ref,
        function_name=function_name
    )


# ============================================================================
# Multicast delegate type parsers
# ============================================================================

def parse_multicast_delegate_property(tag: PropertyTag, archive: FArchive) -> list:
    """解析 MulticastDelegateProperty"""
    from uasset_read.parsers.utils import read_validated_count
    count = read_validated_count(archive, 10_000, "MulticastDelegate")
    delegates = []
    for _ in range(count):
        obj_index = archive.read_i32()
        func_name = archive.read_fstring()
        delegates.append({"object": obj_index, "function": func_name})
    return delegates


def parse_multicast_inline_delegate_property(tag: PropertyTag, archive: FArchive) -> list:
    """解析 MulticastInlineDelegateProperty"""
    return parse_multicast_delegate_property(tag, archive)


def parse_multicast_sparse_delegate_property(tag: PropertyTag, archive: FArchive) -> list:
    """解析 MulticastSparseDelegateProperty"""
    return parse_multicast_delegate_property(tag, archive)


# ============================================================================
# Special type parsers
# ============================================================================

def parse_interface_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 InterfaceProperty"""
    return archive.read_i32()


def parse_field_path_property(tag: PropertyTag, archive: FArchive) -> dict:
    """解析 FieldPathProperty"""
    from uasset_read.parsers.utils import read_validated_count
    count = read_validated_count(archive, 10_000, "FieldPath")
    path = []
    for _ in range(count):
        path.append(archive.read_fstring())
    return {"path": path}


def parse_optional_property(tag: PropertyTag, archive: FArchive, name_map: List[str] = None, export_map: List[Any] = None, summary: Optional[Any] = None) -> dict:
    """解析 OptionalProperty"""
    has_value = archive.read_bool()
    if has_value:
        parse_property_value = _get_parse_property_value()
        inner_type = getattr(tag, "inner_type", None) or "Unknown"
        inner_tag = PropertyTag(
            name=f"{tag.name}.Value",
            type=inner_type,
            size=max(0, (tag.size or 0) - 4),
        )
        inner_value = parse_property_value(inner_tag, archive, name_map or [], export_map or [], summary)
        return {"has_value": True, "value": inner_value}
    return {"has_value": False, "value": None}


# ============================================================================
# Verse language type parsers
# ============================================================================

def parse_verse_string_property(tag: PropertyTag, archive: FArchive) -> str:
    """解析 VerseStringProperty"""
    return archive.read_fstring()


def parse_verse_class_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 VerseClassProperty"""
    return archive.read_i32()


def parse_verse_function_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 VerseFunctionProperty"""
    return archive.read_i32()


def parse_verse_dynamic_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 VerseDynamicProperty"""
    return archive.read_i32()


def parse_ansi_str_property(tag: PropertyTag, archive: FArchive) -> str:
    """解析 AnsiStrProperty — UE4/老版本资产中的 ANSI 字符串。

    与 FString 使用相同的长度前缀格式，但内容以 Latin-1 解码而非 UTF-8/UTF-16。
    """
    return archive.read_fstring()  # read_fstring 已经处理长度前缀字符串


def parse_verse_cell_property(tag: PropertyTag, archive: FArchive) -> dict:
    """解析 VerseCellProperty（UE5.6+ Verse 脚本系统）。

    VerseCell 引用指向 Verse 文件中的单元格，序列化格式为 PackageIndex + 名称索引。
    当前返回原始引用值，完整解析需要 Verse 文件系统。
    """
    start = archive.tell()
    package_index = archive.read_i32() if tag.size >= 4 else 0
    name_index = archive.read_i32() if tag.size >= 8 else -1
    consumed = archive.tell() - start
    raw = archive.read_bytes(tag.size - consumed) if tag.size > consumed else b""
    return {
        "kind": "VerseCellProperty",
        "ref": {"package_index": package_index, "name_index": name_index},
        "raw": raw,
    }


def parse_verse_value_property(tag: PropertyTag, archive: FArchive) -> dict:
    """解析 VerseValueProperty（UE5.6+ Verse 脚本系统）。

    VerseValue 是 Verse 类型系统的运行时值容器，序列化包含类型标签 + 值。
    当前读取类型标签和原始数据，完整解析需要 Verse 类型系统知识。
    """
    start = archive.tell()
    type_tag = archive.read_u8() if tag.size >= 1 else 0
    value_data = None
    try:
        if tag.size > 1:
            value_data = archive.read_fstring()
    except Exception:
        archive.seek(start + 1)
    consumed = archive.tell() - start
    raw = archive.read_bytes(tag.size - consumed) if tag.size > consumed else b""
    return {
        "kind": "VerseValueProperty",
        "type_tag": type_tag,
        "value": value_data,
        "raw": raw,
    }


def parse_double_property(tag: PropertyTag, archive: FArchive) -> float:
    """解析 DoubleProperty（独立解析器）。"""
    return archive.read_f64()


def parse_guid_property(tag: PropertyTag, archive: FArchive) -> str:
    """解析 GuidProperty — FGuid 结构体（16 字节）。

    返回标准十六进制字符串格式的 GUID，如 "A1B2C3D4-E5F6-...".
    """
    data = archive.read_bytes(16)
    # 标准 GUID 格式: 8-4-4-4-12 十六进制
    return (
        f"{data[0]:02x}{data[1]:02x}{data[2]:02x}{data[3]:02x}-"
        f"{data[4]:02x}{data[5]:02x}-"
        f"{data[6]:02x}{data[7]:02x}-"
        f"{data[8]:02x}{data[9]:02x}-"
        f"{data[10]:02x}{data[11]:02x}{data[12]:02x}{data[13]:02x}{data[14]:02x}{data[15]:02x}"
    )


# ============================================================================
# TypeName extraction helpers (lines 5517-5641 equivalent)
# ============================================================================

def _get_inner_type(array_type: str) -> str:
    """从 ArrayProperty 类型名推断内部元素类型。

    支持基本的类型映射，从 UE5 完整类型名格式（如 ArrayProperty(IntProperty)）
    或带下划线的类型名推断内部类型。
    """
    # 尝试从括号格式提取：ArrayProperty(IntProperty) -> IntProperty
    if "(" in array_type and ")" in array_type:
        start = array_type.find("(")
        end = array_type.find(")")
        inner = array_type[start + 1:end].strip()
        # 处理带路径的类型：/Script/CoreUObject.IntProperty -> IntProperty
        if "." in inner:
            inner = inner.split(".")[-1]
        return inner

    # 基本类型映射（用于下划线分隔的类型名）
    type_mapping = {
        "ArrayProperty_IntProperty": "IntProperty",
        "ArrayProperty_FloatProperty": "FloatProperty",
        "ArrayProperty_StrProperty": "StrProperty",
        "ArrayProperty_StructProperty": "StructProperty",
        "ArrayProperty_ObjectProperty": "ObjectProperty",
        "ArrayProperty_NameProperty": "NameProperty",
        "ArrayProperty_BoolProperty": "BoolProperty",
        "ArrayProperty_ByteProperty": "ByteProperty",
        "ArrayProperty_Int64Property": "Int64Property",
        "ArrayProperty_DoubleProperty": "DoubleProperty",
        "ArrayProperty_TextProperty": "TextProperty",
        "ArrayProperty_SoftObjectProperty": "SoftObjectProperty",
        "ArrayProperty_EnumProperty": "EnumProperty",
    }
    return type_mapping.get(array_type, "IntProperty")


def _extract_struct_type_from_tag(tag: PropertyTag) -> str:
    """从 PropertyTag 提取结构体类型名（D-08）。"""
    if getattr(tag, "struct_type", None):
        return str(tag.struct_type).split(".")[-1]

    inner = extract_inner_from_tag(tag.type)
    if inner is not None:
        if "." in inner:
            return inner.split(".")[-1]
        return inner

    return "UnknownStruct"


def _extract_map_types_from_tag(tag: PropertyTag) -> Tuple[str, str]:
    """从 PropertyTag 提取 Map Key/Value 类型（D-08）。"""
    inner = extract_inner_from_tag(tag.type)
    if inner is not None:
        parts = inner.split(",", 1)  # split on first comma only (type names may contain commas)
        if len(parts) >= 2:
            return parts[0].strip(), parts[1].strip()

    return "IntProperty", "IntProperty"


def _extract_set_type_from_tag(tag: PropertyTag) -> str:
    """从 PropertyTag 提取 Set 元素类型（D-08）。"""
    inner = extract_inner_from_tag(tag.type)
    if inner is not None:
        return inner.strip()

    return "IntProperty"


def _extract_enum_type_from_tag(tag: PropertyTag) -> str:
    """从 PropertyTag 提取枚举类型名（D-08）。"""
    inner = extract_inner_from_tag(tag.type)
    if inner is not None:
        if "." in inner:
            return inner.split(".")[-1]
        return inner

    return "UnknownEnum"


# ============================================================================
# Internal dispatch helpers for MapProperty (lines 5773-5841 equivalent)
# ============================================================================

def _dispatch_key_parse(key_type: str, archive: FArchive, name_map: List[str], export_map: List[Any], summary: Optional[Any] = None) -> Any:
    """键类型分派解析（D-02b）。"""
    basic_types = [
        "IntProperty", "Int64Property", "FloatProperty", "DoubleProperty",
        "StrProperty", "NameProperty", "BoolProperty", "ByteProperty",
        "UInt16Property", "UInt32Property", "UInt64Property",
    ]
    if key_type in basic_types:
        dummy_tag = PropertyTag(name="Key", type=key_type, size=0)
        parse_property_value = _get_parse_property_value()
        return parse_property_value(dummy_tag, archive, name_map, export_map, summary, depth=0)

    if key_type == "ObjectProperty":
        return archive.read_i32()

    if key_type == "EnumProperty":
        return archive.read_name(name_map)

    return None


def _dispatch_value_parse(value_type: str, archive: FArchive, name_map: List[str], export_map: List[Any], summary: Optional[Any] = None) -> Any:
    """值类型分派解析。"""
    dummy_tag = PropertyTag(name="Value", type=value_type, size=0)
    parse_property_value = _get_parse_property_value()
    return parse_property_value(dummy_tag, archive, name_map, export_map, summary, depth=0)


# ============================================================================
# 默认值解析（等价迁移 uasset_read.py §4650-4704）
# ============================================================================

def parse_default_value(value_str: str, var_type: FEdGraphPinType) -> Any:
    """
    解析 DefaultValue 字符串到 Python 原生类型（BLUE-03）。

    Per D-13: 解析为 int, float, bool, str。
    Per D-14: 解析失败时回退到原始字符串。
    Per D-15: 仅基本类型 — 无数组、向量、对象。
    Per D-16: Vector 类型保持为字符串 "(X=...,Y=...,Z=...)"。
    """
    if not value_str:
        return None

    # 检查向量格式，保持为字符串
    if value_str.startswith("(") and value_str.endswith(")"):
        return value_str

    # 使用 PinCategory 进行类型检测
    category = var_type.pin_category.lower()

    # 布尔解析
    if category in ("bool", "boolean"):
        if value_str.lower() in ("true", "1"):
            return True
        elif value_str.lower() in ("false", "0"):
            return False
        return value_str

    # 整数解析
    if category in ("int", "integer"):
        if re.match(r'^-?\d+$', value_str):
            return int(value_str)
        return value_str

    # 浮点/实数解析
    if category in ("float", "real", "double"):
        if re.match(r'^-?\d+\.?\d*$', value_str):
            return float(value_str)
        return value_str

    # 字符串/名称：保持原样
    if category in ("string", "name", "text"):
        return value_str

    # 未知类别：回退到原始字符串
    return value_str


# ============================================================================
# 变量类型格式化（等价迁移 uasset_read.py §4829-4907）
# ============================================================================

def format_variable_type(pin_type: FEdGraphPinType, name_map: List[str] = None) -> str:
    """
    将 FEdGraphPinType 格式化为完整类型字符串（per D-04）。

    处理：基本类型、容器类型（TArray/TSet/TMap）、引用类型、const 类型。
    """
    # Container type prefix
    container_prefix = ""
    container_type = getattr(pin_type, 'container_type', 0)
    if container_type == 1:  # Array
        container_prefix = "TArray<"
    elif container_type == 2:  # Set
        container_prefix = "TSet<"
    elif container_type == 3:  # Map
        container_prefix = "TMap<"

    # Base type from PinCategory
    category = pin_type.pin_category.lower()
    sub_category = getattr(pin_type, 'pin_subcategory', '') or getattr(pin_type, 'pin_sub_category', '') or ''
    sub_category = sub_category.lower()

    # Type mapping
    type_str = ""
    if category in ("bool", "boolean"):
        type_str = "bool"
    elif category in ("int", "integer"):
        type_str = "int"
    elif category in ("float", "real", "double"):
        type_str = "float"
    elif category in ("string", "str"):
        type_str = "FString"
    elif category in ("name",):
        type_str = "FName"
    elif category in ("text",):
        type_str = "FText"
    elif category in ("object", "class", "interface"):
        pin_subcategory_object = getattr(pin_type, 'pin_subcategory_object', 0)
        if pin_subcategory_object != 0 and name_map:
            if sub_category and sub_category != "none":
                type_str = sub_category
            else:
                type_str = "UObject"
        else:
            type_str = "UObject"
        is_weak = getattr(pin_type, 'is_weak_pointer', False)
        if not is_weak:
            type_str += "*"
    elif sub_category and sub_category != "none":
        type_str = sub_category
        if category in ("object", "class") or "object" in category:
            type_str += "*"
    else:
        type_str = category

    # Container suffix
    container_suffix = ">" if container_prefix else ""

    # Const prefix (backward compat: is_const may not exist)
    const_prefix = ""
    if getattr(pin_type, 'is_const', False):
        const_prefix = "const "

    return f"{const_prefix}{container_prefix}{type_str}{container_suffix}"

