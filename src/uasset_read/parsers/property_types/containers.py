"""容器属性类型解析函数 — array, map, set, optional。

从 _all_types.py 拆分出的容器类型解析器集合。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Dict, Any, Optional

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.models.properties import (
    PropertyTag, MapValue, SetValue,
)
from uasset_read.parsers.utils import extract_inner_from_tag, read_validated_count
from uasset_read.constants import MAX_PROPERTY_COUNT, MAX_ARRAY_COUNT
from uasset_read.exceptions import ParseError


# ============================================================================
# Tag extraction helpers
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


def _extract_map_types_from_tag(tag: PropertyTag) -> tuple[str, str]:
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


# ============================================================================
# Lazy import helpers
# ============================================================================

def _get_parse_property_value():
    """Lazy import to avoid circular dependency."""
    from uasset_read.parsers.property_parser import parse_property_value
    return parse_property_value


# ============================================================================
# Container parsers
# ============================================================================

def parse_array_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[Any],
    summary: Optional[Any] = None,
    depth: int = 0
) -> List[Any]:
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


def parse_map_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[Any],
    summary: Optional[Any] = None
) -> MapValue:
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


def parse_set_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[Any],
    summary: Optional[Any] = None
) -> SetValue:
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


def parse_optional_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str] = None,
    export_map: List[Any] = None,
    summary: Optional[Any] = None
) -> dict:
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
# Dispatch helpers for MapProperty
# ============================================================================

def _dispatch_key_parse(
    key_type: str,
    archive: FArchive,
    name_map: List[str],
    export_map: List[Any],
    summary: Optional[Any] = None
) -> Any:
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


def _dispatch_value_parse(
    value_type: str,
    archive: FArchive,
    name_map: List[str],
    export_map: List[Any],
    summary: Optional[Any] = None
) -> Any:
    """值类型分派解析。"""
    dummy_tag = PropertyTag(name="Value", type=value_type, size=0)
    parse_property_value = _get_parse_property_value()
    return parse_property_value(dummy_tag, archive, name_map, export_map, summary, depth=0)
