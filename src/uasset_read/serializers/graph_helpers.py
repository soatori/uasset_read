"""Shared helper functions for graph serializers.

Extracted from graph.py to break the circular import dependency between
graph.py, graph_node.py, and graph_pin.py.

Both graph_node.py and graph_pin.py import helpers from this module
instead of from graph.py, eliminating the cycle:
  graph.py -> graph_pin.py -> graph.py (helpers)
  graph.py -> graph_node.py -> graph.py (helpers)
"""

from __future__ import annotations

import logging
import struct
import threading
from typing import TYPE_CHECKING, List, Optional, Dict, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport

from uasset_read.constants import (
    MAX_SAFE_COUNT,
    format_guid_bytes,
)
from uasset_read.exceptions import ParseError
from uasset_read.serializers.object_resources import (
    resolve_class_name,
    resolve_class_name_with_linker,
    get_asset_class,
    get_asset_class_with_linker,
)
from uasset_read.serializers.property_tags import read_tag_value_bounded

logger = logging.getLogger(__name__)

_thread_local = threading.local()


# ============================================================================
# Core helpers
# ============================================================================


def _read_guid(archive: FArchive, uppercase: bool = True) -> str:
    data = archive.read_bytes(16)
    if len(data) != 16:
        raise ParseError(f"FGuid requires 16 bytes, got {len(data)}")
    return format_guid_bytes(data, uppercase=uppercase)


def _get_thread_local():
    """Return per-thread isolated diagnostic state, avoiding global mutable race."""
    if not hasattr(_thread_local, "linkedto_failure_seen"):
        _thread_local.linkedto_failure_seen: set[tuple[int, str, str]] = set()
    return _thread_local


def _rcn(idx, im, em, lk):
    """Resolve class name - linker version if available."""
    return resolve_class_name_with_linker(idx, lk) if lk else resolve_class_name(idx, im, em)


def _gac(exp, im, em, lk):
    """Get asset class - linker version if available."""
    return get_asset_class_with_linker(exp, lk) if lk else get_asset_class(exp, im, em)


# ============================================================================
# PropertyTag helper functions
# ============================================================================


def _read_tag_bool(archive: FArchive, tag) -> bool:
    """Read bool value from PropertyTag.

    Handles both inline bool and value body forms:
    - tag.size > 0: read i32 from value body (UE5 bool serialization)
    - tag.size == 0: use tag.bool_val (inline bool)

    Args:
        archive: FArchive instance
        tag: PropertyTag instance

    Returns:
        bool value
    """

    def _reader() -> bool:
        if tag.size > 0:
            return archive.read_i32() != 0
        return tag.bool_val != 0

    return read_tag_value_bounded(archive, tag, _reader)


def _read_tag_i32(archive: FArchive, tag) -> int:
    """Read int32 value from PropertyTag and seek to value_end_offset.

    Standardizes int property reading flow.

    Args:
        archive: FArchive instance
        tag: PropertyTag instance

    Returns:
        int32 value
    """
    return read_tag_value_bounded(archive, tag, archive.read_i32)


def _read_tag_fname(archive: FArchive, tag, name_map: List[str]) -> str:
    """Read FName value from PropertyTag and seek to value_end_offset.

    Standardizes FName property reading flow.

    Args:
        archive: FArchive instance
        tag: PropertyTag instance
        name_map: name mapping list

    Returns:
        FName string
    """
    return read_tag_value_bounded(archive, tag, lambda: archive.read_name(name_map))


# ============================================================================
# FText reading (UE5 multi history_type support)
# ============================================================================


def _read_fstring_safe(archive: FArchive, max_length: int = MAX_SAFE_COUNT) -> str:
    """Read FString with tolerance for abnormal lengths.

    References UE C++ FArchive& operator<<(FString&) implementation.

    FString serialization format (UE C++ String.cpp.inl:1810-1904):
    - length == 0: empty string (no data region)
    - length > 0: ANSI string, read length bytes
    - length < 0: UTF-16 string, read (-length * 2) bytes; -1 is a 2-byte NUL, never "no data"

    Fixes length == -1 boundary condition (common in SubPin PinToolTip).
    """
    length = archive.read_i32()
    if length == 0:
        return ""
    if abs(length) > max_length:
        # Abnormal length, fall back to empty string
        if archive.tell() >= 4:
            archive.seek(archive.tell() - 4)
        return ""
    if length < 0:
        data = archive.read(-length * 2)
        return data.decode("utf-16-le", errors="replace").rstrip("\x00")
    data = archive.read(length)
    return data.decode("utf-8", errors="replace").rstrip("\x00")


