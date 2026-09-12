"""Blueprint Pin binary serializer — FEdGraphPinType, UEdGraphPin read functions.

Split from serializers/graph.py, contains all Pin-related read logic.
"""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING

from uasset_read.parsers.errors import BINARY_READ_ERRORS

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport

from uasset_read.constants import (
    MAX_LINKEDTO_PER_PIN,
    MAX_FTEXT_CONSUMPTION,
)
from uasset_read.exceptions import ParseError
from uasset_read.versioning import RELEASE_GUID, get_custom_version
from uasset_read.models.core import UEdGraphPin, FEdGraphPinType

from uasset_read.serializers.graph_helpers import (
    _read_guid,
    _read_fstring_safe,
    _read_ftext_value,
    ftext_dev_notes_enabled,
    validate_pin_reference_at,
)

logger = logging.getLogger(__name__)


# ============================================================================
# FEdGraphPinType read functions
# ============================================================================


def read_ed_graph_pin_type(
    archive: FArchive,
    name_map: list[str],
    summary: PackageFileSummary | None = None,
    import_map: list[ObjectImport] | None = None,
    export_map: list[ObjectExport] | None = None,
) -> FEdGraphPinType:
    """Parse FEdGraphPinType (UE5.7 specific — custom serialization path).

    All archive.read_*() cursor steps are mandatory; only the retained fields
    are stored on the model (write-only category/object names stay cursor-only).
    """
    pin_type = FEdGraphPinType()

    # PinCategory / PinSubCategory (UE5 always uses FName format)
    pin_type.pin_category = archive.read_name(name_map)
    archive.read_name(name_map)  # PinSubCategory (write-only)

    # PinSubCategoryObject (FPackageIndex, write-only)
    archive.read_i32()

    # ContainerType (UE5 always uses modern uint8 format)
    pin_type.container_type = archive.read_u8()
    if pin_type.container_type == 3:  # Map
        # Map key terminal type (FEdGraphTerminalType serialization)
        # Reference: UE EdGraphPin.cpp:218 — Ar << PinValueType
        archive.read_name(name_map)  # map key terminal category (write-only)
        archive.read_name(name_map)  # map key terminal sub-category (write-only)
        archive.read_i32()  # map key terminal sub-category object (write-only)

        # FEdGraphTerminalType tail — EdGraphNode.cpp operator<<: two unconditional
        # 4-byte bools, then bTerminalIsUObjectWrapper gated on
        # FReleaseObjectVersion >= PinTypeIncludesUObjectWrapperFlag (=31).
        pin_type.map_key_terminal_is_const = archive.read_bool()
        pin_type.map_key_terminal_is_weak_pointer = archive.read_bool()
        if summary is not None and get_custom_version(summary, RELEASE_GUID) >= 31:
            pin_type.map_key_terminal_is_uobject_wrapper = archive.read_bool()
        else:
            pin_type.map_key_terminal_is_uobject_wrapper = False

    # bIsReference / bIsWeakPointer (UE5 FArchive bool = uint32, 4B)
    pin_type.is_reference = archive.read_bool()
    archive.read_bool()  # bIsWeakPointer (write-only)

    # FSimpleMemberReference (UE5 always present)
    archive.read_i32()
    archive.read_name(name_map)
    archive.read_bytes(16)

    # bIsConst / bIsUObjectWrapper / bSerializeAsSinglePrecisionFloat (write-only)
    archive.read_bool()
    archive.read_bool()
    archive.read_bool()

    return pin_type


# ============================================================================
# Pin reference helper functions
# ============================================================================


def read_pin_reference(archive: FArchive) -> dict | None:
    """Read a single Pin reference (FBlueprintEditorUtils::FPinReference)."""
    b_null_ptr = archive.read_i32()
    if b_null_ptr != 0:
        return None  # null marker consumed 4 bytes only, no more reading

    archive.read_i32()  # owning_node index (write-only; validation lives in validate_pin_reference_at)
    pin_guid_raw = _read_guid(archive)

    # Normalize to 32-char lowercase hex (remove dashes), matching pin_id format
    pin_guid = pin_guid_raw.replace("-", "").lower() if pin_guid_raw else pin_guid_raw
    return {"pin_guid": pin_guid}


def read_pin_array(
    archive: FArchive,
    export_map: list[ObjectExport],
    import_map: list[ObjectImport],
) -> list[dict]:
    """Read Pin reference array (SerializePinArray format).

    Corrupt or out-of-range counts fail closed with ParseError — no
    sliding-window salvage of a misaligned stream.
    """
    array_count = archive.read_i32()

    if array_count < 0:
        raise ParseError(f"Invalid pin array count: {array_count} (negative)")
    if array_count > MAX_LINKEDTO_PER_PIN:
        raise ParseError(f"Pin array count {array_count} exceeds MAX_LINKEDTO_PER_PIN {MAX_LINKEDTO_PER_PIN}")

    pins: list[dict] = []
    for _ in range(array_count):
        ref_pos = archive.tell()
        ref_validation = validate_pin_reference_at(archive, ref_pos, export_map, import_map)
        if ref_validation is None or not ref_validation[0]:
            reason = ref_validation[1] if ref_validation else "not enough bytes"
            raise ParseError(f"Invalid pin reference at pos {ref_pos}: {reason}")
        pin_ref = read_pin_reference(archive)
        if pin_ref is not None:
            pins.append(pin_ref)
    return pins


