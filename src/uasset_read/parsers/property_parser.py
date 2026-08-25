from __future__ import annotations

"""Property parsing dispatcher and export entry property loop.

Equivalent migration of uasset_read.py lines 6007-6220.
"""

import logging
import struct as _struct
from typing import TYPE_CHECKING, List, Optional, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.link.linker import PackageLinker
    from uasset_read.serializers.object_resources import ObjectImport
    from uasset_read.serializers.package_summary import PackageFileSummary

from uasset_read.models.properties import PropertyTag, PropertyValue
from uasset_read.models.fallback import PropertyFallback, FallbackReason
from uasset_read.exceptions import ParseError, ErrorContext
from uasset_read.constants import (
    MAX_PROPERTY_COUNT,
    PKG_UnversionedProperties,
    UE5_PROPERTY_TAG_EXTENSION,
    FIXED_UNVERSIONED_SIZES,
    UE_NONE_SENTINEL,
)
from uasset_read.serializers.property_tags import read_property_tag, read_tag_value_bounded
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex
from uasset_read.models.validators import validate_parse_status

logger = logging.getLogger(__name__)

# D-02: SerializationControlExtensions bit name constants (module-level to avoid rebuild per call)
_KNOWN_SERIALIZATION_CONTROL_BITS = 0x03  # 0x01 | 0x02
_SERIALIZATION_CONTROL_BIT_NAMES = {
    0x01: "ReserveForFutureUse",
    0x02: "OverridableSerializationInformation",
    0x04: "Unknown_Bit2",
    0x08: "Unknown_Bit3",
    0x10: "Unknown_Bit4",
    0x20: "Unknown_Bit5",
    0x40: "Unknown_Bit6",
    0x80: "Unknown_Bit7",
}

# #341/#428: PropertyTag corruption recovery max scan bytes
_MAX_RECOVERY_SCAN = 2048

# #428: Known property type name set (used to filter candidates during recovery scan)
_KNOWN_PROPERTY_TYPES = {
    "BoolProperty",
    "IntProperty",
    "Int64Property",
    "Int16Property",
    "Int8Property",
    "ByteProperty",
    "UInt16Property",
    "UInt32Property",
    "UInt64Property",
    "FloatProperty",
    "DoubleProperty",
    "StrProperty",
    "NameProperty",
    "ObjectProperty",
    "SoftObjectProperty",
    "ArrayProperty",
    "StructProperty",
    "MapProperty",
    "SetProperty",
    "EnumProperty",
    "TextProperty",
    "DelegateProperty",
    "Utf8StrProperty",
    "WeakObjectProperty",
    "LazyObjectProperty",
    "ClassProperty",
    "SoftClassProperty",
    "AssetObjectProperty",
    "AssetClassProperty",
    "MulticastDelegateProperty",
    "MulticastInlineDelegateProperty",
    "MulticastSparseDelegateProperty",
    "InterfaceProperty",
    "FieldPathProperty",
    "OptionalProperty",
    "VerseStringProperty",
    "VerseClassProperty",
    "VerseFunctionProperty",
    "VerseDynamicProperty",
    "VerseCellProperty",
    "VerseValueProperty",
    "AnsiStrProperty",
    "GuidProperty",
}

# Lazy import + cache: avoid circular dependency + avoid rebuilding dict per property parse
_TYPE_HANDLER_MAP: dict | None = None


def _get_parse_functions():
    """Get property type -> parse function mapping（module-level cache, not rebuilt after first call）。"""
    global _TYPE_HANDLER_MAP
    if _TYPE_HANDLER_MAP is not None:
        return _TYPE_HANDLER_MAP
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
        parse_utf8_str_property,
        parse_weak_object_property,
        parse_lazy_object_property,
        parse_class_property,
        parse_soft_class_property,
        parse_asset_object_property,
        parse_multicast_delegate_property,
        parse_multicast_inline_delegate_property,
        parse_multicast_sparse_delegate_property,
        parse_interface_property,
        parse_field_path_property,
        parse_optional_property,
        parse_verse_string_property,
        parse_verse_class_property,
        parse_verse_function_property,
        parse_verse_dynamic_property,
        parse_ansi_str_property,
        parse_verse_cell_property,
        parse_verse_value_property,
        parse_double_property,
        parse_guid_property,
    )

    _TYPE_HANDLER_MAP = {
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
        "Utf8StrProperty": parse_utf8_str_property,
        "WeakObjectProperty": parse_weak_object_property,
        "LazyObjectProperty": parse_lazy_object_property,
        "ClassProperty": parse_class_property,
        "SoftClassProperty": parse_soft_class_property,
        "AssetObjectProperty": parse_asset_object_property,
        "AssetClassProperty": parse_asset_object_property,
        "MulticastDelegateProperty": parse_multicast_delegate_property,
        "MulticastInlineDelegateProperty": parse_multicast_inline_delegate_property,
        "MulticastSparseDelegateProperty": parse_multicast_sparse_delegate_property,
        "InterfaceProperty": parse_interface_property,
        "FieldPathProperty": parse_field_path_property,
        "OptionalProperty": parse_optional_property,
        "VerseStringProperty": parse_verse_string_property,
        "VerseClassProperty": parse_verse_class_property,
        "VerseFunctionProperty": parse_verse_function_property,
        "VerseDynamicProperty": parse_verse_dynamic_property,
        "VerseCellProperty": parse_verse_cell_property,
        "VerseValueProperty": parse_verse_value_property,
        "AnsiStrProperty": parse_ansi_str_property,
        "GuidProperty": parse_guid_property,
    }
    return _TYPE_HANDLER_MAP


