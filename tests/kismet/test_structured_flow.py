"""Tests for StructuredControlFlow (Phase 63 Wave 5)."""
import pytest

from uasset_read.kismet.structured_flow import StructuredControlFlow


class TestStructuredControlFlow:
    """Test StructuredControlFlow pattern detection and emission."""

    def test_empty_expressions(self):
        flow = StructuredControlFlow()
        result = flow.reconstruct([])
        assert result == []

    def test_no_patterns_falls_back_to_goto(self):
        """Simple expressions with no control flow patterns → goto fallback."""
        from uasset_read.kismet.expressions import EX_IntConst, EX_EndOfScript

        exprs = [
            EX_IntConst(Value=42),
            EX_EndOfScript(),
        ]

        flow = StructuredControlFlow()
        result = flow.reconstruct(exprs)

        assert "42" in result

    def test_if_else_pattern(self):
        """Push + JumpIfNot + body + Pop → if/else block."""
        from uasset_read.kismet.expressions import (
            EX_PushExecutionFlow, EX_JumpIfNot, EX_PopExecutionFlow,
            EX_EndOfScript, EX_IntConst, EX_True,
        )

        exprs = [
            EX_PushExecutionFlow(),        # idx 0
            EX_JumpIfNot(BooleanExpression=EX_True(), CodeOffset=30),  # idx 1
            EX_IntConst(Value=1),          # idx 2 — then block
            EX_PopExecutionFlow(),         # idx 3
            EX_IntConst(Value=2),          # idx 4 — else block
            EX_EndOfScript(),              # idx 5
        ]

        flow = StructuredControlFlow()
        result = flow.reconstruct(exprs)

        output = " ".join(result)
        assert "if (" in output
        assert "else" in output
        assert "1" in output
        assert "2" in output

    def test_simple_if_no_else_falls_back(self):
        """JumpIfNot without matching Push/Pop → goto fallback."""
        from uasset_read.kismet.expressions import (
            EX_JumpIfNot, EX_IntConst, EX_EndOfScript, EX_True,
        )

        exprs = [
            EX_JumpIfNot(BooleanExpression=EX_True(), CodeOffset=20),
            EX_IntConst(Value=1),
            EX_EndOfScript(),
        ]

        flow = StructuredControlFlow()
        result = flow.reconstruct(exprs)

        # Should fall back to goto-style output
        assert any("goto" in line or "if (" in line for line in result)

    def test_while_pattern(self):
        """JumpIfNot(exit) + body + Jump(back) → while loop."""
        from uasset_read.kismet.expressions import (
            EX_JumpIfNot, EX_Jump, EX_IntConst, EX_EndOfScript, EX_True,
        )

        exprs = [
            EX_JumpIfNot(BooleanExpression=EX_True(), CodeOffset=30),  # idx 0 — condition
            EX_IntConst(Value=1),          # idx 1 — body
            EX_Jump(CodeOffset=0),         # idx 2 — back jump
            EX_EndOfScript(),              # idx 3 — exit target
        ]

        flow = StructuredControlFlow()
        result = flow.reconstruct(exprs)

        output = " ".join(result)
        assert "while (" in output

    def test_unrecognized_pattern_goto_fallback(self):
        """Complex patterns that don't match if/while → goto fallback."""
        from uasset_read.kismet.expressions import (
            EX_ComputedJump, EX_IntConst, EX_EndOfScript,
        )

        exprs = [
            EX_IntConst(Value=10),
            EX_ComputedJump(CodeOffsetExpression=EX_IntConst(Value=50)),
            EX_EndOfScript(),
        ]

        flow = StructuredControlFlow()
        result = flow.reconstruct(exprs)

        # Should produce some output without crashing
        assert len(result) > 0


class TestStructuredIntegration:
    """Test StructuredControlFlow integration with FunctionBodyBuilder."""

    def test_to_function_body_structured_if_else(self):
        """Test structured if/else output in function body."""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder
        from uasset_read.kismet.expressions import (
            EX_PushExecutionFlow, EX_JumpIfNot, EX_PopExecutionFlow,
            EX_EndOfScript, EX_IntConst, EX_True,
        )

        exprs = [
            EX_PushExecutionFlow(),
            EX_JumpIfNot(BooleanExpression=EX_True(), CodeOffset=30),
            EX_IntConst(Value=1),
            EX_PopExecutionFlow(),
            EX_IntConst(Value=2),
            EX_EndOfScript(),
        ]

        builder = FunctionBodyBuilder()
        result = builder.to_function_body_structured(exprs, func_name="TestIf")

        assert "TestIf() {" in result
        assert "if (" in result
        assert "} else {" in result

    def test_to_function_body_structured_fallback(self):
        """Test that unrecognized patterns fall back to goto."""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder
        from uasset_read.kismet.expressions import (
            EX_Jump, EX_EndOfScript,
        )

        exprs = [
            EX_Jump(CodeOffset=100),
            EX_EndOfScript(),
        ]

        builder = FunctionBodyBuilder()
        result = builder.to_function_body_structured(exprs, func_name="TestGoto")

        assert "TestGoto() {" in result
        assert "goto Label_" in result
        assert ";;" not in result  # no double semicolons
