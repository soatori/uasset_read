"""Blueprint Pin binary serializer — FEdGraphPinType, UEdGraphPin read functions.

Split from serializers/graph.py, contains all Pin-related read logic.
"""

from __future__ import annotations

import json
import logging
import struct
from typing import TYPE_CHECKING, List, Optional, Dict, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.constants import (
    MAX_LINKEDTO_PER_PIN,
    MAX_FTEXT_CONSUMPTION,
)
from uasset_read.exceptions import ParseError
from uasset_read.serializers.object_resources import PackageIndex
from uasset_read.models.core import UEdGraphPin, FEdGraphPinType

from uasset_read.serializers.graph_helpers import (
    _read_guid,
    _rcn,
    _get_thread_local,
    _pin_trace_enabled,
    _record_pin_recovery,
    _trace_fields_append,
    _read_fstring_safe,
    _read_ftext_value,
    validate_pin_reference_at,
)

logger = logging.getLogger(__name__)


# ============================================================================
# FEdGraphPinType read functions
# ============================================================================


def read_ed_graph_pin_type(
    archive: FArchive,
    name_map: List[str],
    summary: Optional[PackageFileSummary] = None,
    import_map: Optional[List[ObjectImport]] = None,
    export_map: Optional[List[ObjectExport]] = None,
    linker: Optional["PackageLinker"] = None,
) -> FEdGraphPinType:
    """Parse FEdGraphPinType (UE5.7 specific — custom serialization path)."""
    pin_type = FEdGraphPinType()

    # PinCategory / PinSubCategory (UE5 always uses FName format)
    pin_type.pin_category = archive.read_name(name_map, "PinType.PinCategory")
    pin_type.pin_subcategory = archive.read_name(name_map, "PinType.PinSubCategory")

    # PinSubCategoryObject (FPackageIndex)
    pin_type.pin_subcategory_object = archive.read_i32("PinType.PinSubCategoryObject")
    if pin_type.pin_subcategory_object:
        pkg_idx = PackageIndex(pin_type.pin_subcategory_object)
        try:
            if linker is not None:
                pin_type.pin_subcategory_object_ref = linker.resolve_package_index(pkg_idx)
                if pin_type.pin_subcategory_object_ref is not None:
                    pin_type.pin_subcategory_object_name = getattr(
                        pin_type.pin_subcategory_object_ref, "object_name", None
                    )
            elif import_map is not None and export_map is not None:
                pin_type.pin_subcategory_object_name = _rcn(pkg_idx, import_map, export_map, linker)
        except (KeyError, IndexError, AttributeError):
            pin_type.pin_subcategory_object_ref = None
            pin_type.pin_subcategory_object_name = None

    # ContainerType (UE5 always uses modern uint8 format)
    pin_type.container_type = archive.read_u8("PinType.ContainerType")
    if pin_type.container_type == 3:  # Map
        # Map key terminal type (FEdGraphTerminalType serialization)
        # Reference: UE EdGraphPin.cpp:218 — Ar << PinValueType
        pin_type.map_key_terminal_category = archive.read_name(name_map, "PinType.TerminalCategory")
        pin_type.map_key_terminal_sub_category = archive.read_name(name_map, "PinType.TerminalSubCategory")
        terminal_sub_category_object = archive.read_i32("PinType.TerminalSubCategoryObject")
        pin_type.map_key_terminal_sub_category_object = terminal_sub_category_object
        if terminal_sub_category_object:
            pkg_idx = PackageIndex(terminal_sub_category_object)
            try:
                if linker is not None:
                    ref = linker.resolve_package_index(pkg_idx)
                    if ref is not None:
                        pin_type.map_key_terminal_sub_category_object_name = getattr(ref, "object_name", None)
                elif import_map is not None and export_map is not None:
                    pin_type.map_key_terminal_sub_category_object_name = _rcn(pkg_idx, import_map, export_map, linker)
            except (KeyError, IndexError, AttributeError):
                pin_type.map_key_terminal_sub_category_object_name = None

    # bIsReference / bIsWeakPointer (UE5 FArchive bool = uint32, 4B)
    pin_type.is_reference = archive.read_bool("PinType.bIsReference")
    pin_type.is_weak_pointer = archive.read_bool("PinType.bIsWeakPointer")

    # FSimpleMemberReference (UE5 always present)
    archive.read_i32("PinType.MemberParent")
    archive.read_name(name_map, "PinType.MemberName")
    archive.read_bytes(16, "PinType.MemberGuid")

    # bIsConst (UE5 FArchive bool = uint32, 4B)
    pin_type.is_const = archive.read_bool("PinType.bIsConst")

    # bIsUObjectWrapper (UE5 FArchive bool = uint32, 4B)
    pin_type.is_uobject_wrapper = archive.read_bool("PinType.bIsUObjectWrapper")

    # bSerializeAsSinglePrecisionFloat (UE5 FArchive bool = uint32, 4B)
    pin_type.b_serialize_as_single_precision_float = archive.read_bool("PinType.bSerializeAsSinglePrecisionFloat")

    return pin_type