def _skip_type_tree_nodes(
    archive,
    limit: int,
    name_map: List[str],
    map_len: int,
) -> bool:
    """Try to skip UE5.3+ FPropertyTypeName type tree, locating to the size field start position.

    FPropertyTypeName uses preorder traversal: each node is FName(8) + inner_count(4),
    inner_count indicates child node count. Skip the tree node by node using inner_count.

    Args:
        archive: FArchive positioned at the type tree start
        limit: readable upper bound (scan window or data boundary)
        name_map: name table
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


def _try_recover_property_tag(
    archive,
    name_map: List[str],
    *,
    max_scan: int = 64,
    property_end: int | None = None,
) -> bool:
    """#341: Try to locate the next valid PropertyTag start position.

    Scan strategy: search forward for valid FName signatures from current position, then verify subsequent
    PropertyTag structure (type + size) by version.

    - legacy (ue5 < 1012): name(8) + type_fname(8) -> size at +16
    - UE5.3+ (ue5 >= 1012): name(8) + FPropertyTypeName tree -> size after tree

    Args:
        archive: FArchive instance
        name_map: name table, used to validate candidate index validity
        max_scan: maximum scan byte count
        property_end: property data boundary (optional)

    Returns:
        True if a potentially valid position is found (seeked), False otherwise.
    """
    current = archive.tell()
    limit = current + max_scan
    # #341: Do NOT limit scan by property_end — when the preceding property's size
    # was miscalculated, property_end itself may be wrong.  Limit only by the
    # scan budget and actual file size to maximise recovery chance.
    file_size = getattr(archive, "_file_size", None)
    if isinstance(file_size, int):
        limit = min(limit, file_size)

    # Size validation uses actual data boundary (excluding max_scan) to avoid false positives from scan window truncation
    if property_end is not None and isinstance(file_size, int):
        data_boundary = min(property_end, file_size)
    elif property_end is not None:
        data_boundary = property_end
    elif isinstance(file_size, int):
        data_boundary = file_size
    else:
        data_boundary = limit

    map_len = len(name_map)
    # Get UE5 version number to determine PropertyTag type field format
    from uasset_read.constants import PROPERTY_TAG_COMPLETE_TYPE_NAME

    file_version_ue5 = getattr(archive, "_file_version_ue5", PROPERTY_TAG_COMPLETE_TYPE_NAME)

    # #341: Use file_size for size validation (not property_end) to avoid rejecting
    # valid candidates whose size spans beyond property_end but within file.
    size_boundary = file_size if isinstance(file_size, int) else data_boundary

    for candidate in range(current + 1, limit):
        remaining = limit - candidate
        if remaining < 8:  # Minimum FName: 4(index) + 4(number) = 8 bytes
            break
        archive.seek(candidate)
        try:
            raw = archive.read(8)
            if len(raw) < 8:
                continue
            index, number = _struct.unpack("<II", raw)
            # Verify index is within name_map range
            if not (0 <= index < map_len):
                continue
            # Verify number is a reasonable small non-negative integer (in UE, number is typically 0-100)
            if number > 10000:
                continue
            # Extra validation: name should not be a pure number, empty, or "None" (exclude false hits)
            name = name_map[index]
            if not name or name.isdigit() or name == "None":
                continue

            # #341 enhancement: validate subsequent PropertyTag structure by version
            size_valid = False

            if file_version_ue5 < PROPERTY_TAG_COMPLETE_TYPE_NAME:
                # legacy format: type is simple FName(8), size at candidate+16
                size_pos = candidate + 16
                if size_pos + 4 > limit:
                    continue
                # Validate type FNAME index
                type_raw = archive.read(8)  # already seeked to candidate+8 (after name)
                if len(type_raw) < 8:
                    continue
                type_idx, _ = _struct.unpack("<II", type_raw)
                if not (0 <= type_idx < map_len):
                    continue
                type_name = name_map[type_idx]
                if not type_name or type_name.isdigit() or type_name == "None":
                    continue
                # #428: validate type_name is a known property type
                if type_name not in _KNOWN_PROPERTY_TYPES:
                    continue
                # Validate size
                archive.seek(size_pos)
                size_raw = archive.read(4)
                if len(size_raw) < 4:
                    continue
                tag_size = _struct.unpack("<i", size_raw)[0]
                size_remaining = size_boundary - (size_pos + 4)
                if 0 <= tag_size <= size_remaining:
                    size_valid = True
            else:
                # UE5.3+ format: type is FPropertyTypeName preorder traversal tree
                # Read first node name (property type) and validate
                archive.seek(candidate + 8)
                first_node_raw = archive.read(8)
                if len(first_node_raw) < 8:
                    continue
                first_idx, first_ic = _struct.unpack("<II", first_node_raw)
                if not (0 <= first_idx < map_len):
                    continue
                first_type_name = name_map[first_idx]
                # #428: validate type tree root node is a known property type
                if first_type_name not in _KNOWN_PROPERTY_TYPES:
                    continue
                # Skip remaining type tree (first node already read, inner_count=first_ic)
                # Re-seek and use _skip_type_tree_nodes to fully skip
                archive.seek(candidate + 8)
                if not _skip_type_tree_nodes(archive, limit, name_map, map_len):
                    continue
                size_pos = archive.tell()
                if size_pos + 4 > limit:
                    continue
                size_raw = archive.read(4)
                if len(size_raw) < 4:
                    continue
                tag_size = _struct.unpack("<i", size_raw)[0]
                size_remaining = size_boundary - (size_pos + 4)
                if 0 <= tag_size <= size_remaining:
                    size_valid = True

            if not size_valid:
                continue
            archive.seek(candidate)
            return True
        except (_struct.error, OSError):
            continue

    archive.seek(current)  # restore original position
    return False


def _try_asset_type_handler(
    export: ObjectExport,
    archive: FArchive,
    name_map: List[str],
    class_name: str,
    parsed_properties: Optional[List["PropertyValue"]] = None,
    property_end: int = 0,
    export_map: Optional[List[Any]] = None,
    import_map: Optional[List[Any]] = None,
    summary: Optional["PackageFileSummary"] = None,
    linker: Optional["PackageLinker"] = None,
) -> None:
    """Try to extract raw binary data using a registered ClassHandler.

    For asset types like StaticMesh, SkeletalMesh, Material, Texture2D,
    handler reads custom payload from property_end (Super::Serialize completion position),
    attaching results to the export objects _asset_type_data attribute.

    For animation types（AnimBlueprint/AnimSequence/AnimMontage），
    Set parsed properties list to export.properties,
    so the handler can extract structured metadata.
    """
    from uasset_read.parsers.class_registry import get_class_registry

    registry = get_class_registry()
    handler = registry.find_handler(class_name)
    if handler is None:
        return

    # Set parsed properties to the export object
    # For animation handlers (AnimBlueprint/AnimSequence/AnimMontage) to extract metadata
    if parsed_properties is not None:
        export.properties = parsed_properties

    # Store resolved class name on export for handler use
    setattr(export, "resolved_class_name", class_name)

    # Store package tables for handlers that resolve object references (#521)
    if export_map is not None:
        setattr(export, "package_export_map", export_map)
        setattr(export, "package_import_map", import_map or [])

    # Store summary and linker for handlers that need version info or full resolution
    if summary is not None:
        setattr(export, "package_summary", summary)
    if linker is not None:
        setattr(export, "package_linker", linker)

    saved_pos = archive.tell()
    try:
        # Do not seek to property_end -- After property parsing the current position is already past Super::Serialize.
        # Custom payloads for assets like DataTable follow immediately after properties, rather than at the export data end.
        result = handler.parse(export, archive, context=name_map)
        if result.success and result.data:
            # Attach to export object for downstream use
            setattr(export, "_asset_type_data", result.data)
            # Sync animation data to custom_data (for ir_builder use)
            custom_data = getattr(export, "custom_data", {})
            if not custom_data:
                custom_data = {}
            for key in ["anim_blueprint", "anim_sequence", "anim_montage"]:
                if key in result.data and key not in custom_data:
                    custom_data[key] = result.data[key]
            if custom_data:
                setattr(export, "custom_data", custom_data)
            # Propagate handler parse_status to export level
            handler_status = result.data.get("parse_status")
            if handler_status:
                setattr(export, "parse_status", validate_parse_status(handler_status))
            else:
                setattr(export, "parse_status", validate_parse_status("success"))
            logger.debug(
                "AssetTypeHandler '%s' extracted data for '%s' (status=%s)",
                handler.handler_name,
                export.object_name,
                handler_status,
            )
        elif not result.success:
            # Handler reported a recoverable failure via HandlerResult.
            # Record the error on the export so callers see it in parse_status.
            setattr(export, "parse_status", validate_parse_status("partial"))
            if result.error_message:
                setattr(export, "handler_error", result.error_message)
            logger.warning(
                "AssetTypeHandler '%s' failed for '%s' (%s): %s",
                handler.handler_name,
                export.object_name,
                class_name,
                result.error_message,
            )
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(
            "AssetTypeHandler failed for '%s' (%s): %s",
            export.object_name,
            class_name,
            e,
        )
    finally:
        archive.seek(saved_pos)


def parse_property_value(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    export_map: List[Any],
    summary: Optional[Any] = None,
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
    mappings = getattr(summary, "_mappings", None)
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
        # Try to use a known type parser
        from uasset_read.parsers.binary_or_native_handlers import BINARY_OR_NATIVE_HANDLERS

        handler = BINARY_OR_NATIVE_HANDLERS.get(tag.type)
        if handler is not None:
            try:
                result = handler(tag, archive, name_map, export_map, summary)
                if result is not None:
                    return result
                # Handler returned None (unknown type/parse failed), continue falling back to raw_data
            except (_struct.error, OSError, ValueError) as e:
                logger.debug("BinaryOrNative handler failed for %s: %s", tag.type, e)
        # Also try by struct_type (with F-prefix fallback) for struct-specific handlers
        struct_type = getattr(tag, "struct_type", None)
        if struct_type:
            handler = BINARY_OR_NATIVE_HANDLERS.get(struct_type)
            if handler is None and not struct_type.startswith("F"):
                handler = BINARY_OR_NATIVE_HANDLERS.get(f"F{struct_type}")
            if handler is not None:
                try:
                    result = handler(tag, archive, name_map, export_map, summary)
                    if result is not None:
                        return result
                except (_struct.error, OSError, ValueError) as e:
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
        from uasset_read.parsers.custom_properties import CUSTOM_PROPERTY_HANDLERS, handle_custom_property

        type_parts = getattr(tag, "type_parts", None)
        if type_parts:
            first_node_name = type_parts[0][0] if type_parts else ""
            custom_id_map = {"CustomProperty_FD": 0xFD, "CustomProperty_FE": 0xFE}
            custom_id = custom_id_map.get(first_node_name)
            if custom_id is not None:
                try:
                    return handle_custom_property(
                        custom_id, tag, archive, name_map, mappings=mappings, game=game, summary=summary
                    )
                except (_struct.error, OSError, ValueError) as e:
                    logger.debug("Custom property handler (0x%02X) failed for %s: %s", custom_id, tag.type, e)
        game_key = game.lower() if game else None
        if (game_key, tag.type) in CUSTOM_PROPERTY_HANDLERS or (None, tag.type) in CUSTOM_PROPERTY_HANDLERS:
            try:
                return handle_custom_property(
                    0xFF, tag, archive, name_map, mappings=mappings, game=game, summary=summary
                )
            except (_struct.error, OSError, ValueError) as e:
                logger.debug("Game-specific custom property handler failed for %s (game=%s): %s", tag.type, game, e)

        # All handlers do not match -- read raw bytes and return PropertyFallback
        raw_data = archive.read(tag.size) if tag.size > 0 else b""
        return PropertyFallback(
            name=tag.name,
            type=tag.type,
            size=tag.size,
            raw_bytes=raw_data,
            reason=FallbackReason.UNSUPPORTED_TYPE,
            array_index=getattr(tag, "array_index", 0),
            tag_data=getattr(tag, "tag_data", None),
        )

    try:
        # Dispatch based on handler signature
        # Special case: ByteProperty with enum backing needs name_map (reads FName)
        if tag.type == "ByteProperty" and tag.enum_type is not None:
            return handler(tag, archive, name_map)
        elif tag.type in (
            "BoolProperty",
            "IntProperty",
            "Int64Property",
            "Int16Property",
            "Int8Property",
            "ByteProperty",
            "UInt16Property",
            "UInt32Property",
            "UInt64Property",
            "FloatProperty",
            "DoubleProperty",
            "StrProperty",
            "ObjectProperty",
            "TextProperty",
            "Utf8StrProperty",
            "WeakObjectProperty",
            "LazyObjectProperty",
            "ClassProperty",
            "AssetObjectProperty",
            "AssetClassProperty",
            "InterfaceProperty",
            "VerseStringProperty",
            "VerseClassProperty",
            "VerseFunctionProperty",
            "VerseDynamicProperty",
            "AnsiStrProperty",
            "GuidProperty",
        ):
            return handler(tag, archive)
        elif tag.type in (
            "NameProperty",
            "DelegateProperty",
            "MulticastDelegateProperty",
            "MulticastInlineDelegateProperty",
            "MulticastSparseDelegateProperty",
            "FieldPathProperty",
        ):
            return handler(tag, archive, name_map)
        elif tag.type in ("SoftObjectProperty", "SoftClassProperty"):
            # These need soft_object_path_list for UE5.7+ index-based resolution
            soft_path_list = getattr(summary, "_soft_object_path_list", None) if summary is not None else None
            return handler(tag, archive, name_map, soft_path_list)
        elif tag.type in ("ArrayProperty",):
            return handler(tag, archive, name_map, export_map, summary, depth)
        elif tag.type in ("StructProperty",):
            return handler(tag, archive, name_map, export_map, summary, depth)
        elif tag.type in ("MapProperty", "SetProperty", "OptionalProperty"):
            return handler(tag, archive, name_map, export_map, summary)
        elif tag.type in ("EnumProperty",):
            return handler(tag, archive, name_map, summary)
        elif tag.type in ("VerseCellProperty", "VerseValueProperty"):
            return handler(tag, archive)
    except (_struct.error, OSError, ValueError, AttributeError, KeyError, ParseError) as e:
        if not tolerant:
            raise
        logger.debug("Property handler failed for %s.%s: %s", tag.name, tag.type, e)
        return PropertyFallback(
            name=tag.name,
            type=tag.type,
            size=tag.size,
            raw_bytes=b"",
            reason=FallbackReason.PARSE_ERROR,
            array_index=getattr(tag, "array_index", 0),
            tag_data=getattr(tag, "tag_data", None),
            error_message=str(e),
        )


# ---------------------------------------------------------------------------
# parse_properties_from_export sub-functions
# ---------------------------------------------------------------------------


def _handle_serialization_control(
    archive: "FArchive",
    summary: "PackageFileSummary",
    export: ObjectExport,
) -> None:
    """Handle SerializationControlExtensions header (D-02).

    UE5 >= 1011: root-level overridable serialization control header.
    Applied to all UObject exports (via UObject::SerializeScriptProperties -> ObjClass->SerializeTaggedProperties).
    ObjClass is UClass*, so IsA<UClass>() is always true.
    Known bits: 0x01 = ReserveForFutureUse, 0x02 = OverridableSerializationInformation.
    Unknown high bits (0x04+) may be new UE5.6+ flags; record as diagnostic info without affecting offsets.
    """
    control_offset = archive.tell()
    serialization_control = archive.read_u8()
    overridden_operation = None
    if serialization_control & 0x02:
        overridden_operation = archive.read_u8()
    # Record unknown bits (bits other than known bits 0x01|0x02)
    unknown_bits = serialization_control & ~_KNOWN_SERIALIZATION_CONTROL_BITS
    if unknown_bits:
        # Record which bits are set in detail
        bit_names = []
        for bit, name in _SERIALIZATION_CONTROL_BIT_NAMES.items():
            if unknown_bits & bit:
                bit_names.append(name)
        archive._record_structured_diagnostic(
            code="unknown_serialization_control_bits",
            stage="parse_properties",
            offset=control_offset,
            raw_value=serialization_control,
            fallback="skipped_subsequent_reads",
            message=f"Export '{getattr(export, 'object_name', '')}' SerializationControlExtensions unknown bits: 0x{unknown_bits:02X} (bits: {', '.join(bit_names)})",
        )
        # Record diagnostic info
        archive._record_diagnostic(
            module="property_parser",
            field="serialization_control",
            source="parse_properties_from_export",
            target_offset=control_offset,
            file_size=getattr(archive, "_file_size", 0),
            error=f"SerializationControlExtensions unknown bits: 0x{unknown_bits:02X} ({', '.join(bit_names)})",
        )
        # Store in export transforms, for IR/JSON output
        if not hasattr(export, "transforms") or export.transforms is None:
            export.transforms = {}
        export.transforms["serialization_control"] = {
            "value": serialization_control,
            "overridden_operation": None,
            "unknown_bits": unknown_bits,
            "offset": control_offset,
        }
        # Unknown bits may cause subsequent byte misalignment; return early so caller handles recovery
        return
    # Store in export transforms, for IR/JSON output
    if not hasattr(export, "transforms") or export.transforms is None:
        export.transforms = {}
    export.transforms["serialization_control"] = {
        "value": serialization_control,
        "overridden_operation": overridden_operation,
        "unknown_bits": unknown_bits,
        "offset": control_offset,
    }


def _handle_unversioned_properties(
    export: ObjectExport,
    archive: "FArchive",
    summary: "PackageFileSummary",
    name_map: List[str],
    export_map: List[Any],
    mappings: Any,
    import_map: Optional[List[ObjectImport]],
    property_end: int,
    tolerant: bool,
) -> Optional[List[PropertyValue]]:
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
    if opaque_size > 0:
        raw_bytes = archive.read(opaque_size)
    else:
        raw_bytes = b""
    logger.debug(
        "Unversioned export '%s' without mappings, returning opaque block (%d bytes)",
        export.object_name,
        len(raw_bytes),
    )
    # Mark export status as opaque_unversioned, not as a full success in the final report
    setattr(export, "parse_status", validate_parse_status("opaque_unversioned"))
    setattr(export, "fallback_reason", "missing_mapping")
    return [
        PropertyFallback(
            name=export.object_name,
            type="UnversionedOpaque",
            size=len(raw_bytes),
            raw_bytes=raw_bytes,
            reason=FallbackReason.MISSING_MAPPING,
        )
    ]


def _resolve_object_property(
    tag: PropertyTag,
    value: Any,
    linker: Optional[Any],
    import_map: Optional[List[ObjectImport]],
    export_map: List[Any],
    name_map: List[str],
) -> Optional[Any]:
    """ObjectProperty enhancement: prefer linker resolution, fall back to import_map resolution.

    Return the resolved reference dictionary, or None if no replacement needed.
    """
    if tag.type != "ObjectProperty" or not isinstance(value, int):
        return None
    if linker is not None:
        pkg_idx = PackageIndex(value)
        inst = linker.resolve_package_index(pkg_idx)
        if inst is not None:
            return {
                "type": "import" if inst.is_import else "export",
                "object_name": inst.object_name,
                "object_class": inst.object_class,
                "full_name": inst.get_full_name(),
            }
    elif import_map is not None:
        from uasset_read.serializers.object_resources import resolve_package_index_to_reference

        pkg_idx = PackageIndex(value)
        ref = resolve_package_index_to_reference(pkg_idx, import_map, export_map, name_map)
        if ref and ref.get("source") == "import_map":
            return ref
    return None


def _handle_property_parse_error(
    e: ParseError,
    tag: Optional[PropertyTag],
    start_pos: Optional[int],
    archive: "FArchive",
    name_map: List[str],
    property_end: int,
) -> PropertyValue:
    """Handle property parse error, return PropertyValue wrapped in PropertyFallback.

    Responsible for smart skip of corrupted data, preventing infinite loops.
    """
    # D-19: Smart continue - skip damaged property using PropertyTag.Size
    if tag is not None and start_pos is not None:
        target_pos = start_pos + tag.size
        # Safety net: if target_pos goes backward or stays in place, force advance by at least 1 byte
        if target_pos > start_pos:
            archive.seek(target_pos)
        else:
            archive.seek(min(start_pos + 1, getattr(archive, "_file_size", start_pos + 1)))
    else:
        # start_pos unknown (tag read failed early), try smart recovery
        recover_start = archive.tell()
        recovered = _try_recover_property_tag(
            archive,
            name_map,
            max_scan=_MAX_RECOVERY_SCAN,
            property_end=property_end,
        )
        if recovered:
            scan_distance = archive.tell() - recover_start
            logger.debug(
                "PropertyTag early corruption, recovered to a potentially valid position (offset=%d, scan distance=%d)",
                archive.tell(),
                scan_distance,
            )
        else:
            # Recovery failed, advance 1 byte to prevent infinite loop
            next_pos = archive.tell() + 1
            file_size = getattr(archive, "_file_size", None)
            if isinstance(file_size, int):
                next_pos = min(next_pos, file_size)
            logger.debug(
                "PropertyTag early corruption, cannot recover (scanned %d bytes), skip 1 byte (offset=%d)",
                _MAX_RECOVERY_SCAN,
                archive.tell(),
            )
            archive.seek(next_pos)

    # Use PropertyFallback instead of a plain string error message
    fb = PropertyFallback(
        name=tag.name if tag is not None else "Unknown",
        type=tag.type if tag is not None else "Unknown",
        size=tag.size if tag is not None else 0,
        raw_bytes=b"",
        reason=FallbackReason.PARSE_ERROR,
        array_index=tag.array_index if tag is not None else 0,
        error_message=f"ParseError at offset {start_pos}: {e}",
    )
    return PropertyValue(
        name=fb.name,
        type="Warning",
        value=fb,
        array_index=fb.array_index,
    )


def _read_property_loop(
    export: ObjectExport,
    archive: "FArchive",
    summary: "PackageFileSummary",
    name_map: List[str],
    export_map: List[Any],
    import_map: Optional[List[ObjectImport]],
    linker: Optional[Any],
    mappings: Optional[Any],
    property_end: int,
    tolerant: bool,
    skip_class_name: Optional[str] = None,
) -> List[PropertyValue]:
    """Main property reading loop."""
    properties: List[PropertyValue] = []
    property_count = 0

    while True:
        # D-08/D-09: Property loop limit check
        if property_count >= MAX_PROPERTY_COUNT:
            raise ParseError(
                f"Property count exceeds maximum ({MAX_PROPERTY_COUNT})",
                context=ErrorContext(
                    offset=archive.tell(),
                    phase="properties",
                    operation="property_count_check",
                    context_name=str(export.object_name),
                ),
            )
        property_count += 1

        tag = None
        start_pos = None

        try:
            # Boundary check: current position should not exceed property data range
            current_pos = archive.tell()
            if current_pos >= property_end:
                break
            # #276: EOF check — prevent infinite retry at EOF when archive data is insufficient
            file_size = getattr(archive, "_file_size", None)
            if isinstance(file_size, int) and current_pos >= file_size:
                break

            struct_name = None
            if mappings is not None and import_map is not None:
                try:
                    from uasset_read.serializers.object_resources import resolve_class_name

                    struct_name = resolve_class_name(export.class_index, import_map, export_map)
                except (KeyError, AttributeError, IndexError) as e:
                    logger.debug("Failed to resolve class name in property loop: %s, using fallback", e)
                    struct_name = export.object_name
            try:
                tag = read_property_tag(
                    archive, name_map, tolerant=tolerant, mappings=mappings, struct_name=struct_name
                )
            except ParseError as e:
                # #341: PropertyTag read failed — try recovery scan for next valid tag
                remaining = property_end - archive.tell()
                if remaining < 32:
                    break
                if not tolerant:
                    raise
                # Try smart recovery: scan forward for next valid PropertyTag boundary
                recovered = _try_recover_property_tag(
                    archive,
                    name_map,
                    max_scan=_MAX_RECOVERY_SCAN,
                    property_end=property_end,
                )
                if recovered:
                    logger.debug(
                        "#341: PropertyTag read failed at offset %d, recovered to %d",
                        current_pos,
                        archive.tell(),
                    )
                    # Record a PropertyFallback for the corrupted tag
                    properties.append(
                        PropertyValue(
                            name="Corrupted",
                            type="Warning",
                            value=PropertyFallback(
                                name="Corrupted",
                                type="Unknown",
                                size=0,
                                raw_bytes=b"",
                                reason=FallbackReason.PARSE_ERROR,
                                error_message=f"PropertyTag read failed: {e}",
                            ),
                        )
                    )
                    continue
                # Recovery failed — break to avoid infinite loop
                break

            # Record current position after tag read (for size_exceeded recovery and boundary verification)
            start_pos = archive.tell()

            # Termination marker: Name == UE_NONE_SENTINEL
            if tag.name == UE_NONE_SENTINEL:
                break

            # size exceeds remaining bytes: try recovery, mark as partial on failure
            if tag.size_exceeded:
                # #341/#429: Try recovery — scan from tag_start_offset (the position where
                # the corrupted tag began) rather than start_pos (after the tag).  When the
                # tag read consumed bytes that actually belong to the next valid tag,
                # starting from after the tag skips past the real boundary.
                recovered_from = tag.tag_start_offset if tag.tag_start_offset is not None else start_pos
                if recovered_from is not None:
                    archive.seek(recovered_from)
                    recovered = _try_recover_property_tag(
                        archive,
                        name_map,
                        max_scan=_MAX_RECOVERY_SCAN,
                        property_end=property_end,
                    )
                    if recovered:
                        logger.debug(
                            "size_exceeded: recovered from %d to a potentially valid position (offset=%d)",
                            recovered_from,
                            archive.tell(),
                        )
                        # Record a PropertyFallback for the skipped corrupted tag
                        properties.append(
                            PropertyValue(
                                name=tag.name,
                                type="Warning",
                                value=PropertyFallback(
                                    name=tag.name,
                                    type=tag.type,
                                    size=tag.size,
                                    raw_bytes=b"",
                                    reason=FallbackReason.SIZE_EXCEEDED,
                                    error_message=f"Size {tag.size} exceeds remaining bytes; "
                                    f"skipped to next valid PropertyTag",
                                ),
                            )
                        )
                        continue
                # Recovery failed, create PropertyFallback
                properties.append(
                    PropertyValue(
                        name=tag.name,
                        type=tag.type,
                        value=PropertyFallback(
                            name=tag.name,
                            type=tag.type,
                            size=tag.size,
                            raw_bytes=b"",
                            reason=FallbackReason.SIZE_EXCEEDED,
                            error_message=f"Size {tag.size} exceeds remaining bytes",
                        ),
                        array_index=tag.array_index,
                    )
                )
                setattr(export, "parse_status", validate_parse_status("partial"))
                break

            # Boundary check: PropertyTag.Size should not exceed remaining property data range
            remaining = property_end - archive.tell()
            if tag.size > remaining:
                raise ParseError(
                    f"Property tag size {tag.size} exceeds remaining data {remaining} for '{tag.name}'",
                    context=ErrorContext(
                        offset=archive.tell(),
                        phase="properties",
                        operation="property_tag_size_check",
                        context_name=str(tag.name),
                    ),
                )

            # Dispatch to type-specific parser
            # lambda executes immediately inside read_tag_value_bounded, tag is bound at call time
            value = read_tag_value_bounded(
                archive,
                tag,
                lambda tag=tag: parse_property_value(  # noqa: B023
                    tag, archive, name_map, export_map, summary, tolerant=tolerant
                ),
            )

            # If parsing returns None (old path or handler explicitly returns None), convert to PropertyFallback
            if value is None:
                value = PropertyFallback(
                    name=tag.name,
                    type=tag.type,
                    size=tag.size,
                    raw_bytes=b"",
                    reason=FallbackReason.UNSUPPORTED_TYPE,
                    array_index=tag.array_index,
                    error_message="Parser returned None (unsupported or missing handler)",
                )

            properties.append(PropertyValue(name=tag.name, type=tag.type, value=value, array_index=tag.array_index))

            # ObjectProperty enhancement: prefer linker resolution, fall back to import_map resolution
            resolved = _resolve_object_property(tag, value, linker, import_map, export_map, name_map)
            if resolved is not None:
                properties[-1].value = resolved

        except ParseError as e:
            # #276: strict mode: propagate directly, no retry
            if not tolerant:
                raise
            properties.append(
                _handle_property_parse_error(
                    e,
                    tag,
                    start_pos,
                    archive,
                    name_map,
                    property_end,
                )
            )

    return properties


# ---------------------------------------------------------------------------
# parse_properties_from_export -- main entry point
# ---------------------------------------------------------------------------


def parse_properties_from_export(
    export: ObjectExport,
    archive: FArchive,
    summary: "PackageFileSummary",
    name_map: List[str],
    export_map: List[Any],
    import_map: Optional[List[ObjectImport]] = None,
    linker: Optional[Any] = None,
    mappings: Optional[Any] = None,
    game: Optional[str] = None,
    tolerant: bool = True,
) -> List[PropertyValue]:
    """Read all properties from an export entry (PROP-01).

    Reference: Class.cpp SerializeVersionedTaggedProperties pattern:
    1. Seek to property start position
    2. Loop reading PropertyTag until Name == "None"
    3. Dispatch to type-specific parsing function
    4. Boundary verification (seek to start + tag.size)

    Args:
        export: ObjectExport instance
        archive: FArchive instance
        summary: PackageFileSummary instance (version info)
        name_map: name table
        export_map: export table
        import_map: import table (needed for ObjectProperty parsing, used when linker is not provided)
        linker: PackageLinker instance (optional, preferred for ObjectProperty parsing)

    Returns:
        List[PropertyValue] property value list
    """
    if mappings is not None:
        setattr(summary, "_mappings", mappings)
    if game is not None:
        setattr(summary, "_game", game)

    # UE default: always start property parsing from SerialOffset
    # ScriptSerializationStartOffset only used in special editor scenarios
    # (property bag placeholder or class mismatch) -- see LinkerLoad.cpp:4793
    property_start = export.serial_offset

    archive.seek(property_start)

    # Tolerant skip: directly skip known incompatible class-specific payloads
    from uasset_read.parsers.class_specific_skip import (
        should_skip_export_for_tolerant_parsing,
        skip_export_payload,
    )

    # Parse export class name for skip check
    skip_class_name = None
    if import_map is not None:
        try:
            from uasset_read.serializers.object_resources import resolve_class_name

            skip_class_name = resolve_class_name(export.class_index, import_map, export_map)
        except (KeyError, AttributeError, IndexError) as e:
            logger.debug("Failed to resolve class name for export: %s", e)
    if should_skip_export_for_tolerant_parsing(export, class_name=skip_class_name):
        logger.debug(
            "Tolerant skip: class-specific payload '%s', skipping property parsing",
            export.object_name,
        )
        try:
            skip_export_payload(archive, export, summary)
        except (_struct.error, OSError, ValueError) as e:
            logger.debug("Failed to skip export '%s' payload: %s", export.object_name, e)
        setattr(export, "parse_status", validate_parse_status("skipped"))
        setattr(export, "fallback_reason", "unsupported_type")
        setattr(export, "class_name", skip_class_name or "")
        return []

    # D-02: SerializationControlExtensions header handling
    if summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION:
        _handle_serialization_control(archive, summary, export)

    # Calculate property data boundary
    # UE default: use SerialSize as property boundary
    property_end = export.serial_offset + export.serial_size

    # Unversioned property handling (including opaque fallback)
    unversioned_result = _handle_unversioned_properties(
        export,
        archive,
        summary,
        name_map,
        export_map,
        mappings,
        import_map,
        property_end,
        tolerant,
    )
    if unversioned_result is not None:
        properties = unversioned_result
    else:
        # Main property reading loop
        properties = _read_property_loop(
            export,
            archive,
            summary,
            name_map,
            export_map,
            import_map,
            linker,
            mappings,
            property_end,
            tolerant,
            skip_class_name=skip_class_name,
        )

    # Asset type handler dispatch: called after property parsing
    if skip_class_name is not None:
        _try_asset_type_handler(
            export,
            archive,
            name_map,
            skip_class_name,
            parsed_properties=properties,
            property_end=property_end,
            export_map=export_map,
            import_map=import_map,
            summary=summary,
            linker=linker,
        )

    return properties


def _resolve_mapping_struct_name(
    export: ObjectExport, import_map: Optional[List[ObjectImport]], export_map: List[Any]
) -> str:
    if import_map is not None:
        try:
            from uasset_read.serializers.object_resources import resolve_class_name

            return resolve_class_name(export.class_index, import_map, export_map)
        except (KeyError, AttributeError, IndexError) as e:
            logger.debug("Failed to resolve mapping struct name: %s", e)
    return export.object_name


def _parse_unversioned_properties_from_mapping(
    export: ObjectExport,
    archive: FArchive,
    summary: "PackageFileSummary",
    name_map: List[str],
    export_map: List[Any],
    mappings: Any,
    struct_name: str,
    property_end: int,
    tolerant: bool = True,
) -> List[PropertyValue]:
    """Parse a simple mapping-driven unversioned property stream.

    This covers the common sequential field case and preserves unknown tail data
    as an opaque warning instead of guessing beyond mapped fields.
    """
    struct_mapping = mappings.get_struct(struct_name)
    if struct_mapping is None:
        return []
    ordered_properties = _ordered_mapping_properties(mappings, struct_mapping)
    header = _try_read_unversioned_header(archive, property_end, len(ordered_properties))
    selected_properties = (
        [(ordered_properties[index], is_zero) for index, is_zero in header]
        if header is not None
        else [(info, False) for info in ordered_properties]
    )
    out: List[PropertyValue] = []
    for position, (info, is_zero) in enumerate(selected_properties):
        if archive.tell() >= property_end and not is_zero:
            break
        remaining = property_end - archive.tell()
        is_last = position == len(selected_properties) - 1
        tag = PropertyTag(
            name=info.name,
            type=info.mapping_type.type,
            size=_unversioned_property_size(info.mapping_type, archive, remaining, is_last),
            tag_data=info.mapping_type,
        )
        _apply_mapping_type_to_tag(tag, info.mapping_type)
        if is_zero:
            out.append(PropertyValue(info.name, tag.type, _unversioned_zero_value(info.mapping_type)))
            continue
        start = archive.tell()
        try:
            value = parse_property_value(tag, archive, name_map, export_map, summary, tolerant=tolerant)
        except ParseError as exc:
            # #276: strict mode: propagate directly
            if not tolerant:
                raise
            if tag.size > 0:
                seek_target = min(start + tag.size, property_end, archive.total_size())
                archive.seek(seek_target)
            fb = PropertyFallback(
                name=info.name,
                type=tag.type,
                size=tag.size,
                raw_bytes=b"",
                reason=FallbackReason.PARSE_ERROR,
                array_index=0,
                error_message=f"ParseError: {exc}",
            )
            out.append(PropertyValue(info.name, "Warning", fb))
            continue
        if tag.size <= 0:
            tag.size = archive.tell() - start
        out.append(PropertyValue(info.name, tag.type, value))
    if archive.tell() < property_end:
        remaining = property_end - archive.tell()
        # #276: Safely read tail, prevent property_end from exceeding actual archive size
        current_pos = archive.tell()
        file_size = getattr(archive, "_file_size", None)
        if isinstance(file_size, int):
            tail_size = max(0, min(remaining, file_size - current_pos))
        else:
            tail_size = remaining
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


def _try_read_unversioned_header(
    archive: FArchive,
    property_end: int,
    property_count: int,
) -> Optional[list[tuple[int, bool]]]:
    """Try UE FUnversionedHeader fragments; return None for legacy fixture streams."""
    start = archive.tell()
    fragments: list[tuple[int, bool, int]] = []
    try:
        cursor = 0
        total_values = 0
        while archive.tell() + 2 <= property_end:
            packed = archive.read_u16()
            skip_num = packed & 0x7F
            has_any_zeroes = bool(packed & 0x80)
            value_num = (packed >> 8) & 0xFF
            if value_num == 0:
                break
            cursor += skip_num
            if cursor + value_num > property_count:
                raise ParseError("unversioned fragment exceeds mapping property count")
            fragments.append((cursor, has_any_zeroes, value_num))
            cursor += value_num
            total_values += value_num
            if len(fragments) > property_count:
                raise ParseError("too many unversioned fragments")
        else:
            raise ParseError("unterminated unversioned header")
        if not fragments or total_values == 0:
            raise ParseError("no unversioned values")

        zero_bits: list[bool] = []
        for _cursor, has_any_zeroes, value_num in fragments:
            if not has_any_zeroes:
                zero_bits.extend([False] * value_num)
                continue
            word_count = (value_num + 31) // 32
            bits: list[bool] = []
            for _ in range(word_count):
                word = archive.read_u32()
                bits.extend(bool(word & (1 << bit)) for bit in range(32))
            zero_bits.extend(bits[:value_num])

        selected: list[tuple[int, bool]] = []
        bit_offset = 0
        for cursor, _has_any_zeroes, value_num in fragments:
            for local_index in range(value_num):
                selected.append((cursor + local_index, zero_bits[bit_offset + local_index]))
            bit_offset += value_num
        if archive.tell() >= property_end and not all(is_zero for _index, is_zero in selected):
            raise ParseError("unversioned header consumes entire property payload")
        return selected
    except (_struct.error, ParseError, ValueError) as e:
        logger.debug("Unversioned header parse failed, falling back to legacy: %s", e)
        archive.seek(start)
        return None


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
        inner = getattr(prop_type, "inner_type", None)
        return _fixed_unversioned_size(inner) if inner is not None else 8
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
