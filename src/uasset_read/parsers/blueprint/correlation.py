"""Blueprint graph/bytecode correlation and the E1 semantic projection (Task 8).

``BlueprintCorrelation.build()`` converges typed graph IR, Kismet instruction
IR, object-table identity, imports, and properties into one
``BlueprintSemantic`` for a Blueprint-family owner. The package read path
passes live typed inputs through ``BlueprintAnalysisContext``; the standalone
path consumes the projected ``objects[].semantic`` dictionaries via the frozen
v3 ``from_dict`` helpers. Neither path reopens package bytes.

``project_semantic_blueprint()`` is the document-boundary projector: typed IR
→ JSON-safe dict with the frozen v3 key set (E1). ``ObjectRecord.semantic``
stores only that dictionary, never a live dataclass.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, Iterator, Literal

from uasset_read.models.analysis import (
    BlueprintAnalysisContext,
    BlueprintDeclaration,
    BlueprintGraph,
    BlueprintSemantic,
    CallRecord,
    ComponentRecord,
    ConstructorRecord,
    DispatcherRecord,
    EntrypointRecord,
    ExecChainSummary,
    ExternalReferenceRecord,
    FunctionAnalysis,
    FunctionDeclaration,
    FunctionParameter,
    VariableAccessRecord,
    VariableDefinition,
    VariableEventRecord,
    project_blueprint_graph,
)
from uasset_read.constants import format_guid_fields
from uasset_read.models.byte_ranges import ByteRegion, project_region
from uasset_read.models.diagnostics import Diagnostic
from uasset_read.models.document import PackageDocument
from uasset_read.models.object_model import ObjectRecord
from uasset_read.parsers.blueprint.bytecode import (
    _CALL_OPCODES,
    DEBUG_MAPPING_UNAVAILABLE,
    project_instruction,
    project_operand,
)
from uasset_read.parsers.blueprint.control_flow import project_cfg, project_cfg_edge

if TYPE_CHECKING:
    from uasset_read.models.analysis import NodeId

__all__ = [
    "BlueprintAnalysisContext",
    "BlueprintCorrelation",
    "BlueprintSemantic",
    "project_function_analysis",
    "project_semantic_blueprint",
]

_VAR_OPCODES = frozenset(
    {
        "EX_LocalVariable",
        "EX_InstanceVariable",
        "EX_DefaultVariable",
        "EX_LocalOutVariable",
        "EX_ClassSparseDataVariable",
    }
)
_EVENT_NODE_CLASSES = frozenset({"K2Node_Event", "K2Node_CustomEvent"})
_DISPATCHER_NODE_CLASSES = frozenset({"K2Node_AddDelegate", "K2Node_RemoveDelegate", "K2Node_CallDelegate"})
_FAMILY_CLASSES = frozenset({"Blueprint", "AnimBlueprint", "BlueprintGeneratedClass", "AnimBlueprintGeneratedClass"})
_KINDS = {"blueprint", "anim_blueprint"}


def _pair_key(name: str) -> str:
    """Key joining a Blueprint asset export with its GeneratedClass export."""
    return name[:-2] if name.endswith("_C") else name


def _family_root_key(record: ObjectRecord | None, by_id: dict[str, ObjectRecord]) -> str | None:
    """Pair key of the Blueprint-family root of record's outer chain."""
    current = record
    for _ in range(8):
        if current is None:
            return None
        if (current.class_name or "") in _FAMILY_CLASSES:
            return _pair_key(current.name)
        outer = current.outer_ref
        if outer is None or outer.table != "export":
            return None
        current = by_id.get(f"export:{outer.index}")
    return None


def _is_let_opcode(opcode: str) -> bool:
    return opcode.startswith("EX_Let")


def _region_or_none(value: ByteRegion | None) -> ByteRegion | None:
    return value if isinstance(value, ByteRegion) else None


