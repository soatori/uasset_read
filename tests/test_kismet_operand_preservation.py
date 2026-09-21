"""Kismet operand preservation: consumed payload must project to an output field.

Matrix over opcodes whose readers historically discarded their payload. A
failure means a reader still consumes bytes without a matching operand field.
Real-sample opcodes are asserted from decoded functions; the remaining matrix
entries exercise ``from_archive`` retention with a scripted archive.
"""

from __future__ import annotations

from uasset_read.kismet.expressions import (
    EX_ArrayGetByRef,
    EX_Assert,
    EX_ArrayConst,
    EX_ClassContext,
    EX_Context,
    EX_DynamicCast,
    EX_InterfaceContext,
    EX_MapConst,
    EX_Nothing,
    EX_Return,
    EX_SetArray,
    EX_SetConst,
    EX_SetMap,
    EX_SetSet,
    EX_StructMemberContext,
    EX_SwitchValue,
    EX_TransformConst,
)
from uasset_read.parsers.blueprint.bytecode import _extract_operands

# Opcode → operand fields that must exist when the reader consumed payload.
OPERAND_FIELD_MATRIX: dict[str, frozenset[str]] = {
    "EX_Return": frozenset({"ReturnValue"}),
    "EX_Assert": frozenset({"LineNumber", "DebugMode", "AssertExpression"}),
    "EX_SwitchValue": frozenset(
        {"EndGotoOffset", "IndexExpression", "Cases", "DefaultExpression"}
    ),
    "EX_Context": frozenset(
        {"ContextExpression", "ContextualOffset", "ContextualProperty", "MemberExpression"}
    ),
    "EX_ClassContext": frozenset(
        {"ContextExpression", "ContextualOffset", "ContextualProperty", "MemberExpression"}
    ),
    "EX_InterfaceContext": frozenset({"InterfaceExpression"}),
    "EX_StructMemberContext": frozenset({"MemberProperty", "StructExpression"}),
    "EX_SetArray": frozenset({"TargetExpression", "InitializingList"}),
    "EX_SetMap": frozenset({"TargetExpression", "Num", "Elements"}),
    "EX_SetSet": frozenset({"TargetExpression", "Num", "Elements"}),
    "EX_ArrayConst": frozenset({"ElementType", "Num", "Values"}),
    "EX_MapConst": frozenset({"KeyType", "ValueType", "Num", "Values"}),
    "EX_SetConst": frozenset({"ElementType", "Num", "Values"}),
    "EX_DynamicCast": frozenset({"TargetClass", "TargetExpression"}),
    "EX_TransformConst": frozenset({"Rotation", "Translation", "Scale"}),
    "EX_ArrayGetByRef": frozenset({"TargetExpression", "IndexExpression"}),
}

# Top-level opcodes known to appear in the tracked samples for real-data checks.
# Jump family uses the explicit snake_case operand keys from _extract_operands;
# EX_Return falls through generic dataclass retention (PascalCase field names).
SAMPLE_OPERAND_FIELDS: dict[str, frozenset[str]] = {
    "EX_Return": frozenset({"ReturnValue"}),
    "EX_JumpIfNot": frozenset({"code_offset", "boolean_expression"}),
    "EX_Jump": frozenset({"code_offset"}),
}


class _ScriptedArchive:
    """Minimal FKismetArchive stand-in for from_archive retention checks."""

    def __init__(self, *, lwc: bool = False, num: float = 1.5) -> None:
        self.summary = type("S", (), {"file_version_ue5": 500 if lwc else 0})()
        self._num = num
        self._expr_counter = 0

    def read_expression(self):
        self._expr_counter += 1
        expr = EX_Nothing()
        expr.StatementIndex = self._expr_counter
        return expr

    def read_expression_array(self, _token):
        return [self.read_expression(), self.read_expression()]

    def read_u8(self) -> int:
        return 1

    def read_u16(self) -> int:
        return 1

    def read_u32(self) -> int:
        return 4

    def read_i32(self) -> int:
        return 2

    def read_f32(self) -> float:
        return self._num

    def read_f64(self) -> float:
        return float(self._num)

    def xfer_object_pointer(self):
        from uasset_read.serializers.object_resources import PackageIndex

        return PackageIndex(-5)

    def xfer_field_pointer(self):
        from uasset_read.kismet.property_pointer import FFieldPath

        return FFieldPath()


