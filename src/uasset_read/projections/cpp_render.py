"""Header/source rendering for Blueprint C++ declaration + migration projection.

Public E1 boundary: ``render_cpp(semantic_dict, mode)``. The only dict→IR
mapper is the private ``_coerce_semantic`` helper. This module never accepts a
``PackageDocument`` and never reopens package bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, get_args

from uasset_read.kismet.native_fields import NativeFieldDeclaration
from uasset_read.models.analysis import (
    BlueprintDeclaration,
    BlueprintGraph,
    BlueprintSemantic,
    CallRecord,
    ComponentRecord,
    MatchMethod,
    ConstructorRecord,
    DispatcherRecord,
    EntrypointRecord,
    ExecChainSummary,
    FunctionAnalysis,
    FunctionDeclaration,
    FunctionParameter,
    VariableAccessRecord,
    VariableDefinition,
    VariableEventRecord,
    region_from_projected,
)
from uasset_read.models.diagnostics import Diagnostic
from uasset_read.parsers.blueprint.control_flow import (
    BasicBlock,
    ControlFlowEdge,
    ControlFlowGraph,
)
from uasset_read.projections.cpp_ast import (
    CppClassDecl,
    CppFunctionDecl,
    CppStmt,
    build_cpp_ast,
)

Mode = Literal["declaration", "migration"]

_STATS_KEYS = (
    "instructions_seen",
    "translated",
    "represented",
    "untranslated",
    "unavailable",
    "declarations",
)


@dataclass(frozen=True)
class CppProjection:
    header_text: str
    source_text: str
    diagnostics: list[Diagnostic]
    translation_stats: dict[str, int]


def _offset_or_none(value: Any) -> int | None:
    """Accept raw ints (0 valid) or E1 structured unset dual-offset dicts."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, dict):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _offset_or_default(value: Any, default: int) -> int:
    got = _offset_or_none(value)
    return default if got is None else got


def _normalize_instruction_dict(raw: dict[str, Any]) -> dict[str, Any]:
    out = dict(raw)
    out["statement_index"] = _offset_or_default(raw.get("statement_index"), 0)
    out["statement_ordinal"] = _offset_or_default(raw.get("statement_ordinal"), 0)
    out["logical_end"] = _offset_or_default(raw.get("logical_end"), 0)
    out["serialized_start"] = _offset_or_default(raw.get("serialized_start"), -1)
    out["serialized_end"] = _offset_or_default(raw.get("serialized_end"), -1)
    jump = raw.get("jump_target_statement_index")
    if isinstance(jump, dict) or jump is False:
        out["jump_target_statement_index"] = None
    return out


def _coerce_param(raw: Any) -> FunctionParameter:
    if not isinstance(raw, dict):
        return FunctionParameter(
            name=str(raw),
            type_name=None,
            cpp_type=None,
            direction="in",
            default_value=None,
            source_range=None,
        )
    direction = raw.get("direction")
    if direction not in {"in", "out", "inout"}:
        direction = "in"  # type: ignore[assignment]
    return FunctionParameter(
        name=str(raw.get("name") or ""),
        type_name=raw.get("type_name"),
        cpp_type=raw.get("cpp_type"),
        direction=direction,  # type: ignore[arg-type]
        default_value=raw.get("default_value"),
        source_range=region_from_projected(raw.get("source_range")),
    )


def _coerce_native_field(raw: Any) -> NativeFieldDeclaration | None:
    if not isinstance(raw, dict) or "type_name" not in raw:
        return None
    inners = []
    for item in raw.get("inner_fields") or []:
        child = _coerce_native_field(item)
        if child is not None:
            inners.append(child)
    return NativeFieldDeclaration(
        type_name=str(raw.get("type_name") or ""),
        name=str(raw.get("name") or ""),
        property_flags=raw.get("property_flags"),
        metadata=raw.get("metadata") if isinstance(raw.get("metadata"), dict) else None,
        array_dim=raw.get("array_dim"),
        element_size=raw.get("element_size"),
        rep_index=raw.get("rep_index"),
        rep_notify_func=raw.get("rep_notify_func"),
        replication_condition=raw.get("replication_condition"),
        references=list(raw.get("references") or []),
        reference_names=list(raw.get("reference_names") or []),
        inner_fields=inners,
        opaque_metadata=[],
        source_range=region_from_projected(raw.get("source_range")),
    )