def read_ftext_fstring(archive: FArchive) -> str:
    """Read FText internal FString.

    Unlike _read_fstring_safe, this function raises on abnormal length,
    letting the upper layer decide whether to fall back the entire FText.
    This avoids "read partial body but continue forward" silent misalignment.
    """
    length = archive.read_i32()
    if length == 0:
        return ""
    if length < 0:
        # String.cpp.inl:1810-1904: negative length reads abs(len)*2 UTF-16 bytes;
        # -1 is a 2-byte NUL, never "no data". (archive.py read_fstring already follows UE.)
        utf16_len = -length * 2
        if utf16_len > MAX_SAFE_COUNT * 2:
            raise ParseError(f"Invalid FText FString length: {length}")
        data = archive.read(utf16_len)
        return data.decode("utf-16-le", errors="replace").rstrip("\x00")
    if length > MAX_SAFE_COUNT:
        raise ParseError(f"Invalid FText FString length: {length}")
    data = archive.read(length)
    return data.decode("utf-8", errors="replace").rstrip("\x00")


def _read_ftext_value(
    archive: FArchive,
    tolerant: bool = True,
) -> tuple[str, int, int, int]:
    """Read complete FText, returns (value, flags, history_type, consumed)."""
    start_pos = archive.tell()
    flags = archive.read_i32()
    history_type_raw = archive.read_u8()
    history_type = history_type_raw - 256 if history_type_raw >= 128 else history_type_raw
    value, _ = read_ftext_with_history(archive, history_type, tolerant=tolerant)
    return value, flags, history_type, archive.tell() - start_pos


def read_ftext_with_history(
    archive: FArchive,
    history_type: int,
    tolerant: bool = True,
) -> tuple[str, int]:
    """Read FText, returns (value, consumed_bytes).

    history_type (ETextHistoryType, signed int8):
    - -1 (0xFF): None (no history) - bHasCultureInvariantString (bool=4 bytes) + optional FString
    - 0: Base - Namespace (FString) + Key (FString) + SourceString (FString)
    - 1: NamedFormat - FormatText (recursive FText) + Arguments (TArray<FFormatArgumentData>)
    - 2+: other generated types (not parsed in tolerant mode)

    References UE C++ source:
    - Text.cpp L850-1044: FText::SerializeText
    - TextHistory.cpp L792-861: FTextHistory_Base::Serialize
    - TextHistory.cpp L1150-1169: FTextHistory_NamedFormat::Serialize
    - Text.cpp L1680-1761: FFormatArgumentData serialization
    """
    start_pos = archive.tell()
    value = ""

    if history_type not in range(-1, 11):
        raise ParseError(f"Invalid FText history_type={history_type} at pos {start_pos}")

    if history_type in (-1, 255):
        b_has_culture = archive.read_bool()
        if b_has_culture:
            value = read_ftext_fstring(archive)
    elif history_type == 0:
        _namespace = read_ftext_fstring(archive)
        _key = read_ftext_fstring(archive)
        value = read_ftext_fstring(archive)
    elif history_type == 1:
        format_text, _, _, _ = _read_ftext_value(archive, tolerant=tolerant)
        arg_count = archive.read_i32()
        if arg_count < 0 or arg_count > MAX_SAFE_COUNT:
            # Design decision: from raise ParseError to warning+skip,
            # aligned with project tolerant mode, avoiding parse interruption from corrupt data
            logger.debug("FText NamedFormat arg_count=%d exceeds limit %d, skipping args", arg_count, MAX_SAFE_COUNT)
            arg_count = 0  # Skip subsequent argument reading
        format_args: Dict[str, str] = {}
        for _ in range(arg_count):
            arg_name = read_ftext_fstring(archive)
            arg_type = archive.read_u8()
            arg_value = ""
            if arg_type == 0:
                arg_value = str(archive.read_i64())
            elif arg_type == 1:
                arg_value = str(archive.read_u64())
            elif arg_type == 2:
                arg_value = str(archive.read_f32())
            elif arg_type == 3:
                arg_value = str(archive.read_f64())
            elif arg_type == 4:
                arg_value, _, _, _ = _read_ftext_value(archive, tolerant=tolerant)
            elif arg_type == 5:
                arg_value = str(archive.read_u8())
            else:
                raise ParseError(f"Unsupported FFormatArgumentType={arg_type}")
            format_args[arg_name] = arg_value
        value = format_text
        for key, arg in format_args.items():
            if key:
                value = value.replace("{" + key + "}", arg)
    else:
        raise ParseError(f"Unsupported FText history_type={history_type}")

    consumed = archive.tell() - start_pos
    return value, consumed


