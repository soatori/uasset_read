"""Phase 57: C++ Method/Call IR data model tests."""
import pytest

from uasset_read.cpp_gen import CppMethodIR, CppCallParameter, CppCallStatement, CppClassIR
from uasset_read.cpp_gen.formatters import CppMethodIR as FCppMethodIR, CppCallParameter as FCppCallParameter, CppCallStatement as FCppCallStatement


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
