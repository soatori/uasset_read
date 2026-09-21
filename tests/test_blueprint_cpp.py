# tests/test_blueprint_cpp.py
import json
from pathlib import Path

from uasset_read.projections.cpp_ast import build_cpp_ast
from uasset_read.projections.cpp_render import render_cpp

ORACLE = json.loads(
    (Path(__file__).parent / "samples/golden/blueprint_header_view/MyProject_UE58_TestBlueprint.json")
    .read_text(encoding="utf-8")
)


def test_declaration_ast_matches_normalized_oracle(ue58_semantic):
    decl = build_cpp_ast(ue58_semantic)
    assert decl.name == ORACLE["class_name"]
    assert decl.parent == ORACLE["parent_class"]
    actual_properties = {item.name: item.type.name for item in decl.properties}
    assert ORACLE["required_properties"].items() <= actual_properties.items()
    function = next(item for item in decl.functions if item.name == ORACLE["functions"][0]["name"])
    expected = ORACLE["functions"][0]
    assert function.return_type.name == expected["return_type"]
    assert [(p.name, p.type.name, p.direction) for p in function.params] == [
        (p["name"], p["type"], p["direction"]) for p in expected["parameters"]
    ]


def test_declaration_mode_contains_blueprint_header_elements(stackobot_semantic):
    from uasset_read.parsers.blueprint.correlation import project_semantic_blueprint

    result = render_cpp(project_semantic_blueprint(stackobot_semantic), mode="declaration")
    assert "UCLASS" in result.header_text
    assert "UPROPERTY" in result.header_text
    assert "UFUNCTION" in result.header_text
    assert result.translation_stats["declarations"] > 0


def test_migration_mode_reports_each_untranslated_instruction(ue58_semantic):
    from uasset_read.parsers.blueprint.correlation import project_semantic_blueprint

    result = render_cpp(project_semantic_blueprint(ue58_semantic), mode="migration")
    assert result.source_text
    stats = result.translation_stats
    assert stats["instructions_seen"] > 0
    assert stats["instructions_seen"] == (
        stats["translated"]
        + stats["represented"]
        + stats["untranslated"]
        + stats["unavailable"]
    )


def test_unresolved_type_is_not_silently_void(stackobot_semantic):
    from uasset_read.parsers.blueprint.correlation import project_semantic_blueprint

    result = render_cpp(project_semantic_blueprint(stackobot_semantic), mode="declaration")
    assert "/* unresolved:" in result.header_text or result.diagnostics


def test_render_cpp_public_entry_accepts_projected_dict(stackobot_document):
    from tests.fixtures import find_blueprint_object
    from uasset_read.projections.cpp_render import render_cpp as public_render

    semantic = find_blueprint_object(stackobot_document).semantic
    assert isinstance(semantic, dict)
    result = public_render(semantic, mode="declaration")
    assert result.header_text


def test_dual_offset_accepts_structured_unset_and_raw_int():
    """E1 dual-offset: envelope may carry raw ints or {"kind":"unset"}."""
    from tests.fixtures import parse_sample
    from uasset_read.parsers.blueprint.correlation import (
        BlueprintCorrelation,
        project_semantic_blueprint,
    )

    doc = parse_sample("MyProject_UE58_TestBlueprint.uasset", depth="decode")
    semantic = BlueprintCorrelation().build(doc)
    projected = project_semantic_blueprint(semantic)
    fn = next(f for f in projected["functions"] if f.get("function_name") == "NewFunction")
    assert fn["instructions"], "measured NewFunction must expose instructions"
    raw = fn["instructions"][0]
    assert isinstance(raw.get("statement_index"), int)
    fn["instructions"][0] = {
        **raw,
        "statement_index": {"kind": "unset"},
        "serialized_start": {"kind": "unset"},
        "serialized_end": {"kind": "unset"},
    }
    result = render_cpp(projected, mode="migration")
    assert result.source_text
    stats = result.translation_stats
    assert stats["instructions_seen"] > 0
    assert stats["instructions_seen"] == (
        stats["translated"]
        + stats["represented"]
        + stats["untranslated"]
        + stats["unavailable"]
    )
