"""标量属性类型解析函数 — int, float, bool, byte, enum 等基础类型。

从原 property_types.py 拆分出的标量类型解析器集合。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Any, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.versioning import VersionContainer

from uasset_read.models.properties import (
    PropertyTag, EnumValue,
)
from uasset_read.parsers.utils import make_enum_value


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
    "FrameRate": 8,          # float Numerator + int32 Denominator（紧凑格式）
                             # 部分资产使用 tagged 格式（size=37），通过 tagged fallback 解析
    "AnimNotifyTrack": 8,    # 紧凑格式大小
                             # 部分资产使用 tagged 格式（size=0），通过 tagged fallback 解析
    "GuidProperty": 16,      # FGuid 标准大小
}


# LWC（Large World Coordinates）类型映射
# UE5 UE5_LARGE_WORLD_COORDINATES(1004) 起，数学向量类型使用 double 精度。
_LWC_TYPE_MAP: dict[str, tuple[int, int]] = {
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
    "Transform":     (48, 96),   # FQuat(16/32) + FVector(12/24) + FVector(12/24) + padding(8/16)
}

# LWC 双精度类型名 → 对应的基础类型名
_LWC_DOUBLE_TYPE_TO_BASE: dict[str, str] = {
    "Vector3d":    "Vector",
    "Vector4d":    "Vector4",
    "Rotator3d":   "Rotator",
    "Quat4d":      "Quat",
    "Plane4d":     "Plane",
    "Sphere3d":    "Sphere",
}

# LWC 单精度类型名 → 对应的基础类型名
_LWC_FLOAT_TYPE_TO_BASE: dict[str, str] = {
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
            if version_container.file_version_ue5 >= 1004:  # UE5_LARGE_WORLD_COORDINATES
                return double_size
        return float_size

    # 非 LWC 类型：直接查表
    return _EXPECTED_STRUCT_SIZES.get(struct_type)


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
            raise ValueError("ByteProperty with enum backing requires name_map")
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


def parse_double_property(tag: PropertyTag, archive: FArchive) -> float:
    """解析 DoubleProperty（独立解析器）。"""
    return archive.read_f64()


def parse_str_property(tag: PropertyTag, archive: FArchive) -> str:
    """解析 StrProperty（PROP-05）。"""
    return archive.read_fstring()


def parse_utf8_str_property(tag: PropertyTag, archive: FArchive) -> str:
    """解析 Utf8StrProperty"""
    return archive.read_fstring()


def parse_ansi_str_property(tag: PropertyTag, archive: FArchive) -> str:
    """解析 AnsiStrProperty — UE4/老版本资产中的 ANSI 字符串。

    与 FString 使用相同的长度前缀格式，但内容以 Latin-1 解码而非 UTF-8/UTF-16。
    """
    return archive.read_fstring()


def parse_name_property(tag: PropertyTag, archive: FArchive, name_map: List[str]) -> str:
    """解析 NameProperty（PROP-06）。"""
    return archive.read_name(name_map)


def parse_enum_property(tag: PropertyTag, archive: FArchive, name_map: List[str], summary: Optional[Any] = None) -> EnumValue:
    """解析 EnumProperty（ADVP-04）。"""
    from uasset_read.parsers.property_types.text_delegate import _extract_enum_type_from_tag
    enum_type = _extract_enum_type_from_tag(tag)
    enum_value_name = archive.read_name(name_map)
    return make_enum_value(enum_type, enum_value_name)


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
