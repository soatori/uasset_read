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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.constants import (
    MAX_SAFE_COUNT,
    format_guid_bytes,
)
from uasset_read.exceptions import ParseError
from uasset_read.versioning import get_custom_version

logger = logging.getLogger(__name__)


# ============================================================================
# Core helpers
# ============================================================================


def seek_to_tag_end(archive: FArchive, tag) -> None:
    """Seek past a property tag's value if the reader hasn't reached it yet."""
    if tag.value_end_offset and archive.tell() < tag.value_end_offset:
        archive.seek(tag.value_end_offset)


def _read_guid(archive: FArchive, uppercase: bool = True) -> str:
    data = archive.read_bytes(16)
    if len(data) != 16:
        raise ParseError(f"FGuid requires 16 bytes, got {len(data)}")
    return format_guid_bytes(data, uppercase=uppercase)


# ============================================================================
# PropertyTag helper functions
# ============================================================================


# ============================================================================
# FText reading (UE5 multi history_type support)
# ============================================================================


def _read_fstring(archive: FArchive, max_length: int = MAX_SAFE_COUNT, *, tolerant: bool) -> str:
    """Read FString with explicit abnormal-length policy.

    References UE C++ FArchive& operator<<(FString&) implementation.

    FString serialization format (UE C++ String.cpp.inl:1810-1904):
    - length == 0: empty string (no data region)
    - length > 0: ANSI string, read length bytes
    - length < 0: UTF-16 string, read (-length * 2) bytes; -1 is a 2-byte NUL, never "no data"

    ``tolerant=True`` rewinds to the length prefix and returns "" on an
    abnormal length (pin-field fallback); ``tolerant=False`` raises so the
    upper layer aborts the whole FText instead of silently misaligning.
    """
    length = archive.read_i32()
    if length == 0:
        return ""
    if abs(length) > max_length:
        if not tolerant:
            raise ParseError(f"Invalid FText FString length: {length}")
        if archive.tell() >= 4:
            archive.seek(archive.tell() - 4)
        return ""
    if length < 0:
        data = archive.read(-length * 2)
        return data.decode("utf-16-le", errors="replace").rstrip("\x00")
    data = archive.read(length)
    return data.decode("utf-8", errors="replace").rstrip("\x00")


# FEditorObjectVersion::GUID (Engine/Source/Runtime/Core/Private/UObject/DevObjectVersion.cpp
# — serialized as little-endian FGuid A,B,C,D hex). Used only for the
# FNumberFormattingOptions AlwaysSign gate inside FText history type 4.
EDITOR_OBJECT_GUID = "ed68b0e4e94294f40bda31a241bb462e"
# FEditorObjectVersion::AddedAlwaysSignNumberFormattingOption (EditorObjectVersion.h)
EDITOR_VERSION_ADDED_ALWAYS_SIGN = 21


def _editor_object_version(summary) -> int:
    """FEditorObjectVersion for *summary*; modern layout (-1→skip) when absent."""
    if summary is None:
        # Synthetic callers without a package summary get the modern layout —
        # every UE4.15+/UE5 package that can carry AsNumber histories includes
        # the GUID at >= AddedAlwaysSignNumberFormattingOption.
        return EDITOR_VERSION_ADDED_ALWAYS_SIGN
    return get_custom_version(summary, EDITOR_OBJECT_GUID)


def _read_ftext_value(
    archive: FArchive,
    tolerant: bool = True,
    dev_notes: bool = False,
    summary=None,
) -> tuple[str, int, int, int]:
    """Read complete FText, returns (value, flags, history_type, consumed)."""
    start_pos = archive.tell()
    flags = archive.read_i32()
    history_type_raw = archive.read_u8()
    history_type = history_type_raw - 256 if history_type_raw >= 128 else history_type_raw
    value, _ = read_ftext_with_history(archive, history_type, tolerant=tolerant, dev_notes=dev_notes, summary=summary)
    return value, flags, history_type, archive.tell() - start_pos


