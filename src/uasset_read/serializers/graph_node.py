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
from uasset_read.serializers.property_tags import read_property_tag, read_tag_value_bounded
from uasset_read.models.core import UEdGraphNode, UEdGraphPin
from uasset_read.serializers.object_resources import resolve_class_name

from uasset_read.serializers.graph_helpers import (
    seek_to_tag_end,
)
from uasset_read.serializers.graph_pin import read_ue_graph_pin

logger = logging.getLogger(__name__)

# ============================================================================
# 5 Node type readers
# ============================================================================


# ============================================================================
# AnimGraphNode reading
# ============================================================================


def _read_anim_graph_node(
    export_map: list[ObjectExport],
    import_map: list[ObjectImport],
    raw_properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Read AnimGraphNode type node data.

    Key properties:
    - EditorStateMachineGraph: state machine subgraph (UAnimationStateMachineGraph)
    - BoundGraph: state subgraph (UEdGraph)
    """
    result: dict[str, Any] = {}

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

    # Single dispatch path: AnimGraphNode_/AnimState* full-context reader,
    # else tag-derived allow-list projection.
    if class_name.startswith("AnimGraphNode_") or class_name.startswith("AnimState"):
        base_node.node_data = _read_anim_graph_node(
            export_map,
            import_map,
            raw_properties,
        )
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


def _handle_node_comment(archive, tag, name_map, import_map, export_map, raw_properties):
    """Handle NodeComment tag."""
    if tag.size > 0:
        val = archive.read_fstring()
        seek_to_tag_end(archive, tag)
        return {"node_comment": val}
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
        seek_to_tag_end(archive, tag)
    return {}


def _handle_move_mode(archive, tag, name_map, import_map, export_map, raw_properties):
    """Handle MoveMode tag — byte-enum payload is the enum-entry FName
    (comment-node TEnumAsByte<ECommentBoxMode>, PropertyByte.cpp SerializeItem)."""
    enum_name = _read_byte_enum_tag_name(archive, tag, name_map)
    raw_properties[tag.name] = enum_name
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
    "NodeComment": _handle_node_comment,
    "AdvancedPinDisplay": _handle_advanced_pin_display,
    "EditorStateMachineGraph": _handle_package_index,
    "BoundGraph": _handle_package_index,
    "MoveMode": _handle_move_mode,
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
            val = read_tag_value_bounded(archive, tag, archive.read_i32)
        elif kind == "bool":
            val = read_tag_value_bounded(
                archive,
                tag,
                lambda: archive.read_i32() != 0 if tag.size > 0 else tag.bool_val != 0,
            )
        else:
            val = read_tag_value_bounded(archive, tag, lambda: archive.read_name(name_map))
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
        pin_start = archive.tell()
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
                serial_start=pin_start,
            )
        except (ParseError, struct.error, OSError, ValueError, KeyError) as exc:
            # A mid-array pin failure leaves the cursor untrusted: fail the
            # whole node (structured partial node upstream) rather than
            # continue reading garbage pins into a "complete" node.
            raise ParseError(
                f"Pin {len(pins) + 1}/{pins_count} read failed at node {node_name}: {type(exc).__name__}: {exc}"
            ) from exc
        pins.append(pin)

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

        result.update(_read_node_property_tag(archive, tag, name_map, import_map, export_map, result["raw_properties"]))

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
        base_node,
        raw_properties=raw_properties if raw_properties else None,
    )
