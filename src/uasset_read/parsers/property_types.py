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


# ============================================================================
# Basic type parsers (lines 5289-5406 equivalent)
# ============================================================================

def parse_bool_property(tag: PropertyTag, archive: FArchive) -> bool:
    """解析 BoolProperty（PROP-04）。值存储在 tag.bool_val，无额外读取。"""
    return bool(tag.bool_val)


def parse_int_property(tag: PropertyTag, archive: FArchive) -> int:
    """解析 IntProperty/Int64Property/Int16Property/Int8Property/ByteProperty（PROP-02）。
    
    TODO: 使用UE编辑器源码的加载方式替换实现代码
    参考 UE C++ FArchive& operator<<(int32&) 等实现
    """
    type_name = tag.type
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

    for i in range(count):
        # Dynamic inner_size calculation: distribute remaining bytes evenly
        # Last element gets all remaining size to avoid precision loss
        remaining_count = count - i
        inner_size = remaining_size // remaining_count if remaining_count > 1 else remaining_size
        inner_tag = PropertyTag(
            name=f"{tag.name}[{i}]",
            type=_get_inner_type(tag.type),
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
    fields: Dict[str, Any] = {}
    property_count = 0

    parse_property_value = _get_parse_property_value()
    read_property_tag = _get_read_property_tag()

    while property_count < MAX_PROPERTY_COUNT:
        property_count += 1

        inner_tag = read_property_tag(archive, name_map)

        if inner_tag.name == "None":
            break

        field_value = parse_property_value(inner_tag, archive, name_map, export_map, summary, depth + 1)
        # 当解析器返回 None（未知类型）且 tag.size > 0 时，主动跳过该属性字节
        # 防止在同一位置无限循环读取相同的 PropertyTag
        if field_value is None and inner_tag.size > 0:
            archive.seek(archive.tell() + inner_tag.size)
        fields[inner_tag.name] = field_value

    return StructValue(
        struct_type=struct_type,
        fields=fields
    )


def parse_map_property(tag: PropertyTag, archive: FArchive, name_map: List[str], export_map: List[Any], summary: Optional[Any] = None) -> MapValue:
    """解析 MapProperty（ADVP-02）。"""
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
    element_type = _extract_set_type_from_tag(tag)

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
    """解析 TextProperty（ADVP-05）。"""
    flags = archive.read_i32()  # consume but not used
    namespace = archive.read_fstring()
    key = archive.read_fstring()
    source_string = archive.read_fstring()

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
