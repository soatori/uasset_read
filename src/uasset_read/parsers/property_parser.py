"""Single-tag property value dispatch, per-type readers, and unversioned field walk.

The tagged export loop lives in ``parsers.properties.tagged``; this module
owns value dispatch for a single known tag, the ``parse_*_property`` readers,
and the unversioned mapping-driven field walk.
"""

from __future__ import annotations

import logging
import struct
import struct as _struct
from dataclasses import replace
from functools import cache
from typing import TYPE_CHECKING, Any
from collections.abc import Callable

from uasset_read.exceptions import BINARY_READ_ERRORS, REFERENCE_RESOLVE_ERRORS

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectImport
    from uasset_read.serializers.package_summary import PackageFileSummary

from uasset_read.models.properties import (
    PropertyTag,
    PropertyValue,
    StructValue,
    MapValue,
    SetValue,
    EnumValue,
    TextValue,
    DelegateValue,
    SoftObjectPathValue,
)
from uasset_read.models.fallback import PropertyFallback, FallbackReason
from uasset_read.exceptions import ExportBoundsExceeded, ParseError, StreamPoisonedError
from uasset_read.constants import (
    MAX_PROPERTY_COUNT,
    MAX_ARRAY_COUNT,
    UE5_LARGE_WORLD_COORDINATES,
    UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES,
    UE5_ADD_SOFTOBJECTPATH_LIST,
    MAX_SAFE_COUNT,
    UE_NONE_SENTINEL,
    format_guid_bytes,
    PKG_UnversionedProperties,
    FIXED_UNVERSIONED_SIZES,
)
from uasset_read.versioning import ftext_dev_notes_enabled, require_version_context
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
        payload_offset = archive.tell()
        logger.debug(
            "CustomProperty 0x%02X: no handler registered, skipping %d bytes",
            type_id,
            tag.size,
        )
        raw_data = archive.read(tag.size) if tag.size > 0 else b""
        archive._record_structured_diagnostic(
            code="CUSTOM_PROPERTY_UNHANDLED",
            stage="parse_properties",
            offset=payload_offset,
            size=len(raw_data),
            fallback="retained_as_raw_bytes",
            reason="known_unimplemented",
            message=f"Custom property 0x{type_id:02X} ({tag.type}) has no registered handler",
        )
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
    return any(d.code in _PROPERTY_STREAM_POISON_CODES for d in archive._diagnostics_since(diag_mark))


# Shared control-flow exception (also re-raised by parse_struct_property).


