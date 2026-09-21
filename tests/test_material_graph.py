"""Material expression graph decoder contracts (plan Task 9).

StackOBot's editor material exposes 42 exports / 39 MaterialExpression*
exports with serialized ExpressionInput links; the cooked TestMaterial
header carries no editor expression graph and must say so explicitly.
The decoder consumes only normalized property bags — never raw property
bytes — and the Material handler attaches one projected dict under
``semantic["material_graph"]`` (E1: dicts, not live dataclasses).
"""

from __future__ import annotations

from tests.fixtures import find_material_graph, parse_sample
from uasset_read.parsers.material import MaterialGraphDecoder


def test_stackobot_material_exposes_expression_nodes_and_links(stackobot_material):
    graph = MaterialGraphDecoder().decode(stackobot_material)
    assert len(graph.expressions) == 39
    assert graph.links
    assert graph.parameters
    assert graph.capability in {"complete", "partial"}


def test_cooked_material_marks_editor_graph_unavailable(cooked_material):
    graph = MaterialGraphDecoder().decode(cooked_material)
    assert graph.capability in {"limited", "unavailable"}
    assert any(item.feature == "editor_expression_graph" for item in graph.coverage)


def test_selected_material_export_still_decodes_expression_set():
    """Bounded material dependency closure: selecting export:0 still parses
    the owned MaterialExpression* / MaterialEditorOnlyData property bags, so
    the selected document yields the same expression set and links as the
    full decode."""
    full_doc = parse_sample("StackOBot_M_BotBase.uasset", depth="decode")
    selected_doc = parse_sample(
        "StackOBot_M_BotBase.uasset", depth="decode", object_ids=["export:0"]
    )

    expression_objects = [
        obj
        for obj in selected_doc.objects
        if (obj.class_name or "").startswith("MaterialExpression")
    ]
    assert len(expression_objects) == 39
    assert all(obj.properties for obj in expression_objects), (
        "material dependency closure must parse expression property bags"
    )

    full_graph = MaterialGraphDecoder().decode(full_doc)
    selected_graph = MaterialGraphDecoder().decode(selected_doc)
    assert len(selected_graph.expressions) == len(full_graph.expressions) == 39
    assert {item.object_id for item in selected_graph.expressions} == {
        item.object_id for item in full_graph.expressions
    }
    assert selected_graph.links
    assert len(selected_graph.links) == len(full_graph.links)
    assert selected_graph.parameters
    assert len(selected_graph.parameters) == len(full_graph.parameters)


def test_material_handler_attaches_projected_material_graph(stackobot_material):
    material = next(obj for obj in stackobot_material.objects if obj.class_name == "Material")
    attached = (material.semantic or {}).get("material_graph")
    assert isinstance(attached, dict), "handler must attach a projected dict, not a dataclass"
    assert len(attached["expressions"]) == 39
    assert attached["links"]
    assert attached["parameters"]
    assert attached["capability"] in {"complete", "partial"}
    # Minimal projection shape: identity + diagnostics when cheap.
    assert attached["object_id"] == material.id
    assert attached["name"] == material.name
    assert isinstance(attached["diagnostics"], list)
    assert material.status.semantic == "complete"

    # Shared fixture reads the same projection.
    via_fixture = find_material_graph(stackobot_material)
    assert via_fixture is attached or via_fixture == attached


def test_stackobot_material_semantic_has_graph_dict(stackobot_material):
    """E1: document-boundary material_graph is a projected dict with expressions."""
    from tests.fixtures import find_material_graph

    graph = find_material_graph(stackobot_material)
    assert isinstance(graph, dict)
    assert graph.get("expressions") is not None


def test_material_owner_scope_filters_foreign_expressions():
    """An id provided to decode_objects scopes expressions by outer chain —
    never a silent first-Material fallback."""
    from uasset_read.models.object_model import ObjectRef, ObjectRecord
    from uasset_read.parsers.material import MaterialGraphDecoder

    def export(i: int, class_name: str, name: str, outer: int | None) -> ObjectRecord:
        return ObjectRecord(
            id=f"export:{i}",
            table_index=i,
            name=name,
            class_name=class_name,
            outer_ref=ObjectRef(table="export", index=outer) if outer is not None else None,
        )

    material_a = export(0, "Material", "M_A", None)
    material_b = export(1, "Material", "M_B", None)
    # ObjectRef.index is 0-based and matches the export id suffix.
    expr_a = export(2, "MaterialExpressionConstant", "Const_A", outer=0)
    expr_b = export(3, "MaterialExpressionConstant", "Const_B", outer=1)
    objects = [material_a, material_b, expr_a, expr_b]

    graph_b = MaterialGraphDecoder().decode_objects(objects, material_object_id="export:1")
    assert graph_b.object_id == "export:1"
    assert graph_b.name == "M_B"
    assert [e.object_id for e in graph_b.expressions] == ["export:3"], (
        "expressions must be filtered by outer chain to the requested material"
    )
    assert "export:2" not in {e.object_id for e in graph_b.expressions}

    # Unknown id: unavailable + diagnostic, never first-Material fallback.
    missing = MaterialGraphDecoder().decode_objects(objects, material_object_id="export:9")
    assert missing.capability == "unavailable"
    assert missing.expressions == []
    assert any("material_not_found" in d for d in missing.diagnostics)
