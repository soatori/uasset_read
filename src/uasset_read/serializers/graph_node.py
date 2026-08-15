"""Blueprint Node binary serializer — UEdGraphNode, K2Node read functions.

Extracted from serializers/graph.py, contains all node-related read logic.
"""
from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING, List, Optional, Dict, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport
    from uasset_read.link.linker import PackageLinker

from uasset_read.constants import (
    MAX_PINS_PER_NODE, UE_NONE_SENTINEL,
)
from uasset_read.exceptions import ParseError, ErrorContext
from uasset_read.serializers.object_resources import PackageIndex
from uasset_read.serializers.property_tags import read_property_tag, read_tag_value_bounded
from uasset_read.models.core import UEdGraphNode, UEdGraphPin, FMemberReference

from uasset_read.serializers.graph_helpers import (
    _read_guid, _rcn, _gac, _get_thread_local,
    _read_tag_bool, _read_tag_i32, _read_tag_fname,
    read_ftext_with_history,
)
from uasset_read.serializers.graph_pin import read_ue_graph_pin

logger = logging.getLogger(__name__)

# ============================================================================
# FMemberReference reading
# ============================================================================

def read_fmember_reference(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
) -> FMemberReference:
    """Read FMemberReference (MemberReference.h L74-95)."""
    member_parent_index = archive.read_i32("MemberRef.MemberParent")
    member_parent: Optional[str] = None
    if member_parent_index != 0:
        member_parent = _rcn(
            PackageIndex(member_parent_index), import_map, export_map, linker
        )

    _member_scope = archive.read_fstring("MemberRef.MemberScope")  # noqa: F841 - protocol read
    member_name = archive.read_name(name_map, "MemberRef.MemberName")
    member_guid = _read_guid(archive, uppercase=False)
    b_self_context = archive.read_bool("MemberRef.bSelfContext")
    _b_was_deprecated = archive.read_bool("MemberRef.bWasDeprecated")

    return FMemberReference(
        member_parent=member_parent,
        member_name=member_name,
        member_guid=member_guid,
        b_self_context=b_self_context,
    )

# ============================================================================
# 5 Node type readers
# ============================================================================

def read_k2node_call_function(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
    function_reference: Optional[FMemberReference] = None,
) -> Dict[str, Any]:
    """Read K2Node_CallFunction specific fields, return dict (as node_data).

    If function_reference was already parsed at the PropertyTag layer (script_serial), use it directly;
    otherwise read FMemberReference from the archive's current position.

    Reference: UE C++ FK2Node_CallFunction::Serialize() implementation.
    """
    # D-11: PropertyTag layer already correctly parsed FunctionReference, use it preferentially
    if function_reference is None:
        function_reference = read_fmember_reference(archive, name_map, import_map, export_map, linker)

    b_defaults_to_pure = archive.read_bool("K2Node_CallFunction.bDefaultsToPure")
    return {
        "function_reference": function_reference,
        "b_defaults_to_pure": b_defaults_to_pure,
    }

def read_k2node_event(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
    event_reference: Optional[FMemberReference] = None,
    b_override_function: Optional[bool] = None,
    b_internal_event: Optional[bool] = None,
    custom_function_name: Optional[str] = None,
    function_flags: Optional[int] = None,
) -> Dict[str, Any]:
    """Read K2Node_Event specific fields, return dict (as node_data).

    If event_reference, b_override_function, etc. were already parsed at the PropertyTag layer
    (script_serial), use them directly; fallback reads must be protected by
    script_serial_size / field trace verification.

    Return fields:
    - event_reference: FMemberReference
    - b_override_function: bool
    - b_internal_event: bool (new)
    - custom_function_name: str (new)
    - function_flags: int (new)

    Reference: UE C++ FK2Node_Event::Serialize() implementation.
    """
    # D-11: PropertyTag layer already correctly parsed EventReference, use it preferentially
    if event_reference is None:
        event_reference = read_fmember_reference(archive, name_map, import_map, export_map, linker)

    # b_override_function uses PropertyTag value preferentially, no blind read
    # Only consider fallback when PropertyTag does not provide it, and fallback must be protected by verification
    if b_override_function is None:
        # Legacy fallback: only read when confirmed there are remaining bytes
        # Mark source as "legacy_fallback" for diagnostic tracing
        try:
            b_override_function = archive.read_bool()
            logger.debug(
                "K2Node_Event b_override_function read from legacy fallback (bool at pos %d)",
                archive.tell() - 4
            )
        except (struct.error, OSError, ValueError) as e:
            logger.debug(
                "K2Node_Event b_override_function fallback failed: %s, defaulting to False",
                e
            )
            b_override_function = False

    return {
        "event_reference": event_reference,
        "b_override_function": b_override_function,
        "b_internal_event": b_internal_event if b_internal_event is not None else False,
        "custom_function_name": custom_function_name or "",
        "function_flags": function_flags if function_flags is not None else 0,
        "is_event": True,
    }

def read_k2node_knot(archive: FArchive) -> Dict[str, Any]:
    """K2Node_Knot has no extra fields."""
    return {}