# ============================================================================
# Pin reference helper functions
# ============================================================================


def read_pin_reference(
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    linker: Optional["PackageLinker"] = None,
) -> Optional[dict]:
    """Read a single Pin reference (FBlueprintEditorUtils::FPinReference)."""
    b_null_ptr = archive.read_i32("PinRef.BNullPtr")
    if b_null_ptr != 0:
        return None  # null marker consumed 4 bytes only, no more reading

    owning_node_index = archive.read_i32("PinRef.OwningNode")
    pin_guid_raw = _read_guid(archive)

    # Normalize to 32-char lowercase hex (remove dashes), matching pin_id format
    pin_guid = pin_guid_raw.replace("-", "").lower() if pin_guid_raw else pin_guid_raw

    # Resolve owning node name
    owning_node_name: Optional[str] = None
    if owning_node_index > 0:
        node_idx = owning_node_index - 1
        if node_idx < len(export_map):
            owning_node_name = export_map[node_idx].object_name
    elif owning_node_index < 0:
        import_idx = -owning_node_index - 1
        if import_idx < len(import_map):
            owning_node_name = import_map[import_idx].object_name

    # pin_guid already normalized above to 32-char lowercase hex (no dashes)
    result = {
        "owning_node": owning_node_name,
        "pin_guid": pin_guid,
    }

    # If linker available, resolve owning_node_index to object reference
    if linker is not None and owning_node_index != 0:
        pkg_idx = PackageIndex(owning_node_index)
        if not pkg_idx.is_null:
            obj_ref = linker.resolve_package_index(pkg_idx)
            result["owning_node_object"] = obj_ref

    return result


def read_pin_array(
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    linker: Optional["PackageLinker"] = None,
    recovery_context: str = "linkedto",  # Distinguish linkedto vs subpins
) -> List[dict]:
    """Read Pin reference array (SerializePinArray format).

    Sliding recovery mechanism — when count is abnormal, scan nearby bytes for a valid i32 count,
    validate candidates before resuming parsing, to avoid losing entire pin arrays due to a single field misalignment.

    Recovery context marker distinguishes LinkedTo recovery from SubPins recovery.
    """
    array_count = archive.read_i32("PinArray.Count")

    if array_count < 0 or array_count > MAX_LINKEDTO_PER_PIN:
        # Sliding recovery: scan within ±8 bytes of current pointer for valid count
        recovery_pos = archive.tell()
        recovered = _recover_pin_array_count(archive, recovery_pos, array_count, export_map, import_map)
        if recovered is not None:
            original_bad_count = array_count
            array_count = recovered["count"]
            _record_pin_recovery(
                {
                    "kind": "pin_array_count",
                    "context": recovery_context,
                    "bad_count": original_bad_count,
                    "candidate_pos": recovered["candidate_pos"],
                    "confidence": recovered["confidence"],
                    "reason": recovered["reason"],
                }
            )
            if recovered["confidence"] == "low" and recovery_context == "linkedto":
                # Low-confidence recovery excluded from LinkedTo connection building to avoid polluting downstream semantics
                logger.info(
                    "[P73-RECOVERY] %s low-confidence recovered (count=%d, reason=%s) -> ignored",
                    recovery_context,
                    array_count,
                    recovered["reason"],
                )
                return []
            logger.info(
                "[P73-RECOVERY] %s recovered: count=%d, confidence=%s, reason=%s",
                recovery_context,
                array_count,
                recovered["confidence"],
                recovered["reason"],
            )
        else:
            if array_count < 0:
                raise ParseError(f"Invalid pin array count: {array_count} (negative)")
            raise ParseError(f"Pin array count {array_count} exceeds MAX_LINKEDTO_PER_PIN {MAX_LINKEDTO_PER_PIN}")

    pins: List[dict] = []
    for _ in range(array_count):
        ref_pos = archive.tell()
        ref_validation = validate_pin_reference_at(archive, ref_pos, export_map, import_map)
        if ref_validation is None or not ref_validation["valid"]:
            reason = ref_validation["reason"] if ref_validation else "not enough bytes"
            raise ParseError(f"Invalid pin reference at pos {ref_pos} in {recovery_context}: {reason}")
        pin_ref = read_pin_reference(archive, name_map, export_map, import_map, linker)
        if pin_ref is not None:
            pins.append(pin_ref)
    return pins


