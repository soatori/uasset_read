"""Material expression graph decoder — package-first, PropertyBag only.

Editor-saved Material packages store each MaterialExpression as its own
export; links live in serialized ``FExpressionInput`` / ``FMaterialInput``
structs already normalized inside the property bags. This module never
re-parses raw property bytes: it only walks ``ObjectRecord.properties``.

Links are emitted only when a serialized input reference resolves to a
material expression (or a material channel input on ``MaterialEditorOnlyData``).
Scalar constants never invent edges.

Cooked / editor-stripped packages expose no MaterialExpression* exports;
decode reports ``capability`` limited/unavailable and a coverage entry with
feature ``editor_expression_graph``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...models.document import PackageDocument
from ...models.object_model import CoverageEntry, ObjectRecord

# Property kinds that carry a serialized expression reference after
# normalization (legacy_reader._normalize_structured_dict / binary handlers).
_INPUT_KINDS = frozenset({"struct_property", "material_input"})

# Scalar / constant property names copied onto an expression without ever
# being treated as graph links.
_CONSTANT_PROP_NAMES = frozenset(
    {
        "R",
        "G",
        "B",
        "A",
        "DefaultValue",
        "Constant",
        "Texture",
        "SamplerType",
        "ConstA",
        "ConstB",
        "Brightness",
        "Opacity",
    }
)


@dataclass
class MaterialExpression:
    """One MaterialExpression* export projected as a graph node."""

    object_id: str
    class_name: str
    name: str
    expression_guid: str = ""
    editor_x: int | None = None
    editor_y: int | None = None
    inputs: list[dict[str, Any]] = field(default_factory=list)
    constants: dict[str, Any] = field(default_factory=dict)
    opaque_properties: list[str] = field(default_factory=list)


@dataclass
class MaterialLink:
    """Directed edge: source expression output → target expression input.

    ``target`` is the consumer expression (or the Material export for
    channel inputs on MaterialEditorOnlyData). ``source`` is the producer
    resolved from a serialized ExpressionInput / material input reference.
    """

    source: str
    source_output: int
    target: str
    target_input: str
    mask: int = 0


@dataclass
class MaterialParameter:
    """Named material parameter expression (scalar/vector/texture/switch)."""

    object_id: str
    name: str
    parameter_kind: str
    default: Any = None


@dataclass
class MaterialFunctionCall:
    """MaterialExpressionMaterialFunctionCall node summary."""

    object_id: str
    function_name: str = ""
    input_count: int = 0


@dataclass
class MaterialGraph:
    """Decoded editor expression graph for one package."""

    object_id: str = ""
    name: str = ""
    expressions: list[MaterialExpression] = field(default_factory=list)
    links: list[MaterialLink] = field(default_factory=list)
    parameters: list[MaterialParameter] = field(default_factory=list)
    function_calls: list[MaterialFunctionCall] = field(default_factory=list)
    capability: str = "unavailable"
    coverage: list[CoverageEntry] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)


def _unwrap(value: Any) -> Any:
    """Unwrap a tagged ``{"kind":"value", ...}`` bag entry one level."""
    if isinstance(value, dict) and value.get("kind") == "value":
        return value.get("value")
    return value


def _scalar(value: Any) -> Any:
    value = _unwrap(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    if isinstance(value, dict) and value.get("kind") == "struct_binary_decoded":
        # LinearColor / Guid style decoded structs: keep scalar field map.
        fields = {
            k: v
            for k, v in value.items()
            if k not in {"kind", "size", "struct_type"} and not isinstance(v, (bytes, dict, list))
        }
        if fields:
            return fields
    return None


def _guid_hex(value: Any) -> str:
    value = _unwrap(value)
    if not isinstance(value, dict):
        return ""
    fields = value.get("fields") if value.get("kind") == "struct" else value
    if not isinstance(fields, dict):
        return ""
    try:
        return "".join(f"{int(fields.get(k, 0)) & 0xFFFFFFFF:08x}" for k in ("A", "B", "C", "D"))
    except (TypeError, ValueError):
        return ""


def _as_int(value: Any, default: int = 0) -> int:
    value = _unwrap(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _input_ref(entry: dict[str, Any]) -> tuple[int, int, str, int]:
    """Return (expression_ref, output_index, input_name, mask) from a normalized input."""
    ref = entry.get("expression_ref")
    if ref is None:
        ref = entry.get("expression_index")
    if ref is None:
        ref = entry.get("Expression")
    ref_i = int(ref) if isinstance(ref, int) else 0
    out = entry.get("output_index")
    if out is None:
        out = entry.get("OutputIndex")
    out_i = int(out) if isinstance(out, int) else 0
    name = entry.get("input_name")
    if name is None:
        name = entry.get("InputName")
    mask = entry.get("mask")
    mask_i = int(mask) if isinstance(mask, int) else 0
    return ref_i, out_i, str(name) if name is not None else "", mask_i


def _is_input_entry(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("kind") not in _INPUT_KINDS:
        return False
    return "expression_ref" in value or "expression_index" in value or "Expression" in value


def _outer_chain_reaches(
    objects_by_id: dict[str, ObjectRecord],
    start_id: str,
    target_id: str,
    limit: int = 64,
) -> bool:
    """Walk ObjectRecord.outer_ref from *start_id* up to *target_id*."""
    current_id = start_id
    for _ in range(limit):
        if current_id == target_id:
            return True
        record = objects_by_id.get(current_id)
        if record is None or record.outer_ref is None:
            return False
        ref = record.outer_ref
        current_id = f"{ref.table}:{ref.index}"
    return False


class MaterialGraphDecoder:
    """Decode a PackageDocument's material expression graph from property bags."""

    def decode(self, document: PackageDocument) -> MaterialGraph:
        """Decode expression graphs from *document* objects (PropertyBag only)."""
        return self.decode_objects(document.objects)

    def decode_objects(
        self,
        objects: list[ObjectRecord],
        material_object_id: str | None = None,
    ) -> MaterialGraph:
        """Decode from a bare object list (handler path shares this with decode).

        When *material_object_id* is provided, only that Material and its
        outer-chain-owned MaterialExpression* / MaterialEditorOnlyData
        exports are decoded — never a silent first-Material fallback.
        """
        by_export_index = {i: o for i, o in enumerate(objects) if o.id.startswith("export:")}
        objects_by_id = {o.id: o for o in objects}

        if material_object_id is not None:
            material = objects_by_id.get(material_object_id)
            if material is None or (material.class_name or "") != "Material":
                graph = MaterialGraph(
                    object_id=str(material_object_id),
                    name=getattr(material, "name", "") or "",
                )
                graph.capability = "unavailable"
                graph.coverage.append(
                    CoverageEntry(
                        feature="editor_expression_graph",
                        status="missing",
                        detail=f"requested material {material_object_id} not found among objects",
                    )
                )
                graph.diagnostics.append(f"material_not_found:{material_object_id}")
                graph.diagnostics.extend(
                    f"{entry.feature}:{entry.status}:{entry.detail}" for entry in graph.coverage
                )
                return graph
        else:
            material = next((o for o in objects if (o.class_name or "") == "Material"), None)

        material_id = material.id if material is not None else None
        material_name = material.name if material is not None else ""

        def owned_by_material(obj: ObjectRecord) -> bool:
            if material_id is None:
                return False
            if obj.id == material_id:
                return True
            return _outer_chain_reaches(objects_by_id, obj.id, material_id)

        editor_only = next(
            (
                o
                for o in objects
                if (o.class_name or "") == "MaterialEditorOnlyData"
                and owned_by_material(o)
            ),
            None,
        )
        expression_objs = [
            o
            for o in objects
            if (o.class_name or "").startswith("MaterialExpression") and owned_by_material(o)
        ]

        graph = MaterialGraph(object_id=material_id or "", name=material_name)
        if not expression_objs:
            if material is not None:
                # Material export present but editor expressions stripped (cooked).
                graph.capability = "limited"
                graph.coverage.append(
                    CoverageEntry(
                        feature="editor_expression_graph",
                        status="missing",
                        detail="Material export present without MaterialExpression* exports (cooked or stripped)",
                    )
                )
            else:
                graph.capability = "unavailable"
                graph.coverage.append(
                    CoverageEntry(
                        feature="editor_expression_graph",
                        status="missing",
                        detail="no Material export and no MaterialExpression* exports",
                    )
                )
            graph.diagnostics = [
                f"{entry.feature}:{entry.status}:{entry.detail}" for entry in graph.coverage
            ]
            return graph

        def resolve(ref: int) -> str | None:
            # FPackageIndex > 0 → export index ref-1 (ObjectResource.h).
            if ref <= 0:
                return None
            target = by_export_index.get(ref - 1)
            return target.id if target is not None else None

        for expr_obj in expression_objs:
            node, pins = self._decode_expression(expr_obj, resolve)
            graph.expressions.append(node)
            for pin in pins:
                source = pin.get("source")
                if not source:
                    continue
                graph.links.append(
                    MaterialLink(
                        source=source,
                        source_output=int(pin.get("source_output") or 0),
                        target=expr_obj.id,
                        target_input=str(pin.get("name") or ""),
                        mask=int(pin.get("mask") or 0),
                    )
                )
            param = self._decode_parameter(expr_obj)
            if param is not None:
                graph.parameters.append(param)
            if (expr_obj.class_name or "") == "MaterialExpressionMaterialFunctionCall":
                graph.function_calls.append(self._decode_function_call(expr_obj))

        # Material channel inputs live on MaterialEditorOnlyData (BaseColor, …).
        if editor_only is not None and material_id is not None:
            for prop_name, raw in (editor_only.properties or {}).items():
                if not _is_input_entry(raw):
                    continue
                ref_i, out_i, _name, mask_i = _input_ref(raw)
                source = resolve(ref_i)
                if source is None:
                    continue
                graph.links.append(
                    MaterialLink(
                        source=source,
                        source_output=out_i,
                        target=material_id,
                        target_input=prop_name,
                        mask=mask_i,
                    )
                )

        bags_present = sum(1 for o in expression_objs if o.properties)
        if bags_present == len(expression_objs):
            # Full bags: complete only when the graph actually wires and parametrizes;
            # expression sets with no links/parameters stay partial (#629).
            graph.capability = "complete" if (graph.links and graph.parameters) else "partial"
            status: str = "present" if graph.links else "partial"
            detail = f"{len(graph.expressions)} expressions, {len(graph.links)} links"
        elif bags_present == 0:
            graph.capability = "limited"
            status = "missing"
            detail = "MaterialExpression* exports present but property bags not parsed"
        else:
            graph.capability = "partial"
            status = "partial"
            detail = f"{bags_present}/{len(expression_objs)} expression property bags parsed"

        graph.coverage.append(
            CoverageEntry(feature="editor_expression_graph", status=status, detail=detail)
        )
        graph.diagnostics = [
            f"{entry.feature}:{entry.status}:{entry.detail}"
            for entry in graph.coverage
            if entry.status in {"missing", "partial", "unsupported"}
        ]
        return graph

    def _decode_expression(
        self,
        obj: ObjectRecord,
        resolve: Any,
    ) -> tuple[MaterialExpression, list[dict[str, Any]]]:
        props = obj.properties or {}
        node = MaterialExpression(
            object_id=obj.id,
            class_name=obj.class_name or "",
            name=obj.name,
            expression_guid=_guid_hex(props.get("MaterialExpressionGuid")),
        )
        if "MaterialExpressionEditorX" in props:
            node.editor_x = _as_int(props.get("MaterialExpressionEditorX"), 0)
        if "MaterialExpressionEditorY" in props:
            node.editor_y = _as_int(props.get("MaterialExpressionEditorY"), 0)

        pins: list[dict[str, Any]] = []
        for prop_name, raw in props.items():
            if _is_input_entry(raw):
                ref_i, out_i, input_name, mask_i = _input_ref(raw)
                source = resolve(ref_i)
                pins.append(
                    {
                        "name": prop_name,
                        "source": source,
                        "source_output": out_i,
                        "input_name": input_name,
                        "mask": mask_i,
                    }
                )
                node.inputs.append(pins[-1])
                continue
            if prop_name in (
                "MaterialExpressionGuid",
                "MaterialExpressionEditorX",
                "MaterialExpressionEditorY",
                "Material",
            ):
                continue
            if prop_name in _CONSTANT_PROP_NAMES or prop_name.endswith("ParameterName"):
                val = _scalar(raw)
                if val is not None:
                    node.constants[prop_name] = val
                else:
                    # Structured but not scalar-flattened: name-only opaque marker.
                    node.opaque_properties.append(prop_name)
                continue
            # Unknown / structured fields: name-only opaque marker (no byte reparse).
            node.opaque_properties.append(prop_name)
        return node, pins

    def _decode_parameter(self, obj: ObjectRecord) -> MaterialParameter | None:
        props = obj.properties or {}
        name_val = _unwrap(props.get("ParameterName"))
        if not isinstance(name_val, str) or not name_val:
            return None
        cn = obj.class_name or ""
        if "ScalarParameter" in cn:
            kind = "scalar"
        elif "VectorParameter" in cn:
            kind = "vector"
        elif "TextureSampleParameter" in cn or "TextureParameter" in cn:
            kind = "texture"
        elif "StaticSwitchParameter" in cn or "SwitchParameter" in cn:
            kind = "static_switch"
        elif "DoubleVectorParameter" in cn:
            kind = "double_vector"
        else:
            kind = "parameter"
        default = _scalar(props.get("DefaultValue"))
        return MaterialParameter(
            object_id=obj.id,
            name=name_val,
            parameter_kind=kind,
            default=default,
        )

    def _decode_function_call(self, obj: ObjectRecord) -> MaterialFunctionCall:
        props = obj.properties or {}
        fn = _unwrap(props.get("MaterialFunction"))
        function_name = ""
        if isinstance(fn, dict):
            function_name = str(fn.get("object_name") or "")
        elif isinstance(fn, str):
            function_name = fn
        inputs = _unwrap(props.get("FunctionInputs"))
        input_count = len(inputs) if isinstance(inputs, list) else 0
        return MaterialFunctionCall(
            object_id=obj.id,
            function_name=function_name,
            input_count=input_count,
        )


