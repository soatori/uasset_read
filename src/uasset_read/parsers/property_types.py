"""属性类型解析函数 — 14 种 parse_*_property 函数及 TypeName 提取辅助函数。

等价迁移 uasset_read.py 第 5289-6004 行。
Phase 30: 属性解析模块 (per MOD-07, MOD-09, D-04)。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Dict, Any, Optional, Tuple
import re

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.models.properties import (
    PropertyTag, PropertyValue,
    StructValue, MapValue, SetValue, EnumValue, TextValue, DelegateValue,
)
from uasset_read.models.core import FEdGraphPinType
from uasset_read.exceptions import ParseError
from uasset_read.constants import MAX_PROPERTY_COUNT, MAX_ARRAY_COUNT


# Expected byte sizes for fixed-layout structs (used for fast-path validation)
_EXPECTED_STRUCT_SIZES: dict[str, int] = {
    "Vector": 12, "Rotator": 12, "Vector2D": 8, "Vector4": 16,
    "LinearColor": 16, "Color": 4, "Quat": 16, "Plane": 16,
    "Guid": 16, "IntPoint": 8, "IntVector": 12,
    "Box2D": 20, "Box": 28, "Sphere": 16, "BoxSphereBounds": 40,
    "Matrix": 64, "TwoVectors": 24, "OrientedBox": 60,
    "Transform": 48,
    "TopLevelAssetPath": 16,
}


_TAGGED_FALLBACK_STRUCTS: set[str] = {
    "MemberReference",
    "SimpleMemberReference",
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

    参考 CUE4Parse ByteProperty/EnumProperty 处理逻辑：
    ByteProperty with enum_type → EnumProperty → ReadFName()
    """
    type_name = tag.type

    # ByteProperty with enum backing: read FName (8 bytes) per CUE4Parse
    if type_name == "ByteProperty" and tag.enum_type is not None:
        if name_map is None:
            raise ParseError("ByteProperty with enum backing requires name_map")
        enum_value_name = archive.read_name(name_map)
        value_name = f"{tag.enum_type}::{enum_value_name}"
        return EnumValue(
            enum_type=tag.enum_type,
            value_name=value_name
        )

    if type_name == "Int64Property":
        return archive.read_i64()
    elif type_name == "Int16Property":
        return archive.read_i16()
    elif type_name in ("Int8Property", "ByteProperty"):
        return archive.read_u8()
    else:  # IntProperty (default)
        return archive.read_i32()


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


def parse_soft_object_property(tag: PropertyTag, archive: FArchive, name_map: List[str]) -> Dict[str, str]:
    """解析 SoftObjectProperty（FSoftObjectPath）。"""
    asset_path = archive.read_fstring()
    sub_path = archive.read_fstring()
    return {
        "asset_path": asset_path,
        "sub_path": sub_path
    }


# ============================================================================
# Complex type parsers (lines 5441-6004 equivalent)
# ============================================================================

