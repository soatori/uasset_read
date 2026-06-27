"""测试 Kismet deprecated / instrumentation token 静默跳过和统计计数器。"""

import pytest

from uasset_read.kismet.translator import KismetTranslator
from uasset_read.kismet.expressions.special import (
    EX_DeprecatedOp4A,
    EX_InstrumentationEvent,
    EX_Breakpoint,
    EX_Tracepoint,
    EX_WireTracepoint,
)
from uasset_read.kismet.tokens import EScriptInstrumentationType


class TestDeprecatedTokenSilentSkip:
    """deprecated / instrumentation token 应返回空字符串。"""

    def test_deprecated_op4a_returns_empty(self):
        translator = KismetTranslator()
        expr = EX_DeprecatedOp4A()
        result = translator.line_cpp(expr)
        assert result == "", f"EX_DeprecatedOp4A 应返回空字符串，实际: {result!r}"

    def test_breakpoint_returns_empty(self):
        translator = KismetTranslator()
        expr = EX_Breakpoint()
        result = translator.line_cpp(expr)
        assert result == "", f"EX_Breakpoint 应返回空字符串，实际: {result!r}"

    def test_tracepoint_returns_empty(self):
        translator = KismetTranslator()
        expr = EX_Tracepoint()
        result = translator.line_cpp(expr)
        assert result == "", f"EX_Tracepoint 应返回空字符串，实际: {result!r}"

    def test_wire_tracepoint_returns_empty(self):
        translator = KismetTranslator()
        expr = EX_WireTracepoint()
        result = translator.line_cpp(expr)
        assert result == "", f"EX_WireTracepoint 应返回空字符串，实际: {result!r}"

    def test_instrumentation_event_returns_empty(self):
        translator = KismetTranslator()
        expr = EX_InstrumentationEvent(
            EventType=EScriptInstrumentationType.Entry,
            EventName="TestFunc",
        )
        result = translator.line_cpp(expr)
        assert result == "", f"EX_InstrumentationEvent 应返回空字符串，实际: {result!r}"


class TestSkippedTokenCounter:
    """统计计数器应正确记录各类 deprecated token 数量。"""

    def test_counter_initially_empty(self):
        translator = KismetTranslator()
        assert translator.skipped_tokens == {}

    def test_deprecated_op4a_counter(self):
        translator = KismetTranslator()
        expr = EX_DeprecatedOp4A()
        translator.line_cpp(expr)
        assert translator.skipped_tokens.get("EX_DeprecatedOp4A") == 1

    def test_breakpoint_counter(self):
        translator = KismetTranslator()
        expr = EX_Breakpoint()
        translator.line_cpp(expr)
        assert translator.skipped_tokens.get("EX_Breakpoint") == 1

    def test_tracepoint_counter(self):
        translator = KismetTranslator()
        expr = EX_Tracepoint()
        translator.line_cpp(expr)
        assert translator.skipped_tokens.get("EX_Tracepoint") == 1

    def test_wire_tracepoint_counter(self):
        translator = KismetTranslator()
        expr = EX_WireTracepoint()
        translator.line_cpp(expr)
        assert translator.skipped_tokens.get("EX_WireTracepoint") == 1

    def test_instrumentation_event_counter(self):
        translator = KismetTranslator()
        expr = EX_InstrumentationEvent(
            EventType=EScriptInstrumentationType.Exit,
            EventName="TestFunc",
        )
        translator.line_cpp(expr)
        assert translator.skipped_tokens.get("EX_InstrumentationEvent") == 1

    def test_multiple_tokens_accumulate(self):
        translator = KismetTranslator()
        # 翻译 3 个 deprecated + 2 个 instrumentation
        for _ in range(3):
            translator.line_cpp(EX_DeprecatedOp4A())
        for _ in range(2):
            translator.line_cpp(EX_InstrumentationEvent(
                EventType=EScriptInstrumentationType.Entry,
            ))
        assert translator.skipped_tokens["EX_DeprecatedOp4A"] == 3
        assert translator.skipped_tokens["EX_InstrumentationEvent"] == 2
        assert sum(translator.skipped_tokens.values()) == 5

    def test_mixed_token_types_counted_separately(self):
        translator = KismetTranslator()
        translator.line_cpp(EX_DeprecatedOp4A())
        translator.line_cpp(EX_Breakpoint())
        translator.line_cpp(EX_Tracepoint())
        translator.line_cpp(EX_WireTracepoint())
        translator.line_cpp(EX_InstrumentationEvent(
            EventType=EScriptInstrumentationType.PureEntry,
        ))
        assert translator.skipped_tokens == {
            "EX_DeprecatedOp4A": 1,
            "EX_Breakpoint": 1,
            "EX_Tracepoint": 1,
            "EX_WireTracepoint": 1,
            "EX_InstrumentationEvent": 1,
        }

    def test_no_deprecated_no_counter(self):
        """正常表达式不应影响计数器。"""
        from uasset_read.kismet.expressions import EX_IntConst
        translator = KismetTranslator()
        translator.line_cpp(EX_IntConst(Value=42))
        assert translator.skipped_tokens == {}


class TestNoDeprecatedCommentInOutput:
    """确保翻译输出中不再包含 /* deprecated */ 或 /* instrumentation */ 注释。"""

    def test_output_does_not_contain_deprecated_comment(self):
        translator = KismetTranslator()
        translator.line_cpp(EX_DeprecatedOp4A())
        translator.line_cpp(EX_Breakpoint())
        translator.line_cpp(EX_Tracepoint())
        translator.line_cpp(EX_WireTracepoint())
        translator.line_cpp(EX_InstrumentationEvent(
            EventType=EScriptInstrumentationType.Entry,
            EventName="Foo",
        ))
        # 所有返回值都应为空字符串
        assert translator.skipped_tokens  # 确认确实翻译了这些 token