def read_edgraph_node_comment(raw_properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Read EdGraphNode_Comment specific fields, return dict (as node_data).

    In UE5 samples, the comment node's color and size are in tagged properties.
    The old implementation continued reading float/int from trailing binary,
    which easily misreads subsequent fields as absurd sizes.
    """
    raw_properties = raw_properties or {}
    return {
        "comment_color": raw_properties.get("CommentColor"),
        "node_width": raw_properties.get("NodeWidth"),
        "node_height": raw_properties.get("NodeHeight"),
        "font_size": raw_properties.get("FontSize"),
        "comment_depth": raw_properties.get("CommentDepth"),
    }

def _build_trigger_events_from_pins(pins: List["UEdGraphPin"]) -> Dict[str, str]:
    """Extract trigger_events mapping from EnhancedInputAction node pins.

    Iterates exec-direction output pins and maps pin names to
    ETriggerEvent enum string values via ETRIGGER_EVENT_PIN_MAP.
    """
    from uasset_read.constants import ETRIGGER_EVENT_PIN_MAP

    trigger_events = {}
    for pin in pins:
        pin_category = getattr(pin.pin_type, 'pin_category', '') if pin.pin_type else ''
        direction = getattr(pin, 'direction', None)
        pin_name = getattr(pin, 'pin_name', '')
        
        # Check if this is an output exec pin or if pin_category matches trigger events
        is_exec_output = (pin_category == "exec" and direction == 1)
        is_trigger_pin = (pin_name in ETRIGGER_EVENT_PIN_MAP)
        is_trigger_category = (pin_category in ETRIGGER_EVENT_PIN_MAP)
        
        if is_exec_output or is_trigger_pin or is_trigger_category:
            # Use pin_name if available and valid, otherwise use pin_category
            trigger_name = pin_name if pin_name and pin_name in ETRIGGER_EVENT_PIN_MAP else pin_category
            if trigger_name in ETRIGGER_EVENT_PIN_MAP:
                trigger_events[trigger_name] = ETRIGGER_EVENT_PIN_MAP[trigger_name]
    return trigger_events

def read_k2node_enhanced_input(
    archive: FArchive,
    name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read K2Node_EnhancedInputAction specific fields, return dict (as node_data).

    Retrieves AdvancedPinDisplay, InputAction short name, etc. from the PropertyTag layer.

    Return fields:
    - input_action_path: full object path
    - input_action_short_name: short name (e.g. "IA_Move")
    - input_action_package_index: raw FPackageIndex
    - advanced_pin_display: formatted enum name (e.g. "Hidden")
    - advanced_pin_display_raw: raw int value
    """
    raw_properties = raw_properties or {}

    # InputAction from PropertyTag (already parsed in read_ue_graph_node)
    input_action_path = raw_properties.get("InputAction") or ""
    input_action_short_name = raw_properties.get("InputActionShortName") or ""
    input_action_package_index = raw_properties.get("InputActionPackageIndex", 0)

    # If PropertyTag does not provide it, try reading from archive
    if not input_action_path:
        try:
            input_action_path = archive.read_fstring()
            # Extract short name from path
            if input_action_path:
                input_action_short_name = input_action_path.split(".")[-1].split("'")[0]
        except (struct.error, OSError, ValueError):
            input_action_path = ""

    # AdvancedPinDisplay from PropertyTag
    advanced_pin_display_raw = raw_properties.get("AdvancedPinDisplay", 0)
    advanced_pin_display = raw_properties.get("AdvancedPinDisplayFormatted", "Default")

    return {
        "input_action_path": input_action_path,
        "input_action_short_name": input_action_short_name,
        "input_action_package_index": input_action_package_index,
        "advanced_pin_display": advanced_pin_display,
        "advanced_pin_display_raw": advanced_pin_display_raw,
    }

def read_k2node_functionentry(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
    function_reference: Optional[FMemberReference] = None,
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read K2Node_FunctionEntry specific fields, return dict (as node_data).

    Retrieves ExtraFlags, bIsEditable from the PropertyTag layer.

    FunctionReference was already parsed from PropertyTag in read_ue_graph_node().

    Return fields:
    - function_reference: FMemberReference
    - extra_flags: int
    - b_is_editable: bool
    """
    raw_properties = raw_properties or {}

    extra_flags = raw_properties.get("ExtraFlags", 0)
    b_is_editable = raw_properties.get("bIsEditable", False)

    return {
        "function_reference": function_reference,
        "extra_flags": extra_flags,
        "b_is_editable": b_is_editable,
    }

def read_k2node_message(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
) -> Dict[str, Any]:
    """Read K2Node_Message specific fields."""
    result = {}

    try:
        message_name_idx = archive.read_i32()
        if 0 <= message_name_idx < len(name_map):
            result["message_name"] = name_map[message_name_idx]
        else:
            result["message_name"] = f"Message_{message_name_idx}"
    except (struct.error, OSError, ValueError) as e:
        logger.debug("K2Node_Message read failed: %s", e)
        result["message_name"] = "Unknown"

    return result

def read_k2node_call_delegate(archive: FArchive, name_map: List[str]) -> Dict[str, Any]:
    """Read K2Node_CallDelegate fields."""
    result = {}
    try:
        delegate_idx = archive.read_i32()
        if 0 <= delegate_idx < len(name_map):
            result["delegate_name"] = name_map[delegate_idx]
    except (struct.error, OSError, ValueError) as e:
        logger.debug("K2Node_CallDelegate read failed: %s", e)
    return result

def _read_k2node_function_reference(
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Extract FunctionReference from raw_properties."""
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    func_ref = raw_properties.get("FunctionReference")
    if func_ref is not None:
        result["function_reference"] = func_ref

    return result

def read_k2node_call_array_function(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read K2Node_CallArrayFunction specific fields."""
    return _read_k2node_function_reference(raw_properties)

def read_k2node_call_parent_function(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read K2Node_CallParentFunction specific fields."""
    return _read_k2node_function_reference(raw_properties)

def read_k2node_function_result(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read K2Node_FunctionResult specific fields."""
    return _read_k2node_function_reference(raw_properties)

def read_k2node_create_widget(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read K2Node_CreateWidget specific fields.

    Inherits from K2Node_ConstructObjectFromClass, creates UMG widgets.
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    # WidgetClass from PropertyTag (FPackageIndex -> class name)
    widget_class = raw_properties.get("WidgetClass")
    if widget_class is not None:
        result["widget_class"] = widget_class

    return result

def _read_k2node_delegate_name(
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Extract DelegateName from raw_properties."""
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    delegate_name = raw_properties.get("DelegateName")
    if delegate_name is not None:
        result["delegate_name"] = delegate_name

    return result

def read_k2node_add_delegate(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read K2Node_AddDelegate specific fields."""
    return _read_k2node_delegate_name(raw_properties)

def read_k2node_macro_instance(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read K2Node_MacroInstance specific fields.

    Inherits from K2Node_Tunnel, represents a macro graph instance.
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    # MacroGraph from PropertyTag (FPackageIndex -> macro graph reference)
    macro_graph = raw_properties.get("MacroGraph")
    if macro_graph is not None:
        result["macro_graph"] = macro_graph

    # Macro from PropertyTag (FName -> macro name)
    macro = raw_properties.get("Macro")
    if macro is not None:
        result["macro_name"] = macro

    # MacroGraphReference structured parsing (new format: FGraphReference)
    macro_graph_ref = raw_properties.get("MacroGraphReference")
    if macro_graph_ref is not None:
        result["macro_graph_reference"] = macro_graph_ref

    # ResolvedWildcardType -- type after wildcard pin resolution
    resolved_wildcard = raw_properties.get("ResolvedWildcardType")
    if resolved_wildcard is not None:
        result["resolved_wildcard_type"] = resolved_wildcard

    return result

def read_k2node_assign_delegate(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read K2Node_AssignDelegate specific fields."""
    return _read_k2node_delegate_name(raw_properties)

def read_k2node_get_data_table_row(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read K2Node_GetDataTableRow specific fields.

    Retrieves row data from a data table.
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    # DataTable from PropertyTag
    data_table = raw_properties.get("DataTable")
    if data_table is not None:
        result["data_table"] = data_table

    # RowStructName from PropertyTag
    row_struct = raw_properties.get("RowStructName")
    if row_struct is not None:
        result["row_struct_name"] = row_struct

    return result

def read_k2node_load_asset(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read K2Node_LoadAsset specific fields.

    Asynchronous asset loading node.
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    # AssetType from PropertyTag
    asset_type = raw_properties.get("AssetType")
    if asset_type is not None:
        result["asset_type"] = asset_type

    return result

def read_k2node_spawn_actor_from_class(
    archive: FArchive, name_map: List[str],
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read K2Node_SpawnActorFromClass specific fields.

    Inherits from K2Node_ConstructObjectFromClass, spawns Actors.
    """
    raw_properties = raw_properties or {}
    result: Dict[str, Any] = {}

    # Class from PropertyTag
    spawn_class = raw_properties.get("Class")
    if spawn_class is not None:
        result["spawn_class"] = spawn_class

    return result

# ============================================================================
# dispatch handlers -- unified signature (ctx: Dict[str, Any]) -> Dict[str, Any]
# ctx contains: archive, name_map, summary, export_map, import_map, linker,
#               node_refs, raw_properties, class_name, node_export, base_node
# ============================================================================

def _handle_call_function(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """K2Node_CallFunction dispatch handler."""
    return read_k2node_call_function(
        ctx["archive"], ctx["name_map"], ctx["import_map"], ctx["export_map"], ctx["linker"],
        function_reference=ctx.get("node_refs", {}).get("function_reference"),
    )

def _handle_event(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """K2Node_Event dispatch handler."""
    refs = ctx.get("node_refs") or {}
    return read_k2node_event(
        ctx["archive"], ctx["name_map"], ctx["import_map"], ctx["export_map"], ctx["linker"],
        event_reference=refs.get("event_reference"),
        b_override_function=refs.get("b_override_function"),
        b_internal_event=refs.get("b_internal_event"),
        custom_function_name=refs.get("custom_function_name"),
        function_flags=refs.get("function_flags"),
    )

def _handle_comment(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """EdGraphNode_Comment dispatch handler, with attribute writeback."""
    node_data = read_edgraph_node_comment(ctx.get("raw_properties"))
    base_node = ctx["base_node"]
    if isinstance(node_data, dict):
        for attr, key in (
            ("comment_color", "comment_color"),
            ("node_width", "node_width"),
            ("node_height", "node_height"),
            ("font_size", "font_size"),
        ):
            value = node_data.get(key)
            if value is not None:
                setattr(base_node, attr, value)
    return node_data

def _handle_enhanced_input(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """K2Node_EnhancedInputAction dispatch handler, with trigger_events extraction."""
    node_data = read_k2node_enhanced_input(
        ctx["archive"], ctx["name_map"], ctx.get("raw_properties"),
    )
    if isinstance(node_data, dict):
        node_data["trigger_events"] = _build_trigger_events_from_pins(ctx["base_node"].pins)
    return node_data

def _handle_function_entry(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """K2Node_FunctionEntry dispatch handler."""
    fr = ctx.get("node_refs", {}).get("function_reference")
    return read_k2node_functionentry(
        ctx["archive"], ctx["name_map"], ctx["import_map"], ctx["export_map"], ctx["linker"],
        function_reference=fr,
        raw_properties=ctx.get("raw_properties"),
    )

def _handle_full_context(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """AnimGraphNode type dispatch handler."""
    return _read_anim_graph_node(
        ctx["archive"], ctx["name_map"], ctx["summary"],
        ctx["export_map"], ctx["import_map"], ctx["linker"],
        ctx["class_name"], ctx.get("raw_properties"),
    )

def _handle_unknown_type(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback handler for unknown node types."""
    raw = ctx.get("raw_properties")
    return {"_raw_properties": raw} if raw else {}

# Generic handlers: node types that only need archive + name_map + raw_properties
def _handle_simple_raw_props(ctx: Dict[str, Any], reader) -> Dict[str, Any]:
    return reader(ctx["archive"], ctx["name_map"], raw_properties=ctx.get("raw_properties"))

def _handle_simple_full(ctx: Dict[str, Any], reader) -> Dict[str, Any]:
    return reader(ctx["archive"], ctx["name_map"],
                  ctx["import_map"], ctx["export_map"], ctx["linker"])

# Node type -> handler mapping
_NODE_TYPE_HANDLERS: Dict[str, Any] = {
    "K2Node_CallFunction": _handle_call_function,
    "K2Node_Event": _handle_event,
    "K2Node_Knot": lambda ctx: read_k2node_knot(ctx["archive"]),
    "EdGraphNode_Comment": _handle_comment,
    "K2Node_EnhancedInputAction": _handle_enhanced_input,
    "K2Node_FunctionEntry": _handle_function_entry,
    "K2Node_Message": lambda ctx: _handle_simple_full(ctx, read_k2node_message),
    "K2Node_CallDelegate": lambda ctx: read_k2node_call_delegate(ctx["archive"], ctx["name_map"]),
    "K2Node_CallArrayFunction": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_call_array_function),
    "K2Node_CallParentFunction": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_call_parent_function),
    "K2Node_FunctionResult": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_function_result),
    "K2Node_CreateWidget": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_create_widget),
    "K2Node_AddDelegate": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_add_delegate),
    "K2Node_MacroInstance": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_macro_instance),
    "K2Node_AssignDelegate": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_assign_delegate),
    "K2Node_GetDataTableRow": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_get_data_table_row),
    "K2Node_LoadAsset": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_load_asset),
    "K2Node_SpawnActorFromClass": lambda ctx: _handle_simple_raw_props(ctx, read_k2node_spawn_actor_from_class),
}