def _recover_pin_array_count(
    archive: FArchive,
    error_pos: int,
    bad_count: int,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport] = None,
    scan_window: int = 16,
) -> Optional[Dict[str, Any]]:
    """Sliding recovery enhanced validation (Phase 75: dynamic window).

    Scan error_pos +/- scan_window for a valid i32 count (0..20).

    scan_window adjusts dynamically based on bad_count size:
    - bad_count <= 20: base window 16 bytes
    - bad_count <= 100: window 32 bytes
    - bad_count > 100: window 64 bytes

    Improvements:
    - count=0 alone cannot be a success condition; must verify subsequent structure is reasonable
    - count>0 must validate all or at least the first two PinReferences
    - Successful recovery returns structured result: {count, candidate_pos, confidence, reason}

    Returns:
        None: recovery failed
        Dict: {
            "count": int,
            "candidate_pos": int,
            "confidence": "high"/"medium"/"low",
            "reason": str,
        }
    """
    import struct

    # Phase 75: dynamically adjust scan_window
    if bad_count > 100:
        scan_window = max(scan_window, 64)
    elif bad_count > 20:
        scan_window = max(scan_window, 32)

    current_pos = archive.tell()
    search_start = max(0, error_pos - scan_window)
    # Safely get archive size: prefer public API total_size(),
    # fall back to _file_size attribute for mock archive compatibility in tests
    try:
        archive_size = archive.total_size()
        if not isinstance(archive_size, int):
            raise TypeError("total_size() did not return int")
    except (AttributeError, TypeError):
        archive_size = getattr(archive, "_file_size", 0)
    search_end = min(archive_size, error_pos + scan_window)

    archive.seek(search_start)
    window = archive.read(search_end - search_start)

    best_candidate = None
    best_confidence = "low"
    best_reason = ""

    for offset in range(0, len(window) - 4, 1):
        candidate_bytes = window[offset : offset + 4]
        candidate = struct.unpack("<i", candidate_bytes)[0]
        if candidate < 0 or candidate > 20:
            continue  # Out of reasonable range

        candidate_pos = search_start + offset
        after_count = offset + 4

        # count=0 requires additional verification of subsequent structure
        if candidate == 0:
            # count=0 should be followed by a SubPins array or other reasonable structure
            # Check if another small integer count (0..20) follows immediately
            if after_count + 4 <= len(window):
                next_val = struct.unpack("<i", window[after_count : after_count + 4])[0]
                if 0 <= next_val <= 20:
                    # Another array count follows, matches SubPins structure
                    best_candidate = (candidate_pos, candidate)
                    best_confidence = "medium"
                    best_reason = "count=0 followed by valid SubPins count"
                    # Don't break, continue searching for higher confidence candidates
                    continue
            # count=0 but subsequent structure unknown, low confidence (fallback only)
            if best_candidate is None:
                best_candidate = (candidate_pos, candidate)
                best_confidence = "low"
                best_reason = "count=0 without verified subsequent structure"
            continue

        # count > 0: validate PinReference structure
        if after_count + 24 > len(window):
            continue  # Insufficient space

        # Validate first PinReference
        pin_ref_1 = validate_pin_reference_at(archive, candidate_pos + 4, export_map, import_map)
        if pin_ref_1 is None or not pin_ref_1["valid"]:
            continue

        # Validate second PinReference (if count >= 2)
        if candidate >= 2 and after_count + 48 <= len(window):
            pin_ref_2 = validate_pin_reference_at(archive, candidate_pos + 4 + 24, export_map, import_map)
            if pin_ref_2 is None or not pin_ref_2["valid"]:
                # Second ref invalid, medium confidence
                best_candidate = (candidate_pos, candidate)
                best_confidence = "medium"
                best_reason = f"count={candidate}, ref1 valid but ref2 invalid"
                continue

        # All validations passed, high confidence
        best_candidate = (candidate_pos, candidate)
        best_confidence = "high"
        best_reason = f"count={candidate}, all refs validated"
        break  # Found high-confidence candidate, stop search

    if best_candidate is not None:
        candidate_pos, recovered_count = best_candidate
        logger.debug(
            "[P73-RECOVERY] LinkedTo: count=%d at pos %d (confidence=%s, scan=%d bytes, bad_count=%d, reason=%s)",
            recovered_count,
            candidate_pos,
            best_confidence,
            scan_window,
            bad_count,
            best_reason,
        )
        # Seek to just after the valid count (start of first pin ref)
        archive.seek(candidate_pos + 4)
        return {
            "count": recovered_count,
            "candidate_pos": candidate_pos,
            "confidence": best_confidence,
            "reason": best_reason,
        }

    # Recovery failed: seek back to original error position
    archive.seek(current_pos)
    return None