@cache
def _get_parse_functions():
    """Property type -> parse function mapping (cached)."""
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
    "SoftObjectProperty": ("tag", "archive", "name_map", "file_version_ue5"),
    "SoftClassProperty": ("tag", "archive", "name_map", "file_version_ue5"),
    "MapProperty": ("tag", "archive", "name_map", "export_map", "summary", "depth", "tolerant"),
    "SetProperty": ("tag", "archive", "name_map", "export_map", "summary", "depth", "tolerant"),
    "OptionalProperty": ("tag", "archive", "name_map", "export_map", "summary", "depth", "tolerant"),
    "ArrayProperty": ("tag", "archive", "name_map", "export_map", "summary", "depth", "tolerant"),
    "StructProperty": (
        "tag",
        "archive",
        "name_map",
        "export_map",
        "file_version_ue5",
        "summary",
        "depth",
        "tolerant",
    ),
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

        payload_offset = archive.tell()
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
        archive._record_structured_diagnostic(
            code="BINARY_OR_NATIVE_PROPERTY_OPAQUE",
            stage="parse_properties",
            offset=payload_offset,
            size=len(raw_data),
            fallback="retained_as_raw_bytes",
            reason="known_unimplemented",
            message=f"BinaryOrNative property {tag.name!r} ({tag.type}) could not be decoded",
        )
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
        diag_mark = archive._diagnostic_mark()
        if tag.type == "ByteProperty" and tag.enum_type is not None:
            result = handler(tag, archive, name_map)
        else:
            # FText Base appends DevNotes when FortniteMainBranch >= AddDevNotesToFText=260
            # and the package was not filtered for editor-only data (TextHistory.cpp:917).
            ctx = require_version_context(archive)
            dev_notes = ftext_dev_notes_enabled(summary, ctx)
            values = {
                "tag": tag,
                "archive": archive,
                "name_map": name_map,
                "export_map": export_map,
                "file_version_ue5": ctx.file_version_ue5,
                "summary": summary,
                "depth": depth,
                "tolerant": tolerant,
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
        if hasattr(mapped, "get_struct"):
            if mapped.get_struct(struct_name) is None and mapped.get_struct(export.object_name) is not None:
                # A class export's own unversioned stream follows the schema named by
                # the class itself; resolve_class_name() only sees its metaclass (#665).
                struct_name = export.object_name
            if mapped.get_struct(struct_name) is not None:
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
        diag_mark = archive._diagnostic_mark()
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
        new_diags = archive._diagnostics_since(diag_mark)
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
        archive._record_structured_diagnostic(
            code="INVALID_COLLECTION_COUNT",
            stage="parse_properties",
            offset=offset,
            raw_value=count,
            fallback="used_empty_collection",
            reason="recovered_corruption",
            message=f"{label} count is negative; collection skipped",
        )
        logger.debug(
            "%s: count is negative (%d)，skipping | pos=0x%X, limit=%d",
            label,
            count,
            offset,
            max_count,
        )
        return 0
    if count > max_count:
        archive._record_structured_diagnostic(
            code="INVALID_COLLECTION_COUNT",
            stage="parse_properties",
            offset=offset,
            raw_value=count,
            fallback="used_empty_collection",
            reason="recovered_corruption",
            message=f"{label} count exceeds maximum {max_count}; collection skipped",
        )
        logger.debug(
            "%s: count exceeds maximum (%d > %d)，skipping | pos=0x%X",
            label,
            count,
            max_count,
            offset,
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
    # #143: When enum_type is unknown, do not add "UnknownEnum::" prefix.
    # Some serialized FName values are already fully qualified.
    prefix = f"{enum_type}::"
    full_name = (
        value_name
        if not enum_type or enum_type == "UnknownEnum" or value_name.startswith(prefix)
        else f"{prefix}{value_name}"
    )
    return {
        "enum_type": enum_type,
        "value_name": full_name,
    }


def extract_inner_from_tag(tag_type: str) -> str | None:
    """Extract content within parentheses from tag.type string

    Args:
        tag_type: type string, e.g. "ArrayProperty(IntProperty)"

    Returns:
        Content within parentheses, or None if no parentheses
    """
    start = tag_type.find("(")
    end = tag_type.rfind(")")
    if start != -1 and end != -1 and end > start:
        return tag_type[start + 1 : end]
    return None


# Expected byte sizes for fixed-layout structs (used for fast-path validation)
_EXPECTED_STRUCT_SIZES: dict[str, int] = {
    "LinearColor": 16,
    "Color": 4,
    "Guid": 16,
    "IntPoint": 8,
    "IntVector": 12,
    "Box2D": 20,
    "OrientedBox": 60,
    # Time/frame types
    "Timespan": 8,  # int64
    "DateTime": 8,  # uint64
    "FrameNumber": 4,  # int32
    # Integer vector types
    "IntVector2": 8,  # 2 * int32
    "Int32Vector2": 8,  # alias
    "IntVector4": 16,  # 4 * int32
    "UintVector": 12,  # 3 * uint32
    "UintVector2": 8,  # 2 * uint32
    "Uint32Point": 8,  # alias
    "UintVector4": 16,  # 4 * uint32
    # 64-bit integer vector types
    "Int64Vector2": 16,  # 2 * int64
    "Int64Point": 16,  # alias
    "Int64Vector": 24,  # 3 * int64
    "Int64Vector4": 32,  # 4 * int64
    "UInt64Vector2": 16,  # 2 * uint64
    "UInt64Point": 16,  # alias
    "UInt64Vector": 24,  # 3 * uint64
    "UInt64Vector4": 32,  # 4 * uint64
    # Alias types
    "DeprecateSlateVector2D": 16,  # alias of Vector2D
    "VectorDouble": 24,  # Wuthering Waves alias for Vector3d
    "Int32Point": 8,  # alias of IntPoint
    "Box2f": 16,  # 2 * Vector2f(8)
    "Box3f": 24,  # 2 * Vector3f(12)
    "Matrix44f": 64,  # 4 * Plane4f(16)
    "Transform3f": 40,  # FTransform3f: Quat4f(16) + Vector3f(12) + Vector3f(12)
    # Animation/blendspace high-frequency structs (reported additions)
    "FrameRate": 8,  # compact format: int32 Numerator + int32 Denominator
    # tagged format size is not fixed (measured 37), silently parsed via tagged fallback
    "AnimNotifyTrack": 8,  # compact format size
    # tagged format size=0, silently parsed via tagged fallback (data actually exists)
    "GuidProperty": 16,  # FGuid standard size
}

# LWC (Large World Coordinates) type mapping
# From UE5 UE5_LARGE_WORLD_COORDINATES(1004), math vector types use double precision.
# _LWC_TYPE_MAP: base type name → (float_size, double_size)
# When version_container's file_version_ue5 >= 1004, base types use double_size.
_LWC_TYPE_MAP: dict[str, tuple[int, int]] = {
    "Vector": (12, 24),  # FVector3f → FVector3d
    "Rotator": (12, 24),  # FRotator3f → FRotator3d
    "Vector2D": (8, 16),  # FVector2f → FVector2d
    "Vector4": (16, 32),  # FVector4f → FVector4d
    "Quat": (16, 32),  # FQuat4f → FQuat4d
    "Plane": (16, 32),  # FPlane4f → FPlane4d
    "Sphere": (16, 32),  # FSphere3f → FSphere3d
    # Box.h:45 uint8 IsValid + operator<< (Box.h:666-668) writes Min + Max + IsValid(1 byte)
    "Box": (25, 49),  # float = 12+12+1, double = 24+24+1
    "BoxSphereBounds": (28, 56),  # 3 * FVector + float (float → double)
    "Matrix": (64, 128),  # 4 * FPlane (float → double)
    "TwoVectors": (24, 48),  # 2 * FVector (float → double)
    "Transform": (40, 80),  # FTransform3f(40) → FTransform3d(80), select read precision based on tag.size
}

# LWC double precision type name → corresponding base type name
# e.g. "Vector3d" → "Vector", used for get_struct_size fallback lookup
_LWC_DOUBLE_TYPE_TO_BASE: dict[str, str] = {
    "Vector3d": "Vector",
    "Vector4d": "Vector4",
    "Rotator3d": "Rotator",
    "Quat4d": "Quat",
    "Plane4d": "Plane",
    "Sphere3d": "Sphere",
}

# LWC single precision type name → corresponding base type name
_LWC_FLOAT_TYPE_TO_BASE: dict[str, str] = {
    "Vector3f": "Vector",
    "Vector4f": "Vector4",
    "Rotator3f": "Rotator",
    "Quat4f": "Quat",
    "Plane4f": "Plane",
    "Sphere3f": "Sphere",
    "Vector2f": "Vector2D",
}

# Pure f32/f64 structs on the fast path: name -> field keys, serialization order.
# double-size = 8 * len(keys); any other tag.size reads as f32 (current behavior).
_FLAT_FLOAT_STRUCTS: dict[str, tuple[str, ...]] = {
    "Vector": ("X", "Y", "Z"),
    "Rotator": ("Pitch", "Yaw", "Roll"),
    "Vector2D": ("X", "Y"),
    "Vector4": ("X", "Y", "Z", "W"),
    "Quat": ("X", "Y", "Z", "W"),
    "Plane": ("X", "Y", "Z", "W"),
}


def get_struct_size(
    struct_type: str,
    file_version_ue5: int = 0,
) -> int | None:
    """Return expected byte size for fixed-layout structs (version-aware).

    For LWC (Large World Coordinates) types:
    - If file_version_ue5 >= 1004 (UE5 LWC), return double precision size
    - Otherwise return single precision size
    - If struct_type is an explicit double variant (e.g. "Vector3d"), always return double precision size

    Args:
        struct_type: struct type name (e.g. "Vector", "Vector3d")
        file_version_ue5: UE5 file version number (0 for unknown)

    Returns:
        expected byte size, None for unknown types
    """
    # Explicit double variant: return double size directly, ignoring version
    base_for_double = _LWC_DOUBLE_TYPE_TO_BASE.get(struct_type)
    if base_for_double is not None:
        _, double_size = _LWC_TYPE_MAP[base_for_double]
        return double_size

    # Explicit float variant: return float size directly, ignoring version
    base_for_float = _LWC_FLOAT_TYPE_TO_BASE.get(struct_type)
    if base_for_float is not None:
        float_size, _ = _LWC_TYPE_MAP[base_for_float]
        return float_size

    # LWC-aware base type: determine by version
    if struct_type in _LWC_TYPE_MAP:
        float_size, double_size = _LWC_TYPE_MAP[struct_type]
        if file_version_ue5 >= 1000 and file_version_ue5 >= UE5_LARGE_WORLD_COORDINATES:
            return double_size
        return float_size

    # Non-LWC type: direct table lookup
    return _EXPECTED_STRUCT_SIZES.get(struct_type)


_TAGGED_FALLBACK_STRUCTS: set[str] = {
    "MemberReference",
    "SimpleMemberReference",
    # Blueprint variable description struct (ArrayProperty inner, size=0 still needs tagged parsing)
    "FBPVariableDescription",
    "BPVariableDescription",
    "EdGraphPinType",
    "FEdGraphPinType",
    "BPVariableDescriptionHelper",
    # InheritableComponentHandler Records array (zero-size inner tagged structs)
    "ComponentOverrideRecord",
    # Blueprint related structs
    "ImplementedInterfaces",
    "LastEditedDocuments",
    "EditedDocumentInfo",
    "CategorySorting",
    # AnimSequence structs (some assets use tagged format)
    "FrameRate",  # some assets tag.size=37, uses tagged PropertyTag format
    "AnimNotifyTrack",  # some assets tag.size=0, uses tagged PropertyTag format
    # Editor structs
    "FEditorElement",  # Blueprint editor combo box options (DisplayName/Value/bIsDefault)
    "EditorElement",
    # Material parameter structs (material instance assets use tagged format)
    "ScalarParameterValue",
    "FScalarParameterValue",
    "FMaterialParameterInfo",
    # Animation blendspace structs (some assets use tagged format)
    "BlendSample",  # FBlendSample — BlendSpace sample point (SampleValue/Time/RateScale/bIsValid)
    "FBlendSample",
    # Material instance parameter structs (MaterialInstanceConstant assets, tag.size=0 tagged format)
    "VectorParameterValue",  # FVectorParameterValue — vector parameter (ParameterInfo/ParameterValue)
    "TextureParameterValue",  # FTextureParameterValue — texture parameter (ParameterInfo/ParameterValue)
    "MaterialTextureInfo",  # FMaterialTextureInfo — texture streaming info (UVChannelIndex etc.)
    # BoxSphereBounds (FBoxSphereBounds UPROPERTY structs always use tagged format,
    # because TBoxSphereBoundsStructOpsTypeTraits does not set WithSerialize)
    "BoxSphereBounds",
    "BoxSphereBounds3f",
    "BoxSphereBounds3d",
    # BPInterfaceDescription (ImplementedInterfaces array element)
    "BPInterfaceDescription",
    # Builder polygon struct (CubeBuilder/EditorBrushBuilder Polys array element)
    "BuilderPoly",
    "FBuilderPoly",
    # StaticMesh section info (LOD section description for StaticMesh assets)
    "FMeshSectionInfo",
    "MeshSectionInfo",
    # Animation curve metadata structs (tagged format, size=0)
    "FCurveMetaData",
    "CurveMetaData",
    # AnimBlueprintGeneratedClass::OrderedSavedPoseIndicesMap values
    # (FCachedPoseIndices is tagged FStructFallback: OrderedSavedPoseNodeIndices + None)
    "CachedPoseIndices",
}
"""Set of struct names requiring tagged fallback parsing.

When struct properties use tagged format (PropertyTag contains type information)
but cannot be parsed via standard StructProperty, members of this set are re-read
as inline tagged properties instead of opaque bytes.
"""

# ============================================================================
# ============================================================================
# Basic type parsers (lines 5289-5406 equivalent)
# ============================================================================


def parse_bool_property(tag: PropertyTag, archive: FArchive) -> bool:
    """Parse BoolProperty (PROP-04). Value stored in tag.bool_val, no extra read."""
    return bool(tag.bool_val)


def parse_int_property(tag: PropertyTag, archive: FArchive, name_map: list[str] | None = None) -> Any:
    """Parse IntProperty/Int64Property/Int16Property/Int8Property/ByteProperty (PROP-02).

    ByteProperty special handling:
    - No enum backing: read 1 byte
    - With enum backing (tag.enum_type): read FName (8 bytes), return EnumValue

    Reference: ByteProperty/EnumProperty handling logic:
    ByteProperty with enum_type -> EnumProperty -> ReadFName()
    """
    type_name = tag.type

    # ByteProperty with enum backing: read FName (8 bytes) per
    if type_name == "ByteProperty" and tag.enum_type is not None:
        if name_map is None:
            raise ParseError("ByteProperty with enum backing requires name_map")
        enum_value_name = archive.read_name(name_map)
        return make_enum_value(tag.enum_type, enum_value_name)

    if type_name == "Int64Property":
        return archive.read_i64()
    if type_name == "Int16Property":
        return archive.read_i16()
    if type_name == "Int8Property":
        return archive.read_i8()
    if type_name == "ByteProperty":
        return archive.read_u8()
    return archive.read_i32()  # IntProperty (default)


def parse_uint16_property(tag: PropertyTag, archive: FArchive) -> int:
    """Parse UInt16Property."""
    return archive.read_u16()


def parse_uint32_property(tag: PropertyTag, archive: FArchive) -> int:
    """Parse UInt32Property."""
    return archive.read_u32()


def parse_uint64_property(tag: PropertyTag, archive: FArchive) -> int:
    """Parse UInt64Property."""
    return archive.read_u64()


def parse_float_property(tag: PropertyTag, archive: FArchive) -> float:
    """Parse FloatProperty (PROP-03)."""
    return archive.read_f32()


def parse_str_property(tag: PropertyTag, archive: FArchive) -> str:
    """Parse StrProperty (PROP-05)."""
    return archive.read_fstring()


def parse_name_property(tag: PropertyTag, archive: FArchive, name_map: list[str]) -> str:
    """Parse NameProperty (PROP-06)."""
    return archive.read_name(name_map)


def parse_object_property(tag: PropertyTag, archive: FArchive) -> Any:
    """Parse ObjectProperty (PROP-07), resolving indices in bounded table rows."""
    offset = archive.tell()
    value = archive.read_i32()
    maps = getattr(archive, "_object_reference_maps", None)
    if tag.type != "ObjectProperty" or maps is None:
        return value

    from uasset_read.models.object_model import ObjectRef
    from uasset_read.serializers.object_resources import PackageIndex

    imports, exports = maps
    package_index = PackageIndex(value)
    if package_index.is_null:
        return None
    if package_index.is_import:
        index = package_index.to_import_index()
        if 0 <= index < len(imports):
            return ObjectRef(table="import", index=index)
        table = "import"
    else:
        index = package_index.to_export_index()
        if 0 <= index < len(exports):
            return ObjectRef(table="export", index=index)
        table = "export"

    archive._record_structured_diagnostic(
        code="OBJECT_PROPERTY_INDEX_INVALID",
        stage="parse_properties",
        offset=offset,
        raw_value=value,
        fallback="retained_as_opaque",
        reason="recovered_corruption",
        message=f"ObjectProperty PackageIndex {value} has no matching {table}",
    )
    raise ParseError(f"Invalid ObjectProperty PackageIndex {value}")


def parse_soft_object_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: list[str],
    file_version_ue5: int,
) -> SoftObjectPathValue:
    """Parse SoftObjectProperty (FSoftObjectPath).

    Inline FSoftObjectPath layout (FName-based).
    """
    ue5 = file_version_ue5
    paths = getattr(archive, "_soft_object_paths", None)
    if tag.type in ("SoftObjectProperty", "SoftClassProperty") and tag.size == 4 and ue5 >= UE5_ADD_SOFTOBJECTPATH_LIST:
        offset = archive.tell()
        index = archive.read_i32()
        if index == -1:
            return SoftObjectPathValue(raw_kind=tag.type, asset_path="", sub_path="")
        if paths is not None and 0 <= index < len(paths):
            return replace(paths[index], raw_kind=tag.type)
        archive._record_structured_diagnostic(
            code="SOFT_OBJECT_PATH_INDEX_INVALID",
            stage="parse_properties",
            offset=offset,
            raw_value=index,
            fallback="retained_as_opaque",
            reason="recovered_corruption",
            message=f"SoftObjectPath index {index} has no decoded package path",
        )
        raise ParseError(f"Invalid SoftObjectPath index {index}")

    # FSoftObjectPath inline. A two-FString layout never existed in UE
    # (SoftObjectPath.cpp SerializePathWithoutFixup). UE5 >= 1007:
    # FTopLevelAssetPath = PackageName FName + AssetName FName, then subpath FString.
    # Older: one FName + subpath FString. The pre-4.19 single-FString form is outside
    # this project's supported window; such a package hits the tolerant skip, not a
    # fabricated decode.
    package_name = ""
    if ue5 >= UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES:
        package_name = archive.read_name(name_map)
    asset_path = archive.read_name(name_map)
    sub_path = archive.read_fstring()
    if package_name:
        # FTopLevelAssetPath renders as "PackageName.AssetPath" in FSoftObjectPath
        asset_path = f"{package_name}.{asset_path}"
    return SoftObjectPathValue(raw_kind=tag.type, asset_path=asset_path, sub_path=sub_path)


def parse_lazy_object_property(tag: PropertyTag, archive: FArchive) -> SoftObjectPathValue:
    """Parse LazyObjectProperty."""
    read_size = tag.size if tag.size > 0 else 16
    raw = archive.read_bytes(read_size)
    return SoftObjectPathValue(raw_kind=tag.type, guid=raw.hex())


def parse_asset_object_property(tag: PropertyTag, archive: FArchive) -> SoftObjectPathValue:
    """Parse AssetObjectProperty."""
    return SoftObjectPathValue(raw_kind=tag.type, asset_path=archive.read_fstring())


# ============================================================================
# Complex type parsers (lines 5441-6004 equivalent)
# ============================================================================


def _native_struct_elem_size(struct_type: str | None, payload_size: int, count: int) -> int:
    """Per-element stride for native-serialized struct array elements, else 0.

    PropertyArray.cpp:768-777 writes ONE inner FPropertyTag for struct arrays whose
    Size spans the element payload; native structs (FVector/FGuid/FLinearColor/...)
    serialize each element via operator<<, so payload_size/count is the exact stride
    (384/16=24 for chair's VertexData, 64/4=16 for RawTeamColors). Tagged-serialized
    structs and _TAGGED_FALLBACK_STRUCTS have no fixed stride — those elements keep
    size=0 and the validated None-terminated tagged attempt below.
    """
    if not struct_type or count <= 0 or payload_size <= 0 or payload_size % count != 0:
        return 0
    if struct_type in _TAGGED_FALLBACK_STRUCTS:
        return 0
    stride = payload_size // count
    lwc = _LWC_TYPE_MAP.get(struct_type)
    if lwc is not None:
        return stride if stride in lwc else 0
    return stride if _EXPECTED_STRUCT_SIZES.get(struct_type) == stride else 0


def parse_array_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: list[str],
    export_map: list[Any],
    summary: Any | None = None,
    depth: int = 0,
    tolerant: bool = True,
) -> list[Any]:
    """Parse ArrayProperty (PROP-08, D-16).

    UE serialization format:
      - int32 ArrayCount
      - For each element, serialized natively by its type (not evenly dividing remaining_size)
      - For StructProperty, each element has a complete FPropertyTag
    """
    MAX_DEPTH = 10

    if depth > MAX_DEPTH:
        raise ParseError(f"ArrayProperty nesting depth {depth} exceeds maximum {MAX_DEPTH}")

    if tag.size < 4:
        # #345: tag.size < 4 is usually an empty array or RigVM DebugWatch property
        # Use debug level to avoid log noise
        # Return early to avoid reading count needlessly
        logger.debug(
            "ArrayProperty '%s': tag.size=%d < 4, returning empty array",
            tag.name,
            tag.size,
        )
        return []

    count = read_validated_count_tolerant(archive, MAX_ARRAY_COUNT, "array count")
    elements: list[Any] = []
    from uasset_read.serializers.property_tags import read_property_tag

    inner_type = getattr(tag, "inner_type", None) or _get_inner_type(tag.type)

    if inner_type == "BoolProperty":
        # PropertyBool.cpp SerializeItem: bool container elements serialize as inline
        # 1-byte values, NOT via the property-level tag BoolTrue bit.
        for _ in range(count):
            elements.append(archive.read_u8() != 0)
        return elements

    if inner_type == "FloatProperty" and count:
        byte_count = count * 4
        if (
            tag.size >= 4 + byte_count
            and archive.validate_size(
                byte_count,
                context=f"{tag.name} float array",
                tolerant=True,
                property_type="FloatProperty",
            )
        ):
            try:
                archive._check_read_range(archive.tell(), byte_count)
            except ExportBoundsExceeded:
                pass
            else:
                payload_start = archive.tell()
                try:
                    raw = archive.read(byte_count)
                except BINARY_READ_ERRORS + (ParseError,):
                    archive.seek(payload_start)
                else:
                    if len(raw) == byte_count:
                        return [value for (value,) in struct.iter_unpack("<f", raw)]
                    archive.seek(payload_start)

    # For StructProperty array elements, UE uses complete PropertyTag serialization
    # For other types, serialized natively by type (each element size determined by type)
    inner_type_struct = getattr(tag, "inner_type_struct", None) if inner_type == "StructProperty" else None
    legacy_inner_tag = None
    if inner_type == "StructProperty" and inner_type_struct is None:
        # PropertyArray.cpp: legacy struct arrays serialize ONE inner FPropertyTag
        # after the count; each element is then the struct's tagged-field stream
        # (None-terminated), NOT a per-element tag (the old per-element read
        # flattened multi-field elements).
        legacy_inner_tag = read_property_tag(archive, name_map)
    # Derive the native element stride from the payload size (#665): the inner tag's
    # Size covers the elements only; post-5.3 tags carry count(4) + elements inline.
    element_size = 0
    if inner_type == "StructProperty":
        if legacy_inner_tag is not None:
            element_size = _native_struct_elem_size(
                getattr(legacy_inner_tag, "struct_type", None), int(legacy_inner_tag.size or 0), count
            )
        else:
            element_size = _native_struct_elem_size(inner_type_struct, int(tag.size or 0) - 4, count)
    for i in range(count):
        if legacy_inner_tag is not None:
            inner_tag = PropertyTag(name=f"{tag.name}[{i}]", type=legacy_inner_tag.type, size=element_size)
            inner_tag.struct_type = getattr(legacy_inner_tag, "struct_type", None)
        else:
            # size=0 means the parse function serializes by type natively, or for
            # native struct elements the derived stride from the payload size.
            inner_tag = PropertyTag(
                name=f"{tag.name}[{i}]",
                type=inner_type,
                size=element_size,
            )
            # For StructProperty array elements, pass struct_type so parse_struct_property can hit fast-path
            if inner_type == "StructProperty":
                inner_tag.struct_type = inner_type_struct
        inner_value = parse_property_value(
            inner_tag, archive, name_map, export_map, summary, depth + 1, tolerant=tolerant
        )
        elements.append(inner_value)

    return elements