def _extract_variable_name(value: Any) -> str | None:
    """Display name for a variable reference (typed expr or projected dict)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        if "Variable" in value and not ("Assignment" in value or "Property" in value):
            # Projected EX_*VariableBase: {"Variable": <pointer dict>, ...}
            return _extract_variable_name(value.get("Variable"))
        path = value.get("path")
        if isinstance(path, dict) and isinstance(path.get("path"), list) and path["path"]:
            first = path["path"][0]
            if isinstance(first, dict) and first.get("base_name"):
                return str(first["base_name"])
        segments = value.get("segments")
        if isinstance(segments, list) and segments:
            first = segments[0]
            if isinstance(first, dict) and first.get("base_name"):
                return str(first["base_name"])
        if isinstance(value.get("base_name"), str) and value["base_name"]:
            return value["base_name"]
        if "Variable" in value:
            return _extract_variable_name(value.get("Variable"))
        return None
    # Typed expression: FKismetPropertyPointer or EX_*Variable carrying one.
    pointer = getattr(value, "Variable", None)
    if pointer is not None and pointer is not value:
        if isinstance(pointer, str):
            return pointer or None
        text = str(pointer)
        if text and text != "None" and not text.startswith("<"):
            return text
        nested = _extract_variable_name(pointer)
        if nested:
            return nested
        return None
    text = str(value)
    if not text or text == "None" or text.startswith("<"):
        return None
    return text


def _opcode_of(value: Any) -> str | None:
    """Opcode identity for a typed expression or projected expression dict."""
    if isinstance(value, dict):
        inst = value.get("Inst")
        if isinstance(inst, str) and inst:
            return inst
        if "VirtualFunctionName" in value:
            return "EX_VirtualFunction"
        if "StackNode" in value and "Parameters" in value:
            return "EX_FinalFunction"
        if "AssignmentExpression" in value:
            return "EX_LetValueOnPersistentFrame"
        if "Assignment" in value or ("Property" in value and "Variable" in value):
            return "EX_Let"
        if "Variable" in value:
            # EX_*VariableBase — local vs instance is not recoverable from the
            # projected dict alone; classification stays "variable reference".
            return "EX_LocalVariable"
        return None
    token = getattr(value, "Token", None)
    if token is not None and hasattr(token, "name"):
        return str(token.name)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return type(value).__name__
    return None


def _call_parts(value: Any, opcode: str) -> tuple[str | None, int | None]:
    """(function_name, stack_node) from a call expression (typed or projected)."""
    if isinstance(value, dict):
        name = value.get("VirtualFunctionName") or value.get("Name") or value.get("name")
        stack = value.get("StackNode") or value.get("stack_node")
        if isinstance(name, str) and name:
            return name, stack if isinstance(stack, int) else None
        if isinstance(stack, int) and stack:
            return None, stack
        return None, None
    name = getattr(value, "VirtualFunctionName", None)
    stack = getattr(value, "StackNode", None)
    if isinstance(name, str) and name:
        return name, stack if isinstance(stack, int) else None
    if isinstance(stack, int) and stack:
        return None, stack
    return None, None


_CPF_PARM = 0x0000000000000080  # ufunction_reader/native_fields mirror of UE CPF_Parm
_CPF_RETURN_PARM = 0x0000000000000400  # same table: CPF_ReturnParm
_CPF_OUT_PARM = 0x0000000000000100  # docs/formats/uasset/serialization/uproperty-specifiers.md


def external_ref_record(
    *,
    query: str | None,
    object_id: str,
    match_method: str,
    function_ids_by_name: dict[str, list[str]],
    import_ids_by_name: dict[str, list[str]],
    dep_by_index: dict[int, Any],
    class_by_id: dict[str, str | None],
) -> tuple[ExternalReferenceRecord | None, str | None]:
    """Conservative external-reference record for one resolved call.

    Recomputes candidates from the same tables ``resolve_call`` uses, so a
    name-only first match never hides ambiguity. Same-package exact export
    targets are not external: no record, ``target_ref_key=None``.
    """
    if match_method == "object_id" and object_id.startswith("export:"):
        return None, None
    if match_method == "object_id" and object_id.startswith("import:"):
        index = int(object_id.split(":", 1)[1])
        dep = dep_by_index.get(index)
        package = dep.package_name if dep is not None else None
        class_name = dep.class_name if dep is not None else None
        symbol = (dep.object_name if dep is not None else None) or query or object_id
        local_id: str | None = object_id
        status, reason = "resolved", "exact_package_index"
        candidates = [object_id]
        evidence: list[dict[str, Any]] = [{"kind": "stack_node_package_index", "value": -index - 1}]
    else:
        name = query or ""
        if not name:
            return None, None
        candidates = sorted(set(function_ids_by_name.get(name, []) + import_ids_by_name.get(name, [])))
        if not candidates:
            local_id, status, reason = None, "unresolved", "no_name_match"
        elif len(candidates) == 1:
            local_id, status, reason = candidates[0], "resolved", "unique_name_match"
        else:
            local_id, status, reason = None, "ambiguous", f"{len(candidates)}_name_candidates"
        symbol = name
        dep = dep_by_index.get(int(local_id.split(":", 1)[1])) if local_id and local_id.startswith("import:") else None
        package = dep.package_name if dep is not None else None
        class_name = (dep.class_name if dep is not None else None) or class_by_id.get(local_id or "")
        evidence = [{"kind": "name_query", "value": name}]

    if package and class_name and symbol:
        qualified_key = f"{package}::{class_name}::{symbol}"
    elif local_id and symbol:
        qualified_key = f"{local_id}::{symbol}"
    else:
        qualified_key = f"unresolved::{symbol}"
    origin: str = (
        "project_asset"
        if (package and package.startswith("/Game/")) or (local_id and local_id.startswith("export:"))
        else "unknown_origin"
    )
    return (
        ExternalReferenceRecord(
            local_id=local_id,
            package=package,
            class_name=class_name,
            symbol=symbol,
            qualified_key=qualified_key,
            origin=origin,  # type: ignore[arg-type]
            source_evidence=evidence,
            status=status,  # type: ignore[arg-type]
            reason=reason,
            candidate_local_ids=list(candidates),
        ),
        qualified_key,
    )


class _CallResolver:
    """Identity-first target resolution for call and variable records."""

    def __init__(
        self,
        document: PackageDocument,
        owner: ObjectRecord,
        functions: list[FunctionAnalysis],
        variable_names: set[str],
        component_names: set[str],
    ) -> None:
        self.document = document
        self.owner = owner
        self.functions = functions
        self.variable_names = variable_names
        self.component_names = component_names
        self.export_names: dict[str, str] = {}
        for obj in document.objects:
            if obj.id.startswith("export:"):
                self.export_names[obj.id] = obj.name
        self.import_names: dict[str, str] = {}
        self.import_ids_by_name: dict[str, list[str]] = {}
        for dep in document.dependencies:
            import_id = f"import:{dep.index}"
            self.import_names[import_id] = dep.object_name
            self.import_ids_by_name.setdefault(dep.object_name, []).append(import_id)
        self.function_ids_by_name: dict[str, list[str]] = {}
        for fn in functions:
            if fn.function_name:
                self.function_ids_by_name.setdefault(fn.function_name, []).append(fn.object_id)
        self.diagnostics: list[Diagnostic] = []
        self.dep_by_index: dict[int, Any] = {dep.index: dep for dep in document.dependencies}
        self.class_by_id: dict[str, str | None] = {obj.id: obj.class_name for obj in document.objects}
        self._ref_records: dict[tuple[str | None, str], ExternalReferenceRecord] = {}

    def external_ref(
        self, *, query: str | None, object_id: str, match_method: str
    ) -> tuple[ExternalReferenceRecord | None, str | None]:
        """Deduplicated external-reference record + its stable qualified_key."""
        record, key = external_ref_record(
            query=query,
            object_id=object_id,
            match_method=match_method,
            function_ids_by_name=self.function_ids_by_name,
            import_ids_by_name=self.import_ids_by_name,
            dep_by_index=self.dep_by_index,
            class_by_id=self.class_by_id,
        )
        if record is None or key is None:
            return None, None
        kept = self._ref_records.setdefault((record.local_id, record.qualified_key), record)
        return kept, kept.qualified_key

    def external_refs(self) -> list[ExternalReferenceRecord]:
        return list(self._ref_records.values())

    def resolve_call(
        self, name: str | None, stack_node: int | None
    ) -> tuple[str, str, Literal["object_id", "function_identity", "unresolved"], float, bool]:
        """Return (object_id, function_name, match_method, confidence, unresolved)."""
        if stack_node:
            if stack_node > 0:
                object_id = f"export:{stack_node - 1}"
            else:
                object_id = f"import:{-stack_node - 1}"
            display = self.export_names.get(object_id) or self.import_names.get(object_id) or name
            return (
                object_id,
                display or name or object_id,
                "object_id",
                1.0,
                False,
            )
        if name:
            matches = self.function_ids_by_name.get(name) or []
            if len(matches) == 1:
                return name and matches[0], name, "function_identity", 0.9, False
            if len(matches) > 1:
                self.diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="BLUEPRINT_CALL_NAME_AMBIGUOUS",
                        message=(
                            f"call target {name!r} matches {len(matches)} function "
                            "exports; identity-first attach kept them separate"
                        ),
                        stage="semantic.blueprint.correlation",
                        object_id=self.owner.id,
                        effect="semantic_loss",
                    )
                )
                return matches[0], name, "function_identity", 0.5, False
            imports = self.import_ids_by_name.get(name) or []
            if imports:
                return imports[0], name, "function_identity", 0.7, False
            # No object in this package carries the target (inherited/native
            # parent-class call). Keep an addressable unresolved record.
            return f"unresolved:{name}", name, "unresolved", 0.0, True
        return "", "", "unresolved", 0.0, True

    def resolve_variable(
        self, name: str, fn: FunctionAnalysis
    ) -> tuple[str, Literal["object_id", "unresolved"], float, bool]:
        if name in self.variable_names or name in self.component_names:
            return self.owner.id, "object_id", 0.9, False
        if fn.object_id:
            # Params/locals are declared on the containing function export.
            return fn.object_id, "object_id", 0.7, False
        return "", "unresolved", 0.0, True


def _function_flags(document: PackageDocument, fn: FunctionAnalysis) -> int | None:
    """FunctionFlags from the function export's tagged property bag, if carried."""
    if not fn.object_id.startswith("export:"):
        return None
    record = next((o for o in document.objects if o.id == fn.object_id), None)
    props = record.properties if record is not None else None
    if props is None:
        return None
    entry = props.get("FunctionFlags")
    value = entry.get("value") if isinstance(entry, dict) else entry
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _signature_from_native_fields(
    fields: list[Any],
) -> tuple[str | None, str | None, list[FunctionParameter]]:
    """Return type + parameters from already-decoded native FProperty declarations."""
    from uasset_read.kismet.native_fields import native_field_cpp_type

    if not fields:
        return None, None, []
    return_field = next((f for f in fields if (f.property_flags or 0) & _CPF_RETURN_PARM), None)
    return_type = return_field.type_name if return_field is not None else None
    cpp_return_type = native_field_cpp_type(return_field) if return_field is not None else "void"
    parameters = [
        FunctionParameter(
            name=f.name,
            type_name=f.type_name,
            cpp_type=native_field_cpp_type(f),
            direction=("out" if (f.property_flags or 0) & _CPF_OUT_PARM else "in"),
            default_value=None,
            source_range=None,
        )
        for f in fields
        if (f.property_flags or 0) & _CPF_PARM and not (f.property_flags or 0) & _CPF_RETURN_PARM
    ]
    return return_type, cpp_return_type, parameters