def _try_recover_to_subpins(
    archive: FArchive,
    error_pos: int,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport] = None,
    max_scan: int = 256,
) -> Optional[Dict[str, Any]]:
    """Recover to SubPins after LinkedTo failure.

    Scan strategy: search for a reasonable small integer (0..20) in the range
    error_pos to error_pos + max_scan, then verify the data after that position
    matches pin reference header structure.

    Improvements:
    - Use validate_pin_reference_at() for structural validation
    - Distinguish linkedto_recovered (valid Pin array found) from subpins_resync (jump to next structure)
    - Return structured recovery result

    Returns:
        None: recovery failed
        Dict: {
            "recovered_pos": int,
            "count": int,
            "recovery_type": "linkedto_recovered" / "subpins_resync",
            "reason": str,
        }
    """
    import struct

    scan_start = archive.tell()
    # Safely get archive size: prefer public API total_size(),
    # fall back to _file_size attribute for mock archive compatibility in tests
    try:
        archive_size = archive.total_size()
        if not isinstance(archive_size, int):
            raise TypeError("total_size() did not return int")
    except (AttributeError, TypeError):
        archive_size = getattr(archive, "_file_size", 0)
    scan_end = min(archive_size, scan_start + max_scan)
    archive.seek(scan_start)
    window = archive.read(scan_end - scan_start)

    for offset in range(0, len(window) - 4, 1):
        candidate = struct.unpack("<i", window[offset : offset + 4])[0]
        if candidate < 0 or candidate > 20:
            continue

        candidate_pos = scan_start + offset
        after = offset + 4

        # Validate using validate_pin_reference_at
        if candidate > 0 and after + 24 <= len(window):
            pin_ref_result = validate_pin_reference_at(archive, candidate_pos + 4, export_map, import_map)
            if pin_ref_result is not None and pin_ref_result["valid"]:
                recovered_pos = candidate_pos
                archive.seek(recovered_pos)
                # Converged: this path is only for SubPins resync, no longer marked as linkedto_recovered
                recovery_type = "subpins_resync"
                logger.debug(
                    "[P73-SUBPINS] Recovery at pos %d (count=%d, type=%s, reason=%s)",
                    recovered_pos,
                    candidate,
                    recovery_type,
                    pin_ref_result["reason"],
                )
                _record_pin_recovery(
                    {
                        "kind": "subpins_resync",
                        "recovered_pos": recovered_pos,
                        "count": candidate,
                        "recovery_type": recovery_type,
                        "reason": pin_ref_result["reason"],
                    }
                )
                return {
                    "recovered_pos": recovered_pos,
                    "count": candidate,
                    "recovery_type": recovery_type,
                    "reason": pin_ref_result["reason"],
                }

        # count=0 or b_null!=0 case: check if empty array or null ref
        if after + 4 <= len(window):
            b_null = struct.unpack("<i", window[after : after + 4])[0]
            if b_null != 0:
                # b_null!=0: null reference, valid
                recovered_pos = candidate_pos
                archive.seek(recovered_pos)
                logger.debug(
                    "[P73-SUBPINS] Recovery to SubPins at pos %d (count=%d, null ref)",
                    recovered_pos,
                    candidate,
                )
                _record_pin_recovery(
                    {
                        "kind": "subpins_resync",
                        "recovered_pos": recovered_pos,
                        "count": candidate,
                        "recovery_type": "subpins_resync",
                        "reason": "b_null!=0 null reference",
                    }
                )
                return {
                    "recovered_pos": recovered_pos,
                    "count": candidate,
                    "recovery_type": "subpins_resync",  # Jump to next structure
                    "reason": "b_null!=0 null reference",
                }

    # Recovery failed, stay at current position
    logger.debug(
        "[P73-SUBPINS] Could not find valid structure within %d bytes from pos %d",
        max_scan,
        error_pos,
    )
    return None


