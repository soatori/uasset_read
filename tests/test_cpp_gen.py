"""Phase 57: C++ Method/Call IR data model tests."""
import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass

from uasset_read.cpp_gen import CppMethodIR, CppCallParameter, CppCallStatement, CppClassIR, format_cpp_call_statements
from uasset_read.cpp_gen.formatters import CppMethodIR as FCppMethodIR, CppCallParameter as FCppCallParameter, CppCallStatement as FCppCallStatement, format_cpp_call_statements as f_format_cpp_call_statements
from uasset_read.cpp_gen.formatters.cpp_header_formatter import _format_method_declaration, format_cpp_header
from uasset_read.cpp_gen.extract_cpp_skeleton import (
    _sanitize_identifier,
    _extract_cpp_type_from_pin,
    _extract_parameters_from_pins,
    _infer_ufunction_specifiers,
    _derive_call_target,
    extract_cpp_functions,
    extract_cpp_call_statements,
)
from uasset_read.models.node_types import K2NodeFunctionEntry, K2NodeEvent, K2NodeCallFunction
from uasset_read.models.core import FEdGraphPinType, FMemberReference, UEdGraphPin, UEdGraph


# ============================================================================
# Wave 2a: Plan 02 — Function Signature Extraction Tests
# ============================================================================

class TestSanitizeIdentifier:
    """_sanitize_identifier tests."""

    def test_slash_removal(self):
        assert _sanitize_identifier("Left / Right") == "LeftRight"

    def test_space_removal(self):
        assert _sanitize_identifier("Primary Thumbstick") == "PrimaryThumbstick"

    def test_underscore_preserved(self):
        assert _sanitize_identifier("Axis_X") == "Axis_X"

    def test_leading_digit(self):
        assert _sanitize_identifier("2DValue") == "_2DValue"

    def test_empty_string(self):
        assert _sanitize_identifier("") == "unnamed"


def _make_pin(name: str, category: str = "real", subcategory: str = "double",
              direction: int = 0, is_reference: bool = False, is_const: bool = False,
              hidden: bool = False) -> UEdGraphPin:
    """Helper to create a test pin."""
    return UEdGraphPin(
        pin_id=f"pin_{name}",
        pin_name=name,
        direction=direction,
        pin_type=FEdGraphPinType(
            pin_category=category,
            pin_subcategory=subcategory,
            is_reference=is_reference,
            is_const=is_const,
        ),
        hidden=hidden,
    )


class TestExtractCppTypeFromPin:
    """_extract_cpp_type_from_pin tests."""

    def test_real_type(self):
        pin = _make_pin("test", category="real", subcategory="double")
        assert _extract_cpp_type_from_pin(pin) == "double"

    def test_const_ref(self):
        pin = _make_pin("test", category="real", subcategory="double", is_reference=True, is_const=True)
        assert _extract_cpp_type_from_pin(pin) == "const double&"

    def test_ref_only(self):
        pin = _make_pin("test", category="real", subcategory="double", is_reference=True, is_const=False)
        assert _extract_cpp_type_from_pin(pin) == "double&"

    def test_exec_skipped(self):
        pin = _make_pin("execute", category="exec")
        assert _extract_cpp_type_from_pin(pin) is None


class TestExtractParametersFromPins:
    """_extract_parameters_from_pins tests."""

    def test_move_pins(self):
        pins = [
            _make_pin("Left / Right", direction=1),
            _make_pin("Forward / Backward", direction=1),
        ]
        params = _extract_parameters_from_pins(pins)
        assert len(params) == 2
        assert params[0].name == "LeftRight"
        assert params[0].cpp_type == "double"
        assert params[1].name == "ForwardBackward"

    def test_skips_exec(self):
        pins = [
            _make_pin("execute", category="exec", direction=0),
            _make_pin("test", direction=1),
        ]
        params = _extract_parameters_from_pins(pins)
        assert len(params) == 1
        assert params[0].name == "test"

    def test_skips_hidden(self):
        pins = [_make_pin("hidden_pin", hidden=True)]
        assert _extract_parameters_from_pins(pins) == []

    def test_event_skips_delegate_and_then(self):
        pins = [
            _make_pin("OutputDelegate", category="delegate", direction=1),
            _make_pin("then", category="exec", direction=1),
            _make_pin("Axis_X", direction=1),
        ]
        params = _extract_parameters_from_pins(pins, is_event=True)
        assert len(params) == 1
        assert params[0].name == "Axis_X"