def _json_safe(value: Any) -> Any:
    """Preserve dict/list structure; project model leaves through the frozen v4 shapes.

    ``raw_type`` is copied straight out of the property bag, so its leaves can be
    PropertyValue/PropertyFallback dataclasses that json.dumps and jsonschema reject.
    """
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    from uasset_read.models.properties import project_property_value

    return project_property_value(value)


class BlueprintCorrelation:
    """Multi-level correlation over graphs, bytecode, calls, and variables."""

    def build(
        self,
        document: PackageDocument,
        *,
        analysis_context: BlueprintAnalysisContext | None = None,
    ) -> BlueprintSemantic:
        owner, graphs, functions, seed = self._inputs(document, analysis_context)
        diagnostics: list[Diagnostic] = []
        self._enrich_graphs(document, owner, graphs, diagnostics)

        declaration, parent_class = self._extract_declaration(document, owner, seed)
        variable_definitions = self._extract_variable_definitions(owner)
        components = self._extract_components(document, owner)

        resolver = _CallResolver(
            document,
            owner,
            functions,
            {item.name for item in variable_definitions},
            {item.name for item in components},
        )
        entrypoints = self._correlate_entrypoints(owner, graphs, functions)
        calls: list[CallRecord] = []
        variable_accesses: list[VariableAccessRecord] = []
        for fn in functions:
            fn_calls, fn_accesses = self._analyze_function(fn, resolver)
            calls.extend(fn_calls)
            variable_accesses.extend(fn_accesses)
            # Union walk-derived names back onto the function summary so the
            # projected reads/writes cover nested operand references.
            for access in fn_accesses:
                if access.access in {"read", "read_write"}:
                    fn.reads.add(access.name)
                if access.access in {"write", "read_write"}:
                    fn.writes.add(access.name)
        diagnostics.extend(resolver.diagnostics)
        external_refs = resolver.external_refs()

        dispatchers, variable_events = self._extract_dispatchers(graphs)

        function_declarations = []
        for fn in functions:
            if not fn.function_name:
                continue
            flags = _function_flags(document, fn)
            return_type, cpp_return_type, parameters = _signature_from_native_fields(fn.native_fields)
            function_declarations.append(
                FunctionDeclaration(
                    name=fn.function_name,
                    return_type=return_type,
                    cpp_return_type=cpp_return_type,
                    parameters=parameters,
                    flags=flags,
                    native_fields=list(fn.native_fields),
                    source_range=_region_or_none(fn.script_source_range),
                    unresolved=not fn.native_fields and flags is None,
                )
            )

        constructors, constructor_diags = self._extract_constructors(document, owner, graphs, parent_class, components)
        diagnostics.extend(constructor_diags)

        control_flow = [fn.cfg for fn in functions if fn.cfg.blocks]
        edges = [edge for fn in functions for edge in fn.cfg.edges]
        exec_chains = ExecChainSummary(
            metadata={
                "kind": "direct_exec_edge_summary",
                "edge_count": len(edges),
                "function_count": len(functions),
            },
            edges=edges,
        )

        return BlueprintSemantic(
            object_id=owner.id,
            name=owner.name,
            parent_class=parent_class,
            declaration=declaration,
            variable_definitions=variable_definitions,
            function_declarations=function_declarations,
            entrypoints=entrypoints,
            graphs=graphs,
            functions=functions,
            calls=calls,
            variable_accesses=variable_accesses,
            components=components,
            dispatchers=dispatchers,
            constructors=constructors,
            variable_events=variable_events,
            control_flow=control_flow,
            exec_chains=exec_chains,
            diagnostics=diagnostics,
            external_refs=external_refs,
        )

    # ------------------------------------------------------------------ inputs

    def _inputs(
        self,
        document: PackageDocument,
        analysis_context: BlueprintAnalysisContext | None,
    ) -> tuple[ObjectRecord, list[BlueprintGraph], list[FunctionAnalysis], dict[str, Any]]:
        if analysis_context is not None:
            owner = next(
                (o for o in document.objects if o.id == analysis_context.owner_object_id),
                None,
            )
            if owner is None:
                raise KeyError(f"analysis context owner not in document: {analysis_context.owner_object_id}")
            return (
                owner,
                list(analysis_context.graphs),
                list(analysis_context.functions),
                owner.semantic if isinstance(owner.semantic, dict) else {},
            )
        owner = self._pick_owner(document)
        semantic = owner.semantic if isinstance(owner.semantic, dict) else {}
        graphs = [BlueprintGraph.from_dict(g) for g in semantic.get("graphs") or [] if isinstance(g, dict)]
        functions = [FunctionAnalysis.from_dict(fn) for fn in semantic.get("functions") or [] if isinstance(fn, dict)]
        return owner, graphs, functions, semantic

    @staticmethod
    def _pick_owner(document: PackageDocument) -> ObjectRecord:
        """Standalone entry: prefer the asset export that owns graphs."""
        candidates = [
            o
            for o in document.objects
            if isinstance(o.semantic, dict)
            and o.semantic.get("kind") in _KINDS
            and (o.class_name or "") in _FAMILY_CLASSES
        ]
        if not candidates:
            candidates = [o for o in document.objects if (o.class_name or "") in _FAMILY_CLASSES]
        if not candidates:
            raise KeyError("no Blueprint-family object in document")

        def has_graphs(obj: ObjectRecord) -> bool:
            sem = obj.semantic if isinstance(obj.semantic, dict) else {}
            return bool(sem.get("graphs"))

        def has_functions(obj: ObjectRecord) -> bool:
            sem = obj.semantic if isinstance(obj.semantic, dict) else {}
            return bool(sem.get("functions"))

        def is_asset(obj: ObjectRecord) -> bool:
            return "asset" in obj.roles

        for predicate in (
            lambda o: has_graphs(o) and is_asset(o),
            has_graphs,
            lambda o: has_functions(o) and is_asset(o),
            has_functions,
        ):
            for obj in candidates:
                if predicate(obj):
                    return obj
        return candidates[0]

    def _enrich_graphs(
        self,
        document: PackageDocument,
        owner: ObjectRecord,
        graphs: list[BlueprintGraph],
        diagnostics: list[Diagnostic],
    ) -> None:
        """Adopt raw serializer fields onto typed graphs + strip link artifacts.

        The raw decode pass owns link-resolution diagnostics; the typed
        re-resolution can only report owner-format mismatches for links the raw
        pass already resolved, so those messages are dropped here (they are
        never the graph's own parse_errors).
        """
        for graph in graphs:
            graph.parse_errors = [str(e) for e in graph.parse_errors if not str(e).startswith("pin link ")]

        seed = owner.semantic if isinstance(owner.semantic, dict) else {}
        raw_by_index: dict[int, dict[str, Any]] = {}
        for raw in seed.get("graphs") or []:
            if not isinstance(raw, dict) or not isinstance(raw.get("truncated"), dict):
                continue  # already-projected dict, not the K0/seed raw shape
            try:
                index = int(str(raw.get("id") or "").split(":")[1])
            except (ValueError, IndexError):
                continue
            raw_by_index[index] = raw
        if not raw_by_index:
            return
        for graph in graphs:
            raw = raw_by_index.get(graph.id.graph_export_index)
            if raw is None:
                continue
            kind = raw.get("kind")
            if isinstance(kind, str) and kind:
                graph.kind = kind  # type: ignore[assignment]
            if raw.get("graph_class"):
                graph.graph_class = str(raw["graph_class"])
            raw_nodes = {str(n.get("id") or ""): n for n in raw.get("nodes") or [] if isinstance(n, dict)}
            for node in graph.nodes:
                raw_node = raw_nodes.get(node.id.node_export_id)
                if raw_node is None:
                    continue
                node_data = raw_node.get("node_data")
                node.node_data = dict(node_data) if isinstance(node_data, dict) else None
                position = raw_node.get("position")
                node.position = dict(position) if isinstance(position, dict) else None

    # ------------------------------------------------------------ declarations

    @staticmethod
    def _parent_class_from_properties(document: PackageDocument, owner: ObjectRecord) -> str | None:
        props = owner.properties
        if props is None:
            return None
        entry = props.get("ParentClass")
        if not isinstance(entry, dict):
            return None
        value = entry.get("value")
        if isinstance(value, dict):
            name = value.get("object_name")
            if isinstance(name, str) and name:
                return name
            name = value.get("name")
            if isinstance(name, str) and name:
                return name
            return None
        if isinstance(value, int) and value > 0:
            target = document.objects[value - 1] if 0 < value <= len(document.objects) else None
            return target.name if target is not None else None
        if isinstance(value, str) and value:
            return value
        return None

    def _extract_declaration(
        self,
        document: PackageDocument,
        owner: ObjectRecord,
        seed: dict[str, Any],
    ) -> tuple[BlueprintDeclaration, str | None]:
        parent = self._parent_class_from_properties(document, owner)
        # Interfaces: seed channel on the package path; projected declaration
        # metadata on the standalone path — never recomputed from bytes.
        interfaces: list[Any] = []
        if "declaration" in seed and isinstance(seed["declaration"], dict):
            metadata = seed["declaration"].get("metadata")
            if isinstance(metadata, dict):
                interfaces = list(metadata.get("interfaces") or [])
        else:
            interfaces = list(seed.get("interfaces") or [])
        class_flags: int | None = None
        props = owner.properties
        if props is not None:
            flags_entry = props.get("ClassFlags")
            if isinstance(flags_entry, dict) and isinstance(flags_entry.get("value"), int):
                class_flags = flags_entry["value"]
        declaration = BlueprintDeclaration(
            class_name=owner.name,
            parent_class=parent,
            class_flags=class_flags,
            metadata={"interfaces": interfaces},
            source_range=_region_or_none(owner.serial_region),
        )
        return declaration, parent

    @staticmethod
    def _iter_property_structs(value: Any) -> Iterator[dict[str, Any]]:
        if isinstance(value, dict) and "value" in value:
            value = value.get("value")
        if not isinstance(value, list):
            return
        for item in value:
            if not isinstance(item, dict):
                continue
            fields = item.get("fields")
            yield fields if isinstance(fields, dict) else item

    def _extract_variable_definitions(self, owner: ObjectRecord) -> list[VariableDefinition]:
        props = owner.properties
        if props is None:
            return []
        raw = props.get("NewVariables")
        if raw is None:
            return []
        definitions: list[VariableDefinition] = []
        for fields in self._iter_property_structs(raw):
            name = fields.get("VarName")
            if not isinstance(name, str) or not name:
                continue
            vt_raw = fields.get("VarType")
            vt_fields: dict[str, Any] | None = None
            if isinstance(vt_raw, dict):
                # #654 four-shape matrix: flat pin dict (A) and the
                # kind="struct" / "struct_binary_decoded" wrappers (B/C) all
                # resolve to pin fields here (a wrapper contributes its nested
                # "fields", a flat dict is used as-is). A PropertyFallback
                # model object never reaches this branch — isinstance dict is
                # False and vt_fields stays None, so only type_name is None.
                nested = vt_raw.get("fields")
                candidate = nested if isinstance(nested, dict) else vt_raw
                vt_fields = dict(candidate)
            guid = format_guid_fields((fields.get("VarGuid") or {}).get("fields"))
            # N4 (#654 review): raw_type carries the unwrapped pin fields;
            # wrapper evidence (kind/struct_type/size) is intentionally not
            # duplicated — type_name already holds the resolved answer, and
            # _json_safe keeps raw_type leaves JSON-projectable for the v4
            # envelope (PropertyValue/PropertyFallback dataclasses project
            # through the frozen v4 shapes).
            raw_type: dict[str, Any] = {"VarType": _json_safe(vt_fields), "VarGuid": guid}
            pin_category = (vt_fields or {}).get("pin_category")
            type_name = pin_category if isinstance(pin_category, str) and pin_category else None
            pin_sub = (vt_fields or {}).get("pin_subcategory")
            if type_name and pin_sub:
                type_name = f"{type_name}:{pin_sub}"
            property_flags = fields.get("PropertyFlags")
            definitions.append(
                VariableDefinition(
                    name=name,
                    type_name=type_name,
                    cpp_type=None,
                    raw_type=raw_type,
                    array_dim=None,
                    property_flags=property_flags if isinstance(property_flags, int) else None,
                    default_value=fields.get("DefaultValue"),
                    object_id=owner.id,
                    source_range=None,
                    # #654: unresolved must cover the type, not just name/guid —
                    # a definition whose VarType never decoded claims nothing.
                    unresolved=type_name is None,
                )
            )
        return definitions

    def _extract_components(self, document: PackageDocument, owner: ObjectRecord) -> list[ComponentRecord]:
        by_id = {o.id: o for o in document.objects}
        scope = _family_root_key(owner, by_id)
        if scope is None:
            return []
        records: list[ComponentRecord] = []
        for obj in document.objects:
            if obj.class_name != "SCS_Node" or not obj.properties:
                continue
            if _family_root_key(obj, by_id) != scope:
                continue
            props = obj.properties
            comp = props.get("ComponentTemplate")
            comp_value = comp.get("value") if isinstance(comp, dict) else None
            if isinstance(comp_value, dict):
                name = comp_value.get("object_name") or comp_value.get("name") or obj.name
            elif isinstance(comp_value, int) and comp_value > 0:
                # FPackageIndex (1-based) into the export table: the component
                # template export carries the display name.
                target = next(
                    (o for o in document.objects if o.table_index == comp_value - 1),
                    None,
                )
                name = target.name if target is not None else obj.name
            else:
                name = obj.name
            cclass = props.get("ComponentClass")
            cclass_value = cclass.get("value") if isinstance(cclass, dict) else None
            type_name = cclass_value.get("object_name", "") if isinstance(cclass_value, dict) else ""
            records.append(ComponentRecord(name=str(name), class_name=str(type_name), object_id=obj.id))
        records.sort(key=lambda item: item.object_id)
        return records

    # -------------------------------------------------------------- correlates

    def _correlate_entrypoints(
        self,
        owner: ObjectRecord,
        graphs: list[BlueprintGraph],
        functions: list[FunctionAnalysis],
    ) -> list[EntrypointRecord]:
        entrypoints: list[EntrypointRecord] = []
        for fn in functions:
            record = EntrypointRecord(
                kind="function",
                name=fn.function_name or fn.name,
                object_id=fn.object_id,
                match_method="object_id",
                confidence=1.0,
                unresolved=False,
            )
            fn.entrypoint = record
            entrypoints.append(record)
        for graph in graphs:
            if graph.kind == "construction_script" or graph.name == "UserConstructionScript":
                entrypoints.append(
                    EntrypointRecord(
                        kind="construction",
                        name=graph.name or "UserConstructionScript",
                        object_id=owner.id,
                        match_method="object_id",
                        confidence=0.9,
                        unresolved=False,
                    )
                )
            for node in graph.nodes:
                meta = node.metadata
                is_event = node.class_name in _EVENT_NODE_CLASSES or (meta is not None and bool(meta.event_name))
                if is_event:
                    name = (meta.event_name if meta else None) or node.title
                    entrypoints.append(
                        EntrypointRecord(
                            kind="event",
                            name=name,
                            object_id=node.id.node_export_id,
                            source_node_id=node.id,
                            match_method="source_node",
                            confidence=0.9,
                            unresolved=not bool(name),
                        )
                    )
                elif node.class_name in _DISPATCHER_NODE_CLASSES:
                    name = (meta.dispatcher_name if meta else None) or node.title
                    entrypoints.append(
                        EntrypointRecord(
                            kind="dispatcher",
                            name=name,
                            object_id=node.id.node_export_id,
                            source_node_id=node.id,
                            match_method="source_node",
                            confidence=0.9,
                            unresolved=not bool(meta and meta.dispatcher_name),
                        )
                    )
        return entrypoints

    def _extract_dispatchers(
        self, graphs: list[BlueprintGraph]
    ) -> tuple[list[DispatcherRecord], list[VariableEventRecord]]:
        dispatchers: list[DispatcherRecord] = []
        events: list[VariableEventRecord] = []
        seen: set[str] = set()
        for graph in graphs:
            for node in graph.nodes:
                meta = node.metadata
                if node.class_name in _DISPATCHER_NODE_CLASSES and meta is not None:
                    dispatcher_name = meta.dispatcher_name
                    if dispatcher_name and dispatcher_name not in seen:
                        seen.add(dispatcher_name)
                        dispatchers.append(
                            DispatcherRecord(
                                name=dispatcher_name,
                                object_id=node.id.node_export_id,
                                parameters=[],
                                source_range=None,
                                unresolved=False,
                            )
                        )
                    events.append(
                        VariableEventRecord(
                            variable_name=meta.variable_name or "",
                            dispatcher_name=dispatcher_name,
                            object_id=node.id.node_export_id,
                            source_node_id=node.id,
                            event_kind="dispatcher" if dispatcher_name else "unknown",
                            match_method="source_node",
                            confidence=0.9 if dispatcher_name else 0.0,
                            unresolved=not bool(dispatcher_name),
                        )
                    )
        return dispatchers, events

    def _extract_constructors(
        self,
        document: PackageDocument,
        owner: ObjectRecord,
        graphs: list[BlueprintGraph],
        parent_class: str | None,
        components: list[ComponentRecord],
    ) -> tuple[list[ConstructorRecord], list[Diagnostic]]:
        diagnostics: list[Diagnostic] = []
        generated_class = next(
            (rel.from_id for rel in document.relations if rel.kind == "generated_class_of" and rel.to_id == owner.id),
            None,
        )
        ucs = next(
            (
                graph
                for graph in graphs
                if graph.kind == "construction_script" or graph.name == "UserConstructionScript"
            ),
            None,
        )
        if generated_class is None and ucs is None:
            return [], diagnostics
        target_id = generated_class or owner.id
        super_rel = next(
            (rel for rel in document.relations if rel.kind == "super_of" and rel.from_id == target_id),
            None,
        )
        if super_rel is None and generated_class is not None:
            super_rel = next(
                (rel for rel in document.relations if rel.kind == "super_of" and rel.from_id == owner.id),
                None,
            )
        parent_call = parent_class
        if super_rel is not None and parent_call is None:
            if super_rel.to_id.startswith("export:"):
                index = int(super_rel.to_id.split(":")[1])
                if 0 <= index < len(document.objects):
                    parent_call = document.objects[index].name
        unresolved = ucs is None
        if unresolved:
            diagnostics.append(
                Diagnostic(
                    severity="info",
                    code="BLUEPRINT_CONSTRUCTION_SOURCE_ABSENT",
                    message=(
                        f"{owner.id}: construction record built from generated-class "
                        "evidence only; no UserConstructionScript graph decoded"
                    ),
                    stage="semantic.blueprint.correlation",
                    object_id=owner.id,
                    effect=None,
                )
            )
        return (
            [
                ConstructorRecord(
                    name="UserConstructionScript" if ucs is not None else "ConstructionScript",
                    object_id=target_id,
                    parent_class=parent_class,
                    parent_call=parent_call,
                    component_initializers=[item.name for item in components],
                    variable_initializers=[],
                    source_node_id=None,
                    unresolved=unresolved,
                )
            ],
            diagnostics,
        )

    # ------------------------------------------------------- calls + variables

    def _analyze_function(
        self, fn: FunctionAnalysis, resolver: _CallResolver
    ) -> tuple[list[CallRecord], list[VariableAccessRecord]]:
        walker = _InstructionWalker(fn, resolver)
        for instruction in fn.instructions:
            walker.visit_instruction(instruction)
        return walker.calls, walker.accesses


