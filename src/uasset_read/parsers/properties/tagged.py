"""Bounded tagged property stream reader — sole tagged entry and tag loop.

Owns the production export-level tag loop (moved from ``property_parser``).
``property_parser`` retains only single-tag value dispatch and the unversioned
field walk; this module is the single production tagged entry.
"""

from __future__ import annotations

import logging
import struct as _struct
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from uasset_read.archive import ByteArchive
from uasset_read.constants import (
    MAX_PROPERTY_COUNT,
    PKG_UnversionedProperties,
    UE5_PROPERTY_TAG_EXTENSION,
    UE_NONE_SENTINEL,
)
from uasset_read.exceptions import BINARY_READ_ERRORS, REFERENCE_RESOLVE_ERRORS, ParseError
from uasset_read.models.byte_ranges import opaque_region, region_from_source
from uasset_read.models.diagnostics import Diagnostic
from uasset_read.models.fallback import FallbackReason, PropertyFallback
from uasset_read.models.properties import PropertyBag, PropertyEntry, PropertyValue
from uasset_read.parsers.properties import PropertyInput, PropertyReadResult
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex, script_property_region
from uasset_read.serializers.property_tags import read_property_tag, read_tag_value_bounded

from uasset_read.parsers.property_parser import (
    _get_parse_functions,
    _handle_unversioned_properties,
    _skip_type_tree_nodes,
    _stream_is_poisoned,
    parse_property_value,
)

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectImport
    from uasset_read.serializers.package_summary import PackageFileSummary

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

_IMPORT_JSON_MAX = 65536


def _is_import_data_class(class_name: str | None) -> bool:
    name = class_name or ""
    return name == "AssetImportData" or ("ImportData" in name and name.startswith("Fbx"))


def _maybe_skip_import_data_json_prelude(
    archive: "FArchive",
    *,
    class_name: str | None,
    region_end: int,
) -> bool:
    """Skip UAssetImportData's FAssetImportInfo JSON FString prelude.

    Pre-5.4 packages have no authoritative script region, so the property
    parser starts at SerialOffset while the import JSON still precedes the
    tagged stream (object_resources.script_property_region comment / #626).
    """
    if not _is_import_data_class(class_name):
        return False
    start = archive.tell()
    if region_end - start < 5:
        return False
    # Peek length without committing.
    length = archive.read_i32()
    if length <= 0 or length > _IMPORT_JSON_MAX:
        archive.seek(start)
        return False
    if start + 4 + length > region_end:
        archive.seek(start)
        return False
    first = archive.read(1)
    archive.seek(start)
    if first not in (b"{", b"["):
        return False
    # Consume exactly the FString (length includes optional NUL).
    archive.seek(start + 4 + length)
    return True