def _coerce_diagnostic(raw: Any) -> Diagnostic | None:
    if not isinstance(raw, dict):
        return None
    allowed = {
        "severity",
        "code",
        "message",
        "stage",
        "object_id",
        "offset",
        "size",
        "effect",
        "recoverable",
        "fallback",
        "reason",
    }
    payload = {k: v for k, v in raw.items() if k in allowed}
    if "message" not in payload and "code" not in payload:
        return None
    return Diagnostic(**payload)  # type: ignore[arg-type]


def _coerce_semantic(semantic_dict: dict[str, Any]) -> BlueprintSemantic:
    """Private projected-dict → typed IR mapper (sole dict boundary)."""
    if not isinstance(semantic_dict, dict):
        raise TypeError(
            f"render_cpp accepts only an ObjectRecord.semantic dict (E1); got {type(semantic_dict).__name__}"
        )

    declaration_raw = semantic_dict.get("declaration") or {}
    if not isinstance(declaration_raw, dict):
        declaration_raw = {}
    declaration = BlueprintDeclaration(
        class_name=str(declaration_raw.get("class_name") or semantic_dict.get("name") or ""),
        parent_class=(declaration_raw.get("parent_class") or semantic_dict.get("parent_class") or None),
        class_flags=declaration_raw.get("class_flags"),
        metadata=dict(declaration_raw.get("metadata") or {}),
        source_range=region_from_projected(declaration_raw.get("source_range")),
    )

    variables: list[VariableDefinition] = []
    for raw in semantic_dict.get("variable_definitions") or []:
        if not isinstance(raw, dict):
            continue
        variables.append(
            VariableDefinition(
                name=str(raw.get("name") or ""),
                type_name=raw.get("type_name"),
                cpp_type=raw.get("cpp_type"),
                raw_type=raw.get("raw_type") if isinstance(raw.get("raw_type"), dict) else None,
                array_dim=raw.get("array_dim"),
                property_flags=raw.get("property_flags"),
                default_value=raw.get("default_value"),
                object_id=str(raw.get("object_id") or ""),
                source_range=region_from_projected(raw.get("source_range")),
                unresolved=bool(raw.get("unresolved", False)),
            )
        )

    function_declarations: list[FunctionDeclaration] = []
    for raw in semantic_dict.get("function_declarations") or []:
        if not isinstance(raw, dict):
            continue
        native_fields: list[NativeFieldDeclaration] = []
        for item in raw.get("native_fields") or []:
            field = _coerce_native_field(item)
            if field is not None:
                native_fields.append(field)
        function_declarations.append(
            FunctionDeclaration(
                name=str(raw.get("name") or ""),
                return_type=raw.get("return_type"),
                cpp_return_type=raw.get("cpp_return_type"),
                parameters=[_coerce_param(p) for p in raw.get("parameters") or []],
                flags=raw.get("flags"),
                native_fields=native_fields,
                source_range=region_from_projected(raw.get("source_range")),
                unresolved=bool(raw.get("unresolved", False)),
            )
        )

    entrypoints: list[EntrypointRecord] = []
    for raw in semantic_dict.get("entrypoints") or []:
        if isinstance(raw, dict):
            entrypoints.append(EntrypointRecord.from_dict(raw))

    graphs = [BlueprintGraph.from_dict(g) for g in semantic_dict.get("graphs") or [] if isinstance(g, dict)]

    functions: list[FunctionAnalysis] = []
    for raw in semantic_dict.get("functions") or []:
        if not isinstance(raw, dict):
            continue
        normalized = dict(raw)
        if isinstance(raw.get("instructions"), list):
            normalized["instructions"] = [
                _normalize_instruction_dict(ins) if isinstance(ins, dict) else ins for ins in raw["instructions"]
            ]
        cfg_raw = raw.get("cfg")
        if isinstance(cfg_raw, dict):
            cfg = dict(cfg_raw)
            blocks = []
            for block in cfg.get("blocks") or []:
                if not isinstance(block, dict):
                    continue
                block_out = dict(block)
                if isinstance(block.get("instructions"), list):
                    block_out["instructions"] = [
                        _normalize_instruction_dict(ins) if isinstance(ins, dict) else ins
                        for ins in block["instructions"]
                    ]
                blocks.append(block_out)
            cfg["blocks"] = blocks
            normalized["cfg"] = cfg
        functions.append(FunctionAnalysis.from_dict(normalized))

    calls: list[CallRecord] = []
    for raw in semantic_dict.get("calls") or []:
        if not isinstance(raw, dict):
            continue
        method = raw.get("match_method")
        if method not in get_args(MatchMethod):
            method = "unresolved"
        calls.append(
            CallRecord(
                function_name=str(raw.get("function_name") or ""),
                object_id=str(raw.get("object_id") or ""),
                owner_object_id=str(raw.get("owner_object_id") or ""),
                statement_index=_offset_or_none(raw.get("statement_index")),
                source_node_id=raw.get("source_node_id"),
                serialized_start=_offset_or_none(raw.get("serialized_start")),
                serialized_end=_offset_or_none(raw.get("serialized_end")),
                match_method=method,  # type: ignore[arg-type]
                confidence=float(raw.get("confidence") or 0.0),
                unresolved=bool(raw.get("unresolved", True)),
            )
        )

    accesses: list[VariableAccessRecord] = []
    for raw in semantic_dict.get("variable_accesses") or []:
        if not isinstance(raw, dict):
            continue
        access = raw.get("access")
        if access not in {"read", "write", "read_write", "declaration"}:
            access = "read"
        method = raw.get("match_method")
        if method not in get_args(MatchMethod):
            method = "unresolved"
        accesses.append(
            VariableAccessRecord(
                name=str(raw.get("name") or ""),
                access=access,  # type: ignore[arg-type]
                object_id=str(raw.get("object_id") or ""),
                owner_object_id=str(raw.get("owner_object_id") or ""),
                statement_index=_offset_or_none(raw.get("statement_index")),
                source_node_id=raw.get("source_node_id"),
                serialized_start=_offset_or_none(raw.get("serialized_start")),
                serialized_end=_offset_or_none(raw.get("serialized_end")),
                match_method=method,  # type: ignore[arg-type]
                confidence=float(raw.get("confidence") or 0.0),
                unresolved=bool(raw.get("unresolved", True)),
            )
        )

    components = [
        ComponentRecord(
            name=str(c.get("name") or ""),
            class_name=str(c.get("class_name") or ""),
            object_id=str(c.get("object_id") or ""),
        )
        for c in semantic_dict.get("components") or []
        if isinstance(c, dict)
    ]

    dispatchers: list[DispatcherRecord] = []
    for raw in semantic_dict.get("dispatchers") or []:
        if not isinstance(raw, dict):
            continue
        dispatchers.append(
            DispatcherRecord(
                name=str(raw.get("name") or ""),
                object_id=str(raw.get("object_id") or ""),
                parameters=[_coerce_param(p) for p in raw.get("parameters") or []],
                source_range=region_from_projected(raw.get("source_range")),
                unresolved=bool(raw.get("unresolved", False)),
            )
        )

    constructors: list[ConstructorRecord] = []
    for raw in semantic_dict.get("constructors") or []:
        if not isinstance(raw, dict):
            continue
        constructors.append(
            ConstructorRecord(
                name=str(raw.get("name") or ""),
                object_id=str(raw.get("object_id") or ""),
                parent_class=raw.get("parent_class"),
                parent_call=raw.get("parent_call"),
                component_initializers=list(raw.get("component_initializers") or []),
                variable_initializers=list(raw.get("variable_initializers") or []),
                unresolved=bool(raw.get("unresolved", False)),
            )
        )

    variable_events: list[VariableEventRecord] = []
    for raw in semantic_dict.get("variable_events") or []:
        if not isinstance(raw, dict):
            continue
        kind = raw.get("event_kind")
        if kind not in {"on_changed", "on_initialized", "dispatcher", "unknown"}:
            kind = "unknown"
        variable_events.append(
            VariableEventRecord(
                variable_name=str(raw.get("variable_name") or ""),
                dispatcher_name=raw.get("dispatcher_name"),
                object_id=str(raw.get("object_id") or ""),
                source_node_id=raw.get("source_node_id"),
                event_kind=kind,  # type: ignore[arg-type]
                match_method=str(raw.get("match_method") or "unresolved"),
                confidence=float(raw.get("confidence") or 0.0),
                unresolved=bool(raw.get("unresolved", True)),
            )
        )

    control_flow = []

    for cfg in semantic_dict.get("control_flow") or []:
        if not isinstance(cfg, dict):
            continue
        blocks = []
        by_ordinal: dict[int, Any] = {}
        for fn in functions:
            for item in fn.instructions:
                by_ordinal[item.statement_ordinal] = item
        for block_raw in cfg.get("blocks") or []:
            if not isinstance(block_raw, dict):
                continue
            ordinals = block_raw.get("instruction_ordinals") or []
            block_instructions = [by_ordinal[o] for o in ordinals if o in by_ordinal]
            blocks.append(
                BasicBlock(
                    start_statement_index=_offset_or_default(block_raw.get("start_statement_index"), 0),
                    end_statement_index=_offset_or_default(block_raw.get("end_statement_index"), 0),
                    instructions=block_instructions,
                )
            )
        edges = _coerce_edges(cfg.get("edges"))
        control_flow.append(
            ControlFlowGraph(
                blocks=blocks,
                edges=edges,
                entry=_offset_or_default(cfg.get("entry"), 0),
                metadata=dict(cfg.get("metadata") or {}),
            )
        )
    if not control_flow:
        control_flow = [fn.cfg for fn in functions if fn.cfg.blocks]

    exec_raw = semantic_dict.get("exec_chains") or {}
    if not isinstance(exec_raw, dict):
        exec_raw = {}
    edges = _coerce_edges(exec_raw.get("edges"))
    exec_chains = ExecChainSummary(metadata=dict(exec_raw.get("metadata") or {}), edges=edges)

    diagnostics: list[Diagnostic] = []
    for raw in semantic_dict.get("diagnostics") or []:
        diag = _coerce_diagnostic(raw)
        if diag is not None:
            diagnostics.append(diag)

    return BlueprintSemantic(
        object_id=str(semantic_dict.get("object_id") or ""),
        name=str(semantic_dict.get("name") or declaration.class_name),
        parent_class=declaration.parent_class,
        declaration=declaration,
        variable_definitions=variables,
        function_declarations=function_declarations,
        entrypoints=entrypoints,
        graphs=graphs,
        functions=functions,
        calls=calls,
        variable_accesses=accesses,
        components=components,
        dispatchers=dispatchers,
        constructors=constructors,
        variable_events=variable_events,
        control_flow=control_flow,
        exec_chains=exec_chains,
        diagnostics=diagnostics,
    )