class _InstructionWalker:
    """One recursive visitor over instruction expressions + projected operands."""

    # Statement context for nested (operand-only) emissions.
    _current_statement: int = 0
    _current_start: int | None = None
    _current_end: int | None = None
    _current_source: Any | None = None

    def __init__(self, fn: FunctionAnalysis, resolver: _CallResolver) -> None:
        self.fn = fn
        self.resolver = resolver
        self.calls: list[CallRecord] = []
        self.accesses: list[VariableAccessRecord] = []
        self._call_keys: set[tuple[int, str, str]] = set()
        self._access_keys: set[tuple[int, str, str]] = set()

    def visit_instruction(self, instruction: Any) -> None:
        self._current_statement = instruction.statement_index
        self._current_start = instruction.serialized_start if instruction.serialized_start >= 0 else None
        self._current_end = instruction.serialized_end if instruction.serialized_end >= 0 else None
        self._current_source = _source_node(instruction)
        expression = instruction.expression
        if expression is not None and expression != {}:
            self._visit(expression, root_opcode=instruction.opcode)
        else:
            self._emit_from_operands(instruction)
        # Operand pass covers role-wrapped payloads the expression tree may
        # not retain (deduplicated against the expression walk).
        operands = instruction.operands
        if isinstance(operands, dict):
            for key, value in operands.items():
                if key in {"variable", "property", "destination_property"}:
                    # Destination of a Let — handled via the Let branch on the
                    # expression tree; visiting standalone would fake a read.
                    continue
                self._visit(
                    value, root_opcode=instruction.opcode if key in {"assignment", "boolean_expression"} else None
                )

    def _emit_from_operands(self, instruction: Any) -> None:
        opcode = instruction.opcode
        if opcode in _CALL_OPCODES:
            name = instruction.operands.get("name")
            stack = instruction.operands.get("stack_node")
            self._emit_call(
                name if isinstance(name, str) else None,
                stack if isinstance(stack, int) else None,
                instruction,
            )
        elif _is_let_opcode(opcode):
            dest = _extract_variable_name(instruction.operands.get("variable")) or _extract_variable_name(
                instruction.operands.get("destination_property")
            )
            if dest:
                self._emit_access(dest, "write", instruction)
            assignment = instruction.operands.get("assignment")
            if assignment is None:
                assignment = instruction.operands.get("assignment_expression")
            self._visit(assignment, root_opcode=None)

    def _visit(self, value: Any, *, root_opcode: str | None) -> None:
        if value is None:
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                self._visit(item, root_opcode=None)
            return
        if isinstance(value, (str, int, float, bool, bytes)):
            return
        if isinstance(value, dict):
            self._visit_dict(value, root_opcode=root_opcode)
            return
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            self._visit_dataclass(value, root_opcode=root_opcode)
            return
        # Opaque non-dataclass object (e.g. property pointer leaf): ignore.
        return

    def _visit_dict(self, value: dict[str, Any], *, root_opcode: str | None) -> None:
        opcode = _opcode_of(value) or root_opcode
        if opcode is not None and opcode in _CALL_OPCODES:
            name, stack = _call_parts(value, opcode)
            self._emit_call(name, stack, None, dict_operands=value)
            for param in value.get("Parameters") or []:
                self._visit(param, root_opcode=None)
            return
        if opcode is not None and _is_let_opcode(opcode):
            dest = _extract_variable_name(value.get("Variable")) or _extract_variable_name(
                value.get("DestinationProperty") or value.get("destination_property")
            )
            if dest:
                self._emit_access(dest, "write", None, dict_operands=value)
            for key in ("Assignment", "AssignmentExpression", "assignment", "assignment_expression"):
                if key in value:
                    self._visit(value.get(key), root_opcode=None)
            for key in ("parameters", "Parameters", "boolean_expression", "BooleanExpression"):
                if key in value:
                    self._visit(value.get(key), root_opcode=None)
            return
        if opcode is not None and opcode in _VAR_OPCODES:
            name = _extract_variable_name(value)
            if name:
                self._emit_access(
                    name,
                    "read",
                    None,
                    dict_operands=value,
                )
            return
        # Unknown dict: recurse into containers only (never scalars).
        for key, item in value.items():
            if key in {"raw_region", "StatementIndex", "SerializedStart", "SerializedEnd"}:
                continue
            self._visit(item, root_opcode=None)

    def _visit_dataclass(self, value: Any, *, root_opcode: str | None) -> None:
        opcode = _opcode_of(value) or root_opcode
        if opcode is not None and opcode in _CALL_OPCODES:
            name, stack = _call_parts(value, opcode)
            self._emit_call(name, stack, None, typed=value)
            for param in getattr(value, "Parameters", None) or []:
                self._visit(param, root_opcode=None)
            return
        if opcode is not None and _is_let_opcode(opcode):
            dest = _extract_variable_name(getattr(value, "Variable", None)) or _extract_variable_name(
                getattr(value, "DestinationProperty", None)
            )
            if dest:
                self._emit_access(dest, "write", None, typed=value)
            for attr in ("Assignment", "AssignmentExpression"):
                if hasattr(value, attr):
                    self._visit(getattr(value, attr), root_opcode=None)
            for attr in ("Parameters", "BooleanExpression"):
                if hasattr(value, attr):
                    self._visit(getattr(value, attr), root_opcode=None)
            return
        if opcode is not None and opcode in _VAR_OPCODES:
            name = _extract_variable_name(value)
            if name:
                self._emit_access(name, "read", None, typed=value)
            return
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            for field in dataclasses.fields(value):
                if field.name in {
                    "StatementIndex",
                    "SerializedStart",
                    "SerializedEnd",
                    "Token",
                }:
                    continue
                self._visit(getattr(value, field.name, None), root_opcode=None)
        return

    def _emit_call(
        self,
        name: str | None,
        stack: int | None,
        instruction: Any,
        *,
        dict_operands: dict[str, Any] | None = None,
        typed: Any | None = None,
    ) -> None:
        if instruction is not None:
            stmt = instruction.statement_index
            start = instruction.serialized_start if instruction.serialized_start >= 0 else None
            end = instruction.serialized_end if instruction.serialized_end >= 0 else None
            source = _source_node(instruction)
            fallback_name = instruction.call_target
            stack = stack if stack is not None else _int_or_none((instruction.operands or {}).get("stack_node"))
            name = name or _str_or_none((instruction.operands or {}).get("name"))
        else:
            stmt = self._current_statement
            start = self._current_start
            end = self._current_end
            source = self._current_source
            fallback_name = None
            if typed is not None:
                stack = stack if stack is not None else _int_or_none(getattr(typed, "StackNode", None))
                name = name or _str_or_none(getattr(typed, "VirtualFunctionName", None))
            if dict_operands is not None:
                stack = stack if stack is not None else _int_or_none(dict_operands.get("StackNode"))
                name = name or _str_or_none(dict_operands.get("VirtualFunctionName") or dict_operands.get("Name"))
        # A name-shaped call_target (not an export/import id) is a usable
        # fallback for name-based resolution.
        target_name = name
        if target_name is None and isinstance(fallback_name, str):
            if not fallback_name.startswith(("export:", "import:", "unresolved:")):
                target_name = fallback_name
        object_id, resolved_name, method, confidence, unresolved = self.resolver.resolve_call(target_name, stack)
        _ref, ref_key = self.resolver.external_ref(query=target_name, object_id=object_id, match_method=method)
        function_name = resolved_name or name or fallback_name
        if not function_name:
            function_name = f"{self.fn.function_name}@{stmt}"
        key = (stmt, function_name, object_id)
        if key in self._call_keys:
            return
        self._call_keys.add(key)
        self.calls.append(
            CallRecord(
                function_name=function_name,
                object_id=object_id,
                owner_object_id=self.fn.object_id,
                statement_index=stmt,
                source_node_id=source,
                serialized_start=start,
                serialized_end=end,
                match_method=method,
                confidence=confidence,
                unresolved=unresolved,
                target_ref_key=ref_key,
                source_node_reason=(None if source is not None else DEBUG_MAPPING_UNAVAILABLE),
            )
        )

    def _emit_access(
        self,
        name: str,
        access: Literal["read", "write", "read_write"],
        instruction: Any,
        *,
        dict_operands: dict[str, Any] | None = None,
        typed: Any | None = None,
    ) -> None:
        if instruction is not None:
            stmt = instruction.statement_index
            start = instruction.serialized_start if instruction.serialized_start >= 0 else None
            end = instruction.serialized_end if instruction.serialized_end >= 0 else None
            source = _source_node(instruction)
        else:
            stmt = self._current_statement
            start = self._current_start
            end = self._current_end
            source = self._current_source
        object_id, method, confidence, unresolved = self.resolver.resolve_variable(name, self.fn)
        key = (stmt, name, access)
        if key in self._access_keys:
            return
        self._access_keys.add(key)
        self.accesses.append(
            VariableAccessRecord(
                name=name,
                access=access,
                object_id=object_id,
                owner_object_id=self.fn.object_id,
                statement_index=stmt,
                source_node_id=source,
                serialized_start=start,
                serialized_end=end,
                match_method=method,
                confidence=confidence,
                unresolved=unresolved,
                source_node_reason=(None if source is not None else DEBUG_MAPPING_UNAVAILABLE),
            )
        )


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _source_node(instruction: Any) -> NodeId | None:
    raw = getattr(instruction, "source_node_id", None)
    if not raw:
        return None
    from uasset_read.models.analysis import NodeId

    text = str(raw)
    if "/" in text:
        owner, node = text.split("/", 1)
        return NodeId(owner_object_id=owner, node_export_id=node)
    return NodeId(owner_object_id=text, node_export_id=text)


