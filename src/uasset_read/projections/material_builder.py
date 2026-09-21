"""Material editor-builder projection (plan Task 10A / R3).

Emits editor-only reconstruction C++ when an editor expression graph is
present. Never claims HLSL/shader equivalence and never invents cooked-away
expressions. Cooked/stripped graphs emit explicit unavailable records.
"""

from __future__ import annotations

from typing import Any

from uasset_read.models.diagnostics import make_diagnostic
from uasset_read.models.document import PackageDocument
from uasset_read.models.object_model import ObjectRecord
from uasset_read.projections.records import (
    ProjectionRecord,
    dependency_ids,
    matches_family,
    unavailable_records,
)

ASSET_KINDS = ("material",)
_CLASS_NAMES = ("Material",)

_BUILDER_PAIR = (("material_editor_builder", "text/x-c++src"),)

_EDITOR_HEADER = (
    "// uasset_read material editor-builder projection\n"
    "// Editor-only reconstruction via UMaterialEditingLibrary-style operations.\n"
    "// Not HLSL/shader equivalence; cooked-away expressions are never invented.\n"
)


def _semantic(obj: ObjectRecord) -> dict[str, Any]:
    semantic = obj.semantic
    return semantic if isinstance(semantic, dict) else {}


def _editor_graph(semantic: dict[str, Any]) -> dict[str, Any] | None:
    graph = semantic.get("material_graph")
    return graph if isinstance(graph, dict) else None


def _render_builder(obj: ObjectRecord, graph: dict[str, Any]) -> str:
    name = obj.name or "Material"
    expressions = graph.get("expressions") or []
    links = graph.get("links") or []
    parameters = graph.get("parameters") or []
    lines = [
        _EDITOR_HEADER.rstrip("\n"),
        f"// material: {name}",
        f"// expressions: {len(expressions)} links: {len(links)} parameters: {len(parameters)}",
        f"void Reconstruct_{name}()",
        "{",
        "    // UMaterialEditingLibrary-style reconstruction sketch from the editor graph.",
    ]
    for expression in expressions:
        if not isinstance(expression, dict):
            continue
        class_name = expression.get("class_name") or "MaterialExpression"
        expr_name = expression.get("name") or expression.get("object_id") or "Expression"
        lines.append(f"    // create expression {class_name} {expr_name}")
    for link in links:
        if not isinstance(link, dict):
            continue
        lines.append(
            "    // connect "
            f"{link.get('source')}:{link.get('source_output')} -> "
            f"{link.get('target')}:{link.get('target_input')}"
        )
    for parameter in parameters:
        if not isinstance(parameter, dict):
            continue
        lines.append(
            f"    // set parameter {parameter.get('name')} "
            f"({parameter.get('parameter_kind')}) = {parameter.get('default')!r}"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


class MaterialEditorBuilderProjector:
    """Material family: material_editor_builder from the projected editor graph."""

    asset_kinds = ASSET_KINDS

    def can_project(self, obj: ObjectRecord) -> bool:
        return matches_family(obj, self.asset_kinds, _CLASS_NAMES)

    def project(self, document: PackageDocument, obj: ObjectRecord) -> list[ProjectionRecord]:
        semantic = _semantic(obj)
        graph = _editor_graph(semantic)
        deps = dependency_ids(document, obj.id)
        if not isinstance(graph, dict):
            return unavailable_records(
                obj.id,
                _BUILDER_PAIR,
                code="material_editor_graph_missing",
                message="Material semantic carries no projected editor expression graph",
                stage="projection.material_builder",
                dependencies=deps,
            )
        capability = str(graph.get("capability") or "")
        if capability not in {"complete", "partial"}:
            return unavailable_records(
                obj.id,
                _BUILDER_PAIR,
                code="material_editor_graph_unavailable",
                message=(
                    "Material editor expression graph is unavailable "
                    f"(capability={capability or 'unknown'})"
                ),
                stage="projection.material_builder",
                dependencies=deps,
            )
        content = _render_builder(obj, graph)
        # Editor graph is present; builder stays represented, never HLSL-complete.
        diagnostics = []
        for raw in graph.get("diagnostics") or []:
            if isinstance(raw, dict) and raw.get("code"):
                diagnostics.append(
                    make_diagnostic(
                        str(raw.get("code")),
                        str(raw.get("message") or ""),
                        str(raw.get("stage") or "projection.material_builder"),
                        object_id=obj.id,
                    )
                )
        return [
            ProjectionRecord(
                kind="material_editor_builder",
                source_object_id=obj.id,
                media_type="text/x-c++src",
                content=content,
                embedded=True,
                status="represented",
                completeness=1.0 if capability == "complete" else 0.5,
                dependencies=deps,
                diagnostics=diagnostics,
            )
        ]