# ============================================================================


def _read_pin_fstring_field(
    archive: FArchive,
    field_name: str,
    trace_mode: bool,
    trace_fields: Dict[str, Any],
    pin_name: str = "",
    max_length: int = 4096,
) -> str:
    """Read Pin FString field (DefaultValue / AutogeneratedDefaultValue / PinToolTip)."""
    from uasset_read.archive import _contains_binary_data

    _field_start = archive.tell()
    try:
        value = _read_fstring_safe(archive, max_length=max_length)
        if _contains_binary_data(value):
            logger.debug(
                "Binary %s at pos %d for pin '%s' — returning empty", field_name, archive.tell() - len(value), pin_name
            )
            if trace_mode:
                _trace_fields_append(trace_fields, field_name, _field_start, archive.tell(), "[BINARY]")
            return ""
        if trace_mode:
            _trace_fields_append(
                trace_fields, field_name, _field_start, archive.tell(), value[:30] if value else "[empty]"
            )
        return value
    except (struct.error, OSError, ValueError):
        if trace_mode:
            _trace_fields_append(trace_fields, field_name, _field_start, archive.tell(), "", is_exception=True)
        return ""


def _read_pin_ftext_field(
    archive: FArchive,
    field_name: str,
    trace_mode: bool,
    trace_fields: Dict[str, Any],
) -> tuple:
    """Read Pin FText field (PinFriendlyName / DefaultTextValue)."""
    _start = archive.tell()
    try:
        value, flags, history_type, _ = _read_ftext_value(archive, tolerant=True)
        consumed = archive.tell() - _start
        if consumed > MAX_FTEXT_CONSUMPTION:
            logger.debug(
                "[FTEXT-SAFETY] %s consumed %d bytes (> %d), possible corruption, recovering from field start %d",
                field_name,
                consumed,
                MAX_FTEXT_CONSUMPTION,
                _start,
            )
            archive._record_diagnostic(
                module="graph_pin",
                field="FTEXT-SAFETY",
                source=field_name,
                target_offset=_start,
                read_size=consumed,
                file_size=archive.total_size(),
                error=f"FText consumed {consumed} bytes, exceeding limit {MAX_FTEXT_CONSUMPTION}",
            )
            archive.seek(_start)  # Seek back to field start, not _start + 5
            value = None
        if trace_mode:
            _trace_fields_append(
                trace_fields, field_name, _start, archive.tell(), f"flags={flags},htype={history_type}"
            )
        return value, True
    except (struct.error, OSError, ValueError):
        archive.seek(_start)  # On exception, also seek back to start position
        if trace_mode:
            _trace_fields_append(
                trace_fields, field_name, _start, archive.tell(), "", is_exception=True, is_fallback=True
            )
        return None, False