def read_ftext(archive: FArchive, tolerant: bool = True) -> str:
    """Read complete FText (flags + history_type + payload), return decoded string.

    Convenience wrapper: reads the FText header (u32 Flags + i8 HistoryType)
    then delegates to read_ftext_with_history. On any failure in tolerant mode,
    restores archive to field start and returns "".
    """
    start_pos = archive.tell()
    try:
        _flags = archive.read_u32()
        history_type_raw = archive.read_u8()
        history_type = history_type_raw - 256 if history_type_raw >= 128 else history_type_raw
        value, _ = read_ftext_with_history(archive, history_type, tolerant=tolerant)
        return value
    except (ParseError, struct.error, EOFError, OSError):
        if tolerant:
            archive.seek(start_pos)
            return ""
        raise


# ============================================================================
# Pin reference validation helper
# ============================================================================


def validate_pin_reference_at(
    archive: FArchive,
    pos: int,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport] = None,
) -> Optional[Dict[str, Any]]:
    """Validate PinReference structure at given position.

    Does not move pointer; only checks if the position conforms to PinReference format:
    - b_null (i32): 0 means normal ref, non-0 means null ref (4 bytes only)
    - owning_node (i32): within import/export range (only when b_null == 0)
    - pin_guid (16 bytes): non-zero (unless ParentPin null ref)

    Supports 4-byte null PinReference (only 4 bytes when b_null != 0).

    Returns:
        None: invalid structure
        Dict: {
            "b_null": int,
            "owning_node": int,
            "owning_node_valid": bool,
            "guid_nonzero": bool,
            "valid": bool,
            "reason": str,
            "serialized_size": int,  # 4 for null, 24 for non-null
        }
    """
    current_pos = archive.tell()

    file_size = getattr(archive, "_file_size", getattr(archive, "file_size", 0))

    # At least 4 bytes needed to read b_null
    if file_size and pos + 4 > file_size:
        archive.seek(current_pos)
        return None

    fmt = ">" if getattr(archive, "_byte_swapping", False) else "<"

    archive.seek(pos)
    header_bytes = archive.read(4)
    b_null = struct.unpack(f"{fmt}i", header_bytes[0:4])[0]

    if b_null != 0:
        # Null PinReference: only consumes 4 bytes
        archive.seek(current_pos)
        return {
            "b_null": b_null,
            "owning_node": 0,
            "owning_node_valid": True,
            "guid_nonzero": False,
            "valid": True,
            "reason": "valid null ref (b_null!=0, no actual pin)",
            "serialized_size": 4,
        }

    # b_null == 0: needs full 24 bytes
    if file_size and pos + 24 > file_size:
        archive.seek(current_pos)
        return None

    archive.seek(pos)
    header_bytes = archive.read(24)
    archive.seek(current_pos)

    owning_node = struct.unpack(f"{fmt}i", header_bytes[4:8])[0]
    guid_bytes = header_bytes[8:24]
    guid_nonzero = any(b != 0 for b in guid_bytes)

    # Validate owning_node range
    owning_node_abs = abs(owning_node)
    export_count = len(export_map)
    import_count = len(import_map) if import_map else 0
    max_valid_index = export_count + import_count + 50  # Allow some margin

    owning_node_valid = (
        owning_node == 0  # 0 means no ref
        or owning_node_abs < max_valid_index
    )

    # Validate b_null semantics
    if not owning_node_valid:
        valid = False
        reason = f"owning_node {owning_node} exceeds range 0..{max_valid_index}"
    elif not guid_nonzero:
        # b_null == 0 but GUID all-zero: possibly ParentPin null ref or uninitialized
        valid = True
        reason = "valid ref with zero guid (parent pin empty)"
    else:
        valid = True
        reason = "valid pin reference"

    return {
        "b_null": b_null,
        "owning_node": owning_node,
        "owning_node_valid": owning_node_valid,
        "guid_nonzero": guid_nonzero,
        "valid": valid,
        "reason": reason,
        "serialized_size": 24,
    }
