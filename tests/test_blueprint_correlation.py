# tests/test_blueprint_correlation.py
from uasset_read.parsers.blueprint.correlation import BlueprintCorrelation


def test_stackobot_has_event_entrypoint_and_function_calls(stackobot_document):
    semantic = BlueprintCorrelation().build(stackobot_document)
    assert semantic.entrypoints
    assert semantic.calls
    assert semantic.variable_accesses
    assert all(call.execution_mode == "static_reference" for call in semantic.calls)


def test_exec_summary_is_not_runtime_execution(stackobot_document):
    semantic = BlueprintCorrelation().build(stackobot_document)
    assert semantic.exec_chains.metadata["kind"] == "direct_exec_edge_summary"
    assert semantic.control_flow


def test_constructor_parent_and_variable_event_records_are_explicit(ue58_blueprint_document):
    semantic = BlueprintCorrelation().build(ue58_blueprint_document)
    assert semantic.constructors
    constructor = semantic.constructors[0]
    assert constructor.object_id
    assert constructor.parent_class is not None
    assert all(item.object_id for item in semantic.variable_events)


def test_stackobot_kismet_counts(stackobot_document):
    semantic = BlueprintCorrelation().build(stackobot_document)
    assert len(semantic.functions) == 3
    total_expr = sum(fn.expression_count for fn in semantic.functions)
    assert total_expr == 85
    assert any(fn.cfg.blocks for fn in semantic.functions)


def test_ue58_new_function_preserves_branch_and_variable_flow(ue58_blueprint_document):
    semantic = BlueprintCorrelation().build(ue58_blueprint_document)
    function = next(fn for fn in semantic.functions if fn.name == "NewFunction")
    branch = next(item for item in function.instructions if item.opcode == "EX_JumpIfNot")
    assert branch.jump_target_statement_index is not None
    assert {edge.kind for edge in function.cfg.edges} >= {"true", "false"}
    assert "NewParam" in function.reads
    assert "NewParam1" in function.writes
    assert function.entrypoint.kind == "function"


def test_every_call_and_variable_record_is_traceable(stackobot_document):
    semantic = BlueprintCorrelation().build(stackobot_document)
    for call in semantic.calls:
        assert call.function_name
        assert call.object_id
        assert call.owner_object_id
        assert call.unresolved or call.statement_index is not None or call.source_node_id
        assert 0.0 <= call.confidence <= 1.0
        assert call.unresolved or call.match_method != "unresolved"
    for variable in semantic.variable_accesses:
        assert variable.name
        assert variable.access in {"read", "write", "read_write", "declaration"}
        assert variable.object_id
        assert variable.owner_object_id
        assert 0.0 <= variable.confidence <= 1.0
        assert variable.unresolved or variable.match_method != "unresolved"


def test_duplicate_function_names_keep_export_identity(stackobot_document, function_analysis_ir):
    from dataclasses import replace
    from uasset_read.models.analysis import BlueprintAnalysisContext

    first = replace(function_analysis_ir, object_id="export:9", name="Same", function_name="Same")
    second = replace(function_analysis_ir, object_id="export:10", name="Same", function_name="Same")
    semantic = BlueprintCorrelation().build(
        stackobot_document,
        analysis_context=BlueprintAnalysisContext(
            owner_object_id="export:0", graphs=[], functions=[first, second]
        ),
    )
    assert [fn.object_id for fn in semantic.functions] == ["export:9", "export:10"]