def _read_pin_linkedto(
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    linker: Optional["PackageLinker"],
    trace_mode: bool,
    trace_fields: Dict[str, Any],
    pin_name: str,
) -> list:
    """Read Pin LinkedTo array."""
    linkedto_start = archive.tell()
    linkedto_raw_count: Optional[int] = None
    try:
        _count_pos = archive.tell()
        linkedto_raw_count = archive.read_i32()
        archive.seek(_count_pos)
    except (struct.error, OSError):
        linkedto_raw_count = None
    try:
        linked_to = read_pin_array(archive, name_map, export_map, import_map, linker)
        logger.debug("LinkedTo: %d refs at pos %d", len(linked_to), linkedto_start)
        if trace_mode:
            refs_preview = [ref.get("owning_node", "?") for ref in linked_to[:2]]
            _trace_fields_append(
                trace_fields,
                "LinkedTo",
                linkedto_start,
                archive.tell(),
                f"raw_count={linkedto_raw_count},count={len(linked_to)},refs={refs_preview}",
            )
    except (struct.error, OSError, ValueError) as e:
        failure_key = (linkedto_start, type(e).__name__, pin_name)
        tl = _get_thread_local()
        if failure_key not in tl.linkedto_failure_seen:
            tl.linkedto_failure_seen.add(failure_key)
            logger.error("LinkedTo read failed at pos %d (pin=%s): %s", linkedto_start, pin_name, e)
        else:
            logger.debug("LinkedTo read failed (deduped) at pos %d (pin=%s): %s", linkedto_start, pin_name, e)
        if trace_mode:
            _trace_fields_append(trace_fields, "LinkedTo", linkedto_start, archive.tell(), "", is_exception=True)
        linked_to = []
        recovery_result = _try_recover_to_subpins(archive, linkedto_start, export_map, import_map)
        if recovery_result is not None:
            logger.info(
                "[P73-RECOVERY] SubPins resynced: pos=%d, type=%s",
                recovery_result.get("recovered_pos"),
                recovery_result.get("recovery_type"),
            )
    return linked_to


def _read_pin_subpins(
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    linker: Optional["PackageLinker"],
    trace_mode: bool,
    trace_fields: Dict[str, Any],
) -> list:
    """Read Pin SubPins array."""
    subpins_start = archive.tell()
    subpins_raw_count: Optional[int] = None
    try:
        _count_pos = archive.tell()
        subpins_raw_count = archive.read_i32()
        archive.seek(_count_pos)
    except (struct.error, OSError):
        subpins_raw_count = None
    try:
        sub_pins = read_pin_array(archive, name_map, export_map, import_map, linker)
        if trace_mode:
            _trace_fields_append(
                trace_fields,
                "SubPins",
                subpins_start,
                archive.tell(),
                f"raw_count={subpins_raw_count},count={len(sub_pins)}",
            )
    except (struct.error, OSError, ValueError):
        sub_pins = []
        if trace_mode:
            _trace_fields_append(
                trace_fields,
                "SubPins",
                subpins_start,
                archive.tell(),
                f"raw_count={subpins_raw_count}",
                is_exception=True,
            )
    return sub_pins


def _read_pin_bitfield(
    archive: FArchive,
    trace_mode: bool,
    trace_fields: Dict[str, Any],
) -> tuple:
    """Read Pin BitField (EditorOnly). Returns (hidden, not_connectable, advanced_view, orphaned_pin)."""
    hidden = False
    not_connectable = False
    advanced_view = False
    orphaned_pin = False
    try:
        bitfield_start = archive.tell()
        bitfield = archive.read_u32()
        hidden = bool(bitfield & (1 << 0))
        not_connectable = bool(bitfield & (1 << 1))
        advanced_view = bool(bitfield & (1 << 4))
        orphaned_pin = bool(bitfield & (1 << 5))
        if trace_mode:
            _trace_fields_append(trace_fields, "BitField", bitfield_start, archive.tell(), str(bitfield))
    except (struct.error, OSError, ValueError, AttributeError) as e:
        logger.debug("Failed to read Pin BitField: %s", e, exc_info=True)
    return hidden, not_connectable, advanced_view, orphaned_pin


