"""Kismet 模块合并测试 — 覆盖主链路、边界与恢复场景。

保留 5 个关键用例：
1. 函数引用解析（FunctionRefResolver 基础功能）
2. CFG 构建（空/条件分支）
3. JumpAnalyzer 控制流模式检测（if-else）
4. 字节码恢复（_has_false_positive_pattern）
5. 数学函数简化（MathFunctionCleaner）
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from uasset_read.kismet.bytecode_extractor import _has_false_positive_pattern
from uasset_read.kismet.cfg import build_cfg
from uasset_read.kismet.cfg.data import EdgeKind
from uasset_read.kismet.expressions.control_flow import EX_Jump, EX_JumpIfNot
from uasset_read.kismet.function_resolver import FunctionRefResolver
from uasset_read.kismet.jump_analyzer import JumpAnalyzer
from uasset_read.kismet.translator import MathFunctionCleaner


# ============================================================================
# 辅助工厂
# ============================================================================

def _make_linker():
    return MagicMock()

def _make_instance(object_name, object_class=None, outer=None):
    inst = MagicMock()
    inst.object_name = object_name
    inst.object_class = object_class
    inst.outer = outer
    return inst

def _stub(statement_index: int, label: str = "stmt"):
    class _Stub:
        StatementIndex = statement_index
        def __repr__(self):
            return f"<Stub {label}@{statement_index}>"
    return _Stub()

def _make_let(stmt_idx: int):
    from uasset_read.kismet.expressions.assignments import EX_Let
    e = EX_Let()
    e.StatementIndex = stmt_idx
    return e

def _make_jump_if_not(stmt_idx: int, code_offset: int) -> EX_JumpIfNot:
    e = EX_JumpIfNot(CodeOffset=code_offset, BooleanExpression=None)
    e.StatementIndex = stmt_idx
    return e

def _make_end(stmt_idx: int):
    from uasset_read.kismet.expressions.control_flow import EX_EndOfScript
    e = EX_EndOfScript()
    e.StatementIndex = stmt_idx
    return e


# ============================================================================
# 用例 1: 函数引用解析
# ============================================================================

class TestFunctionRefResolution:
    def test_basic_resolution(self):
        """正数 StackNode 应解析为 ClassName::FuncName 格式。"""
        linker = _make_linker()
        inst = _make_instance("ReceiveBeginPlay", object_class="AActor")
        linker.resolve_package_index.return_value = inst
        resolver = FunctionRefResolver(linker)
        assert resolver.resolve_string(1) == "AActor::ReceiveBeginPlay"


# ============================================================================
# 用例 2: CFG 构建
# ============================================================================

class TestBuildCfg:
    def test_conditional_edges(self):
        """JumpIfNot 应产生 CONDITIONAL + FALSE_BRANCH 边。"""
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)
        cfg = build_cfg([let0, jmp, let1, let2, end])
        bb0 = cfg.blocks[0]
        edge_kinds = set(bb0.edge_kinds.values())
        assert EdgeKind.CONDITIONAL in edge_kinds
        assert EdgeKind.FALSE_BRANCH in edge_kinds


# ============================================================================
# 用例 3: JumpAnalyzer 控制流模式检测
# ============================================================================

class TestControlFlowDetection:
    def test_if_else_pattern(self):
        """JumpIfNot → then → Jump(end) → else → end 应识别为 if_else。"""
        cond = _stub(0)
        jin = EX_JumpIfNot(CodeOffset=30, BooleanExpression=cond)
        jin.StatementIndex = 1
        then_body = _stub(20)
        jmp_end = EX_Jump(CodeOffset=50)
        jmp_end.StatementIndex = 25
        else_body = _stub(30)
        end_expr = _stub(50)
        exprs = [cond, jin, then_body, jmp_end, else_body, end_expr]
        analyzer = JumpAnalyzer(exprs)
        result = analyzer.detect_if_else_pattern(1)
        assert result is not None
        assert result["type"] == "if_else"


# ============================================================================
# 用例 4: 字节码恢复
# ============================================================================

class TestBytecodeRecovery:
    def test_valid_bytecode_preserved(self):
        """有效字节码不应被过滤。"""
        data = bytes([0x04, 0x1C, 0x01, 0x02, 0x03, 0x04, 0x53])
        assert _has_false_positive_pattern(data) is False


# ============================================================================
# 用例 5: 数学函数简化
# ============================================================================

class TestMathFunctionCleaner:
    def test_add_int_int(self):
        """Add_IntInt->a+b；未知->ClassName::FuncName。"""
        assert MathFunctionCleaner.clean("KismetMathLibrary", "Add_IntInt", ["a", "b"]) == "a + b"
        assert MathFunctionCleaner.clean("KismetMathLibrary", "SomeUnknownFunc", ["a", "b"]) == "KismetMathLibrary::SomeUnknownFunc(a, b)"