def parse_array_property(tag: PropertyTag, archive: FArchive, name_map: List[str], export_map: List[Any], summary: Optional[Any] = None, depth: int = 0) -> List[Any]:
    """解析 ArrayProperty（PROP-08, D-16）。"""
    MAX_DEPTH = 10

    if depth > MAX_DEPTH:
        raise ParseError(
            f"ArrayProperty nesting depth {depth} exceeds maximum {MAX_DEPTH}"
        )

    count = archive.read_i32()
    if count < 0 or count > MAX_ARRAY_COUNT:
        raise ParseError(
            f"ArrayProperty count {count} out of range [0, {MAX_ARRAY_COUNT}]"
        )
    elements: List[Any] = []
    parse_property_value = _get_parse_property_value()
    remaining_size = tag.size - 4  # subtract 4-byte count field
    inner_type = getattr(tag, "inner_type", None) or _get_inner_type(tag.type)

    for i in range(count):
        # Dynamic inner_size calculation: distribute remaining bytes evenly
        # Last element gets all remaining size to avoid precision loss
        remaining_count = count - i
        inner_size = remaining_size // remaining_count if remaining_count > 1 else remaining_size
        inner_tag = PropertyTag(
            name=f"{tag.name}[{i}]",
            type=inner_type,
            size=inner_size
        )
        element_start = archive.tell()
        inner_value = parse_property_value(inner_tag, archive, name_map, export_map, summary, depth + 1)
        elements.append(inner_value)
        # Track bytes consumed to update remaining_size
        bytes_consumed = archive.tell() - element_start
        remaining_size -= bytes_consumed

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
    # UE5 LWC stores some math structs as doubles, so accept those explicitly.
    # If mismatch, fall through to PropertyTag loop (generic path)
    expected_size = _EXPECTED_STRUCT_SIZES.get(struct_type)
    allowed_lwc_sizes = {
        "Vector": {12, 24},
        "Rotator": {12, 24},
        "Vector2D": {8, 16},
    }
    if expected_size is not None and tag.size != expected_size and tag.size not in allowed_lwc_sizes.get(struct_type, set()):
        import logging
        logging.getLogger(__name__).warning(
            "StructProperty '%s': tag.size=%d != expected=%d, using fallback",
            struct_type, tag.size, expected_size,
        )
        struct_type = None  # Skip all fast-path branches

    # Phase 72g M-01: Fast-path for simple structs (CUE4Parse FScriptStruct.cs L174-178)
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

    # Phase 76 COR-01: Additional fast-path structs (raw reads, no PropertyTags loop)
    if struct_type == "Vector4":
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
        x = archive.read_f32()
        y = archive.read_f32()
        z = archive.read_f32()
        w = archive.read_f32()
        return StructValue(struct_type="Quat", fields={"X": x, "Y": y, "Z": z, "W": w})

    if struct_type == "Plane":
        x = archive.read_f32()
        y = archive.read_f32()
        z = archive.read_f32()
        w = archive.read_f32()
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
        cx = archive.read_f32()
        cy = archive.read_f32()
        cz = archive.read_f32()
        w = archive.read_f32()
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

    if declared_struct_type not in _TAGGED_FALLBACK_STRUCTS:
        if tag.size > 0:
            archive.seek(archive.tell() + tag.size)
        return StructValue(
            struct_type=declared_struct_type or "UnknownStruct",
            fields={},
            raw_size=tag.size,
            parse_status="opaque",
        )

    # Only known tagged fallback structs use an inner PropertyTag loop.
    fields: Dict[str, Any] = {}
    property_count = 0

    parse_property_value = _get_parse_property_value()
    read_property_tag = _get_read_property_tag()
    read_tag_value_bounded = _get_read_tag_value_bounded()

    # Phase 73 Wave 4: Track expected struct end position for recovery
    struct_start = archive.tell()
    struct_end = struct_start + tag.size if tag.size > 0 else None

    while property_count < MAX_PROPERTY_COUNT:
        property_count += 1

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

    if struct_end is not None and archive.tell() != struct_end:
        archive.seek(struct_end)

    return StructValue(
        struct_type=declared_struct_type,
        fields=fields,
        raw_size=tag.size,
        parse_status="parsed",
    )


def parse_map_property(tag: PropertyTag, archive: FArchive, name_map: List[str], export_map: List[Any], summary: Optional[Any] = None) -> MapValue:
    """解析 MapProperty（ADVP-02）。"""
    key_type = getattr(tag, "key_type", None)
    value_type = getattr(tag, "value_type", None)
    if not key_type or not value_type:
        key_type, value_type = _extract_map_types_from_tag(tag)

    num_entries = archive.read_i32()
    if num_entries < 0 or num_entries > MAX_PROPERTY_COUNT:
        raise ParseError(
            f"MapProperty entries count {num_entries} out of range [0, {MAX_PROPERTY_COUNT}]"
        )
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
    """解析 SetProperty（ADVP-03）。"""
    element_type = getattr(tag, "inner_type", None) or _extract_set_type_from_tag(tag)

    num_elements = archive.read_i32()
    if num_elements < 0 or num_elements > MAX_PROPERTY_COUNT:
        raise ParseError(
            f"SetProperty elements count {num_elements} out of range [0, {MAX_PROPERTY_COUNT}]"
        )
    elements: List[Any] = []
    parse_property_value = _get_parse_property_value()

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
    value_name = f"{enum_type}::{enum_value_name}"

    return EnumValue(
        enum_type=enum_type,
        value_name=value_name
    )