def _render_type(type_obj: Any, *, annotate_unresolved: bool = True) -> str:
    name = getattr(type_obj, "name", None) or "unresolved"
    resolved = bool(getattr(type_obj, "resolved", True))
    if not resolved and annotate_unresolved:
        return f"/* unresolved: {name} */ {name}"
    return name


def _function_signature_text(fn: CppFunctionDecl, *, annotate_unresolved: bool = True) -> str:
    params = []
    for p in fn.params:
        prefix = ""
        if p.direction == "out":
            prefix = "/* out */ "
        elif p.direction == "inout":
            prefix = "/* inout */ "
        type_text = _render_type(p.type, annotate_unresolved=annotate_unresolved)
        if getattr(p.type, "is_reference", False) and not type_text.endswith("&"):
            type_text = f"{type_text}&"
        params.append(f"{prefix}{type_text} {p.name}")
    return_type = _render_type(fn.return_type, annotate_unresolved=annotate_unresolved)
    if getattr(fn.return_type, "is_reference", False) and not return_type.endswith("&"):
        return_type = f"{return_type}&"
    joined = ", ".join(params)
    return f"{return_type} {fn.name}({joined})"


def _declaration_count(decl: CppClassDecl) -> int:
    return (
        len(decl.properties)
        + len(decl.functions)
        + len(decl.components)
        + len(decl.dispatchers)
        + len(decl.constructors)
    )