class TestInferUfunctionSpecifiers:
    """_infer_ufunction_specifiers tests."""

    def test_pure_no_exec(self):
        pins = [_make_pin("result", direction=1)]
        assert _infer_ufunction_specifiers(pins, "K2Node_FunctionEntry", False) == ["BlueprintPure"]

    def test_callable_exec_output(self):
        pins = [_make_pin("then", category="exec", direction=1)]
        assert _infer_ufunction_specifiers(pins, "K2Node_FunctionEntry", False) == ["BlueprintCallable"]

    def test_callable_exec_input(self):
        pins = [_make_pin("execute", category="exec", direction=0)]
        assert _infer_ufunction_specifiers(pins, "K2Node_FunctionEntry", False) == ["BlueprintCallable"]

    def test_override_empty(self):
        pins = [_make_pin("then", category="exec", direction=1)]
        assert _infer_ufunction_specifiers(pins, "K2Node_Event", True) == []


class TestExtractCppFunctions:
    """extract_cpp_functions() integration tests."""

    def _make_function_entry(self, name: str, pins=None):
        node = MagicMock(spec=K2NodeFunctionEntry)
        node.class_name = "K2Node_FunctionEntry"
        node.function_reference = FMemberReference(member_name=name, b_self_context=False)
        node.pins = pins or [_make_pin("then", category="exec", direction=1)]
        node.b_is_editable = True
        node.extra_flags = 0
        return node

    def _make_event_override(self, name: str, pins=None):
        node = MagicMock(spec=K2NodeEvent)
        node.class_name = "K2Node_Event"
        node.event_reference = FMemberReference(member_name=name, b_self_context=False)
        node.pins = pins or [_make_pin("then", category="exec", direction=1)]
        node.b_override_function = True
        return node

    def test_extract_move_function(self):
        pins = [
            _make_pin("then", category="exec", direction=1),
            _make_pin("Left / Right", direction=1),
            _make_pin("Forward / Backward", direction=1),
        ]
        graph = MagicMock(spec=UEdGraph)
        graph.nodes = [self._make_function_entry("Move", pins)]
        result = extract_cpp_functions([graph])
        assert len(result) == 1
        m = result[0]
        assert m.cpp_name == "Move"
        assert m.return_type == "void"
        assert len(m.parameters) == 2
        assert m.ufunction_specifiers == ["BlueprintCallable"]
        assert m.is_override is False

    def test_extract_event_override(self):
        pins = [
            _make_pin("OutputDelegate", category="delegate", direction=1),
            _make_pin("then", category="exec", direction=1),
            _make_pin("Axis_X", direction=1),
            _make_pin("Axis_Y", direction=1),
        ]
        graph = MagicMock(spec=UEdGraph)
        graph.nodes = [self._make_event_override("Primary Thumbstick", pins)]
        result = extract_cpp_functions([graph])
        assert len(result) == 1
        m = result[0]
        assert m.cpp_name == "PrimaryThumbstick"
        assert m.is_override is True
        assert m.ufunction_specifiers == []
        assert len(m.parameters) == 2


# ============================================================================
# Wave 2b: Plan 03 — Call Statement Extraction Tests
# ============================================================================

class TestDeriveCallTarget:
    """_derive_call_target tests."""

    def test_self_context(self):
        assert _derive_call_target([], True) == ("this", "this")

    def test_no_self_context_no_self_pin(self):
        assert _derive_call_target([], False) == ("Unknown", "pointer")

    def test_no_self_context_with_self_pin(self):
        pin = UEdGraphPin(
            pin_id="self",
            pin_name="self",
            pin_type=FEdGraphPinType(
                pin_category="object",
                pin_subcategory="/Script/CoreUObject.Class'/Script/Engine.Character'",
            ),
        )
        target, ttype = _derive_call_target([pin], False)
        # ue_path_to_cpp_type should resolve this to ACharacter or similar
        assert ttype == "pointer"
        assert "Character" in target or "ACharacter" in target


