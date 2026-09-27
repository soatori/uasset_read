"""Single-tag property value dispatch + unversioned field walk.

The tagged export loop lives in ``parsers.properties.tagged``; this module
owns only value dispatch for a single known tag and the unversioned
mapping-driven field walk.
"""

from __future__ import annotations

import logging
import struct as _struct
from functools import cache
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

from uasset_read.exceptions import BINARY_READ_ERRORS, REFERENCE_RESOLVE_ERRORS

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectImport
    from uasset_read.serializers.package_summary import PackageFileSummary

from uasset_read.models.properties import PropertyTag, PropertyValue
from uasset_read.models.fallback import PropertyFallback, FallbackReason
from uasset_read.exceptions import ParseError, StreamPoisonedError
from uasset_read.constants import (
    MAX_PROPERTY_COUNT,
    PKG_UnversionedProperties,
    FIXED_UNVERSIONED_SIZES,
)
from uasset_read.versioning import ftext_dev_notes_enabled
from uasset_read.serializers.object_resources import ObjectExport

logger = logging.getLogger(__name__)

# Poison diagnostics mean the stream is misaligned (cursor rolled back);
# continuing the export property loop only multiplies the same OOR (Lyra
# MovieScene x28). name_index_out_of_range is intentionally excluded: read_name
# advances 8 bytes and returns "None" without rollback, so an aligned stream
# with an incomplete name map is a supported recovery path, not a stream abort.
_PROPERTY_STREAM_POISON_CODES = frozenset(
    {
        "fstring_out_of_range",
        "fstring_length_exceeds_limit",
    }
)


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
# There are no (None, ...) keys: unscoped slots raw-skip.
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

    Registry keys are (game_key, type_id | property_name). Only game-scoped
    keys are registered; an unhandled slot raw-skips ``tag.size`` bytes.
    """
    game_key = game.lower() if game else None
    handler = CUSTOM_PROPERTY_HANDLERS.get((game_key, type_id)) or CUSTOM_PROPERTY_HANDLERS.get((game_key, tag.type))
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


def _stream_is_poisoned(archive: "FArchive", diag_mark: int) -> bool:
    """True if a poison diagnostic was recorded since diag_mark."""
    new_diags = archive.get_structured_diagnostics()[diag_mark:]
    return any(d.code in _PROPERTY_STREAM_POISON_CODES for d in new_diags)


# Shared control-flow exception (also re-raised by parse_struct_property).


@cache
def _get_parse_functions():
    """Property type -> parse function mapping (cached; avoids circular import at module load)."""
    from uasset_read.parsers.property_types import (
        parse_bool_property,
        parse_int_property,
        parse_float_property,
        parse_str_property,
        parse_name_property,
        parse_object_property,
        parse_soft_object_property,
        parse_array_property,
        parse_struct_property,
        parse_map_property,
        parse_set_property,
        parse_enum_property,
        parse_text_property,
        parse_delegate_property,
        parse_uint16_property,
        parse_uint32_property,
        parse_uint64_property,
        parse_lazy_object_property,
        parse_asset_object_property,
        parse_multicast_delegate_property,
        parse_field_path_property,
        parse_optional_property,
        parse_verse_cell_property,
        parse_verse_value_property,
        parse_double_property,
        parse_guid_property,
    )

    # Type strings map straight to base functions; aliases like
    # parse_utf8_str_property / parse_class_property were removed with T12.
    return {
        "BoolProperty": parse_bool_property,
        "IntProperty": parse_int_property,
        "Int64Property": parse_int_property,
        "Int16Property": parse_int_property,
        "Int8Property": parse_int_property,
        "ByteProperty": parse_int_property,
        "UInt16Property": parse_uint16_property,
        "UInt32Property": parse_uint32_property,
        "UInt64Property": parse_uint64_property,
        "FloatProperty": parse_float_property,
        "DoubleProperty": parse_double_property,
        "StrProperty": parse_str_property,
        "NameProperty": parse_name_property,
        "ObjectProperty": parse_object_property,
        "SoftObjectProperty": parse_soft_object_property,
        "ArrayProperty": parse_array_property,
        "StructProperty": parse_struct_property,
        "MapProperty": parse_map_property,
        "SetProperty": parse_set_property,
        "EnumProperty": parse_enum_property,
        "TextProperty": parse_text_property,
        "DelegateProperty": parse_delegate_property,
        "Utf8StrProperty": parse_str_property,
        "WeakObjectProperty": parse_object_property,
        "LazyObjectProperty": parse_lazy_object_property,
        "ClassProperty": parse_object_property,
        "SoftClassProperty": parse_soft_object_property,
        "AssetObjectProperty": parse_asset_object_property,
        "AssetClassProperty": parse_asset_object_property,
        "MulticastDelegateProperty": parse_multicast_delegate_property,
        "MulticastInlineDelegateProperty": parse_multicast_delegate_property,
        "MulticastSparseDelegateProperty": parse_multicast_delegate_property,
        "InterfaceProperty": parse_object_property,
        "FieldPathProperty": parse_field_path_property,
        "OptionalProperty": parse_optional_property,
        "VerseStringProperty": parse_str_property,
        "VerseClassProperty": parse_object_property,
        "VerseFunctionProperty": parse_object_property,
        "VerseDynamicProperty": parse_object_property,
        "VerseCellProperty": parse_verse_cell_property,
        "VerseValueProperty": parse_verse_value_property,
        "AnsiStrProperty": parse_str_property,
        "GuidProperty": parse_guid_property,
    }


# Positional args parse_property_value passes each handler. Only the deviations from
# the ("tag", "archive") default are listed; names index the `values` dict below.
_ARGS_DEFAULT: tuple[str, ...] = ("tag", "archive")
_ARGS_OVERRIDES: dict[str, tuple[str, ...]] = {
    "TextProperty": ("tag", "archive", "dev_notes"),
    "NameProperty": ("tag", "archive", "name_map"),
    "DelegateProperty": ("tag", "archive", "name_map"),
    "MulticastDelegateProperty": ("tag", "archive", "name_map"),
    "MulticastInlineDelegateProperty": ("tag", "archive", "name_map"),
    "MulticastSparseDelegateProperty": ("tag", "archive", "name_map"),
    "FieldPathProperty": ("tag", "archive", "name_map"),
    "EnumProperty": ("tag", "archive", "name_map", "summary"),
    "SoftObjectProperty": ("tag", "archive", "name_map", "summary"),
    "SoftClassProperty": ("tag", "archive", "name_map", "summary"),
    "MapProperty": ("tag", "archive", "name_map", "export_map", "summary"),
    "SetProperty": ("tag", "archive", "name_map", "export_map", "summary"),
    "OptionalProperty": ("tag", "archive", "name_map", "export_map", "summary"),
    "ArrayProperty": ("tag", "archive", "name_map", "export_map", "summary", "depth"),
    "StructProperty": ("tag", "archive", "name_map", "export_map", "summary", "depth"),
}


def _skip_type_tree_nodes(
    archive,
    limit: int,
    map_len: int,
) -> bool:
    """Try to skip UE5.3+ FPropertyTypeName type tree, locating to the size field start position.

    FPropertyTypeName uses preorder traversal: each node is FName(8) + inner_count(4),
    inner_count indicates child node count. Skip the tree node by node using inner_count.

    Args:
        archive: FArchive positioned at the type tree start
        limit: readable upper bound (scan window or data boundary)
        map_len: name table length

    Returns:
        True if tree was skipped successfully (archive positioned before size), False indicates insufficient or invalid data
    """
    pending = 1
    max_nodes = 50  # safety limit consistent with _read_property_type_name
    for _ in range(max_nodes):
        if pending <= 0:
            break
        remaining = limit - archive.tell()
        if remaining < 12:  # minimum node: FName(8) + inner_count(4)
            return False
        # read node FName
        node_raw = archive.read(8)
        if len(node_raw) < 8:
            return False
        node_idx, _ = _struct.unpack("<II", node_raw)
        if not (0 <= node_idx < map_len):
            return False
        # read inner_count
        ic_raw = archive.read(4)
        if len(ic_raw) < 4:
            return False
        inner_count = _struct.unpack("<i", ic_raw)[0]
        if inner_count < 0 or inner_count > 100:
            return False
        pending = pending - 1 + inner_count
    return pending == 0


def parse_property_value(
    tag: PropertyTag,
    archive: FArchive,
    name_map: list[str],
    export_map: list[Any],
    summary: Any | None = None,
    depth: int = 0,
    tolerant: bool = True,
) -> Any:
    """Dispatch property value parsing (PROP-02 to PROP-06, ADVP-01 to ADVP-06).

    Unknown types return PropertyFallback (per D-05).

    Args:
        tag: PropertyTag instance
        archive: FArchive instance
        name_map: name table
        export_map: export table
        summary: PackageFileSummary instance (optional)
        depth: recursion depth (default 0)

    Returns:
        Parsed property value, unknown types return PropertyFallback
    """
    game = getattr(summary, "_game", None)

    if getattr(tag, "serialize_type", "Property") == "Skipped":
        raw_data = archive.read(tag.size) if tag.size > 0 else b""
        return {
            "kind": "skipped_property",
            "type": tag.type,
            "size": tag.size,
            "raw_data": raw_data,
        }
    if getattr(tag, "serialize_type", "Property") == "BinaryOrNative":
        from uasset_read.parsers.binary_or_native_handlers import BINARY_OR_NATIVE_HANDLERS

        def _native_handler(key: str):
            """struct_type handler with the F-prefix fallback, looked up once per key."""
            handler = BINARY_OR_NATIVE_HANDLERS.get(key)
            if handler is None and not key.startswith("F"):
                handler = BINARY_OR_NATIVE_HANDLERS.get(f"F{key}")
            return handler

        # Prefer concrete struct_type handlers before generic StructProperty
        # raw fallback so known natives (ExpressionInput family) stay structured.
        struct_type = getattr(tag, "struct_type", None)
        if tag.type == "StructProperty" and struct_type:
            handler = _native_handler(struct_type)
            if handler is not None:
                try:
                    result = handler(tag, archive, name_map, export_map, summary)
                    if result is not None:
                        return result
                except BINARY_READ_ERRORS as e:
                    logger.debug("BinaryOrNative struct_type handler failed for %s: %s", struct_type, e)

        # Try to use a known type parser
        handler = BINARY_OR_NATIVE_HANDLERS.get(tag.type)
        if handler is not None:
            try:
                result = handler(tag, archive, name_map, export_map, summary)
                if result is not None:
                    return result
                # Handler returned None (unknown type/parse failed), continue falling back to raw_data
            except BINARY_READ_ERRORS as e:
                logger.debug("BinaryOrNative handler failed for %s: %s", tag.type, e)
        # Also try by struct_type (with F-prefix fallback) for struct-specific
        # handlers — skipped when the struct-native pass above already ran.
        if struct_type and tag.type != "StructProperty":
            handler = _native_handler(struct_type)
            if handler is not None:
                try:
                    result = handler(tag, archive, name_map, export_map, summary)
                    if result is not None:
                        return result
                except BINARY_READ_ERRORS as e:
                    logger.debug("BinaryOrNative struct_type handler failed for %s: %s", struct_type, e)

        raw_data = archive.read(tag.size) if tag.size > 0 else b""
        return {
            "kind": "binary_or_native_property",
            "type": tag.type,
            "size": tag.size,
            "raw_data": raw_data,
        }

    parsers = _get_parse_functions()
    handler = parsers.get(tag.type)
    if handler is None:
        # D-05: Unknown type -- return structured PropertyFallback instead of None
        # First try custom property handling (0xFD/0xFE)
        type_parts = getattr(tag, "type_parts", None)
        if type_parts:
            first_node_name = type_parts[0][0] if type_parts else ""
            custom_id_map = {"CustomProperty_FD": 0xFD, "CustomProperty_FE": 0xFE}
            custom_id = custom_id_map.get(first_node_name)
            if custom_id is not None:
                try:
                    return handle_custom_property(custom_id, tag, archive, name_map, game=game)
                except BINARY_READ_ERRORS as e:
                    logger.debug("Custom property handler (0x%02X) failed for %s: %s", custom_id, tag.type, e)
        game_key = game.lower() if game else None
        if (game_key, tag.type) in CUSTOM_PROPERTY_HANDLERS:
            try:
                return handle_custom_property(0xFF, tag, archive, name_map, game=game)
            except BINARY_READ_ERRORS as e:
                logger.debug("Game-specific custom property handler failed for %s (game=%s): %s", tag.type, game, e)

        # All handlers do not match -- consume the payload and return PropertyFallback
        if tag.size > 0:
            archive.read(tag.size)
        return PropertyFallback.from_tag(tag, FallbackReason.UNSUPPORTED_TYPE)

    try:
        # Dispatch based on handler signature
        # Special case: ByteProperty with enum backing needs name_map (reads FName);
        # bypasses the arg table below.
        diag_mark = len(archive.get_structured_diagnostics())
        if tag.type == "ByteProperty" and tag.enum_type is not None:
            result = handler(tag, archive, name_map)
        else:
            # FText Base appends DevNotes when FortniteMainBranch >= AddDevNotesToFText=260
            # and the package was not filtered for editor-only data (TextHistory.cpp:917).
            dev_notes = ftext_dev_notes_enabled(summary)
            values = {
                "tag": tag,
                "archive": archive,
                "name_map": name_map,
                "export_map": export_map,
                "summary": summary,
                "depth": depth,
                "dev_notes": dev_notes,
            }
            result = handler(*(values[n] for n in _ARGS_OVERRIDES.get(tag.type, _ARGS_DEFAULT)))
        if _stream_is_poisoned(archive, diag_mark):
            # Abort nested multi-entry parsers (Map/Set/Array) that would
            # re-read the same misaligned position for every remaining entry.
            raise StreamPoisonedError(
                f"Poison diagnostic while parsing '{tag.name}' ({tag.type}); aborting value stream"
            )
        return result
    except StreamPoisonedError:
        raise
    except (_struct.error, OSError, ValueError, AttributeError, KeyError, ParseError) as e:
        if not tolerant:
            raise
        logger.debug("Property handler failed for %s.%s: %s", tag.name, tag.type, e)
        return PropertyFallback.from_tag(tag, FallbackReason.PARSE_ERROR)


def _handle_unversioned_properties(
    export: ObjectExport,
    archive: "FArchive",
    summary: "PackageFileSummary",
    name_map: list[str],
    export_map: list[Any],
    mappings: Any,
    import_map: list[ObjectImport] | None,
    property_end: int,
    tolerant: bool,
) -> list[PropertyValue] | None:
    """Handle unversioned properties. Return parse result or None (need to fall back to normal parsing)."""
    uses_unversioned = bool(getattr(summary, "package_flags", 0) & PKG_UnversionedProperties)
    if not uses_unversioned:
        return None

    if mappings is not None:
        struct_name = _resolve_mapping_struct_name(export, import_map, export_map)
        mapped = getattr(mappings, "mappings", mappings)
        if hasattr(mapped, "get_struct") and mapped.get_struct(struct_name) is not None:
            return _parse_unversioned_properties_from_mapping(
                export,
                archive,
                summary,
                name_map,
                export_map,
                mapped,
                struct_name,
                property_end,
                tolerant=tolerant,
            )

    # Unversioned package with no reliable mapping -> output opaque block, do not guess fields
    opaque_size = property_end - archive.tell()
    raw_bytes = archive.read(opaque_size) if opaque_size > 0 else b""
    logger.debug(
        "Unversioned export '%s' without mappings, returning opaque block (%d bytes)",
        export.object_name,
        len(raw_bytes),
    )
    return [
        PropertyFallback(
            name=export.object_name,
            type="UnversionedOpaque",
            size=len(raw_bytes),
            reason=FallbackReason.MISSING_MAPPING,
        )
    ]


def _resolve_mapping_struct_name(
    export: ObjectExport, import_map: list[ObjectImport] | None, export_map: list[Any]
) -> str:
    if import_map is not None:
        try:
            from uasset_read.serializers.object_resources import resolve_class_name

            return resolve_class_name(export.class_index, import_map, export_map) or export.object_name
        except REFERENCE_RESOLVE_ERRORS as e:
            logger.debug("Failed to resolve mapping struct name: %s", e)
    return export.object_name


def _parse_unversioned_properties_from_mapping(
    export: ObjectExport,
    archive: FArchive,
    summary: "PackageFileSummary",
    name_map: list[str],
    export_map: list[Any],
    mappings: Any,
    struct_name: str,
    property_end: int,
    tolerant: bool = True,
) -> list[PropertyValue]:
    """Parse a mapping-driven unversioned property stream.

    Principles (Wave B P6):
    1. No usmap / struct miss → whole-region UnversionedOpaque.
    2. Hit → sequential read from correct unversioned start; variable size
       unreliable → stop and opaque remainder.
    3. Never fall back to tagged FName parsing.
    """
    struct_mapping = mappings.get_struct(struct_name)
    if struct_mapping is None:
        return []
    ordered_properties = _ordered_mapping_properties(mappings, struct_mapping)
    region_start = archive.tell()
    header = _try_read_unversioned_header(archive, property_end, len(ordered_properties))
    if header is None:
        # Unversioned packages always carry an FUnversionedHeader; a failed
        # header means the stream start is wrong or the schema does not match.
        # Never fall back to sequential tagged-style guessing.
        archive.seek(region_start)
        remaining = property_end - region_start
        raw_bytes = archive.read(remaining) if remaining > 0 else b""
        return [
            PropertyFallback(
                name=export.object_name,
                type="UnversionedOpaque",
                size=len(raw_bytes),
                reason=FallbackReason.MISSING_MAPPING,
            )
        ]
    selected_properties = [(ordered_properties[index], is_zero) for index, is_zero in header]
    out: list[PropertyValue] = []
    for position, (info, is_zero) in enumerate(selected_properties):
        if archive.tell() >= property_end and not is_zero:
            break
        remaining = property_end - archive.tell()
        is_last = position == len(selected_properties) - 1
        fixed_size = _fixed_unversioned_size(info.mapping_type)
        estimated_size = (
            0 if fixed_size > 0 else _estimate_unversioned_variable_size(info.mapping_type, archive, remaining)
        )
        # Unversioned bool is a raw uint8; the tagged handler reads tag.bool_val.
        if info.mapping_type.type == "BoolProperty" and not is_zero:
            if remaining < 1:
                break
            out.append(PropertyValue(info.name, "BoolProperty", bool(archive.read_u8())))
            continue
        # Unversioned FText: flags(i32) + history(u8) + typed body.
        if info.mapping_type.type == "TextProperty" and not is_zero:
            text_value = _read_unversioned_ftext(archive, property_end)
            if text_value is None:
                break
            out.append(PropertyValue(info.name, "TextProperty", text_value))
            continue
        # Unversioned EnumProperty: FName value; validate index before consuming.
        if info.mapping_type.type == "EnumProperty" and not is_zero:
            if remaining < 8:
                break
            name_pos = archive.tell()
            name_idx = archive.read_i32()
            name_num = archive.read_i32()
            if not (0 <= name_idx < len(name_map)):
                archive.seek(name_pos)
                break
            from uasset_read.models.properties import EnumValue

            enum_type = getattr(info.mapping_type, "enum_name", None) or "UnknownEnum"
            value_name = name_map[name_idx]
            if name_num > 0:
                value_name = f"{value_name}_{name_num}"
            out.append(
                PropertyValue(
                    info.name,
                    "EnumProperty",
                    EnumValue(enum_type=enum_type, value_name=value_name),
                )
            )
            continue
        # Unversioned StructProperty: nested FUnversionedHeader for the struct.
        if info.mapping_type.type == "StructProperty" and not is_zero:
            struct_type = getattr(info.mapping_type, "struct_type", None)
            fields = None
            if struct_type and hasattr(mappings, "get_struct") and mappings.get_struct(struct_type) is not None:
                nested_ordered = _ordered_mapping_properties(mappings, mappings.get_struct(struct_type))
                nested_start = archive.tell()
                nested_header = _try_read_unversioned_header(archive, property_end, len(nested_ordered))
                if nested_header is not None:
                    fields = {}
                    for npos, (ninfo, nzero) in enumerate([(nested_ordered[ix], z) for ix, z in nested_header]):
                        if archive.tell() >= property_end and not nzero:
                            break
                        if nzero:
                            fields[ninfo.name] = _unversioned_zero_value(ninfo.mapping_type)
                            continue
                        nfixed = _fixed_unversioned_size(ninfo.mapping_type)
                        nest_remaining = property_end - archive.tell()
                        ntag = PropertyTag(
                            name=ninfo.name,
                            type=ninfo.mapping_type.type,
                            size=_unversioned_property_size(
                                ninfo.mapping_type, archive, nest_remaining, npos == len(nested_header) - 1
                            ),
                        )
                        _apply_mapping_type_to_tag(ntag, ninfo.mapping_type)
                        nstart = archive.tell()
                        try:
                            nvalue = parse_property_value(
                                ntag, archive, name_map, export_map, summary, tolerant=tolerant
                            )
                        except (ParseError, *BINARY_READ_ERRORS):
                            fields = None
                            archive.seek(nested_start)
                            break
                        if nfixed <= 0 and ntag.size <= 0 and archive.tell() == nstart:
                            fields = None
                            archive.seek(nested_start)
                            break
                        fields[ninfo.name] = nvalue
                else:
                    archive.seek(nested_start)
            if fields is not None:
                from uasset_read.models.properties import StructValue

                out.append(
                    PropertyValue(
                        info.name,
                        "StructProperty",
                        StructValue(
                            struct_type=struct_type or "UnknownStruct",
                            fields=fields,
                            raw_size=0,
                            parse_status="complete",
                        ),
                    )
                )
                continue
            # Nested struct unmapped/unreliable: opaque remainder.
            tail_start = archive.tell()
            tail_size = max(0, property_end - tail_start)
            tail = archive.read(tail_size) if tail_size > 0 else b""
            if tail:
                out.append(
                    PropertyValue(
                        name="_unversioned_tail",
                        type="Opaque",
                        value={
                            "parse_status": "opaque",
                            "raw_offset": tail_start,
                            "raw_size": len(tail),
                            "raw_data": tail,
                        },
                    )
                )
            break
        # Variable-size types without reliable estimate: stop and opaque remainder.
        # SoftObjectProperty reads FNames that can emit name-index diagnostics when
        # misaligned; stop before parsing rather than after.
        if (
            not is_zero
            and fixed_size <= 0
            and estimated_size <= 0
            and info.mapping_type.type
            in ("ArrayProperty", "SetProperty", "MapProperty", "OptionalProperty", "SoftObjectProperty")
        ):
            tail_start = archive.tell()
            tail_size = max(0, property_end - tail_start)
            tail = archive.read(tail_size) if tail_size > 0 else b""
            if tail:
                out.append(
                    PropertyValue(
                        name="_unversioned_tail",
                        type="Opaque",
                        value={
                            "parse_status": "opaque",
                            "raw_offset": tail_start,
                            "raw_size": len(tail),
                            "raw_data": tail,
                        },
                    )
                )
            break
        tag = PropertyTag(
            name=info.name,
            type=info.mapping_type.type,
            size=_unversioned_property_size(info.mapping_type, archive, remaining, is_last),
        )
        _apply_mapping_type_to_tag(tag, info.mapping_type)
        if is_zero:
            out.append(PropertyValue(info.name, tag.type, _unversioned_zero_value(info.mapping_type)))
            continue
        start = archive.tell()
        diag_mark = len(archive.get_structured_diagnostics())
        try:
            value = parse_property_value(tag, archive, name_map, export_map, summary, tolerant=tolerant)
        except ParseError:
            if not tolerant:
                raise
            if tag.size > 0:
                seek_target = min(start + tag.size, property_end, archive.total_size())
                archive.seek(seek_target)
            fb = PropertyFallback(
                name=info.name,
                type=tag.type,
                size=tag.size,
                reason=FallbackReason.PARSE_ERROR,
                array_index=0,
            )
            out.append(PropertyValue(info.name, "Warning", fb))
            continue
        # Name-index diagnostics mean the stream is misaligned; stop and opaque.
        new_diags = archive.get_structured_diagnostics()[diag_mark:]
        if any(d.code == "name_index_out_of_range" for d in new_diags):
            archive.seek(start)
            tail_start = archive.tell()
            tail_size = max(0, property_end - tail_start)
            tail = archive.read(tail_size) if tail_size > 0 else b""
            if tail:
                out.append(
                    PropertyValue(
                        name="_unversioned_tail",
                        type="Opaque",
                        value={
                            "parse_status": "opaque",
                            "raw_offset": tail_start,
                            "raw_size": len(tail),
                            "raw_data": tail,
                        },
                    )
                )
            break
        if tag.size <= 0:
            tag.size = archive.tell() - start
        out.append(PropertyValue(info.name, tag.type, value))
    if archive.tell() < property_end:
        remaining = property_end - archive.tell()
        current_pos = archive.tell()
        file_size = getattr(archive, "_file_size", None)
        tail_size = max(0, min(remaining, file_size - current_pos)) if isinstance(file_size, int) else remaining
        tail = archive.read(tail_size) if tail_size > 0 else b""
        if tail:
            out.append(
                PropertyValue(
                    name="_unversioned_tail",
                    type="Opaque",
                    value={
                        "parse_status": "opaque",
                        "raw_offset": property_end - len(tail),
                        "raw_size": len(tail),
                        "raw_data": tail,
                    },
                )
            )
    return out


def _read_unversioned_ftext(archive: FArchive, property_end: int) -> Any | None:
    """Read an unversioned FText value; return None when the stream is short.

    UE FText layout (Text.cpp / TextHistory.cpp): flags(i32) + history(u8) +
    typed body. ETextHistoryType::None is -1 (0xFF): bHasCultureInvariantString
    (bool as u32) + optional FString. Base (0) is three FStrings.
    """
    from uasset_read.models.properties import TextValue

    start = archive.tell()
    try:
        if start + 5 > property_end:
            return None
        _flags = archive.read_i32()
        history = archive.read_u8()
        if history == 0:  # Base
            namespace = archive.read_fstring()
            key = archive.read_fstring()
            source = archive.read_fstring()
            return TextValue(
                namespace=namespace or "",
                key=key or "",
                source_string=source or "",
                history_type=0,
            )
        if history in (255, 0xFF):  # None / culture-invariant
            if archive.tell() + 4 > property_end:
                return None
            has_culture = archive.read_bool()
            source = archive.read_fstring() if has_culture else ""
            return TextValue(
                namespace="",
                key="",
                source_string=(source or "").rstrip("\x00"),
                history_type=255,
            )
        # Other history types: body layout unknown without tag.size — stop so
        # the caller can opaque the remainder instead of inventing empty text.
        archive.seek(start)
        return None
    except (*BINARY_READ_ERRORS, ValueError, _struct.error):
        archive.seek(start)
        return None


def _try_read_unversioned_header(
    archive: FArchive,
    property_end: int,
    property_count: int,
) -> list[tuple[int, bool | None]] | None:
    """Try UE FUnversionedHeader fragments; return None for legacy fixture streams.

    Byte-level fragment + zero-mask parsing is delegated to
    ``parse_unversioned_header`` (the single header parser); this wrapper only
    binds the stream to a bounded read and maps fragments onto schema indices.
    """
    from uasset_read.parsers.properties.unversioned import parse_unversioned_header

    start = archive.tell()
    try:
        raw = archive.read(property_end - start)
        header = parse_unversioned_header(raw)
    except (ValueError, _struct.error, OSError, ParseError) as e:
        logger.debug("Unversioned header parse failed, falling back to legacy: %s", e)
        archive.seek(start)
        return None

    total_values = 0
    schema_cursor = 0
    for frag in header.fragments:
        schema_cursor += frag.skip_num
        if schema_cursor + frag.value_num > property_count:
            logger.debug("unversioned fragment exceeds mapping property count")
            archive.seek(start)
            return None
        schema_cursor += frag.value_num
        total_values += frag.value_num
    if total_values == 0:
        logger.debug("no unversioned values")
        archive.seek(start)
        return None

    selected: list[tuple[int, bool | None]] = []
    bit_offset = 0
    schema_cursor = 0
    for frag in header.fragments:
        schema_cursor += frag.skip_num
        for local_index in range(frag.value_num):
            is_zero = header.zero_bits[bit_offset + local_index] if frag.has_any_zeroes else False
            selected.append((schema_cursor + local_index, is_zero))
        if frag.has_any_zeroes:
            bit_offset += frag.value_num
        schema_cursor += frag.value_num

    archive.seek(start + header.header_size)
    return selected


def _unversioned_zero_value(prop_type: Any) -> Any:
    type_name = getattr(prop_type, "type", prop_type)
    if type_name in {"BoolProperty"}:
        return False
    if type_name in {
        "IntProperty",
        "UInt32Property",
        "Int64Property",
        "UInt64Property",
        "Int16Property",
        "UInt16Property",
        "Int8Property",
        "ByteProperty",
        "ObjectProperty",
        "ClassProperty",
    }:
        return 0
    if type_name in {"FloatProperty", "DoubleProperty"}:
        return 0.0
    if type_name in {"ArrayProperty", "SetProperty"}:
        return []
    if type_name == "MapProperty":
        from uasset_read.models.properties import MapValue

        return MapValue(key_type="Unknown", value_type="Unknown", entries=[])
    if type_name == "OptionalProperty":
        return {"has_value": False, "value": None}
    return None


def _ordered_mapping_properties(mappings: Any, struct_mapping: Any) -> list[Any]:
    """Return mapped fields in serialized order, including inherited fields first."""
    chain: list[Any] = []
    seen: set[str] = set()

    def visit(mapping: Any) -> None:
        if mapping is None or mapping.name in seen:
            return
        seen.add(mapping.name)
        visit(mappings.get_struct(getattr(mapping, "super_type", None)))
        chain.extend(mapping.properties[index] for index in sorted(mapping.properties))

    visit(struct_mapping)
    return chain


def _unversioned_property_size(prop_type: Any, archive: FArchive, remaining: int, is_last: bool) -> int:
    fixed = _fixed_unversioned_size(prop_type)
    if fixed > 0:
        return fixed
    estimated = _estimate_unversioned_variable_size(prop_type, archive, remaining)
    if estimated > 0:
        return estimated
    if is_last:
        return remaining
    return 0


def _estimate_unversioned_variable_size(prop_type: Any, archive: FArchive, remaining: int) -> int:
    """Estimate simple variable-size unversioned containers without consuming bytes."""
    type_name = getattr(prop_type, "type", prop_type)
    current = archive.tell()
    try:
        if remaining < 4:
            return 0
        if type_name == "ArrayProperty":
            inner = getattr(prop_type, "inner_type", None)
            inner_size = _fixed_unversioned_size(inner)
            if inner_size <= 0:
                return 0
            count = archive.read_i32()
            if count < 0 or count > MAX_PROPERTY_COUNT:
                return 0
            return min(remaining, 4 + count * inner_size)
        if type_name == "SetProperty":
            inner = getattr(prop_type, "inner_type", None)
            inner_size = _fixed_unversioned_size(inner)
            if inner_size <= 0:
                return 0
            count = archive.read_i32()
            if count < 0 or count > MAX_PROPERTY_COUNT:
                return 0
            return min(remaining, 4 + count * inner_size)
        if type_name == "MapProperty":
            key = getattr(prop_type, "inner_type", None)
            value = getattr(prop_type, "value_type", None)
            entry_size = _fixed_unversioned_size(key) + _fixed_unversioned_size(value)
            if entry_size <= 0:
                return 0
            count = archive.read_i32()
            if count < 0 or count > MAX_PROPERTY_COUNT:
                return 0
            return min(remaining, 4 + count * entry_size)
        if type_name == "OptionalProperty":
            inner = getattr(prop_type, "inner_type", None)
            inner_size = _fixed_unversioned_size(inner)
            if inner_size <= 0:
                return 0
            return min(remaining, 4 + inner_size)
    except (_struct.error, ValueError, AttributeError) as e:
        logger.debug("Unversioned variable size estimation failed: %s", e)
        return 0
    finally:
        archive.seek(current)
    return 0


def _fixed_unversioned_size(prop_type: Any) -> int:
    type_name = getattr(prop_type, "type", prop_type)
    if type_name == "EnumProperty":
        # EnumProperty.cpp / UnversionedPropertySerialization.cpp: unversioned enum
        # values serialize as FName (index+number), regardless of the byte-property underlying.
        return 8
    return FIXED_UNVERSIONED_SIZES.get(type_name, 0)


def _apply_mapping_type_to_tag(tag: PropertyTag, prop_type: Any) -> None:
    tag.struct_type = getattr(prop_type, "struct_type", None)
    tag.enum_type = getattr(prop_type, "enum_name", None)
    inner = getattr(prop_type, "inner_type", None)
    value = getattr(prop_type, "value_type", None)
    if inner is not None:
        tag.inner_type = getattr(inner, "type", None)
        # For Array/Set inner elements that are StructProperty, save inner struct_type
        if tag.type in ("ArrayProperty", "SetProperty"):
            tag.inner_type_struct = getattr(inner, "struct_type", None)
        if tag.type == "MapProperty":
            tag.key_type = getattr(inner, "type", None)
            tag.key_type_struct = getattr(inner, "struct_type", None)
    if value is not None:
        tag.value_type = getattr(value, "type", None)
        tag.value_type_struct = getattr(value, "struct_type", None)