_EDGE_KINDS = {
    "fallthrough",
    "true",
    "false",
    "jump",
    "loop_back",
    "computed_jump",
    "return",
}


def _coerce_edges(raw_edges: Any) -> list[ControlFlowEdge]:
    """Projected CFG/exec edge dicts → typed edges, unknown kinds demoted."""
    edges: list[ControlFlowEdge] = []
    for edge in raw_edges or []:
        if not isinstance(edge, dict):
            continue
        kind = edge.get("kind") or "fallthrough"
        if kind not in _EDGE_KINDS:
            kind = "fallthrough"
        edges.append(
            ControlFlowEdge(
                source_block=_offset_or_default(edge.get("source_block"), 0),
                target_block=_offset_or_default(edge.get("target_block"), 0),
                kind=kind,  # type: ignore[arg-type]
                targets_known=bool(edge.get("targets_known", True)),
            )
        )
    return edges


def _empty_stats() -> dict[str, int]:
    return {key: 0 for key in _STATS_KEYS}


def _render_header(decl: CppClassDecl, diagnostics: list[Diagnostic]) -> str:
    lines: list[str] = []
    lines.append("// uasset_read C++ declaration projection (Blueprint Header View scope)")
    lines.append("// Not a claim of binary/runtime equivalence; unresolved types are explicit.")
    lines.append("UCLASS()")
    lines.append(f"class {decl.name} : public {decl.parent}")
    lines.append("{")
    lines.append("    GENERATED_BODY()")
    lines.append("public:")

    for prop in decl.properties:
        type_text = _render_type(prop.type)
        lines.append("    UPROPERTY()")
        lines.append(f"    {type_text} {prop.name};")

    for component in decl.components:
        type_text = _render_type(component.type)
        lines.append("    UPROPERTY()")
        lines.append(f"    {type_text} {component.name};")

    for dispatcher in decl.dispatchers:
        lines.append("    // event dispatcher (measured declaration; body stays migration scope)")
        lines.append("    UPROPERTY()")
        params = ", ".join(f"{_render_type(p.type)} {p.name}" for p in dispatcher.params)
        lines.append(f"    FMulticastScriptDelegate {dispatcher.name}; // params: [{params}]")

    for fn in decl.functions:
        sig = _function_signature_text(fn, annotate_unresolved=True)
        lines.append("    UFUNCTION()")
        native_sig = getattr(fn, "native_signature", None)
        if native_sig:
            lines.append(f"    // native: {native_sig}")
        lines.append(f"    {sig};")
        if not fn.return_type.resolved:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="cpp_projection_unresolved_return",
                    message=f"unresolved return type for UFUNCTION {fn.name}",
                    stage="projections.cpp.declaration",
                    effect="semantic_loss",
                    recoverable=True,
                    reason="schema_required",
                )
            )
        for p in fn.params:
            if not p.type.resolved:
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="cpp_projection_unresolved_param",
                        message=f"unresolved parameter type {p.name} on UFUNCTION {fn.name}",
                        stage="projections.cpp.declaration",
                        effect="semantic_loss",
                        recoverable=True,
                        reason="schema_required",
                    )
                )

    for ctor in decl.constructors:
        lines.append("    // constructor record (declaration input from construction graph)")
        if ctor.parent_call:
            lines.append(
                f"    {decl.name}(); // parent_call={ctor.parent_call}; components={ctor.component_initializers}"
            )
        else:
            lines.append(f"    {decl.name}(); // parent_call=unresolved; components={ctor.component_initializers}")

    lines.append("};")
    return "\n".join(lines) + "\n"