def _try_recover_property_tag(
    archive,
    name_map: list[str],
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
    data_boundary = min((b for b in (property_end, file_size) if isinstance(b, int)), default=limit)

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
                if type_name not in _get_parse_functions():
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
                first_idx, _ = _struct.unpack("<II", first_node_raw)
                if not (0 <= first_idx < map_len):
                    continue
                first_type_name = name_map[first_idx]
                # #428: validate type tree root node is a known property type
                if first_type_name not in _get_parse_functions():
                    continue
                # Skip remaining type tree (first node already read)
                # Re-seek and use _skip_type_tree_nodes to fully skip
                archive.seek(candidate + 8)
                if not _skip_type_tree_nodes(archive, limit, map_len):
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


def _handle_serialization_control(
    archive: "FArchive",
    summary: "PackageFileSummary",
    export: ObjectExport,
) -> bool:
    """Handle SerializationControlExtensions header (D-02).

    UE5 >= 1011: root-level overridable serialization control header.
    Applied to all UObject exports (via UObject::SerializeScriptProperties -> ObjClass->SerializeTaggedProperties).
    ObjClass is UClass*, so IsA<UClass>() is always true.
    Known bits: 0x01 = ReserveForFutureUse, 0x02 = OverridableSerializationInformation.
    Unknown high bits (0x04+) may be new UE5.6+ flags; they are recorded as a
    diagnostic and make the header terminal — the caller must stop the property
    stream rather than risk reading at a misaligned cursor.

    Returns:
        True when the control byte is fully understood; False on unknown bits.
    """
    control_offset = archive.tell()
    serialization_control = archive.read_u8()
    if serialization_control & 0x02:
        archive.read_u8()  # overridden operation — write-only; advance cursor only.
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
        # Unknown bits may cause subsequent byte misalignment; the caller must
        # stop instead of continuing into the property loop.
        return False
    return True


def _resolve_object_property(
    tag: Any,
    value: Any,
    import_map: list["ObjectImport"] | None,
    export_map: list[Any],
    name_map: list[str],
) -> Any | None:
    """ObjectProperty enhancement: resolve the index against import_map.

    Return the resolved reference dictionary, or None if no replacement needed.
    """
    if tag.type != "ObjectProperty" or not isinstance(value, int):
        return None
    if import_map is not None:
        from uasset_read.serializers.object_resources import resolve_package_index_to_reference

        pkg_idx = PackageIndex(value)
        ref = resolve_package_index_to_reference(pkg_idx, import_map, export_map, name_map)
        if ref and ref.get("source") == "import_map":
            return ref
    return None


def _handle_property_parse_error(
    e: ParseError,
    tag: Any | None,
    start_pos: int | None,
    archive: "FArchive",
    name_map: list[str],
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
        reason=FallbackReason.PARSE_ERROR,
        array_index=tag.array_index if tag is not None else 0,
    )
    return PropertyValue(
        name=fb.name,
        type="Warning",
        value=fb,
        array_index=fb.array_index,
    )


def _read_property_loop(
    export: ObjectExport | SimpleNamespace,
    archive: "FArchive",
    summary: "PackageFileSummary",
    name_map: list[str],
    export_map: list[Any],
    import_map: list["ObjectImport"] | None,
    mappings: Any | None,
    property_end: int,
    tolerant: bool,
) -> list[PropertyValue]:
    """Main property reading loop."""
    properties: list[PropertyValue] = []
    property_count = 0
    # Stop reason for the bounded PropertyInput reader: "none" only when the
    # None terminator was consumed; "tag_failed"/"size_exceeded"/"bound"/
    # "poison" mark abnormal exits. Production read_export ignores this.
    archive._tag_stream_stop = "running"

    while True:
        # D-08/D-09: Property loop limit check
        if property_count >= MAX_PROPERTY_COUNT:
            raise ParseError(f"Property count exceeds maximum ({MAX_PROPERTY_COUNT})")
        property_count += 1

        tag = None
        start_pos = None
        diag_mark = len(archive.get_structured_diagnostics())

        try:
            # Boundary check: current position should not exceed property data range
            current_pos = archive.tell()
            if current_pos >= property_end:
                archive._tag_stream_stop = "bound"
                break
            # #276: EOF check — prevent infinite retry at EOF when archive data is insufficient
            file_size = getattr(archive, "_file_size", None)
            if isinstance(file_size, int) and current_pos >= file_size:
                archive._tag_stream_stop = "bound"
                break

            struct_name = None
            if mappings is not None and import_map is not None:
                try:
                    from uasset_read.serializers.object_resources import resolve_class_name

                    struct_name = resolve_class_name(export.class_index, import_map, export_map)
                except REFERENCE_RESOLVE_ERRORS as e:
                    logger.debug("Failed to resolve class name in property loop: %s, using fallback", e)
                    struct_name = export.object_name
            try:
                tag = read_property_tag(
                    archive, name_map, tolerant=tolerant, mappings=mappings, struct_name=struct_name
                )
            except ParseError:
                # #341: PropertyTag read failed — try recovery scan for next valid tag
                remaining = property_end - archive.tell()
                if remaining < 32:
                    archive._tag_stream_stop = "tag_failed"
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
                                reason=FallbackReason.PARSE_ERROR,
                            ),
                        )
                    )
                    if _stream_is_poisoned(archive, diag_mark):
                        archive._tag_stream_stop = "poison"
                        break
                    continue
                # Recovery failed — break to avoid infinite loop
                archive._tag_stream_stop = "tag_failed"
                break

            # Record current position after tag read (for size_exceeded recovery and boundary verification)
            start_pos = archive.tell()

            # Termination marker: Name == UE_NONE_SENTINEL
            if tag.name == UE_NONE_SENTINEL:
                archive._tag_stream_stop = "none"
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
                                    reason=FallbackReason.SIZE_EXCEEDED,
                                ),
                            )
                        )
                        if _stream_is_poisoned(archive, diag_mark):
                            archive._tag_stream_stop = "poison"
                            break
                        continue
                # Recovery failed, create PropertyFallback
                properties.append(
                    PropertyValue(
                        name=tag.name,
                        type=tag.type,
                        value=PropertyFallback.from_tag(
                            tag,
                            FallbackReason.SIZE_EXCEEDED,
                        ),
                        array_index=tag.array_index,
                    )
                )
                archive._tag_stream_stop = "size_exceeded"
                break

            # Boundary check: PropertyTag.Size should not exceed remaining property data range
            remaining = property_end - archive.tell()
            if tag.size > remaining:
                raise ParseError(f"Property tag size {tag.size} exceeds remaining data {remaining} for '{tag.name}'")

            # Dispatch to type-specific parser
            # lambda executes immediately inside read_tag_value_bounded, tag is bound at call time
            value_start = archive.tell()
            value = read_tag_value_bounded(
                archive,
                tag,
                lambda tag=tag: parse_property_value(  # noqa: B023
                    tag, archive, name_map, export_map, summary, tolerant=tolerant
                ),
            )
            value_end = archive.tell()

            # If parsing returns None (old path or handler explicitly returns None), convert to PropertyFallback
            if value is None:
                value = PropertyFallback.from_tag(
                    tag,
                    FallbackReason.UNSUPPORTED_TYPE,
                )

            properties.append(
                PropertyValue(
                    name=tag.name,
                    type=tag.type,
                    value=value,
                    array_index=tag.array_index,
                    tag_start_offset=tag.tag_start_offset,
                    value_start_offset=value_start,
                    value_end_offset=value_end,
                )
            )

            # ObjectProperty enhancement: resolve the index against import_map
            resolved = _resolve_object_property(tag, value, import_map, export_map, name_map)
            if resolved is not None:
                properties[-1].value = resolved

            if _stream_is_poisoned(archive, diag_mark):
                archive._tag_stream_stop = "poison"
                break

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
            if _stream_is_poisoned(archive, diag_mark):
                archive._tag_stream_stop = "poison"
                break

    return properties


