"""NiagaraNode asset type handler

Generic handler for all NiagaraNode* classes.
Projects tagged properties (class-specific), decodes pins from native tails.

Node families and their verified properties:
- NiagaraNodeInput: Input, CallSortPriority, ChangeId
- NiagaraNodeFunctionCall: FunctionScript, CachedChangeId, FunctionDisplayName, ChangeId
- NiagaraNodeParameterMapGet: PinOutputToPinDefaultPersistentId, ChangeId
- NiagaraNodeParameterMapSet: ChangeId
- NiagaraNodeOp: OpName, ChangeId
- NiagaraNodeOutput: Outputs, ScriptType, ChangeId
- NiagaraNodeReroute: ChangeId
- NiagaraNodeSelect: SelectorPinType, SelectorPinGuid, OutputVars, OutputVarGuids, NumOptionsPerVariable, ChangeId
- NiagaraNodeStaticSwitch: InputParameterName, SwitchTypeData, OutputVars, OutputVarGuids, NumOptionsPerVariable, ChangeId

Pin layout: issue-521-b0-gate-decision.md §Pin-record layout.
Source: EdGraphPin.cpp:1838-1948 (UEdGraphPin::Serialize).
"""

import logging
from typing import TYPE_CHECKING, Any, Optional, Set

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.object_resources import ObjectExport

from uasset_read.parsers.asset_types.property_extractor import build_properties_dict
from uasset_read.parsers.class_registry import ClassHandler, FallbackPolicy, HandlerResult
from uasset_read.models.validators import validate_parse_status

logger = logging.getLogger(__name__)

# Classes this handler can handle
_HANDLED_CLASSES: Set[str] = {
    "NiagaraNodeInput",
    "NiagaraNodeFunctionCall",
    "NiagaraNodeParameterMapGet",
    "NiagaraNodeParameterMapSet",
    "NiagaraNodeOp",
    "NiagaraNodeOutput",
    "NiagaraNodeReroute",
    "NiagaraNodeSelect",
    "NiagaraNodeStaticSwitch",
}

# ---------------------------------------------------------------------------
# Pin decode helpers
# ---------------------------------------------------------------------------

def _decode_ftext_fstring(archive: "FArchive") -> str:
    """Read FText internal FString. Length=-1 means empty string (not UTF-16).

    Source: Text.cpp, graph_helpers.py _read_ftext_fstring.
    """
    length = archive.read_i32()
    if length == 0 or length == -1:
        return ""
    if length < -1:
        # UTF-16
        data = archive.read(-length * 2)
        return data.decode('utf-16-le', errors='replace').rstrip('\x00')
    # UTF-8
    data = archive.read(length)
    return data.decode('utf-8', errors='replace').rstrip('\x00')


def _decode_ftext(archive: "FArchive") -> str:
    """Decode FText binary format from the archive.

    Source: Text.cpp:888-988, TextHistory.h:24-27, TextHistory.cpp:810-911.
    Format: u32 Flags + i8 HistoryType + history payload.
    - HistoryType -1 (None): empty FText = Flags(0) + 0xFF + u32 bHasCultureInvariantString(0)
    - HistoryType 0 (Base) and types 2-10 (OrderedFormat, ArgumentFormat, AsNumber,
      AsCurrency, AsPercent, AsDate, AsTime, AsDateTime, AsRelative):
      Namespace FString + Key FString + SourceString FString
    - HistoryType 1 (NamedFormat): recursive FText + Arguments (skipped, returns "")
    On failure, restores archive to field start and returns "".
    """
    start_pos = archive.tell()
    try:
        flags = archive.read_u32()
        history_type = archive.read_i8()

        if history_type == -1:  # None -- empty FText
            b_has_culture = archive.read_u32()
            if b_has_culture:
                return _decode_ftext_fstring(archive)
            return ""
        elif history_type in (0,) or 2 <= history_type <= 10:
            # Base and derived types: Namespace + Key + SourceString
            _decode_ftext_fstring(archive)  # Namespace
            _decode_ftext_fstring(archive)  # Key
            source_string = _decode_ftext_fstring(archive)  # SourceString
            return source_string
        elif history_type == 1:  # NamedFormat -- complex, skip
            logger.debug("FText NamedFormat at offset %d, skipping", start_pos)
            archive.seek(start_pos)
            return ""
        else:
            logger.debug("Unknown FText HistoryType %d at offset %d", history_type, start_pos)
            archive.seek(start_pos)
            return ""
    except Exception:
        archive.seek(start_pos)
        return ""