def _variable_ref_text(value: Any) -> tuple[str | None, str | None]:
    """Return (rendered_text, diagnostic) for one projected operand/expression."""
    if value is None:
        return None, None
    if isinstance(value, (str, int, float, bool)):
        return repr(value) if isinstance(value, str) else str(value), None
    if isinstance(value, dict):
        inst = value.get("Inst") or value.get("opcode")
        if value.get("kind") == "opaque_operand":
            reason = value.get("reason") or value.get("role") or "opaque"
            return f"/* opaque_operand: {reason} */", f"opaque operand ({reason})"
        if inst in {"EX_LocalVariable", "EX_LocalOutVariable", "EX_InstanceVariable", "EX_DefaultVariable"}:
            var = value.get("Variable")
            if isinstance(var, dict):
                segments = var.get("segments") or []
                if segments and isinstance(segments[0], dict):
                    name = segments[0].get("base_name") or segments[0].get("name")
                    if name:
                        return str(name), None
            return f"/* unresolved variable {inst} */", f"unresolved variable reference {inst}"
        if inst in {"EX_True", "EX_False"}:
            return ("true" if inst == "EX_True" else "false"), None
        if inst == "EX_Nothing":
            return "/* nothing */", None
        if inst == "EX_IntConst":
            return str(value.get("value", value.get("Value", "0"))), None
        if inst == "EX_FloatConst":
            return str(value.get("value", value.get("Value", "0.0"))), None
        if inst == "EX_StringConst":
            return f'TEXT("{value.get("value", value.get("Value", ""))}")', None
        if inst == "EX_NameConst":
            return f'FName(TEXT("{value.get("value", value.get("Value", ""))}"))', None
        if inst:
            return f"/* unresolved: {inst} */", f"unsupported expression {inst}"
        return "/* opaque expression */", "expression missing Inst"
    return f"/* unsupported operand {type(value).__name__} */", "unsupported operand type"