# Export class name prefixes/keywords that need skipping.
# These classes have serialization data not fully compatible with the generic property parser.
SKIP_CLASS_PREFIXES = (
    # P0: Builder / Brush
    "GeomModifier_",
    "BrushBuilder",
    # P0: Animation -- migrated to opaque whitelist (#166)
    # P1: Niagara
    "NiagaraMeshRendererProperties",
    "NiagaraNode",
    "NiagaraSystem",
    # P1: MovieScene -- moved to opaque whitelist (#164)
    # P2: MetaSound -- moved to opaque whitelist (#165)
    # P2: K2Node
    # K2Node_FunctionEntry removed from skip list (#286):
    # Generic tagged property parser can handle it. K2Node_FunctionEntry specific fields
    # are serialized via PropertyTag, no skip needed. Skipping would mark legitimate assets as partial.
    "K2Node_FormatText",
    # P2: Material
    # MaterialExpressionDynamicParameter removed from skip list (#136 extension):
    # Generic tagged property parser can handle it; failures handled by generic fallback.
    # MaterialExpression removed from skip list (#136):
    # Generic tagged property parser can handle most MaterialExpression subclasses.
    # Subclasses that fail to parse are handled by generic fallback (opaque/partial).
    # P3: Other
    "SkySphereMesh",
    "AggGeom_",
)