# ---------------------------------------------------------------- projections


def project_function_analysis(fn: FunctionAnalysis) -> dict[str, Any]:
    # Keep expression_count and entrypoint at the top level so
    # tests/fixtures.find_function and Task 12 gates can read them without
    # walking the instruction list.
    return {
        "function_name": fn.function_name,
        "name": fn.name,
        "object_id": fn.object_id,
        "owner_object_id": fn.owner_object_id,
        "source_range": project_region(fn.script_source_range),
        "expression_count": fn.expression_count,
        "entrypoint": (
            {
                "kind": fn.entrypoint.kind,
                "name": fn.entrypoint.name,
                "object_id": fn.entrypoint.object_id,
                "source_node_id": (str(fn.entrypoint.source_node_id) if fn.entrypoint.source_node_id else None),
                "match_method": fn.entrypoint.match_method,
                "confidence": fn.entrypoint.confidence,
                "unresolved": fn.entrypoint.unresolved,
            }
            if fn.entrypoint
            else None
        ),
        "instructions": [project_instruction(i) for i in fn.instructions],
        "cfg": project_cfg(fn.cfg),
        "reads": sorted(fn.reads),
        "writes": sorted(fn.writes),
        "calls": list(fn.calls),
        # Same static-content emission as function_declarations[].native_fields:
        # normal-mode signature evidence, never debug evidence.
        "native_fields": [project_operand(field) for field in fn.native_fields],
        "bytecode_status": fn.bytecode_status,
        "diagnostics": [d.to_dict() for d in fn.diagnostics],
    }