def _try_fast_path_struct(
    struct_type: str,
    tag,
    archive: FArchive,
    name_map: list[str],
) -> StructValue | None:
    """Try fast-path parsing for simple structs (no PropertyTag loop). Returns None if no match."""
    keys = _FLAT_FLOAT_STRUCTS.get(struct_type)
    if keys:
        reader = archive.read_f64 if tag.size == 8 * len(keys) else archive.read_f32
        return StructValue(struct_type=struct_type, fields={k: reader() for k in keys})

    if struct_type == "LinearColor":
        return StructValue(
            struct_type="LinearColor",
            fields={
                "R": archive.read_f32(),
                "G": archive.read_f32(),
                "B": archive.read_f32(),
                "A": archive.read_f32(),
            },
        )

    if struct_type == "Color":
        return StructValue(
            struct_type="Color",
            fields={
                "B": archive.read_u8(),
                "G": archive.read_u8(),
                "R": archive.read_u8(),
                "A": archive.read_u8(),
            },
        )

    if struct_type == "Guid":
        return StructValue(
            struct_type="Guid",
            fields={
                "A": archive.read_u32(),
                "B": archive.read_u32(),
                "C": archive.read_u32(),
                "D": archive.read_u32(),
            },
        )

    if struct_type == "IntPoint":
        return StructValue(struct_type="IntPoint", fields={"X": archive.read_i32(), "Y": archive.read_i32()})

    if struct_type == "IntVector":
        return StructValue(
            struct_type="IntVector",
            fields={
                "X": archive.read_i32(),
                "Y": archive.read_i32(),
                "Z": archive.read_i32(),
            },
        )

    if struct_type == "Box2D":
        min_x, min_y = archive.read_f32(), archive.read_f32()
        max_x, max_y = archive.read_f32(), archive.read_f32()
        b_valid = archive.read_i32() != 0
        return StructValue(
            struct_type="Box2D",
            fields={
                "Min": {"X": min_x, "Y": min_y},
                "Max": {"X": max_x, "Y": max_y},
                "bIsValid": b_valid,
            },
        )

    if struct_type == "Box":
        # Box.h operator<< (Box.h:666-668): Min + Max + IsValid as uint8 (Box.h:45).
        # float = 25 bytes, double = 49 bytes; the pre-check admits exactly those sizes.
        reader = archive.read_f64 if tag.size == 49 else archive.read_f32
        min_x, min_y, min_z = reader(), reader(), reader()
        max_x, max_y, max_z = reader(), reader(), reader()
        b_valid = archive.read_u8() != 0
        return StructValue(
            struct_type="Box",
            fields={
                "Min": {"X": min_x, "Y": min_y, "Z": min_z},
                "Max": {"X": max_x, "Y": max_y, "Z": max_z},
                "bIsValid": b_valid,
            },
        )

    if struct_type == "Sphere":
        reader = archive.read_f64 if tag.size == 32 else archive.read_f32
        cx, cy, cz, w = reader(), reader(), reader(), reader()
        return StructValue(struct_type="Sphere", fields={"Center": {"X": cx, "Y": cy, "Z": cz}, "W": w})

    if struct_type == "TopLevelAssetPath":
        return StructValue(
            struct_type="TopLevelAssetPath",
            fields={
                "PackageName": archive.read_name(name_map),
                "AssetName": archive.read_name(name_map),
            },
        )

    if struct_type == "PointerToUberGraphFrame":
        return StructValue(struct_type="PointerToUberGraphFrame", fields={"FrameIndex": archive.read_i64()})

    if struct_type == "Matrix":
        reader = archive.read_f64 if tag.size == 128 else archive.read_f32
        matrix = [[reader() for _ in range(4)] for _ in range(4)]
        return StructValue(struct_type="Matrix", fields={"M": matrix})

    if struct_type == "TwoVectors":
        reader = archive.read_f64 if tag.size == 48 else archive.read_f32
        e1 = {"X": reader(), "Y": reader(), "Z": reader()}
        e2 = {"X": reader(), "Y": reader(), "Z": reader()}
        return StructValue(struct_type="TwoVectors", fields={"E1": e1, "E2": e2})

    if struct_type == "OrientedBox":
        ax = {"X": archive.read_f32(), "Y": archive.read_f32(), "Z": archive.read_f32()}
        ay = {"X": archive.read_f32(), "Y": archive.read_f32(), "Z": archive.read_f32()}
        az = {"X": archive.read_f32(), "Y": archive.read_f32(), "Z": archive.read_f32()}
        ext = {"X": archive.read_f32(), "Y": archive.read_f32(), "Z": archive.read_f32()}
        ctr = {"X": archive.read_f32(), "Y": archive.read_f32(), "Z": archive.read_f32()}
        return StructValue(
            struct_type="OrientedBox",
            fields={
                "AxisX": ax,
                "AxisY": ay,
                "AxisZ": az,
                "Extent": ext,
                "Center": ctr,
            },
        )

    if struct_type == "Transform":
        # Serialization order: Rotation -> Translation -> Scale3D (UE source TransformNonVectorized.h:616-622)
        if tag.size == 40:  # FTransform3f (all float): 16 + 12 + 12
            rx, ry, rz, rw = archive.read_f32(), archive.read_f32(), archive.read_f32(), archive.read_f32()
            tx, ty, tz = archive.read_f32(), archive.read_f32(), archive.read_f32()
            sx, sy, sz = archive.read_f32(), archive.read_f32(), archive.read_f32()
        elif tag.size == 80:  # FTransform3d (all double): 32 + 24 + 24
            rx, ry, rz, rw = archive.read_f64(), archive.read_f64(), archive.read_f64(), archive.read_f64()
            tx, ty, tz = archive.read_f64(), archive.read_f64(), archive.read_f64()
            sx, sy, sz = archive.read_f64(), archive.read_f64(), archive.read_f64()
        else:
            # Unknown size: likely corrupted data, refuse to parse
            if not archive._tolerant:
                raise ParseError(f"Transform: unexpected size {tag.size} (expected 40 or 80)")
            archive._record_structured_diagnostic(
                code="TRANSFORM_SIZE_INVALID",
                stage="parse_properties",
                offset=archive.tell(),
                raw_value=tag.size,
                size=max(tag.size, 0),
                fallback="opaque_value",
                reason="recovered_corruption",
                message=f"Transform has unexpected size {tag.size}; value kept opaque",
            )
            return StructValue(
                struct_type="Transform",
                fields={"_warning": f"unexpected size {tag.size}"},
            )
        return StructValue(
            struct_type="Transform",
            fields={
                "Translation": {"X": tx, "Y": ty, "Z": tz},
                "Rotation": {"X": rx, "Y": ry, "Z": rz, "W": rw},
                "Scale3D": {"X": sx, "Y": sy, "Z": sz},
            },
        )

    if struct_type == "BoxSphereBounds":
        if tag.size == 28:
            ox, oy, oz = archive.read_f32(), archive.read_f32(), archive.read_f32()
            bx, by, bz = archive.read_f32(), archive.read_f32(), archive.read_f32()
            sr = archive.read_f32()
        elif tag.size == 56:
            ox, oy, oz = archive.read_f64(), archive.read_f64(), archive.read_f64()
            bx, by, bz = archive.read_f64(), archive.read_f64(), archive.read_f64()
            sr = archive.read_f64()
        elif tag.size == 52:
            ox, oy, oz = archive.read_f64(), archive.read_f64(), archive.read_f64()
            bx, by, bz = archive.read_f64(), archive.read_f64(), archive.read_f64()
            sr = archive.read_f32()
        elif tag.size == 40:
            ox, oy, oz = archive.read_f64(), archive.read_f64(), archive.read_f64()
            bx, by, bz = archive.read_f32(), archive.read_f32(), archive.read_f32()
            sr = archive.read_f32()
        else:
            ox, oy, oz = archive.read_f32(), archive.read_f32(), archive.read_f32()
            bx, by, bz = archive.read_f32(), archive.read_f32(), archive.read_f32()
            sr = archive.read_f32()
            remaining = tag.size - 28
            if remaining > 0:
                archive.read_bytes(remaining)
        return StructValue(
            struct_type="BoxSphereBounds",
            fields={
                "Origin": {"X": ox, "Y": oy, "Z": oz},
                "BoxExtent": {"X": bx, "Y": by, "Z": bz},
                "SphereRadius": sr,
            },
        )

    # MovieSceneFloat/DoubleChannel — animation keyframe channels (#515)
    # UE source: Engine/Source/Runtime/MovieScene/Public/MovieSceneChannel.h
    # Binary layout: [Traits_version:u8][Values_count:u8][Times_count:u8][bHasDefaults:u8]
    #                [Values:<T>[]][Times:i32[]][DefaultValue:<T> (if bHasDefaults)]
    # with T = f32 (Float) or f64 (Double)
    _channel_value_size = {"MovieSceneFloatChannel": 4, "MovieSceneDoubleChannel": 8}.get(struct_type)
    if _channel_value_size is not None and tag.size >= 4:
        read_value = archive.read_f32 if _channel_value_size == 4 else archive.read_f64
        start = archive.tell()
        header = archive.read(4)
        traits_ver = header[0]
        vc = header[1]
        tc = header[2]
        bhd = header[3]

        # Validate: reasonable counts, header version
        if (
            0 < vc < 50
            and 0 <= tc <= vc
            and traits_ver in (0, 1, 2, 3, 4, 5)
            and start + 4 + vc * _channel_value_size + tc * 4 + (_channel_value_size if bhd else 0)
            <= start + tag.size + 16
        ):
            try:
                values = [read_value() for _ in range(vc)]
                times = [archive.read_i32() for _ in range(tc)]
                default_val = read_value() if bhd else None
                # Seek to end of struct
                archive.seek(start + tag.size)
                fields: dict[str, Any] = {
                    "Values": values,
                    "Times": times,
                    "keyframe_count": vc,
                    "bHasDefaults": bool(bhd),
                }
                if default_val is not None:
                    fields["DefaultValue"] = default_val
                return StructValue(
                    struct_type=struct_type,
                    fields=fields,
                    raw_size=tag.size,
                    parse_status="success",
                )
            except Exception:
                archive.seek(start)

    # MovieSceneFrameRange — frame range with LowerBound/UpperBound (#515)
    # Binary layout: [header:2][LowerBound:i32][UpperBound:i32] (10 bytes total)
    if struct_type == "MovieSceneFrameRange" and tag.size == 10:
        start = archive.tell()
        try:
            header = archive.read(2)
            lb = archive.read_i32()
            ub = archive.read_i32()
            archive.seek(start + tag.size)
            return StructValue(
                struct_type="MovieSceneFrameRange",
                fields={
                    "LowerBound": lb,
                    "UpperBound": ub,
                },
                raw_size=tag.size,
                parse_status="success",
            )
        except Exception:
            archive.seek(start)

    return None