class _TolerantSkip:
    """Marker for read_export's return list: payload seeked, not decoded."""


# Sole-element return when should_skip_export_for_tolerant_parsing fires. The
# caller must not register byte accounting for it -- no structural byte was
# read (#653).
TOLERANT_SKIP = _TolerantSkip()


def should_skip_export_for_tolerant_parsing(
    export: ObjectExport,
    class_name: str | None = None,
) -> bool:
    """True when the export should bypass the generic property parser."""
    return str(export.object_name).startswith(SKIP_CLASS_PREFIXES) or (class_name or "").startswith(SKIP_CLASS_PREFIXES)


def skip_export_payload(
    archive: "FArchive",
    export: ObjectExport,
    summary: "PackageFileSummary",
) -> None:
    """Safely skip the payload data of a single export.

    Seek past the export property region without attempting to parse.

    Args:
        archive: FArchive instance
        export: ObjectExport instance
        summary: PackageFileSummary instance
    """
    from uasset_read.constants import UE5_SCRIPT_SERIALIZATION_OFFSET

    if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
        # Use getattr for safe fallback to prevent AttributeError when attribute does not exist
        script_serial_end = getattr(export, "script_serialization_end_offset", None)
        if script_serial_end is None:
            # Fall back to serial_size for compatibility
            script_serial_end = export.serial_size
        payload_end = export.serial_offset + script_serial_end
    else:
        payload_end = export.serial_offset + export.serial_size

    # Ensure it does not exceed file size
    file_size = archive.total_size()
    safe_end = min(payload_end, file_size)

    logger.debug(
        "Skipping export '%s' payload: seek from %d to %d (%d bytes)",
        export.object_name,
        archive.tell(),
        safe_end,
        safe_end - archive.tell(),
    )
    archive.seek(safe_end)


def parse_properties_from_export(
    export: ObjectExport,
    archive: "FArchive",
    summary: "PackageFileSummary",
    name_map: list[str],
    export_map: list[Any],
    import_map: list["ObjectImport"] | None = None,
    mappings: Any | None = None,
    game: str | None = None,
    tolerant: bool = True,
) -> list[Any]:
    """Read all properties from an export entry (PROP-01).

    The production export-level tagged stream; the tag loop lives in
    ``_read_property_loop`` above. ``TaggedPropertyReader.read_export`` is the
    public wrapper.

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
        import_map: import table (needed for ObjectProperty parsing)

    Returns:
        list[PropertyValue] property value list
    """
    if game is not None:
        setattr(summary, "_game", game)

    # The tagged-property region is recorded per export from UE 5.4 on
    # (script_property_region); before that version the field does not exist, so
    # SerialOffset is all we have. Class-native bytes can precede the stream
    # (UAssetImportData's FAssetImportInfo JSON), which is why SerialOffset alone
    # is not a safe start once the offsets are available.
    property_start, property_end, _authoritative = script_property_region(export)

    archive.seek(property_start)

    # Tolerant skip: directly skip known incompatible class-specific payloads
    # Parse export class name for skip check
    skip_class_name = None
    if import_map is not None:
        try:
            from uasset_read.serializers.object_resources import resolve_class_name

            skip_class_name = resolve_class_name(export.class_index, import_map, export_map)
        except REFERENCE_RESOLVE_ERRORS as e:
            logger.debug("Failed to resolve class name for export: %s", e)
    if should_skip_export_for_tolerant_parsing(export, class_name=skip_class_name):
        logger.debug(
            "Tolerant skip: class-specific payload '%s', skipping property parsing",
            export.object_name,
        )
        try:
            skip_export_payload(archive, export, summary)
        except BINARY_READ_ERRORS as e:
            logger.debug("Failed to skip export '%s' payload: %s", export.object_name, e)
        return [TOLERANT_SKIP]

    # D-02: SerializationControlExtensions header handling.
    # UE source: SerializeVersionedTaggedProperties writes this byte (Class.cpp);
    # SerializeUnversionedProperties starts directly with FUnversionedHeader and
    # never emits the control byte — consuming it here would desync the fragment.
    uses_unversioned = bool(getattr(summary, "package_flags", 0) & PKG_UnversionedProperties)
    if summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION and not uses_unversioned:
        if not _handle_serialization_control(archive, summary, export):
            return [
                PropertyFallback(
                    name=export.object_name,
                    type="SerializationControlExtensions",
                    size=0,
                    reason=FallbackReason.PARSE_ERROR,
                )
            ]

    # When the export records no script region the legacy boundary applies: the whole
    # serial block is the property stream (pre-5.4 packages, unversioned properties).
    if not _authoritative:
        property_end = export.serial_offset + export.serial_size

    # Pre-5.4: no authoritative script region; AssetImportData exports may still
    # begin with UAssetImportData's FAssetImportInfo JSON FString before the
    # tagged stream (#626). Only skip for non-authoritative regions.
    if not _authoritative:
        _maybe_skip_import_data_json_prelude(
            archive,
            class_name=skip_class_name,
            region_end=export.serial_offset + export.serial_size,
        )

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
            mappings,
            property_end,
            tolerant,
        )

    return properties


