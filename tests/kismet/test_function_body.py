"""Tests for FunctionBodyBuilder (Phase 63 Wave 4)."""
import pytest

from uasset_read.kismet.body_builder import FunctionBodyBuilder, _needs_semicolon
from uasset_read.kismet.translator import TypeRegistry


class TestNeedsSemicolon:
    """Test _needs_semicolon helper."""

    def test_plain_expression_needs_semicolon(self):
        assert _needs_semicolon("x = 5") is True
        assert _needs_semicolon("return result") is True

    def test_already_terminated(self):
        assert _needs_semicolon("x = 5;") is False
        assert _needs_semicolon("return;") is False

    def test_control_flow_no_semicolon(self):
        assert _needs_semicolon("goto Label_100;") is False  # already has ;
        assert _needs_semicolon("if (!cond) goto Label_50;") is False
        assert _needs_semicolon("return;") is False

    def test_braces_no_semicolon(self):
        assert _needs_semicolon("{") is False
        assert _needs_semicolon("}") is False

    def test_empty_string(self):
        assert _needs_semicolon("") is False
        assert _needs_semicolon("   ") is False

    def test_comment_no_semicolon(self):
        assert _needs_semicolon("/* RTFM: begin */") is False

    def test_assert_no_semicolon(self):
        assert _needs_semicolon("assert(condition)") is False  # starts with assert(


class TestFunctionBodyBuilder:
    """Test FunctionBodyBuilder core functionality."""

    def test_empty_expressions(self):
        builder = FunctionBodyBuilder()
        result = builder.to_function_body([], func_name="EmptyFunc")
        assert "EmptyFunc()" in result
        assert "{\n}" in result or "{\n\n}" in result

    def test_simple_function_body(self):
        """Test basic function body with variable assignments and return."""
        from uasset_read.kismet.expressions import (
            EX_Let, EX_LocalVariable, EX_IntConst, EX_Return, EX_EndOfScript,
        )
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer, FFieldPath

        # Build expressions: x = 1; y = 2; return 3
        var_x = EX_LocalVariable(Variable=FKismetPropertyPointer(bNew=True, New=FFieldPath(Path=['x'])))
        var_y = EX_LocalVariable(Variable=FKismetPropertyPointer(bNew=True, New=FFieldPath(Path=['y'])))

        exprs = [
            EX_Let(Variable=var_x, Assignment=EX_IntConst(Value=1)),
            EX_Let(Variable=var_y, Assignment=EX_IntConst(Value=2)),
            EX_Return(ReturnExpression=EX_IntConst(Value=3)),
            EX_EndOfScript(),
        ]

        builder = FunctionBodyBuilder()
        result = builder.to_function_body(exprs, func_name="TestFunc")

        assert "TestFunc() {" in result
        assert "x = 1;" in result
        assert "y = 2;" in result
        assert "return 3;" in result

    def test_function_with_goto(self):
        """Test function body with jump/goto labels."""
        from uasset_read.kismet.expressions import (
            EX_JumpIfNot, EX_Jump, EX_EndOfScript, EX_True,
        )
        from uasset_read.kismet.property_pointer import FKismetPropertyPointer
        from uasset_read.kismet.property_pointer import FFieldPath

        var = FKismetPropertyPointer(bNew=True, New=FFieldPath(Path=['cond']))

        from uasset_read.kismet.expressions import EX_LocalVariable
        cond_var = EX_LocalVariable(Variable=var)

        exprs = [
            EX_JumpIfNot(BooleanExpression=cond_var, CodeOffset=20),
            EX_Jump(CodeOffset=30),
            EX_EndOfScript(),  # at offset 20 (label target)
            EX_EndOfScript(),  # at offset 30 (label target)
        ]

        builder = FunctionBodyBuilder()
        result = builder.to_function_body(exprs, func_name="GotoFunc")

        assert "GotoFunc() {" in result
        assert "if (!cond) goto Label_20;" in result
        assert "goto Label_30;" in result

    def test_indentation(self):
        """Test that all lines have 4-space indentation."""
        from uasset_read.kismet.expressions import (
            EX_IntConst, EX_EndOfScript,
        )

        exprs = [
            EX_IntConst(Value=42),
            EX_EndOfScript(),
        ]

        builder = FunctionBodyBuilder()
        result = builder.to_function_body(exprs, func_name="IndentTest")

        lines = result.split("\n")
        # Skip the opening '{' line
        body_lines = lines[1:-1]
        for line in body_lines:
            if line.strip():  # skip empty lines
                assert line.startswith("    "), f"Line not indented: {line!r}"

    def test_semicolons_added(self):
        """Test that semicolons are added to expression lines."""
        from uasset_read.kismet.expressions import (
            EX_IntConst, EX_EndOfScript,
        )

        exprs = [
            EX_IntConst(Value=42),
            EX_EndOfScript(),
        ]

        builder = FunctionBodyBuilder()
        result = builder.to_function_body(exprs, func_name="SemiTest")

        assert "42;" in result

    def test_semicolons_not_duplicated(self):
        """Test that existing semicolons are not duplicated."""
        from uasset_read.kismet.expressions import (
            EX_Jump, EX_EndOfScript,
        )

        exprs = [
            EX_Jump(CodeOffset=100),
            EX_EndOfScript(),
        ]

        builder = FunctionBodyBuilder()
        result = builder.to_function_body(exprs, func_name="NoDoubleSemi")

        # goto already has ;, should not become ;;
        assert ";;" not in result
        assert "goto Label_100;" in result

    def test_default_function_name(self):
        """Test that missing func_name uses default."""
        builder = FunctionBodyBuilder()
        result = builder.to_function_body([], func_name=None)
        assert "void UnknownFunction" in result

    def test_function_name_with_parens(self):
        """Test that func_name with parens is not double-wrapped."""
        builder = FunctionBodyBuilder()
        result = builder.to_function_body([], func_name="int MyFunc(int a)")
        assert "int MyFunc(int a) {" in result
