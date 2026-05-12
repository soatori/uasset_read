"""PropertyTag 序列化器 — read_property_tag, use_complete_type_name。

等价迁移 uasset_read.py 第 5186-5282 行。
Phase 30: 属性解析模块 (per MOD-06, MOD-09)。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.constants import (
    PROPERTY_TAG_COMPLETE_TYPE_NAME,
    PROP_TAG_HAS_ARRAY_INDEX,
    PROP_TAG_HAS_PROPERTY_GUID,
    PROP_TAG_HAS_EXTENSIONS,
    PROP_TAG_BOOL_TRUE,
    use_complete_type_name,
)
from uasset_read.exceptions import ParseError
from uasset_read.models.properties import PropertyTag


def read_property_tag(
    archive: FArchive,
    name_map: List[str],
    legacy_version: int,
    ue5_version: int,
    tolerant: bool = False,
) -> PropertyTag:
    """从 archive 读取 PropertyTag 结构。

    Args:
        archive: FArchive 实例
        name_map: 名称映射列表
        legacy_version: LegacyFileVersion
        ue5_version: UE5 版本号
        tolerant: 是否启用容错模式

    Returns:
        PropertyTag 实例
    """
    tag = PropertyTag(name=archive.read_name(name_map), type="", size=0)

    if tag.name == "None":
        return tag

    if use_complete_type_name(legacy_version, ue5_version):
        # UE5 new format: FPropertyTypeName nodes
        type_parts: List[Tuple[str, int]] = []
        pending = 1
        while pending > 0 and len(type_parts) < 20:
            node_name = archive.read_name(name_map)
            inner_count = archive.read_i32()
            type_parts.append((node_name, inner_count))
            pending = pending - 1 + inner_count

        tag.type = type_parts[0][0] if type_parts else ""
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
    else:
        # UE4 old format
        tag.type = archive.read_name(name_map)
        tag.size = archive.read_i32()
        archive.validate_size(tag.size, tag.name, tolerant=tolerant)
        tag.array_index = archive.read_i32()
        if tag.type == "BoolProperty":
            tag.bool_val = archive.read_u8()

    return tag