class TestExtractCallStatementJump:
    """extract_cpp_call_statements — Jump call test."""

    def _make_call_node(self, name: str, b_self_context: bool = True, pins=None):
        node = MagicMock(spec=K2NodeCallFunction)
        node.class_name = "K2Node_CallFunction"
        node.function_reference = FMemberReference(member_name=name, b_self_context=b_self_context)
        node.pins = pins or [
            _make_pin("execute", category="exec", direction=0),
            _make_pin("then", category="exec", direction=1),
            UEdGraphPin(pin_id="self_pin", pin_name="self",
                        pin_type=FEdGraphPinType(pin_category="object",
                                                 pin_subcategory="/Script/CoreUObject.Class'/Script/Engine.Character'")),
        ]
        return node

    def test_jump_call(self):
        graph = MagicMock(spec=UEdGraph)
        graph.nodes = [self._make_call_node("Jump")]
        result = extract_cpp_call_statements([graph])
        assert len(result) == 1
        s = result[0]
        assert s.method_name == "Jump"
        assert s.target == "this"
        assert s.args == []
        assert s.is_self_context is True

    def test_call_with_args(self):
        pins = [
            _make_pin("execute", category="exec", direction=0),
            _make_pin("then", category="exec", direction=1),
            _make_pin("Left / Right", direction=0),
            _make_pin("Forward / Backward", direction=0),
        ]
        graph = MagicMock(spec=UEdGraph)
        graph.nodes = [self._make_call_node("Move", pins=pins)]
        result = extract_cpp_call_statements([graph])
        assert len(result) == 1
        assert result[0].method_name == "Move"
        assert result[0].args == ["LeftRight", "ForwardBackward"]

    def test_no_self_context(self):
        pins = [
            _make_pin("execute", category="exec", direction=0),
            _make_pin("then", category="exec", direction=1),
            UEdGraphPin(pin_id="self_pin", pin_name="self",
                        pin_type=FEdGraphPinType(pin_category="object",
                                                 pin_subcategory="/Script/CoreUObject.Class'/Script/Engine.Character'")),
        ]
        graph = MagicMock(spec=UEdGraph)
        graph.nodes = [self._make_call_node("SomeMethod", b_self_context=False, pins=pins)]
        result = extract_cpp_call_statements([graph])
        assert len(result) == 1
        assert result[0].target != "this"
        assert result[0].target_type == "pointer"

    def test_skips_special_pins(self):
        pins = [
            _make_pin("execute", category="exec", direction=0),
            _make_pin("then", category="exec", direction=1),
            UEdGraphPin(pin_id="self_pin", pin_name="self",
                        pin_type=FEdGraphPinType(pin_category="object")),
            _make_pin("data_param", direction=0),
        ]
        graph = MagicMock(spec=UEdGraph)
        graph.nodes = [self._make_call_node("Test", pins=pins)]
        result = extract_cpp_call_statements([graph])
        assert len(result) == 1
        # Only data_param should be in args
        assert result[0].args == ["data_param"]

    def test_null_function_reference(self):
        node = MagicMock(spec=K2NodeCallFunction)
        node.class_name = "K2Node_CallFunction"
        node.function_reference = None
        graph = MagicMock(spec=UEdGraph)
        graph.nodes = [node]
        result = extract_cpp_call_statements([graph])
        assert result == []

    def test_none_member_name(self):
        node = MagicMock(spec=K2NodeCallFunction)
        node.class_name = "K2Node_CallFunction"
        node.function_reference = FMemberReference(member_name="None", b_self_context=True)
        graph = MagicMock(spec=UEdGraph)
        graph.nodes = [node]
        result = extract_cpp_call_statements([graph])
        assert result == []


# ============================================================================
# Wave 3: Plan 04 — Formatter Tests
# ============================================================================

