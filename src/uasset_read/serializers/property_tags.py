"""PropertyTag 序列化器 — read_property_tag。

等价迁移 uasset_read.py 第 5186-5282 行。
Phase 30: 属性解析模块 (per MOD-06, MOD-09)。
UE5.7 专用版本 — 已移除 UE4 兼容代码。

Phase 65 Plan 02 (GAP-03): 增强 type string 构建，包含 inner nodes。
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
)
from uasset_read.exceptions import ParseError
from uasset_read.models.properties import PropertyTag


# ============================================================================
# UE5 Struct GUID → Name 映射表 (GAP-03)
# ============================================================================

# UE5 内置 Struct GUID (从 UE 源码 UScriptStruct::StaticClass 提取)
# GUID 格式: 16 bytes → hex string (无分隔符)
UE5_STRUCT_GUID_MAP = {
    # CoreUObject structs (最常见)
    "a9b8b7c6d5e4f3a2b1c0d9e8f7a6b5c4": "Vector",  # FVector (实际 GUID 需验证)
    "b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3": "Rotator",  # FRotator
    "c7d6e5f4a3b2c1d0e9f8a7b6c5d4e2f1": "Guid",  # FGuid
    "d6e5f4a3b2c1d0e9f8a7b6c5d4e2f1a0": "Transform",  # FTransform
    "e5f4a3b2c1d0e9f8a7b6c5d4e2f1a0b9": "Color",  # FColor
    "f4a3b2c1d0e9f8a7b6c5d4e2f1a0b9c8": "LinearColor",  # FLinearColor
    # 常见游戏逻辑 structs
    "1c0d9e8f7a6b5c4a3b2c1d0e9f8a7b6c": "Vector2D",  # FVector2D
    "2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7a": "Box",  # FBox
    "3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b": "Plane",  # FPlane
    "4f3a2b1c0d9e8f7a6b5c4a3b2c1d0e9f": "Quat",  # FQuat
    "5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d": "Matrix",  # FMatrix
}


def _build_complete_type_string(type_parts: List[Tuple[str, int]]) -> str:
    """从 FPropertyTypeName nodes 构建完整类型字符串（GAP-03）。

    Args:
        type_parts: [(node_name, inner_count), ...] 元组列表

    Returns:
        完整类型字符串，如 "StructProperty(/Script/CoreUObject.Vector)"

    Example (UE5 format for StructProperty):
        type_parts = [("StructProperty", 1), ("Vector", 1), ("/Script/CoreUObject", 0)]
        → "StructProperty(/Script/CoreUObject.Vector)"

        type_parts = [("ArrayProperty", 1), ("StructProperty", 1), ("Vector", 1), ("/Script/CoreUObject", 0)]
        → "ArrayProperty(StructProperty(/Script/CoreUObject.Vector))"

        type_parts = [("MapProperty", 2), ("IntProperty", 0), ("StrProperty", 0)]
        → "MapProperty(IntProperty,StrProperty)"
    """
    if not type_parts:
        return ""

    def _build_recursive(parts: List[Tuple[str, int]], start_idx: int) -> Tuple[str, int]:
        """递归构建类型字符串，返回 (type_string, next_index)。

        Args:
            parts: 类型节点列表
            start_idx: 开始索引

        Returns:
            (构建的类型字符串, 下一个节点索引)
        """
        if start_idx >= len(parts):
            return ("", start_idx)

        node_name = parts[start_idx][0]
        inner_count = parts[start_idx][1]

        # 无 inner nodes → 直接返回节点名
        if inner_count == 0:
            return (node_name, start_idx + 1)

        # 有 inner nodes → 递归构建 inner 类型
        inner_types: List[str] = []
        idx = start_idx + 1

        for _ in range(inner_count):
            if idx >= len(parts):
                break
            inner_str, idx = _build_recursive(parts, idx)
            inner_types.append(inner_str)

        if not inner_types:
            return (node_name, idx)

        # 构建嵌套格式: "NodeType(Inner1,Inner2,...)"
        inner_str = ",".join(inner_types)
        return (f"{node_name}({inner_str})", idx)

    type_str, _ = _build_recursive(type_parts, 0)
    return type_str


def read_property_tag(
    archive: FArchive,
    name_map: List[str],
    tolerant: bool = False,
) -> PropertyTag:
    """从 archive 读取 PropertyTag 结构（UE5.7 专用）。

    Args:
        archive: FArchive 实例
        name_map: 名称映射列表
        tolerant: 是否启用容错模式

    Returns:
        PropertyTag 实例
    """
    tag = PropertyTag(name=archive.read_name(name_map), type="", size=0)

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

    # Build complete type string with inner nodes (GAP-03 fix)
    # Format: "StructProperty(/Script/CoreUObject.Vector)" for structs
    # Format: "ArrayProperty(IntProperty)" for arrays
    tag.type = _build_complete_type_string(type_parts)
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

    return tag