def _record_transform_size_invalid(archive: FArchive, tag, declared_struct_type: str | None, offset: int) -> None:
    """Emit TRANSFORM_SIZE_INVALID only when a Transform value stayed opaque.

    The size pre-check alone is not evidence of corruption (#665): tagged
    FTransform payloads legitimately carry sizes such as 162/235. The diagnostic
    fires here, after both the native fast path and the tagged attempt failed.
    """
    if declared_struct_type != "Transform":
        return
    archive._record_structured_diagnostic(
        code="TRANSFORM_SIZE_INVALID",
        stage="parse_properties",
        offset=offset,
        raw_value=tag.size,
        size=max(getattr(tag, "size", 0) or 0, 0),
        fallback="opaque_value",
        reason="unexpected",
        message=f"Transform has unexpected size {tag.size}; value kept opaque",
    )


def parse_struct_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: list[str],
    export_map: list[Any],
    file_version_ue5: int,
    summary: Any | None = None,
    depth: int = 0,
    tolerant: bool = True,
) -> StructValue:
    """Parse StructProperty (ADVP-01)."""
    MAX_DEPTH = 5

    if depth > MAX_DEPTH:
        raise ParseError(f"StructProperty nesting depth {depth} exceeds maximum {MAX_DEPTH}")

    struct_type = _extract_struct_type_from_tag(tag)
    declared_struct_type = struct_type

    # Fast-path pre-check: validate tag.size matches expected layout.
    # Use get_struct_size for version-aware size validation (supporting LWC double precision).
    # For LWC types, accept both float and double sizes (fast-path selects precision based on tag.size).
    expected_size = get_struct_size(struct_type, file_version_ue5=file_version_ue5)
    if expected_size is not None and tag.size != expected_size:
        # Tagged fallback structs: size mismatch is expected behavior (tagged format vs compact format),
        # Silently skip fast-path, go straight to tagged parsing, no warning generated.
        if declared_struct_type in _TAGGED_FALLBACK_STRUCTS:
            struct_type = None  # Skip all fast-path branches
        else:
            # A Transform payload that is neither 40 nor 80 bytes is not corrupt by
            # itself: UScriptStruct values of FTransform are legally written as a
            # SerializeTaggedProperties stream (Rotation/Translation/Scale3D tags,
            # None-terminated — byte-proven in #665 samples and read by the engine at
            # PropertyStruct.cpp:508-511). Skip the fast path silently, exactly like
            # _TAGGED_FALLBACK_STRUCTS; a diagnostic is recorded below only if the
            # tagged attempt then fails and the value stays opaque.
            # For LWC types, check whether tag.size matches the other precision
            lwc_entry = _LWC_TYPE_MAP.get(struct_type)
            if lwc_entry is not None:
                float_size, double_size = lwc_entry
                if tag.size not in (float_size, double_size):
                    logger.debug(
                        "StructProperty '%s': tag.size=%d does not match float(%d) or double(%d), using fallback",
                        struct_type,
                        tag.size,
                        float_size,
                        double_size,
                    )
                    struct_type = None  # Skip all fast-path branches
            else:
                logger.debug(
                    "StructProperty '%s': tag.size=%d != expected=%d, using fallback",
                    struct_type,
                    tag.size,
                    expected_size,
                )
                struct_type = None  # Skip all fast-path branches

    # Handle negative size values gracefully
    if tag.size is not None and tag.size < 0:
        total = archive.total_size()
        remaining = max(0, total - archive.tell())
        unsigned_size = tag.size & 0xFFFFFFFF
        skip_bytes = min(unsigned_size, remaining) if remaining > 0 else 0
        archive._record_structured_diagnostic(
            code="STRUCT_PROPERTY_NEGATIVE_SIZE",
            stage="parse_properties",
            offset=archive.tell(),
            raw_value=tag.size,
            size=skip_bytes,
            fallback="skipped_as_opaque",
            reason="recovered_corruption",
            message=f"StructProperty {declared_struct_type!r} has negative size; bounded bytes skipped",
        )
        if skip_bytes > 0:
            archive.seek(archive.tell() + skip_bytes)
        return StructValue(
            struct_type=declared_struct_type or "UnknownStruct",
            fields={},
            raw_size=tag.size,
            parse_status="opaque",
        )

    # Fast-path for simple structs (FScriptStruct.cs L174-178)
    # These structs have no PropertyTags loop — just raw float reads.
    fast_result = _try_fast_path_struct(struct_type or "", tag, archive, name_map)
    if fast_result is not None:
        return fast_result

    # Unknown struct with no size (Map/Set dummy tags carry no per-value size;
    # legacy tags do not serialize a map value struct name — PropertyTag.cpp
    # 357-371). Attempt the tagged FStructFallback loop below and validate the
    # result: a clean None stop with no new diagnostics is accepted, anything
    # else rewinds to the entry start and stays opaque so the caller's cursor
    # never spills into the next segment (Lyra MovieScene ExpansionStates;
    # export:7 BindingIdToReferences native values keep old behavior).
    validated_attempt = declared_struct_type not in _TAGGED_FALLBACK_STRUCTS and tag.size <= 0

    # Check BinaryOrNative handler registry for known struct types (e.g. NiagaraVariable).
    # These have custom hybrid layouts that the standard tagged loop cannot decode.
    # Try both with and without "F" prefix to handle UE naming inconsistencies.
    if declared_struct_type and not validated_attempt:
        from uasset_read.parsers.binary_or_native_handlers import BINARY_OR_NATIVE_HANDLERS

        bn_handler = BINARY_OR_NATIVE_HANDLERS.get(declared_struct_type) or BINARY_OR_NATIVE_HANDLERS.get(
            f"F{declared_struct_type}"
        )
        if bn_handler is not None:
            try:
                bn_result = bn_handler(tag, archive, name_map, export_map, summary)
                if bn_result is not None:
                    fields = bn_result.get("fields", {})
                    return StructValue(
                        struct_type=declared_struct_type,
                        fields=fields,
                        raw_size=tag.size,
                        parse_status="success",
                    )
                # UE writes USTRUCT names without the F prefix; the F form is a
                # defensive alias (see BINARY_OR_NATIVE_HANDLERS).
                if declared_struct_type in ("EdGraphPinType", "FEdGraphPinType"):
                    # Native-serialized only (WithSerializer = true, EdGraphPin.h):
                    # no tagged loop exists for it, so falling through would read
                    # payload bytes as field-name/type FNames and invent garbage.
                    # Constraints require an opaque region plus a diagnostic —
                    # never a silent empty struct that reads as a decoded value.
                    payload_offset = archive.tell()
                    payload = archive.read(tag.size) if tag.size and tag.size > 0 else b""
                    archive._record_structured_diagnostic(
                        code="edgraphpin_type_undecodable",
                        stage="parse_properties",
                        offset=payload_offset,
                        size=len(payload),
                        fallback="consumed_as_opaque",
                        reason="known_unimplemented",
                        message=(
                            f"StructProperty '{declared_struct_type}' payload of {len(payload)} "
                            "bytes is not a decodable native layout"
                        ),
                    )
                    return StructValue(
                        struct_type=declared_struct_type,
                        fields={},
                        raw_size=tag.size,
                        parse_status="opaque",
                    )
            except BINARY_READ_ERRORS:
                pass  # Fall through to tagged loop

    # Unknown structs may still be tagged FStructFallback payloads. Try the
    # standard inner PropertyTag loop first, then fall back to opaque bytes.
    fields: dict[str, Any] = {}
    property_count = 0

    from uasset_read.serializers.property_tags import read_property_tag
    from uasset_read.serializers.property_tags import read_tag_value_bounded

    # Track expected struct end position for recovery
    struct_start = archive.tell()
    struct_end = struct_start + tag.size if tag.size > 0 else None
    # tag.size=0 tagged format structs: no known boundary, use safe byte limit to prevent offset cascade
    # (corresponds to issue #134: one potential root cause of PackageIndex out of bounds)
    _MAX_TAGGED_FALLBACK_BYTES = 4096
    tagged_byte_limit = struct_start + _MAX_TAGGED_FALLBACK_BYTES if struct_end is None else None

    diag_mark = archive._diagnostic_mark()
    clean_none_stop = False
    # Hoisted out of the except body: `or` under an except_clause trips the
    # no-boolean-in-except rule (S5714 port); value semantics are identical.
    fallback_struct_type = declared_struct_type or "UnknownStruct"

    try:
        while property_count < MAX_PROPERTY_COUNT:
            property_count += 1

            # Byte safety limit: prevent unbounded loops from consuming subsequent properties when tag.size=0
            if tagged_byte_limit is not None and archive.tell() >= tagged_byte_limit:
                break

            inner_tag = read_property_tag(archive, name_map, struct_name=declared_struct_type)

            if inner_tag.name == UE_NONE_SENTINEL:
                clean_none_stop = True
                break

            if (
                struct_end is not None
                and inner_tag.value_end_offset is not None
                and inner_tag.value_end_offset > struct_end
            ):
                raise ParseError(
                    f"Tagged struct '{declared_struct_type}' field '{inner_tag.name}' "
                    f"size {inner_tag.size} exceeds struct boundary"
                )

            field_value = read_tag_value_bounded(
                archive,
                inner_tag,
                lambda inner_tag=inner_tag: parse_property_value(
                    inner_tag, archive, name_map, export_map, summary, depth + 1, tolerant=tolerant
                ),
            )
            fields[inner_tag.name] = field_value
    except StreamPoisonedError:
        # Control-flow signal: do not swallow into an opaque StructValue.
        raise
    except (struct.error, ParseError, OSError, ValueError):
        if not tolerant:
            raise
        if declared_struct_type in _TAGGED_FALLBACK_STRUCTS:
            raise
        if validated_attempt:
            archive.rollback_structured_diagnostics(diag_mark)
            archive.seek(struct_start)
        elif struct_end is not None:
            archive.seek(struct_end)
        elif tag.size > 0:
            archive.seek(struct_start + tag.size)
        _record_transform_size_invalid(archive, tag, declared_struct_type, struct_start)
        return StructValue(
            struct_type=fallback_struct_type,
            fields={},
            raw_size=tag.size,
            parse_status="opaque",
        )

    if validated_attempt and (not clean_none_stop or archive._diagnostic_mark() > diag_mark):
        # Not a clean None-terminated tagged stream (or the attempt recorded
        # recoveries): rewind exactly to the entry start — cursor and
        # diagnostics — and report opaque, byte-identical to pre-fallback.
        archive.rollback_structured_diagnostics(diag_mark)
        archive.seek(struct_start)
        _record_transform_size_invalid(archive, tag, declared_struct_type, struct_start)
        return StructValue(
            struct_type=declared_struct_type or "UnknownStruct",
            fields={},
            raw_size=tag.size,
            parse_status="opaque",
        )

    if struct_end is not None and archive.tell() != struct_end:
        archive.seek(struct_end)

    return StructValue(
        struct_type=declared_struct_type,
        fields=fields,
        raw_size=tag.size,
        parse_status="success",
    )


