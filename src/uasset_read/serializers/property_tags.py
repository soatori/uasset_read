"""PropertyTag 序列化器 — read_property_tag。

等价迁移 uasset_read.py 第 5186-5282 行。
UE5.7 专用版本 — 已移除 UE4 兼容代码。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Tuple, Optional, Any, TypeVar

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.constants import (
    PROPERTY_TAG_COMPLETE_TYPE_NAME,
    PROP_TAG_HAS_ARRAY_INDEX,
    PROP_TAG_HAS_PROPERTY_GUID,
    PROP_TAG_HAS_EXTENSIONS,
    PROP_TAG_HAS_BINARY_OR_NATIVE,
    PROP_TAG_BOOL_TRUE,
    PROP_TAG_SKIPPED_SERIALIZE,
    PROP_EXT_SERIALIZE_CONTROL,
    MAX_PROPERTY_TYPE_NODES,
)
from uasset_read.models.properties import PropertyTag, PropertyTypeName

T = TypeVar("T")


def _read_property_type_name(
    archive: FArchive,
    name_map: List[str],
    max_nodes: int = MAX_PROPERTY_TYPE_NODES,
) -> PropertyTypeName:
    """读取 FPropertyTypeName 前序节点并恢复递归树。

    部分资产的非标准 payload 会让 inner_count 看起来异常大。这里使用 50 节点
    读取上限，平衡复杂类型支持和安全性。
    """
    parts: List[Tuple[str, int]] = []
    pending = 1
    while pending > 0 and len(parts) < max_nodes:
        node_name = archive.read_name(name_map)
        inner_count = archive.read_i32()
        parts.append((node_name, inner_count))
        pending = pending - 1 + max(inner_count, 0)

    def build(index: int) -> Tuple[PropertyTypeName, int]:
        name, count = parts[index]
        index += 1
        children: List[PropertyTypeName] = []
        for _ in range(max(count, 0)):
            if index >= len(parts):
                break
            child, index = build(index)
            children.append(child)
        return PropertyTypeName(name, children), index

    if not parts:
        return PropertyTypeName("")
    return build(0)[0]


def _apply_property_type_to_tag(tag: PropertyTag, prop_type: Any) -> None:
    """将递归类型或 mappings.PropertyType 派生到 PropertyTag 兼容字段。"""
    if prop_type is None:
        return

    name = getattr(prop_type, "name", None) or getattr(prop_type, "type", None)
    children = getattr(prop_type, "children", None)
    if name:
        tag.type = name
    if hasattr(prop_type, "struct_type") and getattr(prop_type, "struct_type"):
        tag.struct_type = getattr(prop_type, "struct_type")
    if hasattr(prop_type, "enum_name") and getattr(prop_type, "enum_name"):
        tag.enum_type = getattr(prop_type, "enum_name")

    def child_type(index: int) -> Any:
        if children is not None:
            return children[index] if index < len(children) else None
        if index == 0:
            return getattr(prop_type, "inner_type", None)
        if index == 1:
            return getattr(prop_type, "value_type", None)
        return None

    if tag.type == "StructProperty":
        struct_child = child_type(0)
        if struct_child is not None:
            tag.struct_type = (getattr(struct_child, "name", None) or getattr(struct_child, "type", None) or "").split(".")[-1]
    elif tag.type in ("ArrayProperty", "SetProperty", "OptionalProperty"):
        inner = child_type(0)
        if inner is not None:
            tag.inner_type = getattr(inner, "name", None) or getattr(inner, "type", None)
            # Array/Set 内层为 StructProperty 时，提取 inner_type_struct
            if tag.inner_type == "StructProperty":
                inner_children = getattr(inner, "children", None)
                if inner_children and len(inner_children) > 0:
                    struct_name_node = inner_children[0]
                    struct_name = getattr(struct_name_node, "name", None) or getattr(struct_name_node, "type", None)
                    if struct_name:
                        tag.inner_type_struct = struct_name.split(".")[-1]
    elif tag.type == "MapProperty":
        key = child_type(0)
        value = child_type(1)
        if key is not None:
            tag.key_type = getattr(key, "name", None) or getattr(key, "type", None)
        if value is not None:
            tag.value_type = getattr(value, "name", None) or getattr(value, "type", None)
    elif tag.type in ("ByteProperty", "EnumProperty"):
        enum_child = child_type(0)
        if enum_child is not None:
            enum_name = getattr(enum_child, "name", None) or getattr(enum_child, "type", None)
            if enum_name and enum_name != "None":
                tag.enum_type = enum_name


def parse_ctrl_flags(flags: int) -> dict:
    """解析 PropertyTag flags 字节为命名布尔字典。

    EPropertyTagFlags 位定义（UE5 源码 PropertyTag.h）：
      0x01 HasArrayIndex        — ArrayIndex 字段存在
      0x02 HasPropertyGuid      — PropertyGuid 字段存在
      0x04 HasPropertyExtensions — 扩展数据存在
      0x08 HasBinaryOrNative    — 二进制/原生序列化
      0x10 BoolTrue             — BoolProperty 值为 true
      0x20 SkippedSerialize     — 已跳过序列化
    """
    return {
        "has_array_index": bool(flags & PROP_TAG_HAS_ARRAY_INDEX),
        "has_property_guid": bool(flags & PROP_TAG_HAS_PROPERTY_GUID),
        "has_extensions": bool(flags & PROP_TAG_HAS_EXTENSIONS),
        "has_binary_or_native": bool(flags & PROP_TAG_HAS_BINARY_OR_NATIVE),
        "bool_true": bool(flags & PROP_TAG_BOOL_TRUE),
        "skipped_serialize": bool(flags & PROP_TAG_SKIPPED_SERIALIZE),
    }


def read_property_tag(
    archive: FArchive,
    name_map: List[str],
    tolerant: bool = False,
    summary: Optional[Any] = None,  # 向后兼容，接受但不使用
    mappings: Optional[Any] = None,
    struct_name: Optional[str] = None,
) -> PropertyTag:
    """从 archive 读取 PropertyTag 结构（UE5.7 专用）。

    Args:
        archive: FArchive 实例
        name_map: 名称映射列表
        tolerant: 是否启用容错模式
        summary: PackageFileSummary 实例（向后兼容参数，当前未使用）

    Returns:
        PropertyTag 实例
    """
    # Record tag start position for cascade failure diagnosis
    tag_start_pos = archive.tell()

    tag = PropertyTag(name=archive.read_name(name_map), type="", size=0, tag_start_offset=tag_start_pos)

    if tag.name == "None":
        return tag

    tag.type_name = _read_property_type_name(archive, name_map)
    tag.type_parts = tag.type_name.to_parts()
    _apply_property_type_to_tag(tag, tag.type_name)

    mapping_container = getattr(mappings, "mappings", mappings)
    struct_mapping = mapping_container.get_struct(struct_name) if mapping_container is not None and hasattr(mapping_container, "get_struct") else None
    if struct_mapping is not None:
        if hasattr(mapping_container, "property_by_name"):
            prop_info = mapping_container.property_by_name(struct_name, tag.name)
        else:
            prop_info = struct_mapping.property_by_name(tag.name)
        if prop_info is not None:
            tag.tag_data = prop_info.mapping_type
            _apply_property_type_to_tag(tag, prop_info.mapping_type)
    tag.size = archive.read_i32()
    archive.validate_size(tag.size, tag.name, tolerant=tolerant)
    tag.flags = archive.read_u8()
    if tag.flags & PROP_TAG_SKIPPED_SERIALIZE:
        tag.serialize_type = "Skipped"
    elif tag.flags & PROP_TAG_HAS_BINARY_OR_NATIVE:
        tag.serialize_type = "BinaryOrNative"
    else:
        tag.serialize_type = "Property"

    if tag.flags & PROP_TAG_HAS_ARRAY_INDEX:
        tag.array_index = archive.read_i32()

    if tag.flags & PROP_TAG_HAS_PROPERTY_GUID:
        tag.property_guid = archive.read_bytes(16)

    if tag.flags & PROP_TAG_HAS_EXTENSIONS:
        property_extensions = archive.read_u8()
        if property_extensions & PROP_EXT_SERIALIZE_CONTROL:
            tag.override_operation = archive.read_u8()
            tag.experimental_overridable_logic = archive.read_u8()

    if tag.flags & PROP_TAG_BOOL_TRUE:
        tag.bool_val = 1

    # Record value start position and expected end position
    tag.value_start_offset = archive.tell()
    if tag.size > 0:
        tag.value_end_offset = tag.value_start_offset + tag.size
    else:
        tag.value_end_offset = tag.value_start_offset

    return tag


def read_tag_value_bounded(
    archive: FArchive,
    tag: PropertyTag,
    reader: Callable[[], T],
) -> T:
    """Read a PropertyTag value and always end at value_start + Size.

    This mirrors's FPropertyTag behavior: value parsers may consume
    fewer or more bytes, or raise, but the archive is restored to the tag's
    calculated final position before control returns.
    """
    final_pos = tag.value_end_offset
    if final_pos is None:
        value_start = tag.value_start_offset if tag.value_start_offset is not None else archive.tell()
        final_pos = value_start + max(tag.size, 0)

    try:
        return reader()
    finally:
        if archive.tell() != final_pos:
            archive.seek(final_pos)


def parse_ue511_ctrl_flags(ctrl: int) -> dict:
    """解析 UE5.11+ 序列化控制扩展头的 ctrl 字节。

    复用标准常量，保持与 parse_ctrl_flags 一致的键名。
    0x02 位在 flags 语境下叫 HasPropertyGuid，在 ctrl 语境下叫 SerializeControl。
    """
    return {
        "has_array_index": bool(ctrl & PROP_TAG_HAS_ARRAY_INDEX),
        "serialize_control": bool(ctrl & PROP_TAG_HAS_PROPERTY_GUID),
        "has_extensions": bool(ctrl & PROP_TAG_HAS_EXTENSIONS),
        "has_binary_or_native": bool(ctrl & PROP_TAG_HAS_BINARY_OR_NATIVE),
        "bool_true": bool(ctrl & PROP_TAG_BOOL_TRUE),
        "skipped_serialize": bool(ctrl & PROP_TAG_SKIPPED_SERIALIZE),
    }