def read_ftext_with_history(
    archive: FArchive,
    history_type: int,
    tolerant: bool = True,
    dev_notes: bool = False,
    summary=None,
) -> tuple[str, int]:
    """Read FText, returns (value, consumed_bytes).

    history_type (ETextHistoryType, signed int8):
    - -1 (0xFF): None (no history) - bHasCultureInvariantString (bool=4 bytes) + optional FString
    - 0: Base - Namespace (FString) + Key (FString) + SourceString (FString)
      [+ DevNotes (FString) when dev_notes is gated]
    - 1: NamedFormat - FormatText (recursive FText) + Arguments (TArray<FFormatArgumentData>)
    - 4: AsNumber - SourceValue (FFormatArgumentValue) + bHasFormatOptions
      [+ FNumberFormattingOptions] + CultureName (FString)
    - 2/3/5+: other generated types (not parsed; raise at the field boundary)

    References UE C++ source (paths relative to the Unreal Engine source root):
    - Engine/Source/Runtime/Core/Private/Internationalization/Text.cpp
      L888-1088: FText::SerializeText (Flags + HistoryType + history body)
      L1498-1538: FFormatArgumentValue operator<< (int8 Type + typed value)
      L140-161: FNumberFormattingOptions operator<< (AlwaysSign gated)
    - Engine/Source/Runtime/Core/Private/Internationalization/TextHistory.h
      L24-42: ETextHistoryType enum (AsNumber = 4)
    - Engine/Source/Runtime/Core/Private/Internationalization/TextHistory.cpp
      L1199-1207: FTextHistory_Generated::Serialize (no bytes)
      L1679-1723: FTextHistory_FormatNumber::Serialize
      L1774-1777: FTextHistory_AsNumber::Serialize
    - Engine/Source/Runtime/Core/Public/UObject/EditorObjectVersion.h
      L55: AddedAlwaysSignNumberFormattingOption (=21)
    """
    start_pos = archive.tell()
    value = ""

    if history_type not in range(-1, 11):
        raise ParseError(f"Invalid FText history_type={history_type} at pos {start_pos}")

    if history_type in (-1, 255):
        b_has_culture = archive.read_bool()
        if b_has_culture:
            value = _read_fstring(archive, tolerant=False)
    elif history_type == 0:
        _namespace = _read_fstring(archive, tolerant=False)
        _key = _read_fstring(archive, tolerant=False)
        value = _read_fstring(archive, tolerant=False)
        if dev_notes:
            # TextHistory.cpp:915-937: the gated 4th DevNotes FString follows SourceString.
            _read_fstring(archive, tolerant=False)
    elif history_type == 1:
        format_text, _, _, _ = _read_ftext_value(archive, tolerant=tolerant, dev_notes=dev_notes, summary=summary)
        arg_count = archive.read_i32()
        if arg_count < 0 or arg_count > MAX_SAFE_COUNT:
            # Design decision: from raise ParseError to warning+skip,
            # aligned with project tolerant mode, avoiding parse interruption from corrupt data
            logger.debug("FText NamedFormat arg_count=%d exceeds limit %d, skipping args", arg_count, MAX_SAFE_COUNT)
            arg_count = 0  # Skip subsequent argument reading
        format_args: dict[str, str] = {}
        for _ in range(arg_count):
            arg_name = _read_fstring(archive, tolerant=False)
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
                arg_value, _, _, _ = _read_ftext_value(archive, tolerant=tolerant, dev_notes=dev_notes, summary=summary)
            elif arg_type == 5:
                arg_value = str(archive.read_u8())
            else:
                raise ParseError(f"Unsupported FFormatArgumentType={arg_type}")
            format_args[arg_name] = arg_value
        value = format_text
        for key, arg in format_args.items():
            if key:
                value = value.replace("{" + key + "}", arg)
    elif history_type == 4:
        # ETextHistoryType::AsNumber → FTextHistory_AsNumber::Serialize
        # (TextHistory.cpp:1774) = FTextHistory_FormatNumber::Serialize
        # (TextHistory.cpp:1679); FTextHistory_Generated::Serialize writes no
        # bytes (TextHistory.cpp:1199).
        #
        # SourceValue: FFormatArgumentValue (Text.cpp) — int8 Type then
        # Int=int64 / UInt=uint64 / Float=f32 / Double=f64 / Text=FText /
        # Gender=uint8 (ETextGender). Widths match the Format (history=1)
        # branch above and UE's FFormatArgumentValue storage.
        arg_type = archive.read_i8()
        if arg_type == 0:  # EFormatArgumentType::Int
            source_value = str(archive.read_i64())
        elif arg_type == 1:  # UInt
            source_value = str(archive.read_u64())
        elif arg_type == 5:  # Gender (ETextGender, uint8)
            source_value = str(archive.read_u8())
        elif arg_type == 2:  # Float
            source_value = str(archive.read_f32())
        elif arg_type == 3:  # Double
            source_value = str(archive.read_f64())
        elif arg_type == 4:  # Text (recursive FText)
            source_value, _, _, _ = _read_ftext_value(archive, tolerant=tolerant, dev_notes=dev_notes, summary=summary)
        else:
            raise ParseError(f"Unsupported FFormatArgumentType={arg_type} in AsNumber history at pos {start_pos}")

        # bHasFormatOptions (FArchive bool = 4 bytes); when set, the
        # FNumberFormattingOptions record follows (Text.cpp:140-161):
        # AlwaysSign bool gated on FEditorObjectVersion >= 21, then UseGrouping
        # bool, RoundingMode int8, and four int32 digit bounds.
        if archive.read_bool():
            if _editor_object_version(summary) >= EDITOR_VERSION_ADDED_ALWAYS_SIGN:
                archive.read_bool()  # AlwaysSign
            archive.read_bool()  # UseGrouping
            archive.read_i8()  # RoundingMode
            archive.read_i32()  # MinimumIntegralDigits
            archive.read_i32()  # MaximumIntegralDigits
            archive.read_i32()  # MinimumFractionalDigits
            archive.read_i32()  # MaximumFractionalDigits

        # CultureName FString (formatting culture; empty in cooked/editor data)
        _read_fstring(archive, tolerant=False)
        value = source_value
    else:
        # Unsupported history: stop at the field boundary. No guessed byte
        # skips — the caller treats this as a structured partial failure.
        raise ParseError(f"Unsupported FText history_type={history_type}")

    consumed = archive.tell() - start_pos
    return value, consumed
