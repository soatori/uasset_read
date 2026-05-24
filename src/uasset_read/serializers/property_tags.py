"""PropertyTag 序列化器 — read_property_tag。

等价迁移 uasset_read.py 第 5186-5282 行。
Phase 30: 属性解析模块 (per MOD-06, MOD-09)。
UE5.7 专用版本 — 已移除 UE4 兼容代码。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple, Optional, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.constants import (
    PROPERTY_TAG_COMPLETE_TYPE_NAME,
    PROP_TAG_HAS_ARRAY_INDEX,
    PROP_TAG_HAS_PROPERTY_GUID,
    PROP_TAG_HAS_EXTENSIONS,
    PROP_TAG_BOOL_TRUE,
)
from uasset_read.exceptions import ParseError
from uasset_read.models.properties import PropertyTag


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

    # Extract enum_type for ByteProperty/EnumProperty from FPropertyTypeName nodes
    # Per CUE4Parse: ByteProperty with enum backing reads FName (8 bytes), not single byte
    # Format: [('ByteProperty', 1), ('EnumName', 1), ('/Script/Module', 0)]
    if tag.type in ("ByteProperty", "EnumProperty") and len(type_parts) >= 2:
        enum_type_name = type_parts[1][0]
        if enum_type_name and enum_type_name != "None":
            tag.enum_type = enum_type_name
    tag.size = archive.read_i32()
    try:
        archive.validate_size(tag.size, tag.name, tolerant=tolerant)
    except ParseError:
        # Size overflow safety net: seek past the bad size to avoid cascading errors.
        # Clamp skip to a reasonable maximum to prevent runaway seeks.
        _safe_skip = min(max(tag.size, 0), 64 * 1024)
        _recovery_pos = archive.tell() + _safe_skip
        if _recovery_pos <= archive._file_size:
            archive.seek(_recovery_pos)
        raise
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