# ============================================================================


def _read_pin_fstring_field(
    archive: FArchive,
    field_name: str,
    pin_name: str = "",
) -> str:
    """Read Pin FString field (DefaultValue / AutogeneratedDefaultValue / PinToolTip)."""
    from uasset_read.archive import _contains_binary_data

    try:
        # 4096 is the pin-field ceiling; _read_fstring_safe's default is MAX_SAFE_COUNT.
        value = _read_fstring_safe(archive, max_length=4096)
        if _contains_binary_data(value):
            logger.debug(
                "Binary %s at pos %d for pin '%s' — returning empty", field_name, archive.tell() - len(value), pin_name
            )
            return ""
        return value
    except BINARY_READ_ERRORS:
        return ""


def _read_pin_ftext_field(
    archive: FArchive,
    field_name: str,
    dev_notes: bool = False,
) -> str | None:
    """Read Pin FText field (PinFriendlyName / DefaultTextValue)."""
    _start = archive.tell()
    try:
        value, flags, history_type, _ = _read_ftext_value(archive, tolerant=True, dev_notes=dev_notes)
        consumed = archive.tell() - _start
        if consumed > MAX_FTEXT_CONSUMPTION:
            logger.debug(
                "[FTEXT-SAFETY] %s consumed %d bytes (> %d), possible corruption, recovering from field start %d",
                field_name,
                consumed,
                MAX_FTEXT_CONSUMPTION,
                _start,
            )
            archive.seek(_start)  # Seek back to field start, not _start + 5
            value = None
        return value
    except BINARY_READ_ERRORS:
        archive.seek(_start)  # On exception, also seek back to start position
        return None


def read_ue_graph_pin(
    archive: FArchive,
    name_map: list[str],
    summary: PackageFileSummary,
    export_map: list[ObjectExport],
    import_map: list[ObjectImport],
    header_owning_node: int | None = None,
    header_pin_id: str | None = None,
) -> UEdGraphPin:
    """Read UEdGraphPin full serialization format (UE5.7 specific).

    D-12: UE5 Pin array uses PinReference format with external header:
      - Header: b_null_ptr + owning_node + pin_guid (read by caller)
      - Body: Complete UEdGraphPin (duplicates owning_node + pin_guid + PinName + ...)

    If header_owning_node and header_pin_id provided, skip internal duplicates and use provided values.
    Write-only UEdGraphPin fields keep their archive.read_*() cursor steps but
    are not stored on the model.
    """
    # 1. OwningNode - D-12: internal duplicate; header path reads the same 4 bytes
    archive.read_i32()

    # 2. PinId (FGuid 16 bytes) - D-12: If header provided, read and discard internal duplicate
    if header_pin_id is not None:
        archive.read_bytes(16)  # Discard internal duplicate
        pin_id = header_pin_id
    else:
        pin_id_bytes = archive.read_bytes(16)
        pin_id = pin_id_bytes.hex()

    # 3. PinName
    pin_name = archive.read_name(name_map)

    # 4. PinFriendlyName (FText) — DevNotes gated per package custom version; write-only
    dev_notes = ftext_dev_notes_enabled(summary)
    _read_pin_ftext_field(archive, "PinFriendlyName", dev_notes=dev_notes)

    # 5. SourceIndex (UE5 always present, write-only)
    archive.read_i32()

    # 6. PinToolTip — FString (NOT FText!); write-only
    _read_pin_fstring_field(archive, "PinToolTip", pin_name)

    # 7. Direction — u8 for both UE4 and UE5
    direction = archive.read_u8()

    # 8. PinType
    pin_type = read_ed_graph_pin_type(archive, name_map, summary, import_map, export_map)

    # 9-10. DefaultValue strings (tolerant, write-only)
    _read_pin_fstring_field(archive, "DefaultValue")
    _read_pin_fstring_field(archive, "AutogeneratedDefaultValue")

    # 11. DefaultObject (FPackageIndex, write-only)
    archive.read_i32()

    # 12. DefaultTextValue (FText, write-only)
    _read_pin_ftext_field(archive, "DefaultTextValue", dev_notes=dev_notes)

    # 13. LinkedTo array
    linked_to = read_pin_array(archive, export_map, import_map)

    # 14. SubPins array (write-only — consumed to keep the cursor aligned)
    read_pin_array(archive, export_map, import_map)

    # 15. ParentPin — reuse read_pin_reference() (UE5: null → 4B, non-null → 24B)
    read_pin_reference(archive)

    # 16. ReferencePassThroughConnection — reuse read_pin_reference()
    read_pin_reference(archive)

    # 17. PersistentGuid (EditorOnly, write-only)
    try:
        _read_guid(archive)
    except (struct.error, OSError, ParseError):
        pass

    # 18. BitField (EditorOnly) — uint32 in both UE4 and UE5 (EdGraphPin.cpp L1902)
    archive.read_u32()

    return UEdGraphPin(
        pin_id=pin_id,
        pin_name=pin_name,
        direction=direction,
        pin_type=pin_type,
        linked_to_raw=linked_to,
    )
