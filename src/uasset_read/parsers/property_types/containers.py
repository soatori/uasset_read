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
from uasset_read.models.fallback import PropertyFallback, FallbackReason
from uasset_read.parsers.utils import extract_inner_from_tag, read_validated_count
from uasset_read.constants import MAX_PROPERTY_COUNT, MAX_ARRAY_COUNT
from uasset_read.exceptions import ParseError


class _UnsupportedMapKeyType(ParseError):
    """Map key 类型不受支持时内部抛出，由 parse_map_property 捕获并转为 fallback。"""
    pass


# ============================================================================
# Supported type definitions for early detection
# ============================================================================

# Map key 支持的类型（UE TMap 支持的基础类型）
_SUPPORTED_MAP_KEY_TYPES = frozenset([
    "IntProperty", "Int64Property", "FloatProperty", "DoubleProperty",
    "StrProperty", "NameProperty", "BoolProperty", "ByteProperty",
    "UInt16Property", "UInt32Property", "UInt64Property",
    "ObjectProperty", "EnumProperty",
])

# Set element 支持的类型（所有 parse_property_value 能处理的类型）
_SUPPORTED_SET_ELEMENT_TYPES = frozenset([
    # 基础类型
    "BoolProperty", "IntProperty", "Int64Property", "Int16Property", "Int8Property",
    "ByteProperty", "UInt16Property", "UInt32Property", "UInt64Property",
    "FloatProperty", "DoubleProperty",
    "StrProperty", "Utf8StrProperty", "AnsiStrProperty", "NameProperty",
    "ObjectProperty", "SoftObjectProperty", "WeakObjectProperty", "LazyObjectProperty",
    "ClassProperty", "SoftClassProperty", "AssetObjectProperty", "AssetClassProperty",
    "ArrayProperty", "StructProperty", "MapProperty", "SetProperty",
    "EnumProperty", "TextProperty", "DelegateProperty",
    "MulticastDelegateProperty", "MulticastInlineDelegateProperty",
    "MulticastSparseDelegateProperty", "InterfaceProperty",
    "FieldPathProperty", "OptionalProperty", "GuidProperty",
    # Verse 类型
    "VerseStringProperty", "VerseClassProperty", "VerseFunctionProperty",
    "VerseDynamicProperty", "VerseCellProperty", "VerseValueProperty",
])


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
    import logging
    logger = logging.getLogger(__name__)

    key_type = getattr(tag, "key_type", None)
    value_type = getattr(tag, "value_type", None)
    if not key_type or not value_type:
        key_type, value_type = _extract_map_types_from_tag(tag)

    # 早期检测：不支持的 key/value 类型
    if key_type not in _SUPPORTED_MAP_KEY_TYPES:
        logger.warning(
            "MapProperty '%s': unsupported key type '%s', returning fallback",
            tag.name, key_type
        )
        # 跳过整个 map 数据（bounded by tag.size）
        if tag.size > 0:
            archive.read(tag.size)
        return MapValue(
            key_type=key_type,
            value_type=value_type,
            entries=[],
            parse_status="fallback",
            unsupported_reason=f"Unsupported key type: {key_type}"
        )

    # 尝试解析，捕获 _UnsupportedMapKeyType 异常
    try:
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
            entries=entries,
            parse_status="parsed"
        )
    except _UnsupportedMapKeyType as e:
        # 不支持的类型：跳过剩余数据，返回 fallback
        logger.warning(
            "MapProperty '%s': %s, returning fallback",
            tag.name, e
        )
        # 计算剩余字节并跳过
        current_pos = archive.tell()
        value_start = tag.value_start_offset if tag.value_start_offset is not None else current_pos
        remaining = max(0, tag.size - (current_pos - value_start))
        if remaining > 0:
            archive.read(remaining)
        return MapValue(
            key_type=key_type,
            value_type=value_type,
            entries=[],
            parse_status="fallback",
            unsupported_reason=str(e)
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
    import logging
    logger = logging.getLogger(__name__)

    element_type = getattr(tag, "inner_type", None) or _extract_set_type_from_tag(tag)

    # 早期检测：不支持的 element 类型
    if element_type not in _SUPPORTED_SET_ELEMENT_TYPES:
        logger.warning(
            "SetProperty '%s': unsupported element type '%s', returning fallback",
            tag.name, element_type
        )
        # 跳过整个 set 数据（bounded by tag.size）
        if tag.size > 0:
            archive.read(tag.size)
        return SetValue(
            element_type=element_type,
            elements=[],
            parse_status="fallback",
            unsupported_reason=f"Unsupported element type: {element_type}"
        )

    # 正常解析流程
    try:
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
            elements=elements,
            parse_status="parsed"
        )
    except Exception as e:
        # 解析错误：跳过剩余数据，返回 fallback
        logger.warning(
            "SetProperty '%s': failed to parse element type '%s': %s, returning fallback",
            tag.name, element_type, e
        )
        # 计算剩余字节并跳过
        current_pos = archive.tell()
        value_start = tag.value_start_offset if tag.value_start_offset is not None else current_pos
        remaining = max(0, tag.size - (current_pos - value_start))
        if remaining > 0:
            archive.read(remaining)
        return SetValue(
            element_type=element_type,
            elements=[],
            parse_status="fallback",
            unsupported_reason=f"Parse error: {e}"
        )