def parse_map_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: list[str],
    export_map: list[Any],
    summary: Any | None = None,
    depth: int = 0,
    tolerant: bool = True,
) -> MapValue:
    """Parse MapProperty (ADVP-02).

    UE serialization format:
      - int32 numKeysToRemove (number of keys to remove)
      - int32 numEntries (number of actual entries)
      - loop reading key-value pairs
    """
    key_type = getattr(tag, "key_type", None)
    value_type = getattr(tag, "value_type", None)
    # Legacy format stores key type in inner_type, not key_type
    if key_type is None:
        key_type = getattr(tag, "inner_type", None)
    if not key_type or not value_type:
        key_type, value_type = _extract_map_types_from_tag(tag)

    # Read number of keys to remove (used in UE source for incremental updates)
    num_keys_to_remove = read_validated_count_tolerant(archive, MAX_PROPERTY_COUNT, "MapProperty keys to remove count")
    # Skip keys to remove (serialized by key_type)
    for _ in range(num_keys_to_remove):
        _dispatch_key_parse(
            key_type, archive, name_map, export_map, summary, tag=tag, depth=depth, tolerant=tolerant
        )

    # Read number of actual entries
    num_entries = read_validated_count_tolerant(archive, MAX_PROPERTY_COUNT, "MapProperty entry count")
    entries: list[dict[str, Any]] = []

    for _ in range(num_entries):
        key = _dispatch_key_parse(
            key_type, archive, name_map, export_map, summary, tag=tag, depth=depth, tolerant=tolerant
        )
        value = _dispatch_value_parse(
            value_type, archive, name_map, export_map, summary, tag=tag, depth=depth, tolerant=tolerant
        )
        entries.append({"key": key, "value": value})

    return MapValue(key_type=key_type, value_type=value_type, entries=entries)