def _property_values_to_bag(
    properties: list[PropertyValue],
    input: PropertyInput,
) -> tuple[PropertyBag, list]:
    """Convert loop PropertyValues into a lossless bag + decoded byte regions."""
    bag = PropertyBag()
    regions: list = []
    for pv in properties:
        name = getattr(pv, "name", None)
        if not name:
            continue
        array_index = getattr(pv, "array_index", None)
        if isinstance(array_index, int) and array_index < 0:
            array_index = None
        type_name = getattr(pv, "type", "") or ""
        value = getattr(pv, "value", None)
        tag_start = getattr(pv, "tag_start_offset", None)
        value_start = getattr(pv, "value_start_offset", None)
        value_end = getattr(pv, "value_end_offset", None)
        tag_region = None
        value_region = None
        if tag_start is not None and value_start is not None and value_start >= tag_start:
            tag_region = region_from_source(
                input.source,
                input.start + tag_start,
                value_start - tag_start,
                status="decoded",
                feature="property_tag",
            )
            regions.append(tag_region)
            if value_end is not None and value_end > value_start:
                value_region = region_from_source(
                    input.source,
                    input.start + value_start,
                    value_end - value_start,
                    status="decoded",
                    feature="property_value",
                )
                regions.append(value_region)
        bag.entries.append(
            PropertyEntry(
                name=str(name),
                type_name=type_name,
                value=value,
                array_index=array_index,
                tag_region=tag_region,
                value_region=value_region,
            )
        )
    return bag, regions