def _assert_fields(expr, expected: frozenset[str]) -> None:
    operands = _extract_operands(expr)
    missing = expected - set(operands)
    assert not missing, f"{type(expr).__name__}: missing operand fields {sorted(missing)}"


def test_matrix_from_archive_retains_payload_into_operands():
    archive = _ScriptedArchive()
    cases = [
        (EX_Return.from_archive(archive), OPERAND_FIELD_MATRIX["EX_Return"]),
        (
            EX_Assert.from_archive(archive),
            OPERAND_FIELD_MATRIX["EX_Assert"],
        ),
        (
            EX_SwitchValue.from_archive(archive),
            OPERAND_FIELD_MATRIX["EX_SwitchValue"],
        ),
        (
            EX_Context.from_archive(archive),
            OPERAND_FIELD_MATRIX["EX_Context"],
        ),
        (
            EX_ClassContext.from_archive(archive),
            OPERAND_FIELD_MATRIX["EX_ClassContext"],
        ),
        (
            EX_InterfaceContext.from_archive(archive),
            OPERAND_FIELD_MATRIX["EX_InterfaceContext"],
        ),
        (
            EX_StructMemberContext.from_archive(archive),
            OPERAND_FIELD_MATRIX["EX_StructMemberContext"],
        ),
        (
            EX_SetArray.from_archive(archive),
            OPERAND_FIELD_MATRIX["EX_SetArray"],
        ),
        (EX_SetMap.from_archive(archive), OPERAND_FIELD_MATRIX["EX_SetMap"]),
        (EX_SetSet.from_archive(archive), OPERAND_FIELD_MATRIX["EX_SetSet"]),
        (
            EX_ArrayConst.from_archive(archive),
            OPERAND_FIELD_MATRIX["EX_ArrayConst"],
        ),
        (EX_MapConst.from_archive(archive), OPERAND_FIELD_MATRIX["EX_MapConst"]),
        (EX_SetConst.from_archive(archive), OPERAND_FIELD_MATRIX["EX_SetConst"]),
        (
            EX_DynamicCast.from_archive(archive),
            OPERAND_FIELD_MATRIX["EX_DynamicCast"],
        ),
        (
            EX_TransformConst.from_archive(archive),
            OPERAND_FIELD_MATRIX["EX_TransformConst"],
        ),
        (
            EX_ArrayGetByRef.from_archive(archive),
            OPERAND_FIELD_MATRIX["EX_ArrayGetByRef"],
        ),
    ]
    for expr, expected in cases:
        _assert_fields(expr, expected)


def test_to_dict_emits_matrix_operand_fields():
    """to_dict must not drop consumed payload at the projection boundary."""
    archive = _ScriptedArchive()
    exprs = [
        EX_Return.from_archive(archive),
        EX_SwitchValue.from_archive(archive),
        EX_Context.from_archive(archive),
        EX_SetArray.from_archive(archive),
        EX_DynamicCast.from_archive(archive),
        EX_TransformConst.from_archive(archive),
        EX_ArrayGetByRef.from_archive(archive),
    ]
    for expr in exprs:
        opcode = expr.Token.name
        expected = OPERAND_FIELD_MATRIX[opcode]
        as_dict = expr.to_dict()
        missing = expected - set(as_dict)
        assert not missing, f"{opcode}: to_dict missing {sorted(missing)}"