def parse_text_property(tag: PropertyTag, archive: FArchive) -> TextValue:
    """解析 TextProperty（ADVP-05）。

    UE FText 序列化格式:
      - flags: i32 (4 bytes)
      - history_type: u8 (1 byte) — FTextHistory 类型标识
      - body: 根据 history_type 不同而不同
        - history_type == 0 (Base): namespace(FString) + key(FString) + source_string(FString)
        - history_type == 1 (NamedString): namespace(FString) + key(FString)
        - 其他: 跳过剩余数据
    """
    flags = archive.read_i32()       # FText flags
    history_type = archive.read_u8() # FTextHistory type

    if history_type == 0:
        # Base text: namespace + key + source_string
        namespace = archive.read_fstring()
        key = archive.read_fstring()
        source_string = archive.read_fstring()
    elif history_type == 1:
        # NamedString: namespace + key (no source_string)
        namespace = archive.read_fstring()
        key = archive.read_fstring()
        source_string = ""
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

    type_str = tag.type

    if "(" in type_str:
        start = type_str.find("(")
        end = type_str.find(")")
        if start != -1 and end != -1:
            struct_path = type_str[start + 1:end]
            if "." in struct_path:
                return struct_path.split(".")[-1]
            return struct_path

    return "UnknownStruct"


def _extract_map_types_from_tag(tag: PropertyTag) -> Tuple[str, str]:
    """从 PropertyTag 提取 Map Key/Value 类型（D-08）。"""
    type_str = tag.type

    if "(" in type_str:
        start = type_str.find("(")
        end = type_str.find(")")
        if start != -1 and end != -1:
            params = type_str[start + 1:end]
            parts = params.split(",", 1)  # split on first comma only (type names may contain commas)
            if len(parts) >= 2:
                return parts[0].strip(), parts[1].strip()

    return "IntProperty", "IntProperty"


def _extract_set_type_from_tag(tag: PropertyTag) -> str:
    """从 PropertyTag 提取 Set 元素类型（D-08）。"""
    type_str = tag.type

    if "(" in type_str:
        start = type_str.find("(")
        end = type_str.find(")")
        if start != -1 and end != -1:
            return type_str[start + 1:end].strip()

    return "IntProperty"


def _extract_enum_type_from_tag(tag: PropertyTag) -> str:
    """从 PropertyTag 提取枚举类型名（D-08）。"""
    type_str = tag.type

    if "(" in type_str:
        start = type_str.find("(")
        end = type_str.find(")")
        if start != -1 and end != -1:
            enum_path = type_str[start + 1:end]
            if "." in enum_path:
                return enum_path.split(".")[-1]
            return enum_path

    return "UnknownEnum"


# ============================================================================
# Internal dispatch helpers for MapProperty (lines 5773-5841 equivalent)
# ============================================================================

def _dispatch_key_parse(key_type: str, archive: FArchive, name_map: List[str], export_map: List[Any], summary: Optional[Any] = None) -> Any:
    """键类型分派解析（D-02b）。"""
    basic_types = [
        "IntProperty", "Int64Property", "FloatProperty", "DoubleProperty",
        "StrProperty", "NameProperty", "BoolProperty", "ByteProperty"
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
    将 FEdGraphPinType 格式化为完整类型字符串（Phase 12, per D-04）。

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