def parse_set_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: list[str],
    export_map: list[Any],
    summary: Any | None = None,
    depth: int = 0,
    tolerant: bool = True,
) -> SetValue:
    """Parse SetProperty (ADVP-03).

    UE serialization format:
      - int32 numElementsToRemove (number of elements to remove)
      - int32 numElements (number of actual elements)
      - loop reading elements
    """
    element_type = getattr(tag, "inner_type", None) or _extract_set_type_from_tag(tag)

    # Read number of elements to remove (used in UE source for incremental updates)
    num_elements_to_remove = read_validated_count_tolerant(
        archive, MAX_PROPERTY_COUNT, "SetProperty elements to remove count"
    )
    # Skip elements to remove (serialized by element_type)
    for _ in range(num_elements_to_remove):
        if element_type == "BoolProperty":
            archive.read_u8()  # inline 1-byte bool (PropertyBool.cpp)
            continue
        dummy_tag = PropertyTag(name="RemovedElement", type=element_type, size=0)
        parse_property_value(
            dummy_tag, archive, name_map, export_map, summary, depth=depth + 1, tolerant=tolerant
        )

    # Read number of actual elements
    num_elements = read_validated_count_tolerant(archive, MAX_PROPERTY_COUNT, "SetProperty element count")
    elements: list[Any] = []

    for _ in range(num_elements):
        if element_type == "BoolProperty":
            # PropertyBool.cpp: set elements are inline 1-byte values, not tag BoolTrue.
            elements.append(archive.read_u8() != 0)
            continue
        dummy_tag = PropertyTag(name="Element", type=element_type, size=0)
        element = parse_property_value(
            dummy_tag, archive, name_map, export_map, summary, depth=depth + 1, tolerant=tolerant
        )
        elements.append(element)

    return SetValue(element_type=element_type, elements=elements)


