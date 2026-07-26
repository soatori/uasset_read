"""Shared utility functions for the parsers module"""
from typing import Any, List, Optional
import logging


logger = logging.getLogger(__name__)


def resolve_name_from_index(
    archive: Any,
    name_map: List[str],
    index: int,
    fallback_prefix: str = "param",
) -> str:
    """Unified name index resolution logic

    Args:
        archive: FArchive instance
        name_map: name mapping table
        index: index value
        fallback_prefix: fallback prefix when index is out of bounds

    Returns:
        Resolved name string
    """
    if 0 <= index < len(name_map):
        return name_map[index]
    return f"{fallback_prefix}_{index}"


def read_validated_count_tolerant(
    archive: Any,
    max_count: int,
    label: str,
) -> int:
    """Read and validate a count value (tolerant version: returns 0 when out of range).

    When count is negative or exceeds max_count, logs a diagnostic and returns 0 (skipping subsequent loops),
    instead of throwing ParseError. This way the caller ``for _ in range(count)`` loop will not execute，
    returning an empty collection，while preserving parent property structure integrity。

    Args:
        archive: FArchive instance
        max_count: maximum allowed value
        label: label used for error messages

    Returns:
        Validated count value (returns 0 when invalid)
    """
    offset = archive.tell()
    count = archive.read_i32()

    # Check whether the value read by struct.unpack is within i32 range（Python automatically handles big integers,
    # but read_i32 uses signed format, so negative values are correctly represented)
    if count < 0:
        logger.debug(
            "%s: count is negative (%d)，skipping | pos=0x%X, limit=%d",
            label, count, offset, max_count,
        )
        return 0
    if count > max_count:
        logger.debug(
            "%s: count exceeds maximum (%d > %d)，skipping | pos=0x%X",
            label, count, max_count, offset,
        )
        return 0
    return count


def make_enum_value(enum_type: str, value_name: str) -> dict:
    """Create EnumValue dictionary

    Args:
        enum_type: enum type name
        value_name: enum value name

    Returns:
        EnumValue dictionary
    """
    # #143: When enum_type is unknown, do not add "UnknownEnum::" prefix
    if enum_type and enum_type != "UnknownEnum":
        full_name = f"{enum_type}::{value_name}"
    else:
        full_name = value_name
    return {
        "enum_type": enum_type,
        "value_name": full_name,
    }


def extract_inner_from_tag(tag_type: str) -> Optional[str]:
    """Extract content within parentheses from tag.type string

    Args:
        tag_type: type string, e.g. "ArrayProperty(IntProperty)"

    Returns:
        Content within parentheses, or None if no parentheses
    """
    start = tag_type.find("(")
    end = tag_type.rfind(")")
    if start != -1 and end != -1 and end > start:
        return tag_type[start + 1:end]
    return None
