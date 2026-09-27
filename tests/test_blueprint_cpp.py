# tests/test_blueprint_cpp.py
import json
from pathlib import Path

from uasset_read.projections.cpp_ast import build_cpp_ast
from uasset_read.projections.cpp_render import render_cpp

ORACLE = json.loads(
    (Path(__file__).parent / "samples/golden/blueprint_header_view/MyProject_UE58_TestBlueprint.json").read_text(
        encoding="utf-8"
    )
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
        stats["translated"] + stats["represented"] + stats["untranslated"] + stats["unavailable"]
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
        stats["translated"] + stats["represented"] + stats["untranslated"] + stats["unavailable"]
    )


def test_no_silent_void_and_native_helpers_reach_output():
    """Review round-1: migration must not silent-void IR-only functions; native helpers must render."""
    from uasset_read.kismet.native_fields import NativeFieldDeclaration
    from uasset_read.models.analysis import (
        BlueprintDeclaration,
        BlueprintSemantic,
        ExecChainSummary,
        FunctionAnalysis,
        FunctionDeclaration,
    )
    from uasset_read.parsers.blueprint.bytecode import BytecodeInstruction
    from uasset_read.parsers.blueprint.control_flow import ControlFlowGraph
    from uasset_read.projections.cpp_ast import build_cpp_ast
    from uasset_read.projections.cpp_render import render_cpp_ir

    # CPF_Parm=0x80, CPF_ReturnParm=0x400 (native_fields.py mirrors).
    native_fields = [
        NativeFieldDeclaration(type_name="BoolProperty", name="NewParam", property_flags=0x80),
        NativeFieldDeclaration(type_name="FloatProperty", name="ReturnValue", property_flags=0x80 | 0x400),
    ]
    fn_decl = FunctionDeclaration(
        name="NativeFn",
        return_type=None,
        cpp_return_type=None,
        parameters=[],
        flags=None,
        native_fields=native_fields,
        source_range=None,
        unresolved=True,
    )
    instruction = BytecodeInstruction(
        statement_index=0,
        statement_ordinal=0,
        logical_end=1,
        serialized_start=0,
        serialized_end=1,
        opcode="EX_EndOfScript",
        operands={},
        expression=None,
        reads=[],
        writes=[],
        call_target=None,
        jump_target_statement_index=None,
        jump_kind="none",
        source_node_id=None,
    )
    only_in_ir = FunctionAnalysis(
        object_id="export:9",
        owner_object_id="export:0",
        name="OnlyInIR",
        function_name="OnlyInIR",
        script_source_range=None,
        expression_count=1,
        entrypoint=None,
        instructions=[instruction],
        cfg=ControlFlowGraph(blocks=[], edges=[], entry=0, metadata={}),
        reads=set(),
        writes=set(),
        calls=[],
        bytecode_status="parsed",
        diagnostics=[],
    )
    semantic = BlueprintSemantic(
        object_id="export:0",
        name="Synth",
        parent_class="Actor",
        declaration=BlueprintDeclaration(
            class_name="Synth",
            parent_class="Actor",
            class_flags=None,
            metadata={},
            source_range=None,
        ),
        variable_definitions=[],
        function_declarations=[fn_decl],
        entrypoints=[],
        graphs=[],
        functions=[only_in_ir],
        calls=[],
        variable_accesses=[],
        components=[],
        dispatchers=[],
        constructors=[],
        variable_events=[],
        control_flow=[],
        exec_chains=ExecChainSummary(metadata={}, edges=[]),
        diagnostics=[],
    )

    decl = build_cpp_ast(semantic)
    native_fn = next(f for f in decl.functions if f.name == "NativeFn")
    assert native_fn.return_type.name == "float"
    assert [(p.name, p.type.name, p.direction) for p in native_fn.params] == [("NewParam", "bool", "in")]
    assert native_fn.native_signature and "NativeFn" in native_fn.native_signature

    result = render_cpp_ir(semantic, mode="migration")
    # Finding 1: no silent void for IR-only functions.
    assert "void OnlyInIR" not in result.source_text
    assert "/* unresolved: return_type */ return_type OnlyInIR()" in result.source_text
    assert any(d.code == "cpp_projection_unresolved_return" for d in result.diagnostics)
    # Findings 2+3: native_field_cpp_type + build_native_function_signature reach output.
    assert native_fn.native_signature in result.header_text
    assert "native:" in result.header_text
    assert "float NativeFn(bool NewParam)" in result.header_text.replace("/* out */ ", "")