def parse_enum_property(
    tag: PropertyTag, archive: FArchive, name_map: list[str], summary: Any | None = None
) -> EnumValue:
    """Parse EnumProperty (ADVP-04)."""
    enum_type = tag.enum_type or _extract_enum_type_from_tag(tag)
    enum_value_name = archive.read_name(name_map)
    result = make_enum_value(enum_type, enum_value_name)
    return EnumValue(enum_type=result["enum_type"], value_name=result["value_name"])


def _read_ftext_base(archive: FArchive, dev_notes: bool = False) -> tuple[str, str, str]:
    """Read Base FText: namespace + key + source_string."""
    namespace = archive.read_fstring()
    key = archive.read_fstring()
    source_string = archive.read_fstring()
    if dev_notes:
        # TextHistory.cpp:915-937 — editor-saved UE5 assets append a fourth (often empty)
        # DevNotes FString after SourceString (FortniteMainBranch >= AddDevNotesToFText=260,
        # !FilterEditorOnly). Without consuming it the value stream is misaligned.
        archive.read_fstring()
    return namespace, key, source_string


def parse_text_property(tag: PropertyTag, archive: FArchive, dev_notes: bool = False) -> TextValue:
    """Parse TextProperty (ADVP-05).

    UE FText serialization format:
      - flags: i32 (4 bytes)
      - history_type: u8 (1 byte) -- ETextHistoryType identifier
      - body: varies based on history_type
        - history_type == 0 (Base): namespace + key + source_string
          (+ DevNotes FString when dev_notes is set, TextHistory.cpp:915-937)
        - history_type 1-10 are NOT decoded: their UE layouts (TextHistory.cpp)
          differ from the old flat 3-FString reads, and a wrong decode silently
          produced wrong values; consume nothing and report the type honestly.
    """
    _flags = archive.read_i32()  # FText flags (unused)
    history_type = archive.read_u8()  # FTextHistory type
    history_note = history_type

    if history_type == 0:  # Base
        namespace, key, source_string = _read_ftext_base(archive, dev_notes=dev_notes)
    elif 1 <= history_type <= 10:
        # UE layouts here differ from the old flat decode (TextHistory.cpp: nested FText +
        # typed FFormatArgumentData args / generated histories without the 3-string prefix).
        # Decoding them incorrectly silently produced wrong values; the value stream is
        # bounded by tag.size, so consume nothing and report the history type honestly.
        namespace = key = source_string = ""
    elif history_type == 255:
        has_culture = archive.read_bool()
        source_string = archive.read_fstring() if has_culture else ""
        namespace = key = ""
    else:
        # Unknown history type: skip remaining data
        remaining = tag.size - 5  # 5 = flags(4) + history_type(1)
        if remaining > 0:
            archive.read(remaining)
        namespace = ""
        key = ""
        source_string = ""

    return TextValue(
        namespace=namespace or "",
        key=key or "",
        source_string=source_string or "",
        history_type=history_note,
    )


def parse_delegate_property(tag: PropertyTag, archive: FArchive, name_map: list[str]) -> DelegateValue:
    """Parse DelegateProperty (ADVP-06)."""
    object_ref = archive.read_i32()
    function_name = archive.read_name(name_map)

    return DelegateValue(object_ref=object_ref, function_name=function_name)


# ============================================================================
# Multicast delegate type parsers
# ============================================================================


def parse_multicast_delegate_property(tag: PropertyTag, archive: FArchive, name_map: list[str] | None = None) -> list:
    """Parse MulticastDelegateProperty.

    UE FMulticastScriptDelegate::SerializeItem serializes function name with FName
    (4-byte index + 4-byte instance number), consistent with parse_delegate_property.
    """
    count = read_validated_count_tolerant(archive, MAX_SAFE_COUNT, "MulticastDelegate")
    delegates = []
    for _ in range(count):
        obj_index = archive.read_i32()
        func_name = archive.read_name(name_map)
        delegates.append({"object": obj_index, "function": func_name})
    return delegates


# ============================================================================
# Special type parsers
# ============================================================================


