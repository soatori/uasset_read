"""Typed Blueprint/Kismet/Material analysis IR (plan Task 6+).

Document-boundary projections are dictionaries; these dataclasses stay
internal to the parser/analysis layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from uasset_read.models.byte_ranges import ByteRegion, OpaqueRegion, project_region
from uasset_read.models.diagnostics import Diagnostic

if TYPE_CHECKING:
    from uasset_read.parsers.blueprint.bytecode import BytecodeInstruction
    from uasset_read.parsers.blueprint.control_flow import ControlFlowGraph


@dataclass(frozen=True)
class OpaqueOperand:
    """Lossless fallback operand for consumed-but-unprojectable payload.

    Shared by nested expression records, normalized instructions, and native
    field reflection so every parser uses one opaque-value type.
    """

    role: str
    source_range: ByteRegion | None
    payload_ref: str | None
    reason: str


@dataclass(frozen=True)
class GraphId:
    owner_export_index: int
    graph_export_index: int

    def __str__(self) -> str:
        return f"export:{self.owner_export_index}/export:{self.graph_export_index}"


@dataclass(frozen=True)
class NodeId:
    owner_object_id: str
    node_export_id: str

    def __str__(self) -> str:
        return f"{self.owner_object_id}/{self.node_export_id}"


@dataclass
class K2NodeMetadata:
    node_class: str
    function_name: str | None = None
    event_name: str | None = None
    variable_name: str | None = None
    dispatcher_name: str | None = None
    member_parent: str | None = None
    member_reference: dict[str, Any] | None = None
    opaque_properties: list[OpaqueRegion] = field(default_factory=list)


@dataclass
class BlueprintPin:
    id: str
    name: str
    direction: str
    category: str
    subcategory: str
    default_value: Any | None
    default_object_ref: str | int | None
    default_text: Any | None
    sub_pin_ids: list[str]
    parent_pin_id: str | None
    reference_pass_through_pin_id: str | None
    linked: list[PinLink]
    owner_node_id: NodeId
    raw_region: ByteRegion | None
    unknown_properties: list[OpaqueRegion]
    is_const: bool = False
    is_weak_pointer: bool = False
    is_uobject_wrapper: bool = False


@dataclass
class BlueprintNode:
    id: NodeId
    guid: str | None
    class_name: str
    title: str
    metadata: K2NodeMetadata | None
    pins: list[BlueprintPin]
    raw_region: ByteRegion | None
    unknown_properties: list[OpaqueRegion]


@dataclass(frozen=True)
class PinLinkRef:
    from_node_id: NodeId
    from_pin_guid: str
    to_owner_node_id: NodeId | None
    to_pin_guid: str


@dataclass(frozen=True)
class PinLink:
    from_node_id: NodeId
    from_pin_id: str
    to_node_id: NodeId
    to_pin_id: str
    raw_ref: PinLinkRef


@dataclass
class LinkResolution:
    links: list[PinLink]
    diagnostics: list[Diagnostic]


@dataclass
class BlueprintGraph:
    id: GraphId
    name: str
    kind: Literal[
        "event_graph",
        "function",
        "construction_script",
        "macro",
        "ubergraph",
        "unknown",
    ]
    nodes: list[BlueprintNode]
    parse_errors: list[str]
    raw_region: ByteRegion | None
    truncated: bool = False


def project_opaque(region: OpaqueRegion) -> dict[str, Any]:
    return project_region(region) or {}


def project_pin_link(link: PinLink) -> dict[str, Any]:
    return {
        "from_node_id": str(link.from_node_id),
        "from_pin_id": link.from_pin_id,
        "to_node_id": str(link.to_node_id),
        "to_pin_id": link.to_pin_id,
        "raw_ref": {
            "from_node_id": str(link.raw_ref.from_node_id),
            "from_pin_guid": link.raw_ref.from_pin_guid,
            "to_owner_node_id": (
                str(link.raw_ref.to_owner_node_id)
                if link.raw_ref.to_owner_node_id
                else None
            ),
            "to_pin_guid": link.raw_ref.to_pin_guid,
        },
    }


def project_k2_metadata(metadata: K2NodeMetadata | None) -> dict[str, Any] | None:
    if metadata is None:
        return None
    return {
        "node_class": metadata.node_class,
        "function_name": metadata.function_name,
        "event_name": metadata.event_name,
        "variable_name": metadata.variable_name,
        "dispatcher_name": metadata.dispatcher_name,
        "member_parent": metadata.member_parent,
        "member_reference": metadata.member_reference,
        "opaque_properties": [project_opaque(item) for item in metadata.opaque_properties],
    }


def project_blueprint_graph(graph: BlueprintGraph) -> dict[str, Any]:
    return {
        "id": str(graph.id),
        "name": graph.name,
        "kind": graph.kind,
        "nodes": [
            {
                "id": str(node.id),
                "guid": node.guid,
                "class_name": node.class_name,
                "title": node.title,
                "metadata": project_k2_metadata(node.metadata),
                "pins": [
                    {
                        "id": pin.id,
                        "name": pin.name,
                        "direction": pin.direction,
                        "category": pin.category,
                        "subcategory": pin.subcategory,
                        "default_value": pin.default_value,
                        "default_object_ref": pin.default_object_ref,
                        "default_text": pin.default_text,
                        "sub_pin_ids": list(pin.sub_pin_ids),
                        "parent_pin_id": pin.parent_pin_id,
                        "reference_pass_through_pin_id": pin.reference_pass_through_pin_id,
                        "links": [project_pin_link(link) for link in pin.linked],
                        "is_const": pin.is_const,
                        "is_weak_pointer": pin.is_weak_pointer,
                        "is_uobject_wrapper": pin.is_uobject_wrapper,
                        "unknown_properties": [
                            project_opaque(region) for region in pin.unknown_properties
                        ],
                    }
                    for pin in node.pins
                ],
                "unknown_properties": [
                    project_opaque(region) for region in node.unknown_properties
                ],
            }
            for node in graph.nodes
        ],
        "parse_errors": list(graph.parse_errors),
        "truncated": graph.truncated,
        "source_range": project_region(graph.raw_region),
    }


@dataclass
class FunctionAnalysis:
    """One function/UFunction export's instruction IR and control-flow graph.

    ``object_id`` is the function/UFunction export identity;
    ``owner_object_id`` is the Blueprint/GeneratedClass export that owns it.
    Both are kept because collapsing them to a display name caused the
    attachment bug. Entry correlation (``entrypoint``) is filled by Task 8.
    """

    object_id: str
    owner_object_id: str
    name: str
    function_name: str
    script_source_range: ByteRegion | None
    expression_count: int
    entrypoint: Any | None
    instructions: list[BytecodeInstruction]
    cfg: ControlFlowGraph
    reads: set[str]
    writes: set[str]
    calls: list[str]
    bytecode_status: Literal["parsed", "partial", "unavailable"]
    diagnostics: list[Diagnostic]
