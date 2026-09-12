"""Custom property slots — 0xFD/0xFE and game-specific custom pairs.

UE PropertyTag.h defines custom property slots (CustomProperty 0xFD/0xFE),
used for plugin/Mod extended custom property types.

Unhandled custom slots are raw-skipped (tag.size bytes); only real custom
pairs (e.g. Borderlands 4) get a handler below.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.models.properties import PropertyTag

logger = logging.getLogger(__name__)


def _parse_bl4_gbx_def_ptr_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: list[str] | None = None,
) -> dict:
    """Borderlands4 GbxDefPtrProperty: FName + FPackageIndex."""
    name = archive.read_name(name_map or [])
    struct_ref = archive.read_i32()
    return {
        "kind": "GbxDefPtrProperty",
        "name": name,
        "struct": struct_ref,
    }


def _parse_bl4_game_data_handle_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: list[str] | None = None,
) -> dict:
    """Borderlands4 GameDataHandleProperty: FName + uint32 flags."""
    name = archive.read_name(name_map or [])
    flags = archive.read_u32()
    return {
        "kind": "GameDataHandleProperty",
        "name": name,
        "flags": flags,
    }


# Real custom pairs only — (game_key, type_id | property_name) -> handler.
# Default 0xFD/0xFE slots are NOT registered: the unhandled path raw-skips
# them, which is identical to the old default handlers.
CUSTOM_PROPERTY_HANDLERS: dict[tuple[str | None, Any], Callable[..., Any]] = {
    ("borderlands4", 0xFD): _parse_bl4_gbx_def_ptr_property,
    ("borderlands4", "GbxDefPtrProperty"): _parse_bl4_gbx_def_ptr_property,
    ("borderlands4", 0xFE): _parse_bl4_game_data_handle_property,
    ("borderlands4", "GameDataHandleProperty"): _parse_bl4_game_data_handle_property,
}


def handle_custom_property(
    type_id: int,
    tag: PropertyTag,
    archive: FArchive,
    name_map: list[str] | None = None,
    game: str | None = None,
) -> Any | None:
    """Find and invoke a registered custom property handler.

    Args:
        type_id: Custom property type ID
        tag: PropertyTag instance
        archive: FArchive instance
        name_map: Name mapping table (optional)
        game: Optional game key for game-specific handler lookup

    Returns:
        Handler return value, or the unhandled raw-skip dict if no handler found
    """
    game_key = game.lower() if game else None
    handler = (
        CUSTOM_PROPERTY_HANDLERS.get((game_key, type_id))
        or CUSTOM_PROPERTY_HANDLERS.get((None, type_id))
        or CUSTOM_PROPERTY_HANDLERS.get((game_key, tag.type))
        or CUSTOM_PROPERTY_HANDLERS.get((None, tag.type))
    )
    if handler is None:
        logger.debug(
            "CustomProperty 0x%02X: no handler registered, skipping %d bytes",
            type_id,
            tag.size,
        )
        raw_data = archive.read(tag.size) if tag.size > 0 else b""
        return {
            "kind": "custom_property_unhandled",
            "type_id": type_id,
            "property_type": tag.type,
            "size": tag.size,
            "raw_data": raw_data,
        }
    return handler(tag, archive, name_map)