class TestFormatMethodDeclaration:
    """_format_method_declaration tests."""

    def test_move_method(self):
        method = CppMethodIR(
            cpp_name="Move",
            return_type="void",
            parameters=[
                CppCallParameter("LeftRight", "double", "input"),
                CppCallParameter("ForwardBackward", "double", "input"),
            ],
            ufunction_specifiers=["BlueprintCallable"],
            is_override=False,
        )
        lines = _format_method_declaration(method)
        assert lines == [
            "    UFUNCTION(BlueprintCallable)",
            "    void Move(double LeftRight, double ForwardBackward);",
        ]

    def test_override_method(self):
        method = CppMethodIR(
            cpp_name="PrimaryThumbstick",
            return_type="void",
            parameters=[
                CppCallParameter("Axis_X", "double", "input"),
                CppCallParameter("Axis_Y", "double", "input"),
            ],
            ufunction_specifiers=[],
            is_override=True,
        )
        lines = _format_method_declaration(method)
        assert lines == [
            "    void PrimaryThumbstick(double Axis_X, double Axis_Y) override;",
        ]

    def test_const_pure_function(self):
        method = CppMethodIR(
            cpp_name="GetVelocity",
            return_type="FVector",
            parameters=[],
            ufunction_specifiers=["BlueprintPure"],
            is_override=False,
            is_const=True,
        )
        lines = _format_method_declaration(method)
        assert "const;" in lines[-1]
        assert "UFUNCTION(BlueprintPure)" in lines[0]


class TestFormatCallStatements:
    """format_cpp_call_statements tests."""

    def test_jump_call(self):
        stmt = CppCallStatement(method_name="Jump", target="this", args=[])
        result = format_cpp_call_statements([stmt])
        assert "this->Jump();" in result

    def test_move_call(self):
        stmt = CppCallStatement(method_name="Move", target="this", args=["LeftRight", "ForwardBackward"])
        result = format_cpp_call_statements([stmt])
        assert "this->Move(LeftRight, ForwardBackward);" in result

    def test_empty_list(self):
        assert format_cpp_call_statements([]) == ""

    def test_import_from_cpp_gen(self):
        from uasset_read.cpp_gen import format_cpp_call_statements
        assert format_cpp_call_statements is not None

    def test_import_from_formatters(self):
        from uasset_read.cpp_gen.formatters import format_cpp_call_statements
        assert format_cpp_call_statements is not None


# ============================================================================
# Wave 4: Plan 05 — Golden-path Integration Tests
# ============================================================================

