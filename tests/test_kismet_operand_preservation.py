def test_function_call_parameters_are_retained_recursively(function_analysis_ir):
    calls = [
        item
        for item in function_analysis_ir.instructions
        if item.opcode in {"EX_FinalFunction", "EX_VirtualFunction", "EX_CallMath"}
    ]
    assert calls
    assert any(item.operands.get("parameters") for item in calls)
    assert all(item.serialized_end > item.serialized_start for item in calls)


def test_nested_operands_are_projectable_without_repr(function_analysis_ir):
    from uasset_read.parsers.blueprint.bytecode import project_instruction

    for instruction in function_analysis_ir.instructions:
        projected = project_instruction(instruction)
        assert projected["expression"] is not None
        assert "0x" not in str(projected["expression"])
        assert projected["parse_status"] in {"parsed", "partial", "unavailable"}
        import json
        json.dumps(projected)