def parse_field_path_property(tag: PropertyTag, archive: FArchive, name_map: list[str] | None = None) -> dict:
    """Parse FieldPathProperty.

    UE FFieldPath::Serialize serializes the path as TArray<FName>
    (int32 count + N * FName), not FString array.
    """
    count = read_validated_count_tolerant(archive, MAX_SAFE_COUNT, "FieldPath")
    path = []
    for _ in range(count):
        path.append(archive.read_name(name_map))
    return {"path": path}


def parse_optional_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: list[str] | None = None,
    export_map: list[Any] | None = None,
    summary: Any | None = None,
    depth: int = 0,
    tolerant: bool = True,
) -> dict:
    """Parse OptionalProperty."""
    has_value = archive.read_bool()
    if has_value:
        inner_type = getattr(tag, "inner_type", None) or "Unknown"
        inner_tag = PropertyTag(
            name=f"{tag.name}.Value",
            type=inner_type,
            size=max(0, (tag.size or 0) - 4),
        )
        inner_value = parse_property_value(
            inner_tag, archive, name_map or [], export_map or [], summary, depth=depth + 1, tolerant=tolerant
        )
        return {"has_value": True, "value": inner_value}
    return {"has_value": False, "value": None}


# ============================================================================
# Verse language type parsers
# ============================================================================


def parse_verse_cell_property(tag: PropertyTag, archive: FArchive) -> dict:
    """Parse VerseCellProperty (UE5.6+ Verse scripting system).

    VerseCell reference points to a cell in a Verse file, serialized as PackageIndex + name index.
    Currently returns raw reference value; full parsing requires Verse file system.
    """
    start = archive.tell()
    package_index = archive.read_i32() if tag.size >= 4 else 0
    name_index = archive.read_i32() if tag.size >= 8 else -1
    consumed = archive.tell() - start
    raw = archive.read_bytes(tag.size - consumed) if tag.size > consumed else b""
    return {
        "kind": "VerseCellProperty",
        "ref": {"package_index": package_index, "name_index": name_index},
        "raw": raw,
    }


def parse_verse_value_property(tag: PropertyTag, archive: FArchive) -> dict:
    """Parse VerseValueProperty (UE5.6+ Verse scripting system).

    VerseValue is a runtime value container of the Verse type system, serialization includes type tag + value.
    Currently reads type tag and raw data; full parsing requires Verse type system knowledge.
    """
    start = archive.tell()
    type_tag = archive.read_u8() if tag.size >= 1 else 0
    value_data = None
    try:
        if tag.size > 1:
            value_data = archive.read_fstring()
    except BINARY_READ_ERRORS:
        archive.seek(start + 1)
    consumed = archive.tell() - start
    raw = archive.read_bytes(tag.size - consumed) if tag.size > consumed else b""
    return {
        "kind": "VerseValueProperty",
        "type_tag": type_tag,
        "value": value_data,
        "raw": raw,
    }


def parse_double_property(tag: PropertyTag, archive: FArchive) -> float:
    """Parse DoubleProperty (standalone parser)."""
    return archive.read_f64()


def parse_guid_property(tag: PropertyTag, archive: FArchive) -> str:
    """Parse GuidProperty -- FGuid struct (16 bytes).

    Returns GUID in standard hex string format, e.g. "A1B2C3D4-E5F6-..."
    """
    data = archive.read_bytes(16)
    return format_guid_bytes(data, uppercase=False)


# ============================================================================
# TypeName extraction helpers (lines 5517-5641 equivalent)
# ============================================================================


def _get_inner_type(array_type: str) -> str:
    """Infer inner element type from ArrayProperty type name.

    Supports the UE5 full type name format, e.g. ArrayProperty(IntProperty)
    -> IntProperty.  Unknown formats return "Unknown".
    """
    inner = extract_inner_from_tag(array_type)
    return inner.rsplit(".", 1)[-1] if inner else "Unknown"


def _split_inner(inner: str | None, default: str) -> str:
    """Return the last dotted segment of *inner*, or *default* when absent."""
    return default if inner is None else inner.rsplit(".", 1)[-1]


def _extract_struct_type_from_tag(tag: PropertyTag) -> str:
    """Extract struct type name from PropertyTag (D-08)."""
    if getattr(tag, "struct_type", None):
        return str(tag.struct_type).split(".")[-1]

    return _split_inner(extract_inner_from_tag(tag.type), "UnknownStruct")


def _extract_map_types_from_tag(tag: PropertyTag) -> tuple[str, str]:
    """Extract Map Key/Value types from PropertyTag (D-08)."""
    inner = extract_inner_from_tag(tag.type)
    if inner is not None:
        parts = inner.split(",", 1)  # split on first comma only (type names may contain commas)
        if len(parts) >= 2:
            return parts[0].strip(), parts[1].strip()

    return "IntProperty", "IntProperty"


def _extract_set_type_from_tag(tag: PropertyTag) -> str:
    """Extract Set element type from PropertyTag (D-08)."""
    inner = extract_inner_from_tag(tag.type)
    if inner is not None:
        return inner.strip()

    return "IntProperty"


def _extract_enum_type_from_tag(tag: PropertyTag) -> str:
    """Extract enum type name from PropertyTag (D-08)."""
    return _split_inner(extract_inner_from_tag(tag.type), "UnknownEnum")


# ============================================================================
# Internal dispatch helpers for MapProperty (lines 5773-5841 equivalent)
# ============================================================================


def _dispatch_key_parse(
    key_type: str,
    archive: FArchive,
    name_map: list[str],
    export_map: list[Any],
    summary: Any | None = None,
    tag: PropertyTag | None = None,
    depth: int = 0,
    tolerant: bool = True,
) -> Any:
    """Key type dispatch parsing (D-02b)."""
    if key_type == "BoolProperty":
        # PropertyBool.cpp: bool map keys are inline 1-byte values, not tag BoolTrue.
        return archive.read_u8() != 0
    basic_types = [
        "IntProperty",
        "Int64Property",
        "FloatProperty",
        "DoubleProperty",
        "StrProperty",
        "NameProperty",
        "ByteProperty",
        "UInt16Property",
        "UInt32Property",
        "UInt64Property",
    ]
    if key_type in basic_types:
        dummy_tag = PropertyTag(name="Key", type=key_type, size=0)
        return parse_property_value(
            dummy_tag, archive, name_map, export_map, summary, depth=depth + 1, tolerant=tolerant
        )

    if key_type == "ObjectProperty":
        return parse_object_property(PropertyTag(name="Key", type=key_type, size=4), archive)

    if key_type == "EnumProperty":
        return archive.read_name(name_map)

    if key_type == "StructProperty":
        # StructProperty key needs to know the concrete struct type for correct parsing
        # Get key_type_struct from tag; if tag is None, try to get from archive
        struct_type = None
        if tag is not None:
            struct_type = getattr(tag, "key_type_struct", None)
        dummy_tag = PropertyTag(name="Key", type="StructProperty", size=0, struct_type=struct_type or "Unknown")
        # Route through parse_property_value so poison diagnostics abort the
        # multi-entry map loop instead of opaque-swallowing inside the struct.
        return parse_property_value(
            dummy_tag, archive, name_map, export_map, summary, depth=depth + 1, tolerant=tolerant
        )

    return None


def _dispatch_value_parse(
    value_type: str,
    archive: FArchive,
    name_map: list[str],
    export_map: list[Any],
    summary: Any | None = None,
    tag: PropertyTag | None = None,
    depth: int = 0,
    tolerant: bool = True,
) -> Any:
    """Value type dispatch parsing."""
    if value_type == "BoolProperty":
        # PropertyBool.cpp: bool map values are inline 1-byte values, not tag BoolTrue.
        return archive.read_u8() != 0
    if value_type == "StructProperty":
        # Propagate struct type from tag so parse_struct_property can identify
        # the concrete struct rather than falling back to UnknownStruct.
        struct_type = None
        if tag is not None:
            struct_type = getattr(tag, "value_type_struct", None)
        dummy_tag = PropertyTag(name="Value", type="StructProperty", size=0, struct_type=struct_type or "Unknown")
        # Same as keys: poison must abort the map entry loop, not become opaque.
        return parse_property_value(
            dummy_tag, archive, name_map, export_map, summary, depth=depth + 1, tolerant=tolerant
        )

    dummy_tag = PropertyTag(name="Value", type=value_type, size=0)
    return parse_property_value(
        dummy_tag, archive, name_map, export_map, summary, depth=depth + 1, tolerant=tolerant
    )
