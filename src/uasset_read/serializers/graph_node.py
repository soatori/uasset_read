"""Blueprint Node binary serializer — UEdGraphNode, K2Node read functions.

Extracted from serializers/graph.py, contains all node-related read logic.
"""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport

from uasset_read.constants import (
    MAX_PINS_PER_NODE,
    UE_NONE_SENTINEL,
)
from uasset_read.exceptions import ParseError
from uasset_read.serializers.object_resources import PackageIndex
from uasset_read.serializers.property_tags import read_property_tag
from uasset_read.models.core import UEdGraphNode, UEdGraphPin
from uasset_read.serializers.object_resources import resolve_class_name

from uasset_read.serializers.graph_helpers import (
    _read_tag_bool,
    _read_tag_i32,
    _read_tag_fname,
    seek_to_tag_end,
)
from uasset_read.serializers.graph_pin import read_ue_graph_pin

logger = logging.getLogger(__name__)

# ============================================================================
# 5 Node type readers
# ============================================================================


# ============================================================================
# dispatch handlers -- unified signature (ctx: dict[str, Any]) -> dict[str, Any]
# ctx contains: archive, name_map, summary, export_map, import_map,
#               raw_properties, class_name, node_export, base_node
# ============================================================================


def _handle_full_context(ctx: dict[str, Any]) -> dict[str, Any]:
    """AnimGraphNode type dispatch handler."""
    return _read_anim_graph_node(
        ctx["archive"],
        ctx["name_map"],
        ctx["summary"],
        ctx["export_map"],
        ctx["import_map"],
        ctx["class_name"],
        ctx.get("raw_properties"),
    )


# ============================================================================
# AnimGraphNode reading
# ============================================================================


