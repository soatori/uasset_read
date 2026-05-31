"""CustomProperty 注册表 — 处理 0xFD/0xFE 等自定义属性槽位。

UE PropertyTag.h 定义了自定义属性槽位（CustomProperty 0xFD/0xFE），
用于插件/Mod 扩展的自定义属性类型。

本模块提供注册表机制，允许动态注册自定义属性处理器。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, Any, Optional, Tuple

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.models.properties import PropertyTag

logger = logging.getLogger(__name__)

@dataclass
class CustomPropertyContext:
    """CustomProperty handler 调用上下文。"""
    type_id: int
    tag: PropertyTag
    archive: FArchive
    name_map: Optional[list[str]] = None
    mappings: Optional[Any] = None
    game: Optional[str] = None
    summary: Optional[Any] = None


# 自定义属性处理器注册表: (game, type_id/property_name) -> handler
CUSTOM_PROPERTY_HANDLERS: Dict[Tuple[Optional[str], Any], Callable[[CustomPropertyContext], Any]] = {}


def register_custom_property(type_id: int | str, game: Optional[str] = None):
    """装饰器：注册自定义属性处理器。

    Args:
        type_id: 自定义属性类型 ID（如 0xFD, 0xFE）

    Usage:
        @register_custom_property(0xFD)
        def parse_fd_custom_property(tag, archive, name_map):
            ...
    """
    def decorator(func: Callable) -> Callable:
        CUSTOM_PROPERTY_HANDLERS[(game.lower() if game else None, type_id)] = func
        return func
    return decorator


def handle_custom_property(
    type_id: int,
    tag: PropertyTag,
    archive: FArchive,
    name_map: Optional[list[str]] = None,
    mappings: Optional[Any] = None,
    game: Optional[str] = None,
    summary: Optional[Any] = None,
) -> Any | None:
    """查找并调用已注册的自定义属性处理器。

    Args:
        type_id: 自定义属性类型 ID
        tag: PropertyTag 实例
        archive: FArchive 实例
        name_map: 名称映射表（可选）

    Returns:
        处理器返回值，未找到处理器时返回 None
    """
    game_key = game.lower() if game else None
    handler = (
        CUSTOM_PROPERTY_HANDLERS.get((game_key, type_id))
        or CUSTOM_PROPERTY_HANDLERS.get((None, type_id))
        or CUSTOM_PROPERTY_HANDLERS.get((game_key, tag.type))
        or CUSTOM_PROPERTY_HANDLERS.get((None, tag.type))
    )
    if handler is None:
        logger.warning(
            "CustomProperty 0x%02X: no handler registered, skipping %d bytes",
            type_id, tag.size,
        )
        raw_data = archive.read(tag.size) if tag.size > 0 else b""
        return {
            "kind": "custom_property_unhandled",
            "type_id": type_id,
            "property_type": tag.type,
            "size": tag.size,
            "raw_data": raw_data,
        }
    return handler(CustomPropertyContext(
        type_id=type_id,
        tag=tag,
        archive=archive,
        name_map=name_map,
        mappings=mappings,
        game=game,
        summary=summary,
    ))


# ============================================================================
# 默认处理器 — 0xFD / 0xFE（Borderlands 4, 2XKO 等游戏使用）
# ============================================================================

@register_custom_property(0xFD)
def _parse_fd_custom_property(context: CustomPropertyContext) -> dict:
    """处理 0xFD 自定义属性（Borderlands 4, 2XKO 等）。

    默认 tolerant 行为：读取 tag.size 字节作为 raw_data 返回。
    """
    raw_data = context.archive.read(context.tag.size) if context.tag.size > 0 else b""
    logger.debug("CustomProperty 0xFD: read %d bytes of custom data", len(raw_data))
    return {
        "type_id": 0xFD,
        "size": context.tag.size,
        "raw_data": raw_data,
    }


@register_custom_property(0xFE)
def _parse_fe_custom_property(context: CustomPropertyContext) -> dict:
    """处理 0xFE 自定义属性（Borderlands 4, 2XKO 等）。

    默认 tolerant 行为：读取 tag.size 字节作为 raw_data 返回。
    """
    raw_data = context.archive.read(context.tag.size) if context.tag.size > 0 else b""
    logger.debug("CustomProperty 0xFE: read %d bytes of custom data", len(raw_data))
    return {
        "type_id": 0xFE,
        "size": context.tag.size,
        "raw_data": raw_data,
    }


@register_custom_property(0xFD, game="Borderlands4")
@register_custom_property("GbxDefPtrProperty", game="Borderlands4")
def _parse_bl4_gbx_def_ptr_property(context: CustomPropertyContext) -> dict:
    """Borderlands4 GbxDefPtrProperty: FName + FPackageIndex。"""
    name = context.archive.read_name(context.name_map or [])
    struct_ref = context.archive.read_i32()
    return {
        "kind": "GbxDefPtrProperty",
        "name": name,
        "struct": struct_ref,
    }


@register_custom_property(0xFE, game="Borderlands4")
@register_custom_property("GameDataHandleProperty", game="Borderlands4")
def _parse_bl4_game_data_handle_property(context: CustomPropertyContext) -> dict:
    """Borderlands4 GameDataHandleProperty: FName + uint32 flags。"""
    name = context.archive.read_name(context.name_map or [])
    flags = context.archive.read_u32()
    return {
        "kind": "GameDataHandleProperty",
        "name": name,
        "flags": flags,
    }