class TestFunctionSignatureGoldenPath:
    """Golden-path integration tests matching BP_FirstPersonCharacter reference data."""

    def _make_function_entry_move(self):
        """K2Node_FunctionEntry for Move function (reference data)."""
        node = MagicMock(spec=K2NodeFunctionEntry)
        node.class_name = "K2Node_FunctionEntry"
        node.function_reference = FMemberReference(member_name="Move", b_self_context=False)
        node.pins = [
            _make_pin("then", category="exec", direction=1),
            _make_pin("Left / Right", direction=1),
            _make_pin("Forward / Backward", direction=1),
        ]
        node.b_is_editable = True
        node.extra_flags = 0
        return node

    def _make_event_primary_thumbstick(self):
        """K2Node_Event for Primary Thumbstick override."""
        node = MagicMock(spec=K2NodeEvent)
        node.class_name = "K2Node_Event"
        node.event_reference = FMemberReference(member_name="Primary Thumbstick", b_self_context=False)
        node.b_override_function = True
        node.pins = [
            _make_pin("OutputDelegate", category="delegate", direction=1),
            _make_pin("then", category="exec", direction=1),
            _make_pin("Axis_X", direction=1),
            _make_pin("Axis_Y", direction=1),
        ]
        return node

    def _make_call_jump(self):
        """K2Node_CallFunction for Jump."""
        node = MagicMock(spec=K2NodeCallFunction)
        node.class_name = "K2Node_CallFunction"
        node.function_reference = FMemberReference(member_name="Jump", b_self_context=True)
        node.pins = [
            _make_pin("execute", category="exec", direction=0),
            _make_pin("then", category="exec", direction=1),
            UEdGraphPin(pin_id="self", pin_name="self",
                        pin_type=FEdGraphPinType(pin_category="object",
                                                 pin_subcategory="/Script/CoreUObject.Class'/Script/Engine.Character'")),
        ]
        return node

    def _make_call_stop_jumping(self):
        """K2Node_CallFunction for StopJumping."""
        node = MagicMock(spec=K2NodeCallFunction)
        node.class_name = "K2Node_CallFunction"
        node.function_reference = FMemberReference(member_name="StopJumping", b_self_context=True)
        node.pins = [
            _make_pin("execute", category="exec", direction=0),
            _make_pin("then", category="exec", direction=1),
            UEdGraphPin(pin_id="self", pin_name="self",
                        pin_type=FEdGraphPinType(pin_category="object",
                                                 pin_subcategory="/Script/CoreUObject.Class'/Script/Engine.Character'")),
        ]
        return node

    def _make_graph_with_all(self):
        """Mock UEdGraph with all nodes."""
        graph = MagicMock(spec=UEdGraph)
        graph.nodes = [
            self._make_function_entry_move(),
            self._make_event_primary_thumbstick(),
            self._make_call_jump(),
            self._make_call_stop_jumping(),
        ]
        return graph

    def test_golden_move_function_signature(self):
        """Move function: UFUNCTION(BlueprintCallable) void Move(double LeftRight, double ForwardBackward);"""
        graph = self._make_graph_with_all()
        methods = extract_cpp_functions([graph])
        move = [m for m in methods if m.cpp_name == "Move"]
        assert len(move) == 1
        m = move[0]
        assert m.return_type == "void"
        assert len(m.parameters) == 2
        assert m.ufunction_specifiers == ["BlueprintCallable"]
        assert m.is_override is False
        assert m.source_node_type == "K2Node_FunctionEntry"

    def test_golden_event_override(self):
        """PrimaryThumbstick: void PrimaryThumbstick(double Axis_X, double Axis_Y) override;"""
        graph = self._make_graph_with_all()
        methods = extract_cpp_functions([graph])
        thumb = [m for m in methods if m.cpp_name == "PrimaryThumbstick"]
        assert len(thumb) == 1
        m = thumb[0]
        assert m.is_override is True
        assert m.ufunction_specifiers == []
        assert len(m.parameters) == 2
        assert m.source_node_type == "K2Node_Event"

    def test_golden_jump_call_statement(self):
        """Jump call: this->Jump();"""
        graph = self._make_graph_with_all()
        calls = extract_cpp_call_statements([graph])
        jump = [c for c in calls if c.method_name == "Jump"]
        assert len(jump) == 1
        assert jump[0].target == "this"
        assert jump[0].args == []

    def test_golden_full_header_output(self):
        """Full pipeline: extract → attach to CppClassIR → format_cpp_header."""
        graph = self._make_graph_with_all()
        methods = extract_cpp_functions([graph])

        ir = CppClassIR(
            name="ABP_FirstPersonCharacter",
            parent_class="ACharacter",
            methods=methods,
        )
        header = format_cpp_header(ir)

        # Verify Move function
        assert "UFUNCTION(BlueprintCallable)" in header
        assert "void Move(double LeftRight, double ForwardBackward);" in header

        # Verify PrimaryThumbstick override
        assert "void PrimaryThumbstick(double Axis_X, double Axis_Y) override;" in header

    def test_golden_call_statements_output(self):
        """Full pipeline: extract calls → format_cpp_call_statements."""
        graph = self._make_graph_with_all()
        calls = extract_cpp_call_statements([graph])
        output = format_cpp_call_statements(calls)

        assert "this->Jump();" in output
        assert "this->StopJumping();" in output