def _loop_recovery_diagnostics(
    properties: list[PropertyValue],
    window: ByteArchive,
    input: PropertyInput,
    diag_mark: int,
) -> list[Diagnostic]:
    """Derive PropertyReadResult diagnostics from unified-loop recovery signals.

    Two sources, matching what the pre-unification ``read()`` reported:

    * Structured diagnostics the loop (and the value parsers it drives) recorded
      on the bounded window after ``diag_mark`` — fstring/name recoveries etc.
    * ``PropertyFallback`` values the loop appended instead of raising, mapped
      back to the PROPERTY_TAG_READ_FAILED / PROPERTY_VALUE_READ_FAILED codes.
    """
    diagnostics: list[Diagnostic] = []

    for sd in window.get_structured_diagnostics()[diag_mark:]:
        offset = input.start + sd.offset if sd.offset is not None else None
        recovered = sd.fallback != "stop_table"
        diagnostics.append(
            Diagnostic(
                severity=sd.severity,
                code=sd.code,
                message=sd.message,
                stage=sd.stage or "properties.tagged",
                object_id=input.object_id,
                offset=offset,
                size=sd.size,
                effect="recovery" if recovered else "data_loss",
                recoverable=recovered,
                fallback=sd.fallback,
                reason=sd.reason,
            )
        )

    for pv in properties:
        fallback = None
        if isinstance(pv, PropertyFallback):
            fallback = pv
        elif isinstance(getattr(pv, "value", None), PropertyFallback):
            fallback = pv.value
        if fallback is None:
            continue

        # Tag-level failures (corrupted-tag placeholder, invalid tag size) keep the
        # old PROPERTY_TAG_READ_FAILED code; value dispatch/unsupported keep VALUE.
        tag_level = pv.name == "Corrupted" or fallback.reason in (FallbackReason.SIZE_EXCEEDED,)
        code = "PROPERTY_TAG_READ_FAILED" if tag_level else "PROPERTY_VALUE_READ_FAILED"
        reason_value = getattr(fallback.reason, "value", str(fallback.reason))
        if fallback.reason in (FallbackReason.UNSUPPORTED_TYPE, FallbackReason.UNSUPPORTED_STRUCT):
            diag_reason: str = "known_unimplemented"
        elif fallback.reason is FallbackReason.MISSING_MAPPING:
            diag_reason = "schema_required"
        else:
            diag_reason = "recovered_corruption"
        tag_start = getattr(pv, "tag_start_offset", None)
        offset = input.start + tag_start if tag_start is not None else input.start
        diagnostics.append(
            Diagnostic(
                severity="warning",
                code=code,
                message=(f"Property {pv.name!r} ({pv.type}) recovered via fallback: {reason_value}"),
                stage="properties.tagged",
                object_id=input.object_id,
                offset=offset,
                size=fallback.size if fallback.size > 0 else None,
                effect="semantic_loss",
                reason=diag_reason,  # type: ignore[arg-type]
            )
        )

    return diagnostics