def read_ue_graph_pin(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    linker: Optional["PackageLinker"] = None,
    header_owning_node: Optional[int] = None,
    header_pin_id: Optional[str] = None,
    trace_mode: bool = False,  # Field-level diagnostic switch
) -> UEdGraphPin:
    """Read UEdGraphPin full serialization format (UE5.7 specific).

    D-12: UE5 Pin array uses PinReference format with external header:
      - Header: b_null_ptr + owning_node + pin_guid (read by caller)
      - Body: Complete UEdGraphPin (duplicates owning_node + pin_guid + PinName + ...)

    If header_owning_node and header_pin_id provided, skip internal duplicates and use provided values.

    When trace_mode=True, outputs field-level diagnostic logs [P73-PINTRACE].
    """
    trace_mode = _pin_trace_enabled(trace_mode)

    # Diagnostic records
    _trace_fields: Dict[str, Any] = {}

    # 1. OwningNode - D-12: If header provided, read and discard internal duplicate to advance position
    _field_start = archive.tell()
    if header_owning_node is not None:
        archive.read_i32("Pin.OwningNode.Duplicate")  # Discard internal duplicate
        owning_node_index = header_owning_node
    else:
        owning_node_index = archive.read_i32("Pin.OwningNode")
    if trace_mode:
        _trace_fields_append(_trace_fields, "OwningNode", _field_start, archive.tell(), str(owning_node_index))

    # 2. PinId (FGuid 16 bytes) - D-12: If header provided, read and discard internal duplicate
    _field_start = archive.tell()
    if header_pin_id is not None:
        archive.read_bytes(16, "Pin.PinId.Duplicate")  # Discard internal duplicate
        pin_id = header_pin_id
    else:
        pin_id_bytes = archive.read_bytes(16, "Pin.PinId")
        pin_id = pin_id_bytes.hex()
    if trace_mode:
        _trace_fields_append(_trace_fields, "PinId", _field_start, archive.tell(), pin_id[:16] + "...")

    # 3. PinName
    pin_start_pos = archive.tell()
    if trace_mode:
        _trace_fields["pin_start_pos"] = pin_start_pos

    _field_start = archive.tell()
    pin_name = archive.read_name(name_map)
    if trace_mode:
        _trace_fields_append(_trace_fields, "PinName", _field_start, archive.tell(), pin_name)

    # 4. PinFriendlyName (FText)
    pin_friendly_name, _ = _read_pin_ftext_field(archive, "PinFriendlyName", trace_mode, _trace_fields)

    # 5. SourceIndex (UE5 always present)
    _field_start = archive.tell()
    source_index = archive.read_i32("Pin.SourceIndex")
    if trace_mode:
        _trace_fields_append(_trace_fields, "SourceIndex", _field_start, archive.tell(), str(source_index))

    # 6. PinToolTip — FString (NOT FText!)
    pin_tooltip = _read_pin_fstring_field(archive, "PinToolTip", trace_mode, _trace_fields, pin_name)

    # 7. Direction — u8 for both UE4 and UE5
    _field_start = archive.tell()
    direction = archive.read_u8("Pin.Direction")
    if trace_mode:
        _trace_fields_append(_trace_fields, "Direction", _field_start, archive.tell(), str(direction))

    # 8. PinType
    _field_start = archive.tell()
    pin_type = read_ed_graph_pin_type(archive, name_map, summary, import_map, export_map, linker)
    if trace_mode:
        _trace_fields_append(_trace_fields, "PinType", _field_start, archive.tell(), "[PinType struct]")

    # 9-10. DefaultValue strings (tolerant)
    default_value = _read_pin_fstring_field(archive, "DefaultValue", trace_mode, _trace_fields)
    autogenerated_default_value = _read_pin_fstring_field(
        archive, "AutogeneratedDefaultValue", trace_mode, _trace_fields
    )

    # 11. DefaultObject (FPackageIndex)
    _field_start = archive.tell()
    default_object = archive.read_i32("Pin.DefaultObject")
    if trace_mode:
        _trace_fields_append(_trace_fields, "DefaultObject", _field_start, archive.tell(), str(default_object))

    # 12. DefaultTextValue (FText)
    default_text_value, _ = _read_pin_ftext_field(archive, "DefaultTextValue", trace_mode, _trace_fields)

    # 13. LinkedTo array
    linked_to = _read_pin_linkedto(
        archive, name_map, export_map, import_map, linker, trace_mode, _trace_fields, pin_name
    )

    # 14. SubPins array
    sub_pins = _read_pin_subpins(archive, name_map, export_map, import_map, linker, trace_mode, _trace_fields)

    # 15. ParentPin — reuse read_pin_reference() (UE5: null → 4B, non-null → 24B)
    parent_start = archive.tell()
    _pp_ref = read_pin_reference(archive, name_map, export_map, import_map, linker)
    parent_pin = _pp_ref
    if trace_mode:
        _trace_fields_append(
            _trace_fields,
            "ParentPin",
            parent_start,
            archive.tell(),
            f"null={1 if _pp_ref is None else 0},owning={_pp_ref.get('owning_node') if _pp_ref else 'N/A'}",
        )

    # 16. ReferencePassThroughConnection — reuse read_pin_reference()
    ref_start = archive.tell()
    _ref_ref = read_pin_reference(archive, name_map, export_map, import_map, linker)
    ref_pass_through = _ref_ref
    if trace_mode:
        _trace_fields_append(
            _trace_fields,
            "ReferencePassThroughConnection",
            ref_start,
            archive.tell(),
            f"null={1 if _ref_ref is None else 0},owning={_ref_ref.get('owning_node') if _ref_ref else 'N/A'}",
        )

    # 17. PersistentGuid (EditorOnly)
    persistent_start = archive.tell()
    try:
        persistent_guid = _read_guid(archive)
    except (struct.error, OSError, ParseError):
        persistent_guid = None
    if trace_mode:
        _trace_fields_append(_trace_fields, "PersistentGuid", persistent_start, archive.tell(), persistent_guid or "")

    # 18. BitField (EditorOnly) — uint32 in both UE4 and UE5 (EdGraphPin.cpp L1902)
    hidden, not_connectable, advanced_view, orphaned_pin = _read_pin_bitfield(archive, trace_mode, _trace_fields)

    default_object_ref = None
    if linker is not None and default_object not in (None, 0):
        try:
            default_object_ref = linker.resolve_package_index(PackageIndex(default_object))
        except (KeyError, IndexError, AttributeError):
            default_object_ref = None

    # Extract object references from raw dicts
    linked_to_objects = [pin.get("owning_node_object") for pin in linked_to]
    sub_pins_objects = [pin.get("owning_node_object") for pin in sub_pins]
    parent_pin_object = parent_pin.get("owning_node_object") if parent_pin else None
    ref_pass_through_object = ref_pass_through.get("owning_node_object") if ref_pass_through else None

    # Diagnostic log output
    if trace_mode:
        # Find the first potentially misaligned field
        first_misaligned = ""
        for f in _trace_fields.get("fields", []):
            if f.get("exception") and not f.get("fallback"):
                first_misaligned = f["name"]
                break
            if "[BINARY]" in str(f.get("value", "")):
                first_misaligned = f["name"]
                break

        logger.info(
            "[P73-PINTRACE] Pin '%s' at pos %d: fields=%d, linkedto=%d, first_misaligned='%s'",
            pin_name,
            pin_start_pos,
            len(_trace_fields.get("fields", [])),
            len(linked_to),
            first_misaligned,
        )
        _get_thread_local().pin_trace_events.append(
            {
                "pin_name": pin_name,
                "pin_id": pin_id,
                "pin_start_pos": pin_start_pos,
                "linkedto_raw_count": None,
                "linkedto_count": len(linked_to),
                "subpins_raw_count": None,
                "subpins_count": len(sub_pins),
                "first_misaligned": first_misaligned,
                "fields": [dict(item) for item in _trace_fields.get("fields", [])],
            }
        )
        if first_misaligned:
            logger.debug("[P73-PINTRACE] Fields detail: %s", json.dumps(_trace_fields.get("fields", [])))

    return UEdGraphPin(
        pin_id=pin_id,
        pin_name=pin_name,
        pin_friendly_name=pin_friendly_name,
        pin_tooltip=pin_tooltip,
        direction=direction,
        pin_type=pin_type,
        default_value=default_value,
        auto_default_value=autogenerated_default_value,
        default_object=default_object,
        default_object_ref=default_object_ref,
        default_text_value=default_text_value,
        linked_to_raw=linked_to,
        sub_pins=sub_pins,
        parent_pin=parent_pin,
        ref_pass_through=ref_pass_through,
        linked_to_objects=linked_to_objects,
        sub_pins_objects=sub_pins_objects,
        parent_pin_object=parent_pin_object,
        ref_pass_through_object=ref_pass_through_object,
        owning_node_index=owning_node_index,
        source_index=source_index,
        persistent_guid=persistent_guid,
        hidden=hidden,
        not_connectable=not_connectable,
        advanced_view=advanced_view,
        orphaned_pin=orphaned_pin,
    )