def _read_anim_graph_node(
    archive: FArchive,
    name_map: list[str],
    summary: PackageFileSummary,
    export_map: list[ObjectExport],
    import_map: list[ObjectImport],
    class_name: str,
    raw_properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Read AnimGraphNode type node data.

    Key properties:
    - EditorStateMachineGraph: state machine subgraph (UAnimationStateMachineGraph)
    - BoundGraph: state subgraph (UEdGraph)
    - Node: animation node runtime data (FAnimNode_StateMachine, etc.)
    """
    result: dict[str, Any] = {
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
                # No linker on the single-package path: resolve from export_map
                if pkg_idx > 0 and pkg_idx <= len(export_map):
                    obj_export = export_map[pkg_idx - 1]
                    subgraph_refs[key] = {
                        "package_index": pkg_idx,
                        "object_name": obj_export.object_name,
                        "class_name": resolve_class_name(obj_export.class_index, import_map, export_map) or "",
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
    name_map: list[str],
    summary: PackageFileSummary,
    export_map: list[ObjectExport],
    import_map: list[ObjectImport],
    node_export: ObjectExport,
    base_node: UEdGraphNode,
    raw_properties: dict[str, Any] | None = None,
) -> UEdGraphNode:
    """Attach node_data to base_node: AnimGraphNode prefix dispatch, else leave unset.

    Exact K2Node class handlers were deleted (their node_data never reached any
    projection); AnimGraphNode_/AnimState* types keep the full-context reader.
    """
    class_name = base_node.class_name

    # If base_node already carries _parse_error flag, skip dispatch to protect existing information
    if isinstance(base_node.node_data, dict) and base_node.node_data.get("_parse_error"):
        return base_node

    # Build unified context for all handlers to use as needed
    ctx: dict[str, Any] = {
        "archive": archive,
        "name_map": name_map,
        "summary": summary,
        "export_map": export_map,
        "import_map": import_map,
        "raw_properties": raw_properties,
        "class_name": class_name,
        "node_export": node_export,
        "base_node": base_node,
    }

    # Prefix match: AnimGraphNode types (cannot exhaustively enumerate)
    if class_name.startswith("AnimGraphNode_") or class_name.startswith("AnimState"):
        base_node.node_data = _handle_full_context(ctx)
    elif raw_properties:
        # Tag-derived allow-list projection only (Wave A removed K2Node binary
        # readers). Surviving primitive tags land on node_data for decode.
        from uasset_read.serializers.node_data_project import project_node_data

        projected = project_node_data(raw_properties)
        if projected is not None:
            base_node.node_data = projected

    return base_node


# ============================================================================
# UEdGraphNode reading
# ============================================================================


# ============================================================================
# node PropertyTag dispatch handlers
# ============================================================================


def _handle_node_guid(archive, tag, name_map, import_map, export_map, raw_properties):
    """Handle NodeGuid tag."""
    if tag.size > 0:
        try:
            data = archive.read_bytes(16)
            if len(data) < 16:
                logger.warning(
                    "NodeGuid: expected 16 bytes, got %d at offset %d",
                    len(data),
                    archive.tell() - len(data),
                )
                val = data.hex().ljust(32, "0")
            else:
                val = data.hex()
        except Exception:
            logger.warning(
                "NodeGuid: failed to read 16 bytes at offset %d, using zero GUID",
                archive.tell(),
            )
            val = "0" * 32
        seek_to_tag_end(archive, tag)
        return {"node_guid": val}
    return {}


def _handle_node_comment(archive, tag, name_map, import_map, export_map, raw_properties):
    """Handle NodeComment tag."""
    if tag.size > 0:
        val = archive.read_fstring()
        seek_to_tag_end(archive, tag)
        return {"node_comment": val}
    return {}


def _handle_input_action(archive, tag, name_map, import_map, export_map, raw_properties):
    """Handle InputAction tag."""
    if tag.size > 0:
        pkg_idx = archive.read_i32()
        input_action_path = resolve_class_name(PackageIndex(pkg_idx), import_map, export_map) if pkg_idx != 0 else ""
        raw_properties[tag.name] = input_action_path
        raw_properties["InputActionShortName"] = (
            input_action_path.split(".")[-1].split("'")[0] if input_action_path else ""
        )
        raw_properties["InputActionPackageIndex"] = pkg_idx
        seek_to_tag_end(archive, tag)
    return {}


def _handle_comment_color(archive, tag, name_map, import_map, export_map, raw_properties):
    """Handle CommentColor tag (RGBA four-component float)."""
    if tag.size >= 16:
        raw_properties[tag.name] = (
            archive.read_f32(),
            archive.read_f32(),
            archive.read_f32(),
            archive.read_f32(),
        )
        seek_to_tag_end(archive, tag)
    return {}


def _read_byte_enum_tag_name(archive, tag, name_map):
    """FByteProperty with UENUM underlying serializes the enum-entry FName (PropertyByte.cpp
    SerializeItem); consume the full value span so the stream stays aligned regardless."""
    enum_name = ""
    if tag.size >= 8:
        enum_name = archive.read_name(name_map) or ""
    if tag.value_end_offset and archive.tell() != tag.value_end_offset:
        archive.seek(tag.value_end_offset)
    return enum_name


def _handle_advanced_pin_display(archive, tag, name_map, import_map, export_map, raw_properties):
    """Handle AdvancedPinDisplay tag — byte-enum payload is the enum FName
    (EdGraphNode.h ENodeAdvancedPins: NoPins=0, Shown=1, Hidden=2)."""
    enum_name = _read_byte_enum_tag_name(archive, tag, name_map)
    raw_properties[tag.name] = enum_name
    ordinal = {"NoPins": 0, "Shown": 1, "Hidden": 2}.get(enum_name)
    raw_properties["AdvancedPinDisplayFormatted"] = enum_name or f"Unknown({enum_name!r})"
    if ordinal is not None:
        raw_properties["AdvancedPinDisplayRaw"] = ordinal
    return {}


def _handle_package_index(archive, tag, name_map, import_map, export_map, raw_properties):
    """Handle PackageIndex type tags (EditorStateMachineGraph, BoundGraph)."""
    if tag.size > 0:
        pkg_idx = archive.read_i32()
        raw_properties[tag.name] = pkg_idx
        raw_properties[f"{tag.name}PackageIndex"] = pkg_idx
        seek_to_tag_end(archive, tag)
    return {}


def _handle_move_mode(archive, tag, name_map, import_map, export_map, raw_properties):
    """Handle MoveMode tag — byte-enum payload is the enum-entry FName
    (comment-node TEnumAsByte<ECommentBoxMode>, PropertyByte.cpp SerializeItem)."""
    enum_name = _read_byte_enum_tag_name(archive, tag, name_map)
    raw_properties[tag.name] = enum_name
    return {}


def _handle_node_details(archive, tag, name_map, import_map, export_map, raw_properties):
    """Handle NodeDetails tag (FText): value is discarded, only the tag span is consumed."""
    if tag.size > 0:
        archive.seek(tag.value_end_offset)
        raw_properties[tag.name] = {"size": tag.size, "type": "FText"}
    return {}


# Tag name -> (reader_kind, out_key | None, skip_when_empty)
# reader_kind: "i32", "bool", "fname"
_NODE_SIMPLE_TAGS: dict[str, tuple[str, str | None, bool]] = {
    "NodePosX": ("i32", "node_pos_x", False),
    "NodePosY": ("i32", "node_pos_y", False),
    "NodeWidth": ("i32", None, True),
    "NodeHeight": ("i32", None, True),
    "FontSize": ("i32", None, True),
    "CommentDepth": ("i32", None, True),
    "ExtraFlags": ("i32", None, True),
    "bCommentBubbleVisible_InDetailsPanel": ("bool", None, False),
    "bDefaultsToPureFunc": ("bool", None, False),
    "bIsEditable": ("bool", None, False),
    "bOverrideFunction": ("bool", "b_override_function", False),
    "bInternalEvent": ("bool", "b_internal_event", False),
    "CustomFunctionName": ("fname", "custom_function_name", False),
    "CustomGeneratedFunctionName": ("fname", None, False),
    "FunctionFlags": ("i32", "function_flags", True),
}

# Tag name -> handler function dispatch dictionary
_NODE_TAG_HANDLERS: dict[str, Any] = {
    "NodeGuid": _handle_node_guid,
    "NodeComment": _handle_node_comment,
    "InputAction": _handle_input_action,
    "CommentColor": _handle_comment_color,
    "AdvancedPinDisplay": _handle_advanced_pin_display,
    "EditorStateMachineGraph": _handle_package_index,
    "BoundGraph": _handle_package_index,
    "MoveMode": _handle_move_mode,
    "NodeDetails": _handle_node_details,
}


def _read_node_property_tag(
    archive: FArchive,
    tag,
    name_map: list[str],
    import_map: list[ObjectImport],
    export_map: list[ObjectExport],
    raw_properties: dict[str, Any],
) -> dict:
    """Read a single node PropertyTag and update local variables. Return named properties to update."""
    # Fast path: table-driven dispatch for trivial tags
    if tag.name in _NODE_SIMPLE_TAGS:
        kind, out_key, skip_when_empty = _NODE_SIMPLE_TAGS[tag.name]
        if skip_when_empty and tag.size <= 0:
            return {}
        if kind == "i32":
            val = _read_tag_i32(archive, tag)
        elif kind == "bool":
            val = _read_tag_bool(archive, tag)
        else:
            val = _read_tag_fname(archive, tag, name_map)
        raw_properties[tag.name] = val
        return {} if out_key is None else {out_key: val}

    handler = _NODE_TAG_HANDLERS.get(tag.name)
    if handler:
        return handler(archive, tag, name_map, import_map, export_map, raw_properties)

    # Unmatched tags: skip bytes when data present to avoid offset misalignment
    if tag.size > 0:
        value_start = archive.tell()
        raw_properties[tag.name] = {"size": tag.size, "offset": value_start}
        archive.seek(tag.value_end_offset)

    return {}


def _read_node_pins(
    archive: FArchive,
    name_map: list[str],
    summary: PackageFileSummary,
    export_map: list[ObjectExport],
    import_map: list[ObjectImport],
    node_export: ObjectExport,
    node_name: str,
    node_guid: str,
) -> list[UEdGraphPin]:
    """Read the Pins array of a node."""
    pins_offset = node_export.script_serialization_end_offset + 4  # Skip end marker
    archive.seek(node_export.serial_offset + pins_offset)

    pins_count = archive.read_i32()

    if pins_count < 0:
        raise ParseError(f"Invalid pins_count {pins_count} (negative) at node {node_name}")
    if pins_count > MAX_PINS_PER_NODE:
        raise ParseError(f"pins_count {pins_count} exceeds MAX_PINS_PER_NODE {MAX_PINS_PER_NODE} at node {node_name}")

    pins: list[UEdGraphPin] = []
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
                archive,
                name_map,
                summary,
                export_map,
                import_map,
                header_owning_node=header_owning,
                header_pin_id=header_pin_id,
            )
            pins.append(pin)
        except (struct.error, OSError, ValueError, KeyError):
            continue

    return pins


def _read_node_script_serial(
    archive: FArchive,
    name_map: list[str],
    summary: PackageFileSummary,
    node_export: ObjectExport,
    import_map: list[ObjectImport],
    export_map: list[ObjectExport],
    node_name: str,
) -> dict[str, Any]:
    """Read script_serial PropertyTags of a node into one dict of parsed fields."""
    result: dict[str, Any] = {
        "node_pos_x": 0,
        "node_pos_y": 0,
        "node_guid": "",
        "node_comment": "",
        "raw_properties": {},
    }

    if not node_export.has_script_serialization:
        return result

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
                ctrl,
                node_name,
            )
            return result

    max_property_iterations = max(1000, node_export.script_serialization_size)
    _property_iterations = 0

    while archive.tell() < script_end:
        _property_iterations += 1
        if _property_iterations > max_property_iterations:
            logger.debug(
                "read_ue_graph_node: exceeded max_property_iterations (%d) at node %s, breaking loop",
                max_property_iterations,
                node_name,
            )
            break

        tag_pos = archive.tell()
        try:
            tag = read_property_tag(archive, name_map, tolerant=getattr(archive, "_tolerant", False))
        except ParseError as e:
            logger.debug("read_ue_graph_node: failed to read PropertyTag at pos %d, node=%s: %s", tag_pos, node_name, e)
            break

        if tag.name == UE_NONE_SENTINEL:
            break

        result.update(
            _read_node_property_tag(archive, tag, name_map, import_map, export_map, result["raw_properties"])
        )

    return result


def read_ue_graph_node(
    archive: FArchive,
    name_map: list[str],
    summary: PackageFileSummary,
    export_map: list[ObjectExport],
    import_map: list[ObjectImport],
    node_export: ObjectExport,
) -> UEdGraphNode:
    """Read UEdGraphNode base class fields (including script_serial PropertyTag parsing)."""
    archive.seek(node_export.serial_offset)

    node_name = node_export.object_name
    # Parse tagged properties in script_serial
    serial = _read_node_script_serial(archive, name_map, summary, node_export, import_map, export_map, node_name)
    raw_properties = serial["raw_properties"]

    # Read Pins array
    pins = _read_node_pins(
        archive,
        name_map,
        summary,
        export_map,
        import_map,
        node_export,
        node_name,
        serial["node_guid"],
    )

    class_name = resolve_class_name(node_export.class_index, import_map, export_map) or ""

    base_node = UEdGraphNode(
        node_pos_x=serial["node_pos_x"],
        node_pos_y=serial["node_pos_y"],
        node_comment=serial["node_comment"],
        pins=pins,
        class_name=class_name,
    )

    return create_node_from_archive(
        archive,
        name_map,
        summary,
        export_map,
        import_map,
        node_export,
        base_node,
        raw_properties=raw_properties if raw_properties else None,
    )