def parse_optional_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str] = None,
    export_map: List[Any] = None,
    summary: Optional[Any] = None
) -> dict:
    """解析 OptionalProperty（Issue #62）。

    UE structured optional 二进制格式：
      - bool has_value (1 byte，表示值是否存在)
      - if has_value:
          * UE5 新版（file_version_ue5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME）：
            直接按 inner_type 原生序列化（无额外 PropertyTag）
          * 旧版：读取完整的 inner FPropertyTag，然后解析 tagged property

    参考 UE 源码：PropertyOptional.cpp::SerializeItem
    """
    from uasset_read.constants import PROPERTY_TAG_COMPLETE_TYPE_NAME
    from uasset_read.parsers.property_types._common import _build_version_container_from_summary

    # 读取 has_value 标志（UE TryEnterField 在二进制中写入 1 byte bool）
    has_value = archive.read_bool()

    if not has_value:
        return {"has_value": False, "value": None}

    # 获取版本信息以选择正确的解析路径
    version_container = _build_version_container_from_summary(summary)
    file_version_ue5 = getattr(version_container, 'file_version_ue5', 0) if version_container else 0
    is_new_format = file_version_ue5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME

    parse_property_value = _get_parse_property_value()
    inner_type = getattr(tag, "inner_type", None) or "Unknown"

    if is_new_format:
        # UE5 新版：直接按 inner_type 原生序列化（无额外 PropertyTag）
        # 参考 UE PropertyOptional.cpp:217
        #   GetValueProperty()->SerializeItem(ValueSlot, ValueData, ValueDefaults)
        inner_tag = PropertyTag(
            name=f"{tag.name}.Value",
            type=inner_type,
            size=0,  # 让解析函数按类型原生序列化
        )
        # 传递完整 inner descriptor（struct_type, enum_type 等）
        if inner_type == "StructProperty":
            inner_tag.struct_type = getattr(tag, "inner_type_struct", None)
        if inner_type in ("ByteProperty", "EnumProperty"):
            inner_tag.enum_type = getattr(tag, "enum_type", None)

        try:
            inner_value = parse_property_value(
                inner_tag, archive, name_map or [], export_map or [], summary
            )
            return {"has_value": True, "value": inner_value}
        except Exception as e:
            # unsupported inner value: bounded fallback 并上报 partial
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "OptionalProperty '%s': failed to parse inner type '%s': %s, using fallback",
                tag.name, inner_type, e
            )
            # 跳过剩余字节（bounded by remaining data in this optional）
            remaining = max(0, (tag.size or 0) - 1)  # 减去 has_value bool
            if remaining > 0:
                archive.read_bytes(remaining)
            return {
                "has_value": True,
                "value": None,
                "parse_status": "partial",
                "error": f"Failed to parse inner type '{inner_type}': {e}"
            }
    else:
        # 旧版：读取完整的 inner FPropertyTag
        # 参考 UE PropertyOptional.cpp:221-249
        read_property_tag = _get_read_property_tag()
        try:
            inner_tag = read_property_tag(archive, name_map or [])
            inner_value = parse_property_value(
                inner_tag, archive, name_map or [], export_map or [], summary
            )
            return {"has_value": True, "value": inner_value}
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "OptionalProperty '%s': failed to parse inner tag: %s, skipping",
                tag.name, e
            )
            # bounded fallback：跳过剩余字节
            remaining = max(0, (tag.size or 0) - 1)
            if remaining > 0:
                archive.read_bytes(remaining)
            return {
                "has_value": True,
                "value": None,
                "parse_status": "partial",
                "error": f"Failed to parse inner tag: {e}"
            }


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
    """键类型分派解析（D-02b）。

    不支持的类型抛出 _UnsupportedMapKeyType，由上层捕获并转为 PropertyFallback。
    """
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

    # 不支持的 key 类型：抛出异常而非返回 None，避免偏移错位
    raise _UnsupportedMapKeyType(f"Unsupported map key type: {key_type}")


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
