"""Typed Blueprint/Kismet/Material analysis IR (plan Task 6+).

Document-boundary projections are dictionaries; these dataclasses stay
internal to the parser/analysis layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, Any, Literal, get_args

from uasset_read.models.byte_ranges import (
    ByteRegion,
    OpaqueRegion,
    SourceSlice,
    project_region,
)
from uasset_read.models.diagnostics import Diagnostic

if TYPE_CHECKING:
    from uasset_read.kismet.native_fields import NativeFieldDeclaration
    from uasset_read.models.document import PackageDocument
    from uasset_read.parsers.blueprint.bytecode import BytecodeInstruction
    from uasset_read.parsers.blueprint.control_flow import ControlFlowEdge, ControlFlowGraph

# Shared validation sets: defined once, checked via get_args(...) at the
# from_dict/projected-dict trust boundaries (tagged/unversioned IR rebuilds).
EntrypointKind = Literal["event", "function", "construction", "dispatcher"]
MatchMethod = Literal["object_id", "function_identity", "source_node", "node_guid", "unresolved"]
BytecodeStatus = Literal["parsed", "partial", "unavailable"]
GraphKind = Literal[
    "event_graph",
    "function",
    "construction_script",
    "macro",
    "ubergraph",
    "state_machine",
    "unknown",
]


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
    is_const: bool = False


@dataclass
class BlueprintNode:
    id: NodeId
    guid: str | None
    class_name: str
    title: str
    metadata: K2NodeMetadata | None
    pins: list[BlueprintPin]
    raw_region: ByteRegion | None
    # Retained serializer-side display fields (plan Task 8): tag-derived
    # node_data and the visual position stay on the typed node so the
    # projected graph keeps every consumed field (E1 lossless projection).
    node_data: dict[str, Any] | None = None
    position: dict[str, Any] | None = None


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
class ExternalReferenceRecord:
    """External (non-package-local) call target with conservative resolution."""

    local_id: str | None
    package: str | None
    class_name: str | None
    symbol: str
    qualified_key: str
    origin: Literal["unreal_engine", "plugin", "project_asset", "unknown_origin"]
    source_evidence: list[dict[str, Any]]
    status: Literal["resolved", "unresolved", "ambiguous"]
    reason: str
    candidate_local_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "local_id": self.local_id,
            "package": self.package,
            "class_name": self.class_name,
            "symbol": self.symbol,
            "qualified_key": self.qualified_key,
            "origin": self.origin,
            "source_evidence": [dict(item) for item in self.source_evidence],
            "status": self.status,
            "reason": self.reason,
            "candidate_local_ids": list(self.candidate_local_ids),
        }


@dataclass
class BlueprintGraph:
    id: GraphId
    name: str
    kind: GraphKind
    nodes: list[BlueprintNode]
    parse_errors: list[str]
    raw_region: ByteRegion | None
    truncated: bool = False
    # Serializer-side provenance retained for the projected graph dict.
    graph_class: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlueprintGraph:
        """Rebuild one typed graph from its frozen-v3 projected dict.

        Only projected keys are consumed; missing ranges stay unresolved
        (``None``). Never reopens package bytes.
        """
        nodes: list[BlueprintNode] = []
        for node_raw in data.get("nodes") or []:
            if not isinstance(node_raw, dict):
                continue
            node_id = _node_id_from_str(str(node_raw.get("id") or ""))
            pins: list[BlueprintPin] = []
            for pin_raw in node_raw.get("pins") or []:
                linked: list[PinLink] = []
                for link_raw in pin_raw.get("links") or []:
                    if not isinstance(link_raw, dict):
                        continue
                    to_node = _node_id_from_str(str(link_raw.get("to_node_id") or ""))
                    to_pin_id = str(link_raw.get("to_pin_id") or "")
                    # The projected link carries the target only; the from-side
                    # identity is the containing node + pin.
                    from_pin_id = str(pin_raw.get("id") or "")
                    linked.append(
                        PinLink(
                            from_node_id=node_id,
                            from_pin_id=from_pin_id,
                            to_node_id=to_node,
                            to_pin_id=to_pin_id,
                            raw_ref=PinLinkRef(
                                from_node_id=node_id,
                                from_pin_guid=from_pin_id,
                                to_owner_node_id=to_node,
                                to_pin_guid=to_pin_id,
                            ),
                        )
                    )
                pins.append(
                    BlueprintPin(
                        id=str(pin_raw.get("id") or ""),
                        name=str(pin_raw.get("name") or ""),
                        direction=str(pin_raw.get("direction") or ""),
                        category=str(pin_raw.get("category") or ""),
                        subcategory=str(pin_raw.get("subcategory") or ""),
                        default_value=pin_raw.get("default_value"),
                        default_object_ref=pin_raw.get("default_object_ref"),
                        default_text=pin_raw.get("default_text"),
                        sub_pin_ids=[str(x) for x in pin_raw.get("sub_pin_ids") or []],
                        parent_pin_id=pin_raw.get("parent_pin_id"),
                        reference_pass_through_pin_id=pin_raw.get("reference_pass_through_pin_id"),
                        linked=linked,
                        owner_node_id=node_id,
                        raw_region=None,
                        is_const=bool(pin_raw.get("is_const") or False),
                    )
                )
            nodes.append(
                BlueprintNode(
                    id=node_id,
                    guid=node_raw.get("guid"),
                    class_name=str(node_raw.get("class_name") or ""),
                    title=str(node_raw.get("title") or ""),
                    metadata=k2_metadata_from_dict(node_raw.get("metadata")),
                    pins=pins,
                    raw_region=None,
                    node_data=(dict(node_raw["node_data"]) if isinstance(node_raw.get("node_data"), dict) else None),
                    position=(dict(node_raw["position"]) if isinstance(node_raw.get("position"), dict) else None),
                )
            )
        kind = data.get("kind") or "unknown"
        allowed_kinds = {
            "event_graph",
            "function",
            "construction_script",
            "macro",
            "ubergraph",
            "state_machine",
            "unknown",
        }
        return cls(
            id=_graph_id_from_str(str(data.get("id") or "")),
            name=str(data.get("name") or ""),
            kind=kind if kind in allowed_kinds else "unknown",  # type: ignore[arg-type]
            nodes=nodes,
            parse_errors=[str(e) for e in data.get("parse_errors") or []],
            raw_region=region_from_projected(data.get("source_range")),
            truncated=bool(data.get("truncated") or False),
            graph_class=str(data.get("graph_class") or ""),
        )


def project_opaque(region: OpaqueRegion) -> dict[str, Any]:
    return project_region(region) or {}


def project_pin_link(link: PinLink) -> dict[str, Any]:
    # The containing pin already carries the from-side identity (owner node +
    # pin id); raw_ref is internal tie-break provenance. Only the resolved
    # target is projected — same information, half the bytes (Task 6 budget
    # rule for large AnimBlueprint pages).
    return {
        "to_node_id": str(link.to_node_id),
        "to_pin_id": link.to_pin_id,
    }


def _project_pin(pin: BlueprintPin) -> dict[str, Any]:
    """Projected pin dict: core identity + links, empty optionals omitted.

    Mirrors the raw decode-pass pin emission (Task 6 budget rule): large
    AnimBlueprint pages stay inside ``project_document`` byte budgets by not
    repeating null optionals for every pin.
    """
    out: dict[str, Any] = {
        "id": pin.id,
        "name": pin.name,
        "direction": pin.direction,
        "category": pin.category,
        "links": [project_pin_link(link) for link in pin.linked],
    }
    if pin.subcategory:
        out["subcategory"] = pin.subcategory
    if pin.default_value is not None:
        out["default_value"] = pin.default_value
    if pin.default_object_ref is not None:
        out["default_object_ref"] = pin.default_object_ref
    if pin.default_text is not None:
        out["default_text"] = pin.default_text
    if pin.sub_pin_ids:
        out["sub_pin_ids"] = list(pin.sub_pin_ids)
    if pin.parent_pin_id is not None:
        out["parent_pin_id"] = pin.parent_pin_id
    if pin.reference_pass_through_pin_id is not None:
        out["reference_pass_through_pin_id"] = pin.reference_pass_through_pin_id
    if pin.is_const:
        out["is_const"] = True
    return out


def _project_node(node: BlueprintNode) -> dict[str, Any]:
    """Projected node dict; null/empty optionals omitted (Task 6 budget rule)."""
    out: dict[str, Any] = {
        "id": str(node.id),
        "class_name": node.class_name,
        "title": node.title,
        "pins": [_project_pin(pin) for pin in node.pins],
    }
    if node.guid:
        out["guid"] = node.guid
    metadata = project_k2_metadata(node.metadata)
    if metadata is not None:
        out["metadata"] = metadata
    if node.node_data is not None:
        out["node_data"] = node.node_data
    if node.position is not None:
        out["position"] = node.position
    return out


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
    node_count = len(graph.nodes)
    pin_count = sum(len(node.pins) for node in graph.nodes)
    edge_count = sum(len(pin.linked) for node in graph.nodes for pin in node.pins)
    return {
        "id": str(graph.id),
        "name": graph.name,
        "kind": graph.kind,
        "graph_class": graph.graph_class,
        "node_count": node_count,
        "pin_count": pin_count,
        "edge_count": edge_count,
        "nodes": [_project_node(node) for node in graph.nodes],
        "parse_errors": list(graph.parse_errors),
        "truncated": graph.truncated,
        "source_range": project_region(graph.raw_region),
    }


def region_from_projected(data: Any) -> ByteRegion | None:
    """Rebuild a ByteRegion from its projected dict (v3 from_dict path).

    Missing ranges stay ``None``; partially projected dicts fall back to the
    fields present so a lossy page never fabricates offsets.
    """
    if not isinstance(data, dict) or data.get("start") is None or data.get("size") is None:
        return None
    slices = tuple(
        SourceSlice(
            source_id=str(item.get("source_id") or "package"),
            source_start=int(item.get("source_start") or 0),
            size=int(item.get("size") or 0),
        )
        for item in data.get("source_slices") or []
        if isinstance(item, dict) and item.get("source_start") is not None
    )
    source_start = data.get("source_start")
    return ByteRegion(
        start=int(data["start"]),
        size=int(data["size"]),
        status=data.get("status") or "decoded",
        source_id=str(data.get("source_id") or "package"),
        source_start=int(source_start) if source_start is not None else None,
        source_slices=slices,
        reason=data.get("reason"),
        feature=str(data.get("feature") or ""),
        payload_ref=data.get("payload_ref"),
    )


def _node_id_from_str(value: str) -> NodeId:
    if "/" in value:
        owner, node = value.split("/", 1)
        return NodeId(owner_object_id=owner, node_export_id=node)
    return NodeId(owner_object_id=value, node_export_id=value)


def _graph_id_from_str(value: str) -> GraphId:
    # Projected form is "export:{owner}/export:{graph}"; tolerate bare ids.
    try:
        owner_part, graph_part = value.split("/", 1)
        owner = int(owner_part.split(":", 1)[1])
        graph = int(graph_part.split(":", 1)[1])
        return GraphId(owner_export_index=owner, graph_export_index=graph)
    except (ValueError, IndexError):
        return GraphId(owner_export_index=-1, graph_export_index=-1)


def k2_metadata_from_dict(data: Any) -> K2NodeMetadata | None:
    if not isinstance(data, dict):
        return None
    opaque: list[ByteRegion] = []
    for item in data.get("opaque_properties") or []:
        region = region_from_projected(item)
        if region is not None:
            opaque.append(region)
    return K2NodeMetadata(
        node_class=str(data.get("node_class") or ""),
        function_name=data.get("function_name"),
        event_name=data.get("event_name"),
        variable_name=data.get("variable_name"),
        dispatcher_name=data.get("dispatcher_name"),
        member_parent=data.get("member_parent"),
        member_reference=data.get("member_reference"),
        opaque_properties=opaque,
    )


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
    bytecode_status: BytecodeStatus
    diagnostics: list[Diagnostic]
    # Signature evidence (already-decoded native FProperty declarations); the
    # correlation layer projects FunctionDeclaration from these.
    native_fields: list[NativeFieldDeclaration] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FunctionAnalysis:
        """Rebuild the typed IR from one frozen-v3 projected function dict.

        Only projected keys are consumed; missing ranges/operands stay
        unresolved/opaque records. This helper never reopens package bytes.
        """
        from uasset_read.parsers.blueprint.bytecode import BytecodeInstruction
        from uasset_read.parsers.blueprint.control_flow import (
            BasicBlock,
            ControlFlowEdge,
            ControlFlowGraph,
        )

        instructions: list[BytecodeInstruction] = []
        for raw in data.get("instructions") or []:
            if not isinstance(raw, dict):
                continue
            instructions.append(
                BytecodeInstruction(
                    statement_index=_projected_offset_int(raw.get("statement_index"), 0),
                    statement_ordinal=_projected_offset_int(raw.get("statement_ordinal"), 0),
                    logical_end=_projected_offset_int(raw.get("logical_end"), 0),
                    serialized_start=_projected_offset_int(raw.get("serialized_start"), -1),
                    serialized_end=_projected_offset_int(raw.get("serialized_end"), -1),
                    opcode=str(raw.get("opcode") or ""),
                    operands=dict(raw.get("operands") or {}),
                    expression=raw.get("expression"),
                    reads=list(raw.get("reads") or []),
                    writes=list(raw.get("writes") or []),
                    call_target=raw.get("call_target"),
                    jump_target_statement_index=(
                        None
                        if isinstance(raw.get("jump_target_statement_index"), dict)
                        else raw.get("jump_target_statement_index")
                    ),
                    jump_kind=raw.get("jump_kind") or "none",
                    source_node_id=raw.get("source_node_id"),
                    parse_status=raw.get("parse_status") or "parsed",
                )
            )
        by_ordinal = {item.statement_ordinal: item for item in instructions}
        cfg_raw = data.get("cfg") or {}
        blocks: list[BasicBlock] = []
        for block_raw in cfg_raw.get("blocks") or []:
            block_instructions = [
                by_ordinal[ord_] for ord_ in block_raw.get("instruction_ordinals") or [] if ord_ in by_ordinal
            ]
            blocks.append(
                BasicBlock(
                    start_statement_index=int(block_raw.get("start_statement_index") or 0),
                    end_statement_index=int(block_raw.get("end_statement_index") or 0),
                    instructions=block_instructions,
                )
            )
        edges = [
            ControlFlowEdge(
                source_block=int(edge.get("source_block") or 0),
                target_block=int(edge.get("target_block") or 0),
                kind=edge.get("kind") or "fallthrough",
                targets_known=bool(edge.get("targets_known", True)),
            )
            for edge in cfg_raw.get("edges") or []
            if isinstance(edge, dict)
        ]
        cfg = ControlFlowGraph(
            blocks=blocks,
            edges=edges,
            entry=int(cfg_raw.get("entry") or 0),
            metadata=dict(cfg_raw.get("metadata") or {}),
        )
        diagnostics = [
            Diagnostic(**{k: v for k, v in raw.items() if k in _DIAGNOSTIC_FIELDS})
            for raw in data.get("diagnostics") or []
            if isinstance(raw, dict)
        ]
        status = data.get("bytecode_status")
        if status not in get_args(BytecodeStatus):
            status = "unavailable"
        entry_raw = data.get("entrypoint")
        entrypoint = EntrypointRecord.from_dict(entry_raw) if isinstance(entry_raw, dict) else None
        return cls(
            object_id=str(data.get("object_id") or ""),
            owner_object_id=str(data.get("owner_object_id") or ""),
            name=str(data.get("name") or data.get("function_name") or ""),
            function_name=str(data.get("function_name") or ""),
            script_source_range=region_from_projected(data.get("source_range")),
            expression_count=(int(c) if (c := data.get("expression_count")) is not None else len(instructions)),
            entrypoint=entrypoint,
            instructions=instructions,
            cfg=cfg,
            reads=set(data.get("reads") or []),
            writes=set(data.get("writes") or []),
            calls=list(data.get("calls") or []),
            bytecode_status=status,  # type: ignore[arg-type]
            diagnostics=diagnostics,
        )


_DIAGNOSTIC_FIELDS = frozenset(f.name for f in fields(Diagnostic))


def _projected_offset_int(value: Any, default: int) -> int:
    """Coerce one projected dual-offset field; 0 is a valid StatementIndex.

    Accepts raw ints (E1 instruction envelope) and structured
    ``{"kind": "unset"}`` values. Never uses ``or`` on the value itself —
    that fabricates -1/0 when the measured offset is legitimately 0.
    """
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, dict):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class BlueprintAnalysisContext:
    """Live typed inputs for one Blueprint-family owner during the package read.

    Passed through the per-package analysis channel so correlation never
    reopens a closed archive or rebuilds a second binary reader.
    """

    owner_object_id: str
    graphs: list[BlueprintGraph]
    functions: list[FunctionAnalysis]


@dataclass(frozen=True)
class BlueprintAnalysisEnvelope:
    """Named package-data channel: assembled envelope + per-owner contexts.

    The Blueprint handler branch accesses ``document``/``contexts`` by
    attribute (named context), never by positional tuple guessing.
    """

    document: PackageDocument
    contexts: dict[str, BlueprintAnalysisContext]


@dataclass(frozen=True)
class EntrypointRecord:
    kind: EntrypointKind
    name: str
    object_id: str
    source_node_id: NodeId | None = None
    match_method: MatchMethod = "unresolved"
    confidence: float = 0.0
    unresolved: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntrypointRecord:
        node_raw = data.get("source_node_id")
        kind = data.get("kind")
        method = data.get("match_method")
        return cls(
            kind=kind if kind in get_args(EntrypointKind) else "event",  # type: ignore[arg-type]
            name=str(data.get("name") or ""),
            object_id=str(data.get("object_id") or ""),
            source_node_id=_node_id_from_str(str(node_raw)) if node_raw else None,
            match_method=(method if method in get_args(MatchMethod) else "unresolved"),  # type: ignore[arg-type]
            confidence=float(data.get("confidence") or 0.0),
            unresolved=bool(data.get("unresolved", True)),
        )


@dataclass(frozen=True)
class CallRecord:
    function_name: str
    object_id: str  # resolved target function/object, when known
    owner_object_id: str  # containing function/UFunction export
    statement_index: int | None
    source_node_id: NodeId | None
    serialized_start: int | None = None
    serialized_end: int | None = None
    match_method: MatchMethod = "unresolved"
    confidence: float = 0.0
    unresolved: bool = True
    execution_mode: Literal["static_reference"] = "static_reference"
    target_ref_key: str | None = None
    source_node_reason: str | None = None


@dataclass(frozen=True)
class VariableAccessRecord:
    name: str
    access: Literal["read", "write", "read_write", "declaration"]
    object_id: str  # resolved variable/property owner, when known
    owner_object_id: str  # containing function/UFunction export
    statement_index: int | None = None
    source_node_id: NodeId | None = None
    serialized_start: int | None = None
    serialized_end: int | None = None
    match_method: MatchMethod = "unresolved"
    confidence: float = 0.0
    unresolved: bool = True
    source_node_reason: str | None = None


@dataclass(frozen=True)
class VariableDefinition:
    name: str
    type_name: str | None
    cpp_type: str | None
    raw_type: dict[str, Any] | None
    array_dim: int | None
    property_flags: int | None
    default_value: Any | None
    object_id: str
    source_range: ByteRegion | None
    unresolved: bool = False


@dataclass(frozen=True)
class FunctionParameter:
    name: str
    type_name: str | None
    cpp_type: str | None
    direction: Literal["in", "out", "inout"]
    default_value: Any | None
    source_range: ByteRegion | None


@dataclass(frozen=True)
class FunctionDeclaration:
    name: str
    return_type: str | None
    cpp_return_type: str | None
    parameters: list[FunctionParameter]
    flags: int | None
    native_fields: list[NativeFieldDeclaration]
    source_range: ByteRegion | None
    unresolved: bool = False


@dataclass(frozen=True)
class BlueprintDeclaration:
    class_name: str
    parent_class: str | None
    class_flags: int | None
    metadata: dict[str, Any]
    source_range: ByteRegion | None


@dataclass(frozen=True)
class ComponentRecord:
    name: str
    class_name: str
    object_id: str


@dataclass(frozen=True)
class DispatcherRecord:
    name: str
    object_id: str
    parameters: list[FunctionParameter]
    source_range: ByteRegion | None
    unresolved: bool = False


@dataclass(frozen=True)
class ConstructorRecord:
    name: str
    object_id: str
    parent_class: str | None
    parent_call: str | None
    component_initializers: list[str]
    variable_initializers: list[str]
    source_node_id: NodeId | None = None
    unresolved: bool = False


@dataclass(frozen=True)
class VariableEventRecord:
    variable_name: str
    dispatcher_name: str | None
    object_id: str
    source_node_id: NodeId | None
    event_kind: Literal["on_changed", "on_initialized", "dispatcher", "unknown"]
    match_method: str
    confidence: float
    unresolved: bool


@dataclass
class ExecChainSummary:
    metadata: dict[str, Any]
    edges: list[ControlFlowEdge]


@dataclass
class BlueprintSemantic:
    object_id: str
    name: str
    parent_class: str | None
    declaration: BlueprintDeclaration
    variable_definitions: list[VariableDefinition]
    function_declarations: list[FunctionDeclaration]
    entrypoints: list[EntrypointRecord]
    graphs: list[BlueprintGraph]
    functions: list[FunctionAnalysis]
    calls: list[CallRecord]
    variable_accesses: list[VariableAccessRecord]
    components: list[ComponentRecord]
    dispatchers: list[DispatcherRecord]
    constructors: list[ConstructorRecord]
    variable_events: list[VariableEventRecord]
    control_flow: list[ControlFlowGraph]
    exec_chains: ExecChainSummary
    diagnostics: list[Diagnostic]
    external_refs: list[ExternalReferenceRecord] = field(default_factory=list)