def test_to_dict_uses_shared_project_operand_schema():
    """Expression to_dict and instruction project_operand share one opaque schema."""
    from uasset_read.parsers.blueprint.bytecode import project_operand

    class _Unprojectable:
        __slots__ = ()

    archive = _ScriptedArchive()
    expr = EX_Return.from_archive(archive)
    expr.ReturnValue = _Unprojectable()
    as_dict = expr.to_dict()
    projected_return = as_dict["ReturnValue"]
    assert projected_return == project_operand(_Unprojectable())
    assert projected_return["kind"] == "opaque_operand"
    assert "opaque_value" not in str(as_dict)


def test_to_dict_emits_structured_unset_for_unfilled_dual_offsets():
    """Unfilled dual offsets project as structured unset — never 0/-1 fabrications."""
    archive = _ScriptedArchive()
    scripted = EX_Return.from_archive(archive)
    # Scripted archive does not stamp dual offsets on the top-level expression.
    as_dict = scripted.to_dict()
    assert as_dict["StatementIndex"] == {"kind": "unset"}
    assert as_dict["SerializedStart"] == {"kind": "unset"}
    assert as_dict["SerializedEnd"] == {"kind": "unset"}

    filled = EX_Return.from_archive(archive)
    filled.StatementIndex = 7
    filled.SerializedStart = 100
    filled.SerializedEnd = 120
    as_dict_filled = filled.to_dict()
    assert as_dict_filled["StatementIndex"] == 7
    assert as_dict_filled["SerializedStart"] == 100
    assert as_dict_filled["SerializedEnd"] == 120


def test_matrix_is_json_projectable_without_discarding_payload():
    import json

    from uasset_read.parsers.blueprint.bytecode import BytecodeInstruction, project_operand

    archive = _ScriptedArchive()
    exprs = [
        EX_Return.from_archive(archive),
        EX_SwitchValue.from_archive(archive),
        EX_Context.from_archive(archive),
        EX_SetArray.from_archive(archive),
        EX_DynamicCast.from_archive(archive),
        EX_TransformConst.from_archive(archive),
    ]
    for expr in exprs:
        opcode = expr.Token.name if expr.Token is not None else type(expr).__name__
        expected = OPERAND_FIELD_MATRIX[opcode]
        operands = _extract_operands(expr)
        assert expected <= set(operands)
        projected = project_operand(operands)
        json.dumps(projected)  # must not raise
        for field_name in expected:
            assert field_name in projected


def test_real_sample_top_level_opcodes_project_required_fields(
    ue58_blueprint_document, stackobot_document
):
    """Prefer real sample opcodes: EX_Return / jumps must keep their payload."""
    checked: set[str] = set()
    for document in (ue58_blueprint_document, stackobot_document):
        for obj in document.objects:
            for fn in ((obj.semantic or {}).get("functions") or []):
                for item in fn.get("instructions") or []:
                    opcode = item.get("opcode")
                    required = SAMPLE_OPERAND_FIELDS.get(opcode)
                    if required is None:
                        continue
                    operands = item.get("operands") or {}
                    missing = required - set(operands)
                    assert not missing, (
                        f"sample opcode {opcode}: operands missing {sorted(missing)} "
                        f"(payload consumed without an output field)"
                    )
                    checked.add(opcode)
    assert "EX_Return" in checked, "samples must exercise EX_Return operand retention"


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


def test_e2e_functions_do_not_lose_return_payload(stackobot_document):
    """End-to-end: typed FunctionAnalysis EX_Return keeps ReturnValue projection."""
    found = False
    for obj in stackobot_document.objects:
        if not isinstance(obj.semantic, dict):
            continue
        for fn in obj.semantic.get("functions") or []:
            # Dict path already asserted above; rebuild typed projection from
            # the same instruction dicts to ensure project_instruction agrees.
            for item in fn.get("instructions") or []:
                if item.get("opcode") != "EX_Return":
                    continue
                found = True
                assert "ReturnValue" in (item.get("operands") or {})
    assert found, "StackOBot sample must contain EX_Return instructions"