def _decode_pin_type(archive: "FArchive", name_map: list) -> dict[str, Any]:
    """Decode FEdGraphPinType from the archive.

    Source: EdGraphPin.cpp:163, graph_pin.py:read_ed_graph_pin_type.
    Fixture version: UE 5.0 -- bSerializeAsSinglePrecisionFloat absent.
    Format: PinCategory(FName) + PinSubCategory(FName) + PinSubCategoryObject(i32)
    + ContainerType(u8) + bIsReference(u32) + bIsWeakPointer(u32)
    + FSimpleMemberReference(i32 + FName + 16bytes)
    + bIsConst(u32) + bIsUObjectWrapper(u32).
    """
    pin_category = archive.read_name(name_map)
    pin_sub_category = archive.read_name(name_map)

    # PinSubCategoryObject -- object reference (PackageIndex)
    obj_index = archive.read_i32()

    # Container type (EPinContainerType) -- stored as u8 in binary
    container_type = archive.read_u8()

    # bIsReference / bIsWeakPointer (UE5 FArchive bool = uint32, 4B)
    b_is_reference = bool(archive.read_u32())
    b_is_weak_pointer = bool(archive.read_u32())

    # FSimpleMemberReference (always present in UE5)
    _member_parent = archive.read_i32()
    _member_name = archive.read_name(name_map)
    archive.read(16)  # MemberGuid

    # bIsConst / bIsUObjectWrapper (UE5 FArchive bool = uint32, 4B)
    b_is_const = bool(archive.read_u32())
    b_is_uobject_wrapper = bool(archive.read_u32())
    # bSerializeAsSinglePrecisionFloat absent in this fixture (gate 36 > fixture 33)

    return {
        "pin_category": pin_category,
        "pin_sub_category": pin_sub_category,
        "sub_category_object_index": obj_index,
        "container_type": container_type,
        "is_reference": b_is_reference,
        "is_weak_pointer": b_is_weak_pointer,
        "is_const": b_is_const,
        "is_uobject_wrapper": b_is_uobject_wrapper,
    }


def _decode_single_pin(archive: "FArchive", name_map: list) -> Optional[dict[str, Any]]:
    """Decode a single UEdGraphPin record.

    Source: EdGraphPin.cpp:1838-1948 (UEdGraphPin::Serialize).
    Layout: Reference(bNullPtr + OwningNode + PinId) + Body(OwningNode + PinId + PinName + ...)
    """
    # --- Pin reference (written by SerializePinArray / linked-to entries) ---
    # bNullPtr (u32 bool) -- if true, this pin is null
    b_null_ptr = archive.read_u32()
    if b_null_ptr:
        return None

    # OwningNode object reference (PackageIndex)
    owning_node_index = archive.read_i32()

    # PinId (FGuid = 4 x u32)
    pin_id = (
        f"{archive.read_u32():08x}-{archive.read_u32():08x}"
        f"-{archive.read_u32():08x}-{archive.read_u32():08x}"
    )

    # --- Pin body (written by Serialize / SerializeAsOwningNode) ---
    # OwningNode (repeated in body)
    _body_owning_node = archive.read_i32()

    # PinId (repeated in body as FGuid)
    _body_pin_id = (
        f"{archive.read_u32():08x}-{archive.read_u32():08x}"
        f"-{archive.read_u32():08x}-{archive.read_u32():08x}"
    )

    # PinName (FName)
    pin_name = archive.read_name(name_map)

    # PinFriendlyName (FText)
    pin_friendly_name = _decode_ftext(archive)

    # SourceIndex (int32) -- present in this fixture (ff ff ff ff = INDEX_NONE)
    source_index = archive.read_i32()

    # PinToolTip (FString)
    pin_tooltip = archive.read_fstring()

    # Direction (u8)
    direction = archive.read_u8()

    # PinType (FEdGraphPinType)
    pin_type = _decode_pin_type(archive, name_map)

    # DefaultValue (FString)
    default_value = archive.read_fstring()

    # AutogeneratedDefaultValue (FString)
    autogenerated_default_value = archive.read_fstring()

    # DefaultObject (object reference -- PackageIndex)
    default_object_index = archive.read_i32()

    # DefaultTextValue (FText)
    default_text_value = _decode_ftext(archive)

    # LinkedTo array
    linked_to_count = archive.read_i32()
    linked_to: list[dict[str, Any] | None] = []
    for _ in range(linked_to_count):
        b_null = archive.read_u32()
        if b_null:
            linked_to.append(None)
            continue
        lt_node = archive.read_i32()
        lt_pin_id = (
            f"{archive.read_u32():08x}-{archive.read_u32():08x}"
            f"-{archive.read_u32():08x}-{archive.read_u32():08x}"
        )
        linked_to.append({"owning_node": lt_node, "pin_id": lt_pin_id})

    # SubPins array
    sub_pin_count = archive.read_i32()
    for _ in range(sub_pin_count):
        archive.read_u32()  # bNullPtr
        archive.read_i32()  # OwningNode
        archive.read(16)    # PinId FGuid

    # ParentPin object reference
    parent_pin_null = archive.read_u32()
    if not parent_pin_null:
        archive.read_i32()  # OwningNode
        archive.read(16)    # PinId

    # ReferencePassThroughConnection object reference
    ref_null = archive.read_u32()
    if not ref_null:
        archive.read_i32()
        archive.read(16)

    # Editor-only tail: PersistentGuid (16) + BitField (4) = 20 bytes
    # Only present when !Ar.IsFilterEditorOnly() (editor-saved assets)
    persistent_guid = (
        f"{archive.read_u32():08x}-{archive.read_u32():08x}"
        f"-{archive.read_u32():08x}-{archive.read_u32():08x}"
    )
    bit_field = archive.read_u32()

    return {
        "owning_node": owning_node_index,
        "pin_id": pin_id,
        "pin_name": pin_name,
        "direction": direction,
        "pin_type": pin_type,
        "default_value": default_value,
        "linked_to": linked_to,
    }