def _map_instruction(fn: FunctionAnalysis, instruction: Any) -> CppStmt:
    opcode = str(getattr(instruction, "opcode", "") or "")
    operands = getattr(instruction, "operands", None)
    if not isinstance(operands, dict):
        operands = {}
    call_target = getattr(instruction, "call_target", None)
    jump_target = getattr(instruction, "jump_target_statement_index", None)
    jump_target = _offset_or_none(jump_target) if not isinstance(jump_target, int) else jump_target
    statement_index = _offset_or_none(getattr(instruction, "statement_index", None))
    serialized_start = _offset_or_none(getattr(instruction, "serialized_start", None))
    serialized_end = _offset_or_none(getattr(instruction, "serialized_end", None))
    parse_status = str(getattr(instruction, "parse_status", "parsed") or "parsed")

    if parse_status in {"unavailable", "partial"} and not opcode:
        return CppStmt(
            kind="unavailable",
            text=f"/* unavailable bytecode for {fn.function_name or fn.name} */",
            statement_index=statement_index,
            serialized_start=serialized_start,
            serialized_end=serialized_end,
            function_name=fn.function_name or fn.name,
            object_id=fn.object_id,
            status="unavailable",
            diagnostic=f"bytecode_status={parse_status}",
        )

    if opcode in {"EX_Tracepoint", "EX_WireTracepoint"}:
        return CppStmt(
            kind="instrumentation",
            text=f"/* represented: {opcode} */",
            statement_index=statement_index,
            serialized_start=serialized_start,
            serialized_end=serialized_end,
            function_name=fn.function_name or fn.name,
            object_id=fn.object_id,
            status="represented",
            diagnostic=None,
        )

    if opcode == "EX_EndOfScript":
        return CppStmt(
            kind="end_of_script",
            text="/* represented: end of script */",
            statement_index=statement_index,
            serialized_start=serialized_start,
            serialized_end=serialized_end,
            function_name=fn.function_name or fn.name,
            object_id=fn.object_id,
            status="represented",
            diagnostic=None,
        )

    if opcode == "EX_Return":
        ret_text, ret_diag = _variable_ref_text(operands.get("ReturnValue"))
        if ret_text is None or ret_text == "/* nothing */":
            text = "return;"
            status = "translated"
            diag = None
        elif ret_diag:
            text = f"return {ret_text};"
            status = "represented"
            diag = ret_diag
        else:
            text = f"return {ret_text};"
            status = "translated"
            diag = None
        return CppStmt(
            kind="return",
            text=text,
            statement_index=statement_index,
            serialized_start=serialized_start,
            serialized_end=serialized_end,
            function_name=fn.function_name or fn.name,
            object_id=fn.object_id,
            status=status,
            diagnostic=diag,
        )

    if opcode.startswith("EX_Let"):
        var_text, var_diag = _variable_ref_text(operands.get("variable"))
        val_text, val_diag = _variable_ref_text(operands.get("assignment"))
        if var_text is None:
            var_text = "/* unresolved lhs */"
            var_diag = var_diag or "missing assignment lhs"
        if val_text is None:
            val_text = "/* unresolved rhs */"
            val_diag = val_diag or "missing assignment rhs"
        diag = var_diag or val_diag
        text = f"{var_text} = {val_text};"
        status = "represented" if diag else "translated"
        return CppStmt(
            kind="assign",
            text=text,
            statement_index=statement_index,
            serialized_start=serialized_start,
            serialized_end=serialized_end,
            function_name=fn.function_name or fn.name,
            object_id=fn.object_id,
            status=status,
            diagnostic=diag,
        )

    if opcode == "EX_JumpIfNot":
        cond_text, cond_diag = _variable_ref_text(operands.get("boolean_expression"))
        if cond_text is None:
            cond_text = "/* unresolved condition */"
            cond_diag = cond_diag or "missing boolean_expression"
        target = jump_target if jump_target is not None else "unresolved"
        text = f"if (!({cond_text})) {{ /* jump -> statement {target} */ }}"
        return CppStmt(
            kind="branch",
            text=text,
            statement_index=statement_index,
            serialized_start=serialized_start,
            serialized_end=serialized_end,
            function_name=fn.function_name or fn.name,
            object_id=fn.object_id,
            status="represented",
            diagnostic=cond_diag,
        )

    if opcode in {"EX_Jump", "EX_ComputedJump"}:
        target = jump_target if jump_target is not None else "computed/unresolved"
        return CppStmt(
            kind="jump",
            text=f"/* untranslated: {opcode} -> statement {target} */",
            statement_index=statement_index,
            serialized_start=serialized_start,
            serialized_end=serialized_end,
            function_name=fn.function_name or fn.name,
            object_id=fn.object_id,
            status="untranslated",
            diagnostic=f"control-flow opcode {opcode} not lowered to structured C++",
        )

    if opcode in {
        "EX_FinalFunction",
        "EX_VirtualFunction",
        "EX_CallMath",
        "EX_LocalFinalFunction",
        "EX_LocalVirtualFunction",
    }:
        if call_target:
            text = f"{call_target}(/* migration call projection */);"
            status = "represented"
            diag = None
        else:
            text = f"/* untranslated: {opcode} without resolved call_target */"
            status = "untranslated"
            diag = "call target unresolved"
        return CppStmt(
            kind="call",
            text=text,
            statement_index=statement_index,
            serialized_start=serialized_start,
            serialized_end=serialized_end,
            function_name=fn.function_name or fn.name,
            object_id=fn.object_id,
            status=status,
            diagnostic=diag,
        )

    if not opcode:
        return CppStmt(
            kind="unknown",
            text="/* unavailable: missing opcode */",
            statement_index=statement_index,
            serialized_start=serialized_start,
            serialized_end=serialized_end,
            function_name=fn.function_name or fn.name,
            object_id=fn.object_id,
            status="unavailable",
            diagnostic="instruction missing opcode",
        )

    return CppStmt(
        kind="unsupported",
        text=f"/* untranslated: {opcode} */",
        statement_index=statement_index,
        serialized_start=serialized_start,
        serialized_end=serialized_end,
        function_name=fn.function_name or fn.name,
        object_id=fn.object_id,
        status="untranslated",
        diagnostic=f"no auditable C++ mapping for {opcode}",
    )