class TestCppMethodIR:
    """CppMethodIR dataclass field and serialization tests."""

    def test_cpp_method_ir_fields(self):
        """Verify CppMethodIR has all required fields and to_dict() works."""
        method = CppMethodIR(
            cpp_name="Move",
            return_type="void",
            parameters=[
                CppCallParameter(name="LeftRight", cpp_type="double", direction="input"),
                CppCallParameter(name="ForwardBackward", cpp_type="double", direction="input"),
            ],
            ufunction_specifiers=["BlueprintCallable"],
            is_override=False,
            is_const=False,
            source_node_type="K2Node_FunctionEntry",
        )
        assert method.cpp_name == "Move"
        assert method.return_type == "void"
        assert len(method.parameters) == 2
        assert method.ufunction_specifiers == ["BlueprintCallable"]
        assert method.is_override is False
        assert method.source_node_type == "K2Node_FunctionEntry"

        d = method.to_dict()
        assert d["cpp_name"] == "Move"
        assert d["return_type"] == "void"
        assert len(d["parameters"]) == 2
        assert d["parameters"][0]["name"] == "LeftRight"
        assert d["ufunction_specifiers"] == ["BlueprintCallable"]
        assert d["is_override"] is False
        assert d["source_node_type"] == "K2Node_FunctionEntry"

    def test_cpp_method_ir_defaults(self):
        """Verify default values."""
        method = CppMethodIR(
            cpp_name="Test",
            return_type="void",
            parameters=[],
            ufunction_specifiers=[],
            is_override=False,
        )
        assert method.is_const is False
        assert method.source_node_type == ""


class TestCppCallParameter:
    """CppCallParameter dataclass field and serialization tests."""

    def test_cpp_call_parameter_fields(self):
        """Verify CppCallParameter has all required fields."""
        param = CppCallParameter(name="Axis_X", cpp_type="double", direction="input")
        assert param.name == "Axis_X"
        assert param.cpp_type == "double"
        assert param.direction == "input"

        d = param.to_dict()
        assert d == {"name": "Axis_X", "cpp_type": "double", "direction": "input"}


class TestCppCallStatement:
    """CppCallStatement dataclass field and serialization tests."""

    def test_cpp_call_statement_fields(self):
        """Verify CppCallStatement has all required fields."""
        stmt = CppCallStatement(
            method_name="Jump",
            target="this",
            target_type="this",
            args=[],
            is_self_context=True,
        )
        assert stmt.method_name == "Jump"
        assert stmt.target == "this"
        assert stmt.target_type == "this"
        assert stmt.args == []
        assert stmt.is_self_context is True

        d = stmt.to_dict()
        assert d["method_name"] == "Jump"
        assert d["target"] == "this"
        assert d["target_type"] == "this"
        assert d["args"] == []
        assert d["is_self_context"] is True

    def test_cpp_call_statement_defaults(self):
        """Verify default values."""
        stmt = CppCallStatement(method_name="Test", target="Other")
        assert stmt.target_type == "pointer"
        assert stmt.args == []
        assert stmt.is_self_context is True


class TestCppClassIRMethodsTyped:
    """CppClassIR.methods typed as List[CppMethodIR]."""

    def test_cpp_class_ir_methods_typed(self):
        """Verify CppClassIR can hold CppMethodIR instances and serialize."""
        ir = CppClassIR(
            name="ABP_Test",
            parent_class="ACharacter",
            methods=[
                CppMethodIR(
                    cpp_name="Move",
                    return_type="void",
                    parameters=[CppCallParameter("LeftRight", "double", "input")],
                    ufunction_specifiers=["BlueprintCallable"],
                    is_override=False,
                ),
            ],
        )
        assert len(ir.methods) == 1
        assert isinstance(ir.methods[0], CppMethodIR)

        d = ir.to_dict()
        assert "methods" in d
        assert len(d["methods"]) == 1
        assert d["methods"][0]["cpp_name"] == "Move"


class TestExports:
    """Verify exports from both cpp_gen and formatters."""

    def test_import_from_cpp_gen(self):
        from uasset_read.cpp_gen import CppMethodIR, CppCallParameter, CppCallStatement
        assert CppMethodIR is not None
        assert CppCallParameter is not None
        assert CppCallStatement is not None

    def test_import_from_formatters(self):
        from uasset_read.cpp_gen.formatters import CppMethodIR, CppCallParameter, CppCallStatement
        assert CppMethodIR is not None
        assert CppCallParameter is not None
        assert CppCallStatement is not None
