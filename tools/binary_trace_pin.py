"""
Binary trace tool for pin body field-level position verification.

Usage:
    python tools/binary_trace_pin.py --asset <path> --node-export-idx <index> --pin-index <index>

Purpose:
    After applying bool serialization fixes (35b-01, 35b-02, 35b-03), this tool
    verifies that pin body fields are read at correct positions. It traces each
    field's archive position before/after reading and reports byte consumption.

Output:
    Table showing each field: name, before/after positions, bytes consumed,
    expected bytes, delta (drift detection), and value.

Critical field:
    LinkedTo array_count — should show > 0 after fixes applied.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uasset_read.archive import FArchive
from uasset_read.serializers.package_summary import read_package_summary, read_name_table, PackageFileSummary
from uasset_read.serializers.object_resources import read_import_map, read_export_map, ObjectExport, ObjectImport
from uasset_read.constants import (
    FFRAMEWORK_OBJECT_VERSION_GUID, FUE5_MAINSTREAM_VERSION_GUID, FRELEASE_OBJECT_VERSION_GUID,
    FFRAMEWORK_VERSION_PINS_STORE_FNAME, FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE,
    FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX, FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER,
)
from uasset_read.serializers.graph import read_ftext_with_history


def trace_field(archive: FArchive, name: str, expected: int, read_func: callable) -> Dict[str, Any]:
    """Trace a single field read, recording position and consumption.

    Args:
        archive: FArchive instance
        name: Field name
        expected: Expected bytes consumed
        read_func: Function to read the field (returns value)

    Returns:
        Dict with field name, positions, consumption, and value
    """
    before = archive.tell()
    try:
        value = read_func()
        after = archive.tell()
        consumed = after - before
        delta = consumed - expected
        success = True
    except Exception as e:
        after = archive.tell()
        consumed = after - before
        delta = consumed - expected
        value = f"ERROR: {e}"
        success = False

    return {
        "field": name,
        "before": before,
        "after": after,
        "consumed": consumed,
        "expected": expected,
        "delta": delta,
        "value": value,
        "success": success,
    }


def trace_fname(archive: FArchive, name_map: List[str]) -> Dict[str, Any]:
    """Trace FName (8 bytes: u32 index + u32 number)."""
    return trace_field(archive, "PinName (FName)", 8, lambda: archive.read_name(name_map))


def trace_ftext_flags(archive: FArchive) -> Dict[str, Any]:
    """Trace FText flags field (i32, 4 bytes)."""
    return trace_field(archive, "FText.flags", 4, lambda: archive.read_i32())


def trace_ftext_history_type(archive: FArchive) -> Dict[str, Any]:
    """Trace FText history_type (u8, 1 byte for UE5)."""
    return trace_field(archive, "FText.history_type", 1, lambda: archive.read_u8())


def trace_ftext_body(archive: FArchive, history_type: int, tolerant: bool = True) -> List[Dict[str, Any]]:
    """Trace FText body based on history_type.

    history_type values:
    - 0xFF (255): None — optional b_has_culture (u8/bool) + culture FString
    - 0: Base — 3 FString (namespace, key, source_string)
    - 1-254: Custom — up to 5 FString

    Returns list of traced fields.
    """
    traces = []

    if history_type == 0xFF:  # None type
        # b_has_culture (UE5: u8, UE4: u32)
        before = archive.tell()
        try:
            b_has_culture = archive.read_u8()
            after = archive.tell()
            traces.append({
                "field": "FText.b_has_culture",
                "before": before,
                "after": after,
                "consumed": after - before,
                "expected": 1,
                "delta": after - before - 1,
                "value": b_has_culture,
                "success": True,
            })
            if b_has_culture:
                # Read culture FString
                traces.append(trace_field(archive, "FText.culture", "variable", lambda: archive.read_fstring()))
        except Exception as e:
            traces.append({
                "field": "FText.b_has_culture",
                "before": before,
                "after": archive.tell(),
                "consumed": archive.tell() - before,
                "expected": 1,
                "delta": archive.tell() - before - 1,
                "value": f"ERROR: {e}",
                "success": False,
            })

    elif history_type == 0:  # Base type
        # 3 FString fields
        traces.append(trace_field(archive, "FText.namespace", "variable", lambda: archive.read_fstring()))
        traces.append(trace_field(archive, "FText.key", "variable", lambda: archive.read_fstring()))
        traces.append(trace_field(archive, "FText.source_string", "variable", lambda: archive.read_fstring()))

    else:  # Custom type (1-254)
        # Up to 5 FString fields
        for i in range(5):
            field_name = f"FText.custom[{i}]"
            traces.append(trace_field(archive, field_name, "variable", lambda: archive.read_fstring()))

    return traces


def trace_source_index(archive: FArchive, summary: PackageFileSummary) -> Dict[str, Any]:
    """Trace SourceIndex field (i32, 4 bytes)."""
    return trace_field(archive, "SourceIndex", 4, lambda: archive.read_i32())


def trace_pin_tooltip(archive: FArchive, summary: PackageFileSummary) -> Dict[str, Any]:
    """Trace PinToolTip (FString).

    UE5: length=-1 means empty with no data bytes.
    """
    if summary.file_version_ue5 > 0:
        # UE5 format: read length first, then data if applicable
        before = archive.tell()
        length = archive.read_i32()
        after_len = archive.tell()

        if length == -1:
            # Empty tooltip, no data bytes
            return {
                "field": "PinToolTip",
                "before": before,
                "after": after_len,
                "consumed": 4,
                "expected": 4,
                "delta": 0,
                "value": "(empty, len=-1)",
                "success": True,
            }
        elif length == 0:
            return {
                "field": "PinToolTip",
                "before": before,
                "after": after_len,
                "consumed": 4,
                "expected": 4,
                "delta": 0,
                "value": "(empty, len=0)",
                "success": True,
            }
        elif length < 0:
            # UTF-16 encoding
            data = archive.read(-length * 2)
            value = data.decode('utf-16', errors='replace').rstrip('\x00')
            after = archive.tell()
            consumed = after - before
            return {
                "field": "PinToolTip",
                "before": before,
                "after": after,
                "consumed": consumed,
                "expected": "variable",
                "delta": "N/A",
                "value": value,
                "success": True,
            }
        else:
            # UTF-8 encoding
            data = archive.read(length)
            value = data.decode('utf-8', errors='replace').rstrip('\x00')
            after = archive.tell()
            consumed = after - before
            return {
                "field": "PinToolTip",
                "before": before,
                "after": after,
                "consumed": consumed,
                "expected": "variable",
                "delta": "N/A",
                "value": value,
                "success": True,
            }
    else:
        # UE4 format: standard FString
        return trace_field(archive, "PinToolTip", "variable", lambda: archive.read_fstring())


def trace_direction(archive: FArchive) -> Dict[str, Any]:
    """Trace Direction (u8, 1 byte)."""
    return trace_field(archive, "Direction", 1, lambda: archive.read_u8())


def trace_pin_type(archive: FArchive, name_map: List[str], summary: PackageFileSummary) -> List[Dict[str, Any]]:
    """Trace FEdGraphPinType fields.

    UE5 default reflection serialization:
    - PinCategory (FName, 8 bytes)
    - PinSubCategory (FName, 8 bytes)
    - PinSubCategoryObject (i32, 4 bytes)
    - MemberReference (i32 + FName + 16B = 28 bytes)
    - TerminalType (FName + FName + i32 = 20 bytes)
    - ContainerType (u8, 1 byte)
    - Flags byte (u8, 1 byte) containing bIsReference, bIsConst, bIsWeakPointer, bIsUObjectWrapper

    UE4 custom serialization (>= 324):
    - PinCategory/PinSubCategory (FName or FString depending on version)
    - PinSubCategoryObject (i32)
    - ContainerType (u8) or legacy bools (bIsMap, bIsSet, bIsArray)
    - bIsReference (bool: UE5=u8, UE4=u32)
    - bIsWeakPointer (bool: UE5=u8, UE4=u32)
    - MemberReference (version dependent)
    - bIsConst (bool, version dependent)
    - bIsUObjectWrapper (bool, version dependent)

    Returns list of traced fields.
    """
    traces = []

    framework_version = summary.get_custom_version(FFRAMEWORK_OBJECT_VERSION_GUID, 0)
    ue4_version = summary.file_version_ue4

    VER_UE4_EDGRAPHPINTYPE_SERIALIZATION = 324
    use_custom_serialization = ue4_version >= VER_UE4_EDGRAPHPINTYPE_SERIALIZATION

    if not use_custom_serialization:
        # UE5 default reflection serialization
        traces.append(trace_field(archive, "PinType.PinCategory", 8, lambda: archive.read_name(name_map)))
        traces.append(trace_field(archive, "PinType.PinSubCategory", 8, lambda: archive.read_name(name_map)))
        traces.append(trace_field(archive, "PinType.PinSubCategoryObject", 4, lambda: archive.read_i32()))

        # MemberReference (FSimpleMemberReference)
        traces.append(trace_field(archive, "PinType.MemberParent", 4, lambda: archive.read_i32()))
        traces.append(trace_field(archive, "PinType.MemberName", 8, lambda: archive.read_name(name_map)))
        traces.append(trace_field(archive, "PinType.MemberGuid", 16, lambda: archive.read_bytes(16).hex()))

        # Terminal type
        traces.append(trace_field(archive, "PinType.TerminalCategory", 8, lambda: archive.read_name(name_map)))
        traces.append(trace_field(archive, "PinType.TerminalSubCategory", 8, lambda: archive.read_name(name_map)))
        traces.append(trace_field(archive, "PinType.TerminalSubCategoryObject", 4, lambda: archive.read_i32()))

        # ContainerType
        traces.append(trace_field(archive, "PinType.ContainerType", 1, lambda: archive.read_u8()))

        # Flags byte
        before = archive.tell()
        flags_byte = archive.read_u8()
        after = archive.tell()
        traces.append({
            "field": "PinType.FlagsByte",
            "before": before,
            "after": after,
            "consumed": 1,
            "expected": 1,
            "delta": 0,
            "value": f"0x{flags_byte:02X} (ref={bool(flags_byte & 0x04)}, const={bool(flags_byte & 0x08)}, weak={bool(flags_byte & 0x10)}, uobj={bool(flags_byte & 0x20)})",
            "success": True,
        })

    else:
        # UE4 custom serialization
        use_fname_format = framework_version >= FFRAMEWORK_VERSION_PINS_STORE_FNAME or summary.file_version_ue5 > 0

        if use_fname_format:
            traces.append(trace_field(archive, "PinType.PinCategory", 8, lambda: archive.read_name(name_map)))
            traces.append(trace_field(archive, "PinType.PinSubCategory", 8, lambda: archive.read_name(name_map)))
        else:
            traces.append(trace_field(archive, "PinType.PinCategory", "variable", lambda: archive.read_fstring()))
            traces.append(trace_field(archive, "PinType.PinSubCategory", "variable", lambda: archive.read_fstring()))

        traces.append(trace_field(archive, "PinType.PinSubCategoryObject", 4, lambda: archive.read_i32()))

        # ContainerType (modern vs legacy)
        use_modern_container = framework_version >= FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE or summary.file_version_ue5 > 0
        if use_modern_container:
            traces.append(trace_field(archive, "PinType.ContainerType", 1, lambda: archive.read_u8()))
            # If Map (3), read terminal type
            # Note: we can't know if it's Map until we read the value, so trace as optional
        else:
            # Legacy bools: bIsMap, bIsSet, bIsArray (each 4 bytes for UE4)
            traces.append(trace_field(archive, "PinType.bIsMap", 4, lambda: archive.read_bool()))
            traces.append(trace_field(archive, "PinType.bIsSet", 4, lambda: archive.read_bool()))
            traces.append(trace_field(archive, "PinType.bIsArray", 4, lambda: archive.read_bool()))

        # bIsReference / bIsWeakPointer (UE5: u8, UE4: u32)
        if summary.file_version_ue5 > 0:
            traces.append(trace_field(archive, "PinType.bIsReference", 1, lambda: archive.read_u8()))
            traces.append(trace_field(archive, "PinType.bIsWeakPointer", 1, lambda: archive.read_u8()))
        else:
            traces.append(trace_field(archive, "PinType.bIsReference", 4, lambda: archive.read_bool()))
            traces.append(trace_field(archive, "PinType.bIsWeakPointer", 4, lambda: archive.read_bool()))

        # MemberReference (version dependent)
        VER_UE4_MEMBERREFERENCE_IN_PINTYPE = 382
        if ue4_version >= VER_UE4_MEMBERREFERENCE_IN_PINTYPE:
            traces.append(trace_field(archive, "PinType.MemberParent", 4, lambda: archive.read_i32()))
            traces.append(trace_field(archive, "PinType.MemberName", 8, lambda: archive.read_name(name_map)))
            traces.append(trace_field(archive, "PinType.MemberGuid", 16, lambda: archive.read_bytes(16).hex()))

        # bIsConst (version dependent)
        VER_UE4_SERIALIZE_PINTYPE_CONST = 366
        if ue4_version >= VER_UE4_SERIALIZE_PINTYPE_CONST:
            if summary.file_version_ue5 > 0:
                traces.append(trace_field(archive, "PinType.bIsConst", 1, lambda: archive.read_u8()))
            else:
                traces.append(trace_field(archive, "PinType.bIsConst", 4, lambda: archive.read_bool()))

        # bIsUObjectWrapper (version dependent, +1 Byte Abweichung Quelle D1)
        # C++: if Ar.CustomVer(FReleaseObjectVersion::GUID) >= PinTypeIncludesUObjectWrapperFlag
        # Fallback: ue5_version > 0 bedeutet immer ReleaseObjectVersion >= 10
        release_version = summary.get_custom_version(FRELEASE_OBJECT_VERSION_GUID, 0)
        if release_version >= FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER or summary.file_version_ue5 > 0:
            if summary.file_version_ue5 > 0:
                traces.append(trace_field(archive, "PinType.bIsUObjectWrapper", 1, lambda: archive.read_u8()))
            else:
                traces.append(trace_field(archive, "PinType.bIsUObjectWrapper", 4, lambda: archive.read_bool()))
        else:
            traces.append({
                "field": "PinType.bIsUObjectWrapper",
                "before": 0,
                "after": 0,
                "consumed": 0,
                "expected": 0,
                "delta": 0,
                "value": "SKIPPED (release_version=0, no ue5 fallback)",
                "success": True,
            })

        # bSerializeAsSinglePrecisionFloat (fehlendes Feld, +1 Byte Abweichung Quelle D2)
        # C++: WITH_EDITOR && FUE5ReleaseStreamObjectVersion >= SerializeFloatPinDefaultValuesAsSinglePrecision
        if summary.file_version_ue5 > 0:
            traces.append(trace_field(archive, "PinType.bSerializeAsSinglePrecisionFloat", 1, lambda: archive.read_u8()))

    return traces


def trace_fstring(archive: FArchive, name: str) -> Dict[str, Any]:
    """Trace a FString field."""
    return trace_field(archive, name, "variable", lambda: archive.read_fstring())


def trace_i32(archive: FArchive, name: str) -> Dict[str, Any]:
    """Trace an i32 field."""
    return trace_field(archive, name, 4, lambda: archive.read_i32())


def trace_linkedto_array(archive: FArchive, name_map: List[str], export_map: List[ObjectExport], import_map: List[ObjectImport]) -> List[Dict[str, Any]]:
    """Trace LinkedTo array (array_count + elements).

    CRITICAL: After fixes applied, array_count should be > 0.

    Returns list of traced fields.
    """
    traces = []

    # array_count (i32, 4 bytes)
    before = archive.tell()
    array_count = archive.read_i32()
    after = archive.tell()
    traces.append({
        "field": "LinkedTo.array_count",
        "before": before,
        "after": after,
        "consumed": 4,
        "expected": 4,
        "delta": 0,
        "value": array_count,
        "success": True,
    })

    # Each element: b_null (i32) + owning_node (i32) + guid (16 bytes) = 24 bytes
    for i in range(array_count):
        elem_name = f"LinkedTo[{i}]"
        before = archive.tell()
        b_null = archive.read_i32()
        owning_node = archive.read_i32()
        guid_bytes = archive.read_bytes(16)
        after = archive.tell()
        traces.append({
            "field": elem_name,
            "before": before,
            "after": after,
            "consumed": 24,
            "expected": 24,
            "delta": 0,
            "value": f"b_null={b_null}, owning={owning_node}, guid={guid_bytes.hex()[:8]}...",
            "success": True,
        })

    return traces


def trace_pin_body(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport]
) -> List[Dict[str, Any]]:
    """Trace entire pin body, field by field.

    Returns list of all traced fields.
    """
    traces = []

    framework_version = summary.get_custom_version(FFRAMEWORK_OBJECT_VERSION_GUID, 0)
    mainstream_version = summary.get_custom_version(FUE5_MAINSTREAM_VERSION_GUID, 0)
    use_fname_format = framework_version >= FFRAMEWORK_VERSION_PINS_STORE_FNAME or summary.file_version_ue5 > 0

    # 1. PinName (FName or FString depending on version)
    if use_fname_format:
        traces.append(trace_fname(archive, name_map))
    else:
        traces.append(trace_fstring(archive, "PinName"))

    # 2. PinFriendlyName (FText) — flags + history_type + body
    traces.append(trace_ftext_flags(archive))
    traces.append(trace_ftext_history_type(archive))

    # Get history_type value to determine body format
    history_type = traces[-1]["value"]
    traces.extend(trace_ftext_body(archive, history_type))

    # 3. SourceIndex (UE5 always serializes)
    if mainstream_version >= FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX or summary.file_version_ue5 > 0:
        traces.append(trace_source_index(archive, summary))

    # 4. PinToolTip
    traces.append(trace_pin_tooltip(archive, summary))

    # 5. Direction (u8)
    traces.append(trace_direction(archive))

    # 6. PinType (complex, many sub-fields)
    traces.extend(trace_pin_type(archive, name_map, summary))

    # 7. DefaultValue (FString)
    traces.append(trace_fstring(archive, "DefaultValue"))

    # 8. AutoDefaultValue (FString)
    traces.append(trace_fstring(archive, "AutoDefaultValue"))

    # 9. DefaultObject (i32)
    traces.append(trace_i32(archive, "DefaultObject"))

    # 10. DefaultTextValue (FText — NICHT FString!)
    # UE5 C++: Ar << DefaultTextValue; (EdGraphPin.cpp L1876)
    # FText: flags(i32,4B) + history_type(u8,1B) + body(variable)
    dtv_before = archive.tell()
    dtv_flags = archive.read_i32()
    dtv_after_flags = archive.tell()
    traces.append({
        "field": "DefaultTextValue.flags",
        "before": dtv_before,
        "after": dtv_after_flags,
        "consumed": 4,
        "expected": 4,
        "delta": 0,
        "value": f"0x{dtv_flags:08X}",
        "success": True,
    })
    dtv_ht_before = archive.tell()
    dtv_history_type = archive.read_u8()
    dtv_after_ht = archive.tell()
    traces.append({
        "field": "DefaultTextValue.history_type",
        "before": dtv_ht_before,
        "after": dtv_after_ht,
        "consumed": 1,
        "expected": 1,
        "delta": 0,
        "value": dtv_history_type,
        "success": True,
    })
    # FText body entsprechend history_type verfolgen
    body_before = archive.tell()
    try:
        dtv_value, dtv_consumed = read_ftext_with_history(
            archive, dtv_history_type,
            tolerant=True,
            ue5_mode=(summary.file_version_ue5 > 0)
        )
        body_after = archive.tell()
        traces.append({
            "field": "DefaultTextValue.body",
            "before": body_before,
            "after": body_after,
            "consumed": body_after - body_before,
            "expected": "variable",
            "delta": "N/A",
            "value": f"history_type={dtv_history_type}, consumed={body_after - body_before}",
            "success": True,
        })
    except Exception as e:
        traces.append({
            "field": "DefaultTextValue.body",
            "before": body_before,
            "after": archive.tell(),
            "consumed": archive.tell() - body_before,
            "expected": "variable",
            "delta": "N/A",
            "value": f"ERROR: {e}",
            "success": False,
        })

    # 11. LinkedTo array (CRITICAL)
    traces.extend(trace_linkedto_array(archive, name_map, export_map, import_map))

    return traces


def find_pin_offset(
    archive: FArchive,
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    node_export_idx: int,
    pin_index: int
) -> int:
    """Find the offset of a specific pin's body data.

    Args:
        archive: FArchive instance
        summary: PackageFileSummary
        export_map: Export map
        node_export_idx: Export index of the node (0-based)
        pin_index: Pin index within the node (0-based)

    Returns:
        Offset to the pin body (after header)
    """
    node_export = export_map[node_export_idx]

    # Node serial data starts at serial_offset
    # Pins array starts at: serial_offset + script_serial_offset + script_serial_size
    pins_offset = node_export.serial_offset + node_export.script_serial_offset + node_export.script_serial_size

    archive.seek(pins_offset)

    # Skip end marker (i32)
    archive.read_i32()

    # Read pins count
    pins_count = archive.read_i32()

    if pin_index >= pins_count:
        raise ValueError(f"Pin index {pin_index} out of range (node has {pins_count} pins)")

    # Iterate through pins to find the target
    for i in range(pins_count):
        # Read header: b_null (i32) + owning_node (i32) + guid (16 bytes) = 24 bytes
        header_start = archive.tell()
        b_null = archive.read_i32()
        owning_node = archive.read_i32()
        guid_bytes = archive.read_bytes(16)

        if i == pin_index:
            if b_null != 0:
                raise ValueError(f"Pin {pin_index} is a NULL reference (b_null={b_null})")
            # This is our target pin, body starts after header
            return archive.tell()
        else:
            # Skip this pin's body
            # Estimate ~180 bytes per pin body (exact size varies)
            # Better approach: read the pin body properly to advance
            if b_null == 0:
                # Non-null pin, estimate and skip
                # We don't know exact size, so we need to parse it
                # For now, seek forward by estimated size
                archive.seek(archive.tell() + 180)
            # Null pins have no body after header

    raise ValueError(f"Could not locate pin {pin_index}")


def print_trace_table(traces: List[Dict[str, Any]]):
    """Print trace results as a formatted table."""
    print("\n" + "=" * 100)
    print("PIN BODY FIELD TRACE")
    print("=" * 100)
    print(f"{'Field':<30} {'Before':>10} {'After':>10} {'Consumed':>10} {'Expected':>10} {'Delta':>8} {'Value':<20}")
    print("-" * 100)

    total_consumed = 0
    total_expected = 0
    drift_count = 0

    for t in traces:
        consumed_str = str(t["consumed"])
        expected_str = str(t["expected"]) if isinstance(t["expected"], int) else t["expected"]
        delta_str = str(t["delta"]) if isinstance(t["delta"], int) else t["delta"]

        # Highlight drift
        if isinstance(t["delta"], int) and t["delta"] != 0:
            delta_display = f"DRIFT({t['delta']})"
            drift_count += 1
        else:
            delta_display = delta_str

        # Truncate value for display
        value_str = str(t["value"])
        if len(value_str) > 20:
            value_str = value_str[:17] + "..."

        success_marker = "" if t["success"] else " [FAIL]"

        print(f"{t['field']:<30} {t['before']:>10} {t['after']:>10} {consumed_str:>10} {expected_str:>10} {delta_display:>8} {value_str:<20}{success_marker}")

        if isinstance(t["consumed"], int):
            total_consumed += t["consumed"]
        if isinstance(t["expected"], int):
            total_expected += t["expected"]

    print("-" * 100)
    print(f"{'TOTAL':<30} {'':<10} {'':<10} {total_consumed:>10} {total_expected:>10} {total_consumed - total_expected:>8}")
    print("=" * 100)

    # Summary
    linkedto_count = 0
    for t in traces:
        if t["field"] == "LinkedTo.array_count":
            linkedto_count = t["value"]
            break

    print("\nSUMMARY:")
    print(f"  Total bytes consumed: {total_consumed}")
    print(f"  Expected bytes (fixed): {total_expected}")
    print(f"  Drift (consumed - expected): {total_consumed - total_expected}")
    print(f"  Fields with drift: {drift_count}")
    print(f"  LinkedTo array_count: {linkedto_count}")

    if linkedto_count > 0:
        print(f"  STATUS: LinkedTo connections FOUND (array_count={linkedto_count})")
    else:
        print(f"  STATUS: LinkedTo connections EMPTY (array_count=0) — byte drift suspected")

    if drift_count > 0:
        print(f"  WARNING: {drift_count} fields show byte drift — review Expected column")
    else:
        print(f"  OK: All fields consumed expected bytes")


def main():
    parser = argparse.ArgumentParser(
        description="Binary trace tool for pin body field-level position verification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--asset", required=True,
        help="Path to .uasset file"
    )
    parser.add_argument(
        "--node-export-idx", type=int, required=True,
        help="Export index of the node (0-based)"
    )
    parser.add_argument(
        "--pin-index", type=int, required=True,
        help="Pin index within the node (0-based)"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show detailed output"
    )

    args = parser.parse_args()

    # Check file exists
    asset_path = Path(args.asset)
    if not asset_path.exists():
        print(f"Error: File not found: {args.asset}", file=sys.stderr)
        sys.exit(1)

    print(f"Asset: {args.asset}")
    print(f"Node export index: {args.node_export_idx}")
    print(f"Pin index: {args.pin_index}")

    # Parse asset
    archive = FArchive(str(asset_path), tolerant=True)

    try:
        summary = read_package_summary(archive)
        print(f"UE5 version: {summary.file_version_ue5}")
        print(f"UE4 version: {summary.file_version_ue4}")

        name_map = read_name_table(archive, summary)
        print(f"Name count: {len(name_map)}")

        archive.seek(summary.import_offset)
        import_map = read_import_map(archive, summary, name_map)
        print(f"Import count: {len(import_map)}")

        archive.seek(summary.export_offset)
        export_map = read_export_map(archive, summary, name_map)
        print(f"Export count: {len(export_map)}")

        if args.node_export_idx >= len(export_map):
            print(f"Error: Node export index {args.node_export_idx} out of range (max {len(export_map) - 1})", file=sys.stderr)
            sys.exit(1)

        node_export = export_map[args.node_export_idx]
        print(f"Node name: {node_export.object_name}")
        print(f"Node class: {node_export.class_index}")

        # Find pin offset
        pin_body_offset = find_pin_offset(archive, summary, export_map, args.node_export_idx, args.pin_index)
        print(f"\nPin body starts at offset: {pin_body_offset}")

        # Seek to pin body and trace
        archive.seek(pin_body_offset)

        traces = trace_pin_body(archive, name_map, summary, export_map, import_map)

        print_trace_table(traces)

    finally:
        archive.close()


if __name__ == "__main__":
    main()