def _migration_statements(semantic: BlueprintSemantic) -> tuple[list[CppStmt], dict[str, int]]:
    stats = _empty_stats()
    statements: list[CppStmt] = []
    for fn in semantic.functions:
        instructions = fn.instructions or []
        if fn.bytecode_status == "unavailable" and not instructions:
            stats["instructions_seen"] += 1
            stats["unavailable"] += 1
            statements.append(
                CppStmt(
                    kind="function_unavailable",
                    text=f"/* unavailable: bytecode for {fn.function_name or fn.name} */",
                    function_name=fn.function_name or fn.name,
                    object_id=fn.object_id,
                    status="unavailable",
                    diagnostic="bytecode_status=unavailable",
                )
            )
            continue
        for instruction in instructions:
            stmt = _map_instruction(fn, instruction)
            statements.append(stmt)
            stats["instructions_seen"] += 1
            stats[stmt.status] += 1
    return statements, stats


def _render_source(
    decl: CppClassDecl,
    semantic: BlueprintSemantic,
    statements: list[CppStmt],
    diagnostics: list[Diagnostic] | None = None,
) -> str:
    lines: list[str] = []
    lines.append("// uasset_read C++ migration projection")
    lines.append("// Auditable static reconstruction only — not binary/runtime equivalence.")
    lines.append(f"// class {decl.name} : public {decl.parent}")
    lines.append("")
    by_function: dict[str, list[CppStmt]] = {}
    for stmt in statements:
        key = stmt.function_name or ""
        by_function.setdefault(key, []).append(stmt)

    fn_names = {fn.name for fn in decl.functions} | {fn.function_name or fn.name for fn in semantic.functions}
    for name in sorted(n for n in fn_names if n):
        decl_fn = next((f for f in decl.functions if f.name == name), None)
        if decl_fn is not None:
            if not decl_fn.return_type.resolved:
                sig = _function_signature_text(decl_fn, annotate_unresolved=True)
                lines.append(f"// unresolved return type for {name}")
            else:
                sig = _function_signature_text(decl_fn, annotate_unresolved=False)
            native_sig = getattr(decl_fn, "native_signature", None)
            if native_sig:
                lines.append(f"// native: {native_sig}")
        else:
            # Functions present only in instruction IR must not be typed silent void.
            sig = f"/* unresolved: return_type */ return_type {name}()"
            if diagnostics is not None:
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="cpp_projection_unresolved_return",
                        message=(
                            f"migration function {name} absent from function_declarations; return type left unresolved"
                        ),
                        stage="projections.cpp.migration",
                        effect="semantic_loss",
                        recoverable=True,
                        reason="schema_required",
                    )
                )
        owner = f"{decl.name}::{sig}"
        lines.append(owner)
        lines.append("{")
        stmts = by_function.get(name, [])
        if not stmts:
            lines.append("    /* unavailable: no projected instruction IR */")
        for stmt in stmts:
            idx = stmt.statement_index if stmt.statement_index is not None else "unset"
            start = stmt.serialized_start if stmt.serialized_start is not None else "unset"
            end = stmt.serialized_end if stmt.serialized_end is not None else "unset"
            lines.append(f"    // stmt={idx} serialized=[{start},{end}) status={stmt.status} object={stmt.object_id}")
            if stmt.diagnostic:
                lines.append(f"    // diagnostic: {stmt.diagnostic}")
            lines.append(f"    {stmt.text}")
        lines.append("}")
        lines.append("")

    for ctor in decl.constructors:
        lines.append(f"{decl.name}::{decl.name}()")
        parent_init = f" : {decl.parent}()" if ctor.parent_call else ""
        lines.append(parent_init if parent_init else "")
        lines.append("{")
        if ctor.parent_call:
            lines.append(f"    // represented: parent construction -> {ctor.parent_call}")
        for item in ctor.component_initializers:
            lines.append(f"    // represented: component initializer {item}")
        for item in ctor.variable_initializers:
            lines.append(f"    // represented: variable initializer {item}")
        if not ctor.parent_call and not ctor.component_initializers:
            lines.append("    /* unavailable: constructor body not recovered */")
        lines.append("}")
        lines.append("")

    return "\n".join(lines) + "\n"