def project_semantic_blueprint(
    semantic: BlueprintSemantic, *, kind: Literal["blueprint", "anim_blueprint"] = "blueprint"
) -> dict[str, Any]:
    """Typed IR → document-boundary dict. Frozen key set for format_version 4.0."""
    return {
        "kind": kind,
        "object_id": semantic.object_id,
        "name": semantic.name,
        "parent_class": semantic.parent_class,
        "declaration": {
            "class_name": semantic.declaration.class_name,
            "parent_class": semantic.declaration.parent_class,
            "class_flags": semantic.declaration.class_flags,
            "metadata": semantic.declaration.metadata,
            "source_range": project_region(semantic.declaration.source_range),
        },
        "variable_definitions": [
            {
                "name": item.name,
                "type_name": item.type_name,
                "cpp_type": item.cpp_type,
                "raw_type": item.raw_type,
                "array_dim": item.array_dim,
                "property_flags": item.property_flags,
                "default_value": project_operand(item.default_value),
                "object_id": item.object_id,
                "source_range": project_region(item.source_range),
                "unresolved": item.unresolved,
            }
            for item in semantic.variable_definitions
        ],
        "function_declarations": [
            {
                "name": item.name,
                "return_type": item.return_type,
                "cpp_return_type": item.cpp_return_type,
                "parameters": [
                    {
                        "name": param.name,
                        "type_name": param.type_name,
                        "cpp_type": param.cpp_type,
                        "direction": param.direction,
                        "default_value": project_operand(param.default_value),
                        "source_range": project_region(param.source_range),
                    }
                    for param in item.parameters
                ],
                "flags": item.flags,
                "native_fields": [project_operand(field) for field in item.native_fields],
                "source_range": project_region(item.source_range),
                "unresolved": item.unresolved,
            }
            for item in semantic.function_declarations
        ],
        "entrypoints": [
            {
                "kind": e.kind,
                "name": e.name,
                "object_id": e.object_id,
                "source_node_id": str(e.source_node_id) if e.source_node_id else None,
                "match_method": e.match_method,
                "confidence": e.confidence,
                "unresolved": e.unresolved,
            }
            for e in semantic.entrypoints
        ],
        "graphs": [project_blueprint_graph(g) for g in semantic.graphs],
        "external_refs": [item.to_dict() for item in semantic.external_refs],
        "functions": [project_function_analysis(fn) for fn in semantic.functions],
        "calls": [
            {
                "function_name": c.function_name,
                "object_id": c.object_id,
                "owner_object_id": c.owner_object_id,
                "statement_index": c.statement_index,
                "source_node_id": str(c.source_node_id) if c.source_node_id else None,
                "source_node_reason": c.source_node_reason,
                "match_method": c.match_method,
                "confidence": c.confidence,
                "unresolved": c.unresolved,
                "target_ref_key": c.target_ref_key,
                "execution_mode": c.execution_mode,
            }
            for c in semantic.calls
        ],
        "variable_accesses": [
            {
                "name": v.name,
                "access": v.access,
                "object_id": v.object_id,
                "owner_object_id": v.owner_object_id,
                "statement_index": v.statement_index,
                "source_node_id": str(v.source_node_id) if v.source_node_id else None,
                "source_node_reason": v.source_node_reason,
                "match_method": v.match_method,
                "confidence": v.confidence,
                "unresolved": v.unresolved,
            }
            for v in semantic.variable_accesses
        ],
        "components": [
            {"name": c.name, "class_name": c.class_name, "object_id": c.object_id} for c in semantic.components
        ],
        "dispatchers": [
            {
                "name": item.name,
                "object_id": item.object_id,
                "parameters": [project_operand(param) for param in item.parameters],
                "source_range": project_region(item.source_range),
                "unresolved": item.unresolved,
            }
            for item in semantic.dispatchers
        ],
        "constructors": [
            {
                "name": item.name,
                "object_id": item.object_id,
                "parent_class": item.parent_class,
                "parent_call": item.parent_call,
                "component_initializers": list(item.component_initializers),
                "variable_initializers": list(item.variable_initializers),
                "source_node_id": str(item.source_node_id) if item.source_node_id else None,
                "unresolved": item.unresolved,
            }
            for item in semantic.constructors
        ],
        "variable_events": [
            {
                "variable_name": item.variable_name,
                "dispatcher_name": item.dispatcher_name,
                "object_id": item.object_id,
                "source_node_id": str(item.source_node_id) if item.source_node_id else None,
                "event_kind": item.event_kind,
                "match_method": item.match_method,
                "confidence": item.confidence,
                "unresolved": item.unresolved,
            }
            for item in semantic.variable_events
        ],
        "control_flow": [project_cfg(cfg) for cfg in semantic.control_flow],
        "exec_chains": {
            "metadata": semantic.exec_chains.metadata,
            "edges": [project_cfg_edge(e) for e in semantic.exec_chains.edges],
        },
        "diagnostics": [d.to_dict() for d in semantic.diagnostics],
    }