# ============================================================================
# AnimGraphNode reading
# ============================================================================

def _read_anim_graph_node(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    linker: Optional["PackageLinker"],
    class_name: str,
    raw_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read AnimGraphNode type node data.

    Key properties:
    - EditorStateMachineGraph: state machine subgraph (UAnimationStateMachineGraph)
    - BoundGraph: state subgraph (UEdGraph)
    - Node: animation node runtime data (FAnimNode_StateMachine, etc.)
    """
    result: Dict[str, Any] = {
        "node_type": class_name,
    }

    if not raw_properties:
        return result

    # Extract subgraph references
    subgraph_refs = {}
    for key in ("EditorStateMachineGraph", "BoundGraph"):
        pkg_idx = raw_properties.get(key)
        if pkg_idx and isinstance(pkg_idx, int) and pkg_idx != 0:
            # Resolve PackageIndex to object reference
            try:
                if linker is not None:
                    obj_ref = linker.resolve_package_index(PackageIndex(pkg_idx))
                    if obj_ref is not None:
                        subgraph_refs[key] = {
                            "package_index": pkg_idx,
                            "object_name": getattr(obj_ref, "object_name", ""),
                            "class_name": getattr(obj_ref, "class_name", ""),
                        }
                else:
                    # No linker, try resolving from export_map
                    if pkg_idx > 0 and pkg_idx <= len(export_map):
                        obj_export = export_map[pkg_idx - 1]
                        subgraph_refs[key] = {
                            "package_index": pkg_idx,
                            "object_name": obj_export.object_name,
                            "class_name": _gac(obj_export, import_map, export_map, linker) or "",
                        }
            except (KeyError, IndexError, AttributeError):
                subgraph_refs[key] = {"package_index": pkg_idx, "error": "resolve_failed"}

    if subgraph_refs:
        result["subgraph_references"] = subgraph_refs

    # Extract other AnimGraphNode specific properties
    node_data = raw_properties.get("Node")
    if node_data and isinstance(node_data, dict):
        result["anim_node_data"] = node_data

    # State machine specific properties
    if "StateMachineIndexInClass" in raw_properties:
        result["state_machine_index"] = raw_properties["StateMachineIndexInClass"]

    return result

# ============================================================================
# Node factory
# ============================================================================

def create_node_from_archive(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    node_export: ObjectExport,
    base_node: UEdGraphNode,
    raw_properties: Optional[Dict[str, Any]] = None,
    linker: Optional["PackageLinker"] = None,
    node_refs: Optional[Dict[str, Any]] = None,
) -> UEdGraphNode:
    """Dispatch to the corresponding node read function based on class_name (D-07/D-08 factory pattern).

    Uses dictionary dispatch instead of if/elif chain. Exact match is preferred (_NODE_TYPE_HANDLERS),
    then prefix match (AnimGraphNode_ / AnimState), finally fallback retains raw_properties.
    """
    class_name = base_node.class_name

    # If base_node already carries _parse_error flag, skip dispatch to protect existing information
    if isinstance(base_node.node_data, dict) and base_node.node_data.get("_parse_error"):
        return base_node

    # Build unified context for all handlers to use as needed
    ctx: Dict[str, Any] = {
        "archive": archive,
        "name_map": name_map,
        "summary": summary,
        "export_map": export_map,
        "import_map": import_map,
        "linker": linker,
        "node_refs": node_refs,
        "raw_properties": raw_properties,
        "class_name": class_name,
        "node_export": node_export,
        "base_node": base_node,
    }

    # Dictionary dispatch: exact match
    handler = _NODE_TYPE_HANDLERS.get(class_name)
    if handler is not None:
        base_node.node_data = handler(ctx)
    # Prefix match: AnimGraphNode types (cannot exhaustively enumerate)
    elif class_name.startswith("AnimGraphNode_") or class_name.startswith("AnimState"):
        base_node.node_data = _handle_full_context(ctx)
    elif raw_properties:
        # Unknown type: retain raw PropertyTag metadata for debugging and future extension
        base_node.node_data = _handle_unknown_type(ctx)

    return base_node

# ============================================================================
# UEdGraphNode reading
# ============================================================================

def _read_member_reference_from_tags(
    archive: FArchive,
    tag,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
) -> FMemberReference:
    """Read FMemberReference structure from PropertyTag (shared by FunctionReference/EventReference)."""
    value_end = tag.value_end_offset or (archive.tell() + tag.size)
    mp_idx = 0
    m_name = ""
    m_guid = ""
    m_self = False

    while archive.tell() < value_end:
        inner = read_property_tag(archive, name_map)
        if inner.name == UE_NONE_SENTINEL:
            break
        if inner.value_end_offset is not None and inner.value_end_offset > value_end:
            raise ParseError(
                f"MemberReference field '{inner.name}' exceeds struct boundary",
                context=ErrorContext(
                    offset=archive.tell(),
                    phase="graph",
                    operation="_read_member_reference_from_tags",
                    context_name="",
                ),
            )

        def _read_inner(inner=inner):
            if inner.name == "MemberParent" and inner.size > 0:
                return archive.read_i32()
            if inner.name == "MemberScope" and inner.size > 0:
                archive.read_fstring()
                return None
            if inner.name == "MemberName":
                return archive.read_name(name_map)
            if inner.name == "MemberGuid" and inner.size > 0:
                return archive.read_bytes(16).hex()
            if inner.name == "bSelfContext":
                return (archive.read_i32() != 0) if inner.size > 0 else (inner.bool_val != 0)
            if inner.name == "bWasDeprecated" and inner.size > 0:
                archive.read_i32()
            return None

        inner_value = read_tag_value_bounded(archive, inner, _read_inner)
        if inner.name == "MemberParent":
            mp_idx = inner_value or 0
        elif inner.name == "MemberName":
            m_name = inner_value or ""
        elif inner.name == "MemberGuid":
            m_guid = inner_value or ""
        elif inner.name == "bSelfContext":
            m_self = bool(inner_value)

    return FMemberReference(
        member_parent=_rcn(PackageIndex(mp_idx), import_map, export_map, linker) if mp_idx != 0 else None,
        member_name=m_name,
        member_guid=m_guid,
        b_self_context=m_self,
    )

# ============================================================================
# node PropertyTag dispatch handlers
# ============================================================================

def _handle_node_pos_x(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle NodePosX tag."""
    return {"node_pos_x": _read_tag_i32(archive, tag)}


def _handle_node_pos_y(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle NodePosY tag."""
    return {"node_pos_y": _read_tag_i32(archive, tag)}


def _handle_node_guid(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle NodeGuid tag."""
    if tag.size > 0:
        val = archive.read_bytes(16).hex()
        if archive.tell() < tag.value_end_offset:
            archive.seek(tag.value_end_offset)
        return {"node_guid": val}
    return {}


def _handle_node_comment(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle NodeComment tag."""
    if tag.size > 0:
        val = archive.read_fstring()
        if archive.tell() < tag.value_end_offset:
            archive.seek(tag.value_end_offset)
        return {"node_comment": val}
    return {}


def _handle_input_action(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle InputAction tag."""
    if tag.size > 0:
        pkg_idx = archive.read_i32()
        input_action_path = (
            _rcn(PackageIndex(pkg_idx), import_map, export_map, linker)
            if pkg_idx != 0 else ""
        )
        raw_properties[tag.name] = input_action_path
        raw_properties["InputActionShortName"] = (
            input_action_path.split(".")[-1].split("'")[0]
            if input_action_path else ""
        )
        raw_properties["InputActionPackageIndex"] = pkg_idx
        if archive.tell() < tag.value_end_offset:
            archive.seek(tag.value_end_offset)
    return {}


def _handle_comment_color(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle CommentColor tag (RGBA four-component float)."""
    if tag.size >= 16:
        raw_properties[tag.name] = (
            archive.read_f32(),
            archive.read_f32(),
            archive.read_f32(),
            archive.read_f32(),
        )
        if archive.tell() < tag.value_end_offset:
            archive.seek(tag.value_end_offset)
    return {}


def _handle_i32_to_raw(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle I32 type tags (NodeWidth, NodeHeight, FontSize, CommentDepth, ExtraFlags)."""
    if tag.size > 0:
        raw_properties[tag.name] = _read_tag_i32(archive, tag)
    return {}


def _handle_bool_to_raw(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle boolean type tags (bCommentBubbleVisible_InDetailsPanel, bIsEditable)."""
    raw_properties[tag.name] = _read_tag_bool(archive, tag)
    return {}


def _handle_advanced_pin_display(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle AdvancedPinDisplay tag (enum value + formatted name)."""
    if tag.size > 0:
        raw_val = _read_tag_i32(archive, tag)
        raw_properties[tag.name] = raw_val
        enum_map = {0: "Default", 1: "Hidden", 2: "Shown"}
        raw_properties["AdvancedPinDisplayFormatted"] = enum_map.get(raw_val, f"Unknown({raw_val})")
    return {}


def _handle_override_function(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle bOverrideFunction tag (writes to both updates and raw_properties)."""
    val = _read_tag_bool(archive, tag)
    raw_properties[tag.name] = val
    return {"b_override_function": val}


def _handle_internal_event(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle bInternalEvent tag (writes to both updates and raw_properties)."""
    val = _read_tag_bool(archive, tag)
    raw_properties[tag.name] = val
    return {"b_internal_event": val}


def _handle_custom_function_name(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle CustomFunctionName tag (FName, writes to both updates and raw_properties)."""
    val = _read_tag_fname(archive, tag, name_map)
    raw_properties[tag.name] = val
    return {"custom_function_name": val}


def _handle_function_flags(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle FunctionFlags tag (writes to both updates and raw_properties)."""
    if tag.size > 0:
        val = _read_tag_i32(archive, tag)
        raw_properties[tag.name] = val
        return {"function_flags": val}
    return {}


def _handle_fname_to_raw(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle FName type tag (CustomGeneratedFunctionName)."""
    raw_properties[tag.name] = _read_tag_fname(archive, tag, name_map)
    return {}


def _handle_package_index(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle PackageIndex type tags (EditorStateMachineGraph, BoundGraph)."""
    if tag.size > 0:
        pkg_idx = archive.read_i32()
        raw_properties[tag.name] = pkg_idx
        raw_properties[f"{tag.name}PackageIndex"] = pkg_idx
        if archive.tell() < tag.value_end_offset:
            archive.seek(tag.value_end_offset)
    return {}


def _handle_move_mode(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle MoveMode tag (single-byte enum value)."""
    if tag.size > 0:
        raw_val = archive.read_u8() if tag.size >= 1 else 0
        raw_properties[tag.name] = raw_val
        if archive.tell() < tag.value_end_offset:
            archive.seek(tag.value_end_offset)
    return {}


def _handle_node_details(archive, tag, name_map, import_map, export_map, linker, raw_properties):
    """Handle NodeDetails tag (FText with history)."""
    if tag.size > 0:
        try:
            _flags = archive.read_i32()  # noqa: F841 - protocol read
            history_type_raw = archive.read_u8()
            history_type = history_type_raw - 256 if history_type_raw >= 128 else history_type_raw
            read_ftext_with_history(archive, history_type, tolerant=True)
        except (struct.error, OSError, ValueError) as e:
            logger.debug("Failed to read NodeDetails FText: %s", e, exc_info=True)
        if archive.tell() < tag.value_end_offset:
            archive.seek(tag.value_end_offset)
        raw_properties[tag.name] = {"size": tag.size, "type": "FText"}
    return {}


# Tag name -> handler function dispatch dictionary
_NODE_TAG_HANDLERS: Dict[str, Any] = {
    "NodePosX": _handle_node_pos_x,
    "NodePosY": _handle_node_pos_y,
    "NodeGuid": _handle_node_guid,
    "NodeComment": _handle_node_comment,
    "InputAction": _handle_input_action,
    "CommentColor": _handle_comment_color,
    "NodeWidth": _handle_i32_to_raw,
    "NodeHeight": _handle_i32_to_raw,
    "FontSize": _handle_i32_to_raw,
    "bCommentBubbleVisible_InDetailsPanel": _handle_bool_to_raw,
    "CommentDepth": _handle_i32_to_raw,
    "ExtraFlags": _handle_i32_to_raw,
    "AdvancedPinDisplay": _handle_advanced_pin_display,
    "bOverrideFunction": _handle_override_function,
    "bInternalEvent": _handle_internal_event,
    "bIsEditable": _handle_bool_to_raw,
    "CustomFunctionName": _handle_custom_function_name,
    "FunctionFlags": _handle_function_flags,
    "CustomGeneratedFunctionName": _handle_fname_to_raw,
    "EditorStateMachineGraph": _handle_package_index,
    "BoundGraph": _handle_package_index,
    "MoveMode": _handle_move_mode,
    "NodeDetails": _handle_node_details,
}


def _read_node_property_tag(
    archive: FArchive,
    tag,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"],
    raw_properties: Dict[str, Any],
) -> dict:
    """Read a single node PropertyTag and update local variables. Return named properties to update."""
    handler = _NODE_TAG_HANDLERS.get(tag.name)
    if handler:
        return handler(archive, tag, name_map, import_map, export_map, linker, raw_properties)

    # Unmatched tags: skip bytes when data present to avoid offset misalignment
    if tag.size > 0:
        value_start = archive.tell()
        raw_properties[tag.name] = {"size": tag.size, "offset": value_start}
        archive.seek(tag.value_end_offset)

    return {}

def _read_node_pins(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    linker: Optional["PackageLinker"],
    node_export: ObjectExport,
    node_name: str,
    node_guid: str,
) -> List[UEdGraphPin]:
    """Read the Pins array of a node."""
    pins_offset = node_export.script_serialization_end_offset + 4  # Skip end marker
    archive.seek(node_export.serial_offset + pins_offset)

    pins_count = archive.read_i32()

    if pins_count < 0:
        raise ParseError(
            f"Invalid pins_count {pins_count} (negative) at node {node_name}",
            context=ErrorContext(
                offset=archive.tell(),
                phase="graph",
                operation="_read_node_pins",
                context_name=node_name,
            ),
        )
    if pins_count > MAX_PINS_PER_NODE:
        raise ParseError(
            f"pins_count {pins_count} exceeds MAX_PINS_PER_NODE {MAX_PINS_PER_NODE} at node {node_name}",
            context=ErrorContext(
                offset=archive.tell(),
                phase="graph",
                operation="_read_node_pins",
                context_name=node_name,
            ),
        )

    pins: List[UEdGraphPin] = []
    for _ in range(pins_count):
        b_null_ptr = archive.read_i32()

        if b_null_ptr != 0:
            archive.read_i32()  # owning_node (unused)
            archive.read_bytes(16)  # pin_guid (unused)
            continue

        header_owning = archive.read_i32()
        header_guid_bytes = archive.read_bytes(16)
        header_pin_id = header_guid_bytes.hex()

        try:
            pin = read_ue_graph_pin(
                archive, name_map, summary, export_map, import_map, linker,
                header_owning_node=header_owning,
                header_pin_id=header_pin_id,
            )
            _local_trace = _get_thread_local().pin_trace_events
            if _local_trace and _local_trace[-1].get("pin_id") == pin.pin_id:
                _local_trace[-1]["node_name"] = node_export.object_name
                _local_trace[-1]["node_guid"] = node_guid
                _local_trace[-1]["node_class"] = _rcn(
                    node_export.class_index, import_map, export_map, linker
                ) or ""
            pins.append(pin)
        except (struct.error, OSError, ValueError, KeyError):
            continue

    return pins

def _read_node_script_serial(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    node_export: ObjectExport,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"],
    node_name: str,
) -> tuple:
    """Read script_serial PropertyTags of a node, returning (function_reference, event_reference, local variables dict, raw_properties)."""
    function_reference: Optional[FMemberReference] = None
    event_reference: Optional[FMemberReference] = None
    b_override_function: Optional[bool] = None
    b_internal_event: Optional[bool] = None
    custom_function_name: Optional[str] = None
    function_flags: Optional[int] = None
    node_pos_x: int = 0
    node_pos_y: int = 0
    node_guid: str = ""
    node_comment: str = ""
    raw_properties: Dict[str, Any] = {}

    if not node_export.has_script_serialization:
        return (function_reference, event_reference, b_override_function,
                b_internal_event, custom_function_name, function_flags,
                node_pos_x, node_pos_y, node_guid, node_comment, raw_properties)

    script_start = node_export.serial_offset + node_export.script_serialization_start_offset
    script_end = node_export.serial_offset + node_export.script_serialization_end_offset
    archive.seek(script_start)

    # UE5 >= 1011: SerializationControlExtensions
    if summary.file_version_ue5 >= 1011:
        ctrl = archive.read_u8()
        if ctrl & 0x02:
            archive.read_u8()
        # Unknown high-bit handling: stop parsing script_serial to prevent cascading offset misalignment
        if ctrl & ~0x03:
            logger.debug(
                "Node script_serial: unknown SerializationControlExtensions bits 0x%02X, skipping remaining properties, node=%s",
                ctrl, node_name
            )
            return (function_reference, event_reference, b_override_function,
                    b_internal_event, custom_function_name, function_flags,
                    node_pos_x, node_pos_y, node_guid, node_comment, raw_properties)

    max_property_iterations = max(1000, node_export.script_serialization_size)
    _property_iterations = 0

    while archive.tell() < script_end:
        _property_iterations += 1
        if _property_iterations > max_property_iterations:
            logger.debug(
                "read_ue_graph_node: exceeded max_property_iterations (%d) at node %s, breaking loop",
                max_property_iterations, node_name
            )
            break

        tag_pos = archive.tell()
        try:
            tag = read_property_tag(archive, name_map, tolerant=getattr(archive, '_tolerant', False))
        except ParseError as e:
            logger.debug(
                "read_ue_graph_node: failed to read PropertyTag at pos %d, node=%s: %s",
                tag_pos, node_name, e
            )
            break

        if tag.name == UE_NONE_SENTINEL:
            break

        if tag.name == "FunctionReference" and tag.size > 0:
            function_reference = read_tag_value_bounded(
                archive, tag,
                lambda: _read_member_reference_from_tags(archive, tag, name_map, import_map, export_map, linker)  # noqa: B023 - tag bound at call time
            )
        elif tag.name == "EventReference" and tag.size > 0:
            event_reference = read_tag_value_bounded(
                archive, tag,
                lambda: _read_member_reference_from_tags(archive, tag, name_map, import_map, export_map, linker)  # noqa: B023 - tag bound at call time
            )
        else:
            updates = _read_node_property_tag(
                archive, tag, name_map, import_map, export_map, linker, raw_properties
            )
            if "node_pos_x" in updates:
                node_pos_x = updates["node_pos_x"]
            if "node_pos_y" in updates:
                node_pos_y = updates["node_pos_y"]
            if "node_guid" in updates:
                node_guid = updates["node_guid"]
            if "node_comment" in updates:
                node_comment = updates["node_comment"]
            if "b_override_function" in updates:
                b_override_function = updates["b_override_function"]
            if "b_internal_event" in updates:
                b_internal_event = updates["b_internal_event"]
            if "custom_function_name" in updates:
                custom_function_name = updates["custom_function_name"]
            if "function_flags" in updates:
                function_flags = updates["function_flags"]

    return (function_reference, event_reference, b_override_function,
            b_internal_event, custom_function_name, function_flags,
            node_pos_x, node_pos_y, node_guid, node_comment, raw_properties)

def read_ue_graph_node(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    node_export: ObjectExport,
    linker: Optional["PackageLinker"] = None,
) -> UEdGraphNode:
    """Read UEdGraphNode base class fields (including script_serial PropertyTag parsing)."""
    archive.seek(node_export.serial_offset)

    node_name = node_export.object_name
    # Parse tagged properties in script_serial
    (function_reference, event_reference, b_override_function,
     b_internal_event, custom_function_name, function_flags,
     node_pos_x, node_pos_y, node_guid, node_comment, raw_properties
     ) = _read_node_script_serial(
        archive, name_map, summary, node_export, import_map, export_map, linker, node_name
    )

    # Read Pins array
    pins = _read_node_pins(
        archive, name_map, summary, export_map, import_map, linker,
        node_export, node_name, node_guid,
    )

    class_name = _rcn(node_export.class_index, import_map, export_map, linker) or ""

    base_node = UEdGraphNode(
        node_guid=node_guid,
        node_pos_x=node_pos_x,
        node_pos_y=node_pos_y,
        node_comment=node_comment,
        pins=pins,
        class_name=class_name,
    )
    base_node._export_object_name = node_export.object_name

    node_refs = {
        'function_reference': function_reference,
        'event_reference': event_reference,
        # K2Node_Event PropertyTag fields
        'b_override_function': b_override_function,
        'b_internal_event': b_internal_event,
        'custom_function_name': custom_function_name,
        'function_flags': function_flags,
    }

    return create_node_from_archive(
        archive, name_map, summary, export_map, import_map, node_export, base_node,
        raw_properties=raw_properties if raw_properties else None,
        linker=linker,
        node_refs=node_refs,
    )