class TaggedPropertyReader:
    """Sole public tagged entry: bounded slice read + production export stream."""

    def read_export(
        self,
        *,
        export: Any,
        archive: Any,
        summary: Any,
        name_map: list[str],
        export_map: list[Any],
        import_map: Any | None = None,
        mappings: Any | None = None,
        game: str | None = None,
        tolerant: bool = True,
    ) -> list[Any]:
        """Production export-level tagged/unversioned stream.

        The tag loop lives in this module (``_read_property_loop``); value
        dispatch stays in ``property_parser.parse_property_value``. Returns
        ``[TOLERANT_SKIP]`` instead of properties when the export payload was
        seeked without decoding.
        """
        return parse_properties_from_export(
            export=export,
            archive=archive,
            summary=summary,
            name_map=name_map,
            export_map=export_map,
            import_map=import_map,
            mappings=mappings,
            game=game,
            tolerant=tolerant,
        )

    def read(self, input: PropertyInput) -> PropertyReadResult:
        if input.size <= 0:
            empty = region_from_source(input.source, input.start, 0, status="decoded")
            return PropertyReadResult(
                values=PropertyBag(),
                consumed=0,
                regions=[empty],
                diagnostics=[],
                status="complete",
            )

        package_context = input.package_context
        if package_context is None:
            diag = Diagnostic(
                severity="warning",
                code="TAGGED_CONTEXT_REQUIRED",
                message="TaggedPropertyReader.read requires preloaded package tables",
                stage="properties.tagged",
                object_id=input.object_id,
                offset=input.start,
                size=input.size,
                effect="semantic_loss",
                recoverable=True,
            )
            region = opaque_region(input.start, input.size, "package_context_required")
            return PropertyReadResult(
                values=PropertyBag(),
                consumed=0,
                regions=[region],
                diagnostics=[diag],
                status="unavailable",
            )

        try:
            package_bytes = input.source.read_at(input.start, input.size)
        except BINARY_READ_ERRORS + (ParseError,) as exc:
            diag = Diagnostic(
                severity="error",
                code="TAGGED_SOURCE_UNREADABLE",
                message=str(exc),
                stage="properties.tagged",
                object_id=input.object_id,
                offset=input.start,
                size=input.size,
                effect="parse_failure",
                reason="unexpected",
            )
            region = opaque_region(input.start, input.size, "source_unreadable")
            return PropertyReadResult(
                values=PropertyBag(),
                consumed=0,
                regions=[region],
                diagnostics=[diag],
                status="failed",
            )

        summary = package_context.summary
        name_map = package_context.name_map
        export_map = package_context.export_map
        import_map = package_context.import_map
        window = ByteArchive(package_bytes, name=input.object_id)
        window._name_map = name_map
        window._file_version_ue4 = summary.file_version_ue4
        window._file_version_ue5 = summary.file_version_ue5
        window._tolerant = True

        synthetic_export = SimpleNamespace(
            object_name=input.class_name,
            class_index=None,
            serial_offset=input.start,
            serial_size=input.size,
        )
        diag_mark = len(window.get_structured_diagnostics())
        try:
            properties = _read_property_loop(
                export=synthetic_export,
                archive=window,
                summary=summary,
                name_map=name_map,
                export_map=export_map,
                import_map=import_map,
                mappings=None,
                property_end=input.size,
                tolerant=True,
            )
        except Exception as exc:
            diag = Diagnostic(
                severity="warning",
                code="TAGGED_PROPERTY_LOOP_FAILED",
                message=str(exc),
                stage="properties.tagged",
                object_id=input.object_id,
                offset=input.start,
                size=input.size,
                effect="semantic_loss",
                reason="unexpected",
            )
            region = opaque_region(input.start, input.size, "tagged_loop_failed")
            return PropertyReadResult(
                values=PropertyBag(),
                consumed=0,
                regions=[region],
                diagnostics=[diag],
                status="failed",
            )

        consumed = min(window.tell(), input.size)
        bag, regions = _property_values_to_bag(properties, input)
        if not regions:
            regions.append(region_from_source(input.source, input.start, consumed, status="decoded"))
        if input.start + consumed > regions[-1].end:
            regions.append(
                region_from_source(
                    input.source,
                    regions[-1].end,
                    input.start + consumed - regions[-1].end,
                    status="decoded",
                    feature="terminator",
                )
            )
        diagnostics = _loop_recovery_diagnostics(properties, window, input, diag_mark)
        stop = getattr(window, "_tag_stream_stop", "running")
        # Silent tag-failure breaks (recovery scan failed or <32 bytes left)
        # append no PropertyFallback — synthesize the old PROPERTY_TAG_READ_FAILED
        # contract so those stops still report partial + a diagnostic.
        if stop == "tag_failed" and not any(
            d.code in ("PROPERTY_TAG_READ_FAILED", "PROPERTY_VALUE_READ_FAILED") for d in diagnostics
        ):
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="PROPERTY_TAG_READ_FAILED",
                    message="PropertyTag read failed and recovery scan did not find a next tag",
                    stage="properties.tagged",
                    object_id=input.object_id,
                    offset=input.start + consumed,
                    size=input.size - consumed if input.size > consumed else None,
                    effect="semantic_loss",
                    reason="recovered_corruption",
                )
            )
        # complete only when the stream ended on the None terminator and no
        # recovery (fallback or structured diagnostic) occurred in the loop.
        status = "complete" if stop == "none" and not diagnostics else "partial"
        return PropertyReadResult(
            values=bag,
            consumed=consumed,
            regions=regions,
            diagnostics=diagnostics,
            status=status,
        )