def _decode_pins_from_tail(
    archive: "FArchive", name_map: list, tail_offset: int, tail_size: int,
) -> list[dict[str, Any]]:
    """Decode pin records from a node's native tail bytes.

    Source: issue-521-b0-gate-decision.md §Pin-record layout.
    Layout: object-GUID marker (u32) + pin_count (i32) + per-pin SerializePin body.
    """
    if tail_size < 8:  # Minimum: GUID marker (4) + pin count (4)
        return []

    archive.seek(tail_offset)

    # Object-GUID presence marker (always false in this fixture)
    guid_marker = archive.read_u32()

    # Pin count
    pin_count = archive.read_i32()
    if pin_count < 0 or pin_count > 1000:  # Sanity check
        return []

    pins: list[dict[str, Any]] = []
    for _ in range(pin_count):
        pin = _decode_single_pin(archive, name_map)
        if pin is None:
            break
        pins.append(pin)

    return pins


# Class-specific properties to project (beyond common ChangeId)
_CLASS_PROPERTIES: dict[str, list[str]] = {
    "NiagaraNodeInput": ["Input", "CallSortPriority"],
    "NiagaraNodeFunctionCall": ["FunctionScript", "CachedChangeId", "FunctionDisplayName"],
    "NiagaraNodeParameterMapGet": ["PinOutputToPinDefaultPersistentId"],
    "NiagaraNodeParameterMapSet": [],
    "NiagaraNodeOp": ["OpName"],
    "NiagaraNodeOutput": ["Outputs", "ScriptType"],
    "NiagaraNodeReroute": [],
    "NiagaraNodeSelect": ["SelectorPinType", "SelectorPinGuid", "OutputVars", "OutputVarGuids", "NumOptionsPerVariable"],
    "NiagaraNodeStaticSwitch": ["InputParameterName", "SwitchTypeData", "OutputVars", "OutputVarGuids", "NumOptionsPerVariable"],
}


class NiagaraNodeHandler(ClassHandler):
    """Generic handler for all NiagaraNode* classes."""

    def can_handle(self, class_name: str) -> bool:
        return class_name in _HANDLED_CLASSES

    @property
    def handler_name(self) -> str:
        return "NiagaraNodeHandler"

    @property
    def fallback_policy(self) -> FallbackPolicy:
        return FallbackPolicy.GENERIC_UOBJECT

    def parse(
        self,
        export: "ObjectExport",
        archive: "FArchive",
        context: Optional[Any] = None,
    ) -> HandlerResult:
        try:
            properties_list = getattr(export, "properties", [])
            if not properties_list:
                return HandlerResult(
                    success=False,
                    error_message="No properties found",
                    fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
                )

            properties = build_properties_dict(properties_list)

            # Determine class name from export (set by _try_asset_type_handler)
            class_name = getattr(export, "resolved_class_name", None) or ""
            if not class_name:
                class_name = getattr(export, "class_name", None) or ""

            # Project tagged properties
            tagged_properties: dict[str, Any] = {}

            # Common property: ChangeId
            if "ChangeId" in properties:
                tagged_properties["ChangeId"] = properties["ChangeId"]

            # Class-specific properties
            class_props = _CLASS_PROPERTIES.get(class_name, [])
            for prop_name in class_props:
                if prop_name in properties:
                    tagged_properties[prop_name] = properties[prop_name]

            # Calculate native tail offset/size
            tail_offset = archive.tell()
            serial_end = export.serial_offset + export.serial_size
            tail_size = max(0, serial_end - tail_offset)

            # Decode pins from native tail
            pins: list[dict[str, Any]] = []
            if tail_size >= 8 and context is not None:
                try:
                    name_map = context if isinstance(context, list) else []
                    pins = _decode_pins_from_tail(archive, name_map, tail_offset, tail_size)
                except Exception as e:
                    logger.debug("Pin decode failed for %s: %s", class_name, e)

            # Build result data
            data: dict[str, Any] = {
                "asset_type": class_name,
                "parse_status": validate_parse_status("partial_metadata"),
                "node_class": class_name,
                "node_name": str(export.object_name),
                "tagged_properties": tagged_properties,
                "pins": pins,
                "native_tail": {
                    "offset": tail_offset,
                    "size": tail_size,
                    "status": "decoded" if pins else "opaque",
                },
            }

            return HandlerResult(
                success=True,
                data=data,
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )

        except (KeyError, TypeError, ValueError) as e:
            logger.warning("NiagaraNode parse error: %s", e)
            return HandlerResult(
                success=False,
                error_message=str(e),
                fallback_policy=FallbackPolicy.GENERIC_UOBJECT,
            )