def project_semantic_material(graph: MaterialGraph) -> dict[str, Any]:
    """Project a MaterialGraph onto the public semantic dict contract (E1)."""
    return {
        "kind": "material_graph",
        "object_id": graph.object_id,
        "name": graph.name,
        "capability": graph.capability,
        "diagnostics": list(graph.diagnostics),
        "expressions": [
            {
                "object_id": e.object_id,
                "class_name": e.class_name,
                "name": e.name,
                "expression_guid": e.expression_guid,
                "editor_x": e.editor_x,
                "editor_y": e.editor_y,
                "inputs": e.inputs,
                "constants": e.constants,
                "opaque_properties": e.opaque_properties,
            }
            for e in graph.expressions
        ],
        "links": [
            {
                "source": ln.source,
                "source_output": ln.source_output,
                "target": ln.target,
                "target_input": ln.target_input,
                "mask": ln.mask,
            }
            for ln in graph.links
        ],
        "parameters": [
            {
                "object_id": p.object_id,
                "name": p.name,
                "parameter_kind": p.parameter_kind,
                "default": p.default,
            }
            for p in graph.parameters
        ],
        "function_calls": [
            {
                "object_id": fc.object_id,
                "function_name": fc.function_name,
                "input_count": fc.input_count,
            }
            for fc in graph.function_calls
        ],
        "coverage": [
            {"feature": c.feature, "status": c.status, "detail": c.detail}
            for c in graph.coverage
        ],
    }
