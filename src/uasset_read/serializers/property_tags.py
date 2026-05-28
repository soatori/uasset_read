"""PropertyTag 序列化器 — read_property_tag。

等价迁移 uasset_read.py 第 5186-5282 行。
Phase 30: 属性解析模块 (per MOD-06, MOD-09)。
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
)
from uasset_read.models.properties import PropertyTag

T = TypeVar("T")


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
    # Phase 73 Wave 4: Record tag start position for cascade failure diagnosis
    tag_start_pos = archive.tell()

    tag = PropertyTag(name=archive.read_name(name_map), type="", size=0, tag_start_offset=tag_start_pos)

    if tag.name == "None":
        return tag

    # UE5 format: FPropertyTypeName nodes
    type_parts: List[Tuple[str, int]] = []
    pending = 1
    while pending > 0 and len(type_parts) < 20:
        node_name = archive.read_name(name_map)
        inner_count = archive.read_i32()
        type_parts.append((node_name, inner_count))
        pending = pending - 1 + inner_count

    tag.type = type_parts[0][0] if type_parts else ""
    tag.type_parts = type_parts

    # Extract enum_type for ByteProperty/EnumProperty from FPropertyTypeName nodes
    # Per CUE4Parse: ByteProperty with enum backing reads FName (8 bytes), not single byte
    # Format: [('ByteProperty', 1), ('EnumName', 1), ('/Script/Module', 0)]
    if tag.type in ("ByteProperty", "EnumProperty") and len(type_parts) >= 2:
        enum_type_name = type_parts[1][0]
        if enum_type_name and enum_type_name != "None":
            tag.enum_type = enum_type_name
    if tag.type == "StructProperty" and len(type_parts) >= 2:
        struct_type_name = type_parts[1][0]
        if struct_type_name and struct_type_name != "None":
            tag.struct_type = struct_type_name.split(".")[-1]
    elif tag.type == "ArrayProperty" and len(type_parts) >= 2:
        tag.inner_type = type_parts[1][0]
    elif tag.type == "SetProperty" and len(type_parts) >= 2:
        tag.inner_type = type_parts[1][0]
    elif tag.type == "MapProperty" and len(type_parts) >= 3:
        tag.key_type = type_parts[1][0]
        tag.value_type = type_parts[2][0]
    tag.size = archive.read_i32()
    archive.validate_size(tag.size, tag.name, tolerant=tolerant)
    tag.flags = archive.read_u8()

    if tag.flags & PROP_TAG_HAS_ARRAY_INDEX:
        tag.array_index = archive.read_i32()

    if tag.flags & PROP_TAG_HAS_PROPERTY_GUID:
        tag.property_guid = archive.read_bytes(16)

    if tag.flags & PROP_TAG_HAS_EXTENSIONS:
        property_extensions = archive.read_u8()
        if property_extensions & 0x02:
            tag.override_operation = archive.read_u8()
            tag.experimental_overridable_logic = archive.read_u8()

    if tag.flags & PROP_TAG_BOOL_TRUE:
        tag.bool_val = 1

    # Phase 73 Wave 4: Record value start position and expected end position
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

    This mirrors CUE4Parse's FPropertyTag behavior: value parsers may consume
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