def render_cpp_ir(semantic: BlueprintSemantic, mode: Mode) -> CppProjection:
    """Internal typed-IR renderer used by build_cpp_ast consumers and tests."""
    if mode not in {"declaration", "migration"}:
        raise ValueError(f"unsupported cpp projection mode: {mode!r}")

    decl = build_cpp_ast(semantic)
    diagnostics: list[Diagnostic] = list(semantic.diagnostics)
    # Native helper reuse lives in build_cpp_ast / CppFunctionDecl.native_signature.

    header = _render_header(decl, diagnostics)
    stats = _empty_stats()
    stats["declarations"] = _declaration_count(decl)

    if mode == "declaration":
        source_lines = [
            "// declaration-mode projection: migration bodies omitted by mode",
            f"// class {decl.name}",
            "",
        ]
        for fn in decl.functions:
            source_lines.append(f"// {_function_signature_text(fn)};")
            if getattr(fn, "native_signature", None):
                source_lines.append(f"// native: {fn.native_signature}")
        source = "\n".join(source_lines) + "\n"
        # Declaration mode does not walk instructions; invariant 0 == 0+0+0+0 holds.
        return CppProjection(
            header_text=header,
            source_text=source,
            diagnostics=diagnostics,
            translation_stats=stats,
        )

    statements, mig_stats = _migration_statements(semantic)
    for key in _STATS_KEYS:
        if key == "declarations":
            continue
        stats[key] = mig_stats[key]
    # Keep diagnostics for untranslated/unavailable statements explicit.
    for stmt in statements:
        if stmt.status in {"untranslated", "unavailable"} and stmt.diagnostic:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="cpp_projection_instruction_boundary",
                    message=stmt.diagnostic,
                    stage="projections.cpp.migration",
                    object_id=stmt.object_id,
                    effect="semantic_loss",
                    recoverable=True,
                    reason="known_unimplemented",
                )
            )
    source = _render_source(decl, semantic, statements, diagnostics)
    return CppProjection(
        header_text=header,
        source_text=source,
        diagnostics=diagnostics,
        translation_stats=stats,
    )


def render_cpp(semantic_dict: dict[str, Any], mode: Mode) -> CppProjection:
    """Public C++ entry for ObjectRecord.semantic dictionaries (E1)."""
    ir = _coerce_semantic(semantic_dict)
    return render_cpp_ir(ir, mode)


# Re-export for the brief's cpp_ast import path and internal callers.
__all__ = [
    "CppProjection",
    "build_cpp_ast",
    "render_cpp",
    "render_cpp_ir",
]
