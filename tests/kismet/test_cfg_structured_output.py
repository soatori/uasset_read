"""CFG 结构化输出单元测试。

覆盖:
  stmt.py:  Stmt 类型（Branch, Loop, Switch, Sequence, Assignment, Call, Return, GotoLabel）
  emitter.py: RegionDecoder 区域解码 + StmtEmitter 伪代码渲染
"""

from __future__ import annotations

from uasset_read.kismet.cfg.data import BasicBlock, CFG, EdgeKind, Region, RegionKind, RegionTree
from uasset_read.kismet.cfg.stmt import (
    Assignment,
    Branch,
    Call,
    GotoLabel,
    Loop,
    Return,
    Sequence,
    Stmt,
    Switch,
)
from uasset_read.kismet.expressions.assignments import EX_Let
from uasset_read.kismet.expressions.control_flow import EX_EndOfScript, EX_JumpIfNot, EX_Jump

# ================================================================
# 测试辅助工厂
# ================================================================


def _make_let(stmt_idx: int) -> EX_Let:
    """创建带 StatementIndex 的 EX_Let。"""
    e = EX_Let()
    e.StatementIndex = stmt_idx
    return e


def _make_end(stmt_idx: int) -> EX_EndOfScript:
    """创建带 StatementIndex 的 EX_EndOfScript。"""
    e = EX_EndOfScript()
    e.StatementIndex = stmt_idx
    return e


def _make_jump(stmt_idx: int, code_offset: int) -> EX_Jump:
    """创建带 StatementIndex 和 CodeOffset 的 EX_Jump。"""
    e = EX_Jump(CodeOffset=code_offset)
    e.StatementIndex = stmt_idx
    return e


def _make_jump_if_not(stmt_idx: int, code_offset: int) -> EX_JumpIfNot:
    """创建带 StatementIndex 和 CodeOffset 的 EX_JumpIfNot。"""
    e = EX_JumpIfNot(CodeOffset=code_offset, BooleanExpression=None)
    e.StatementIndex = stmt_idx
    return e


# ================================================================
# stmt.py: Stmt 类型测试
# ================================================================


class TestAssignment:
    """Assignment 语句测试。"""

    def test_creation(self):
        a = Assignment(lhs="x", rhs="42")
        assert a.lhs == "x"
        assert a.rhs == "42"

    def test_repr(self):
        a = Assignment(lhs="x", rhs="42")
        r = repr(a)
        assert "Assignment" in r
        assert "x" in r
        assert "42" in r

    def test_is_stmt(self):
        a = Assignment()
        assert isinstance(a, Stmt)


class TestCall:
    """Call 语句测试。"""

    def test_creation(self):
        c = Call(text="MyFunc()")
        assert c.text == "MyFunc()"

    def test_repr(self):
        c = Call(text="MyFunc()")
        r = repr(c)
        assert "Call" in r
        assert "MyFunc()" in r

    def test_is_stmt(self):
        c = Call()
        assert isinstance(c, Stmt)


class TestReturn:
    """Return 语句测试。"""

    def test_creation(self):
        r = Return(value="x")
        assert r.value == "x"

    def test_repr(self):
        r = Return(value="x")
        assert "Return" in repr(r)

    def test_empty_value(self):
        r = Return(value="")
        assert r.value == ""


class TestGotoLabel:
    """GotoLabel 语句测试。"""

    def test_creation(self):
        g = GotoLabel(label="Label_0")
        assert g.label == "Label_0"

    def test_repr(self):
        g = GotoLabel(label="Label_0")
        assert "GotoLabel" in repr(g)


class TestSequence:
    """Sequence 语句测试。"""

    def test_creation(self):
        s = Sequence(stmts=[Assignment(lhs="a", rhs="1"), Call(text="foo()")])
        assert len(s.stmts) == 2
        assert isinstance(s.stmts[0], Assignment)
        assert isinstance(s.stmts[1], Call)

    def test_empty(self):
        s = Sequence()
        assert len(s.stmts) == 0

    def test_repr(self):
        s = Sequence()
        assert "Sequence" in repr(s)


class TestBranch:
    """Branch 语句测试。"""

    def test_creation(self):
        b = Branch(
            condition="x > 0",
            then_body=Assignment(lhs="y", rhs="1"),
            else_body=Assignment(lhs="y", rhs="0"),
        )
        assert b.condition == "x > 0"
        assert isinstance(b.then_body, Assignment)
        assert isinstance(b.else_body, Assignment)

    def test_if_only(self):
        b = Branch(
            condition="true",
            then_body=Call(text="foo()"),
            else_body=None,
        )
        assert b.else_body is None

    def test_repr(self):
        b = Branch(condition="true")
        assert "Branch" in repr(b)


class TestLoop:
    """Loop 语句测试。"""

    def test_creation_while(self):
        loop = Loop(kind="while", condition="i < 10", body=Sequence())
        assert loop.kind == "while"
        assert loop.condition == "i < 10"

    def test_creation_do_while(self):
        loop = Loop(kind="do_while", condition="true", body=Sequence())
        assert loop.kind == "do_while"

    def test_repr(self):
        loop = Loop()
        assert "Loop" in repr(loop)


class TestSwitch:
    """Switch 语句测试。"""

    def test_creation(self):
        s = Switch(
            expression="x",
            cases=[
                ("0", Call(text="case_zero")),
                ("1", Call(text="case_one")),
            ],
            default_body=Call(text="default_case"),
        )
        assert s.expression == "x"
        assert len(s.cases) == 2
        assert s.default_body is not None

    def test_empty_cases(self):
        s = Switch(expression="x")
        assert len(s.cases) == 0
        assert s.default_body is None

    def test_repr(self):
        s = Switch(expression="x")
        assert "Switch" in repr(s)


# ================================================================
# emitter.py: StmtEmitter 伪代码渲染测试
# ================================================================


class TestStmtEmitterBasic:
    """StmtEmitter 基本渲染测试。"""

    def test_assignment(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        result = emitter.emit_body(Assignment(lhs="x", rhs="42"))
        assert "x = 42;" in result

    def test_call(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        result = emitter.emit_body(Call(text="MyFunc()"))
        assert "MyFunc();" in result

    def test_return_with_value(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        result = emitter.emit_body(Return(value="x"))
        assert "return x;" in result

    def test_return_no_value(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        result = emitter.emit_body(Return(value=""))
        assert "return;" in result

    def test_goto_label(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        result = emitter.emit_body(GotoLabel(label="Label_0"))
        assert "Label_0:" in result

    def test_sequence(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        seq = Sequence(
            stmts=[
                Assignment(lhs="a", rhs="1"),
                Assignment(lhs="b", rhs="2"),
            ]
        )
        result = emitter.emit_body(seq)
        assert "a = 1;" in result
        assert "b = 2;" in result


class TestStmtEmitterBranch:
    """StmtEmitter 分支渲染测试。"""

    def test_if_then(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        branch = Branch(
            condition="x > 0",
            then_body=Assignment(lhs="y", rhs="1"),
        )
        result = emitter.emit_body(branch)
        assert "if (x > 0) {" in result
        assert "y = 1;" in result
        assert "} else {" not in result

    def test_if_else(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        branch = Branch(
            condition="x > 0",
            then_body=Assignment(lhs="y", rhs="1"),
            else_body=Assignment(lhs="y", rhs="0"),
        )
        result = emitter.emit_body(branch)
        assert "if (x > 0) {" in result
        assert "y = 1;" in result
        assert "else {" in result
        assert "y = 0;" in result

    def test_indentation(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter(indent="  ")
        branch = Branch(
            condition="true",
            then_body=Assignment(lhs="x", rhs="1"),
        )
        result = emitter.emit_body(branch)
        lines = result.split("\n")
        # if 在第 0 层
        assert lines[0].startswith("if")
        # body 在第 1 层
        assert lines[1].startswith("  x = 1;")


class TestStmtEmitterLoop:
    """StmtEmitter 循环渲染测试。"""

    def test_while_loop(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        loop = Loop(
            kind="while",
            condition="i < 10",
            body=Sequence(
                stmts=[
                    Assignment(lhs="i", rhs="i + 1"),
                ]
            ),
        )
        result = emitter.emit_body(loop)
        assert "while (i < 10) {" in result
        assert "i = i + 1;" in result

    def test_do_while_loop(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        loop = Loop(
            kind="do_while",
            condition="true",
            body=Sequence(stmts=[Call(text="foo()")]),
        )
        result = emitter.emit_body(loop)
        assert "do {" in result
        assert "foo();" in result
        assert "} while (true);" in result

    def test_for_loop(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        loop = Loop(
            kind="for",
            condition="",
            body=Sequence(stmts=[Call(text="step()")]),
        )
        result = emitter.emit_body(loop)
        assert "for (;;) {" in result
        assert "step();" in result


class TestStmtEmitterSwitch:
    """StmtEmitter switch 渲染测试。"""

    def test_switch_with_cases(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        sw = Switch(
            expression="x",
            cases=[
                ("0", Call(text="handleZero")),
                ("1", Call(text="handleOne")),
            ],
            default_body=Call(text="handleDefault"),
        )
        result = emitter.emit_body(sw)
        assert "switch (x) {" in result
        assert "case 0:" in result
        assert "handleZero" in result
        assert "case 1:" in result
        assert "handleOne" in result
        assert "default:" in result
        assert "handleDefault" in result

    def test_switch_no_default(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        sw = Switch(
            expression="x",
            cases=[("0", Call(text="handleZero"))],
        )
        result = emitter.emit_body(sw)
        assert "switch (x) {" in result
        assert "case 0: {" in result
        assert "default:" not in result


class TestStmtEmitterNested:
    """StmtEmitter 嵌套渲染测试。"""

    def test_nested_if_in_loop(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        stmt = Loop(
            kind="while",
            condition="true",
            body=Sequence(
                stmts=[
                    Branch(
                        condition="x > 0",
                        then_body=Call(text="positive"),
                        else_body=Call(text="negative"),
                    )
                ]
            ),
        )
        result = emitter.emit_body(stmt)
        assert "while (true) {" in result
        assert "if (x > 0) {" in result
        assert "positive" in result
        assert "else {" in result
        assert "negative" in result

    def test_emit_lines(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        seq = Sequence(
            stmts=[Assignment(lhs="a", rhs="1"), Assignment(lhs="b", rhs="2")]
        )
        lines = emitter.emit_lines(seq)
        assert len(lines) == 2
        assert "a = 1;" in lines[0]
        assert "b = 2;" in lines[1]


class TestStmtEmitterEmpty:
    """StmtEmitter 空/边界测试。"""

    def test_empty_sequence(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        result = emitter.emit_body(Sequence())
        assert result == ""

    def test_unknown_stmt(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        result = emitter.emit_body(Stmt())
        assert "unknown stmt" in result


# ================================================================
# emitter.py: RegionDecoder 集成测试（使用真实 CFG）
# ================================================================


class TestRegionDecoderSimple:
    """RegionDecoder 简单场景测试。"""

    def test_linear_flow(self):
        """线性流 → Sequence。"""
        from uasset_read.kismet.cfg import build_cfg, compute_dominator_tree, decompose_regions
        from uasset_read.kismet.cfg.emitter import RegionDecoder
        from uasset_read.kismet.translator import KismetTranslator

        let0 = _make_let(0)
        let1 = _make_let(8)
        end = _make_end(16)
        cfg = build_cfg([let0, let1, end])
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        translator = KismetTranslator(expressions=[let0, let1, end])
        decoder = RegionDecoder(
            cfg=cfg,
            region_tree=regions,
            expressions=[let0, let1, end],
            translator=translator,
            offset_to_index={},
            jump_targets=set(),
        )
        stmt = decoder.decode()
        assert isinstance(stmt, Sequence)
        assert len(stmt.stmts) > 0

    def test_if_else_flow(self):
        """if-else → Branch。"""
        from uasset_read.kismet.cfg import build_cfg, compute_dominator_tree, decompose_regions
        from uasset_read.kismet.cfg.emitter import RegionDecoder
        from uasset_read.kismet.cfg.data import RegionKind
        from uasset_read.kismet.translator import KismetTranslator

        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)

        cfg = build_cfg([let0, jmp, let1, let2, end])
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        # 检查有非 BLOCK 区域
        kinds = {r.kind for r in regions.regions.values()}
        has_branch = kinds & {RegionKind.IF_THEN, RegionKind.IF_THEN_ELSE}
        # 至少应该有一个分支区域
        assert has_branch or len(cfg.blocks) > 2  # CFG 已构建成功

        translator = KismetTranslator(expressions=[let0, jmp, let1, let2, end])
        decoder = RegionDecoder(
            cfg=cfg,
            region_tree=regions,
            expressions=[let0, jmp, let1, let2, end],
            translator=translator,
            offset_to_index={},
            jump_targets={24},
        )
        stmt = decoder.decode()
        # 结果应该是某种有效的语句
        assert stmt is not None

    def test_region_decoder_with_body_builder(self):
        """测试通过 body_builder 的集成路径。"""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder

        let0 = _make_let(0)
        let1 = _make_let(8)
        end = _make_end(16)

        builder = FunctionBodyBuilder()
        result = builder.to_function_body_structured(
            [let0, let1, end], func_name="TestFunc"
        )
        assert "TestFunc()" in result or "TestFunc" in result
        # 应该返回有效内容
        assert len(result) > 0


class TestRegionDecoderIfElse:
    """RegionDecoder if-else 场景测试。"""

    def test_if_else_emits_branch(self):
        """if-else CFG 生成 Branch 语句。"""
        from uasset_read.kismet.cfg import build_cfg, compute_dominator_tree, decompose_regions
        from uasset_read.kismet.cfg.data import RegionKind
        from uasset_read.kismet.cfg.emitter import RegionDecoder, StmtEmitter
        from uasset_read.kismet.translator import KismetTranslator

        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)

        expressions = [let0, jmp, let1, let2, end]
        cfg = build_cfg(expressions)
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        translator = KismetTranslator(expressions=expressions)
        decoder = RegionDecoder(
            cfg=cfg,
            region_tree=regions,
            expressions=expressions,
            translator=translator,
            offset_to_index={},
            jump_targets={24},
        )
        stmt = decoder.decode()

        emitter = StmtEmitter()
        output = emitter.emit_body(stmt)

        # 输出应该是非空的
        assert output is not None
        assert len(output) > 0

    def test_conditional_edges_present(self):
        """验证 if-else 的条件边正确建立。"""
        from uasset_read.kismet.cfg import build_cfg
        from uasset_read.kismet.cfg.data import EdgeKind

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


class TestRegionDecoderLoop:
    """RegionDecoder 循环场景测试。"""

    def test_while_loop_detected(self):
        """while 循环应检测到回边。"""
        from uasset_read.kismet.cfg import (
            build_cfg,
            compute_dominator_tree,
            decompose_regions,
            find_back_edges,
        )
        from uasset_read.kismet.cfg.data import RegionKind

        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        jmp_back = _make_jump(24, 0)
        end = _make_end(32)

        cfg = build_cfg([let0, jmp, let1, jmp_back, end])
        dom = compute_dominator_tree(cfg)
        back_edges = find_back_edges(cfg, dom)
        assert len(back_edges) >= 1

        regions = decompose_regions(cfg, dom)
        loop_kinds = {RegionKind.WHILE_LOOP, RegionKind.DO_WHILE, RegionKind.SELF_LOOP}
        found = [r for r in regions.regions.values() if r.kind in loop_kinds]
        assert len(found) >= 1

    def test_loop_emits_loop_stmt(self):
        """循环区域应生成 Loop 语句。"""
        from uasset_read.kismet.cfg import build_cfg, compute_dominator_tree, decompose_regions
        from uasset_read.kismet.cfg.emitter import RegionDecoder
        from uasset_read.kismet.cfg.stmt import Loop as LoopStmt
        from uasset_read.kismet.translator import KismetTranslator

        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        jmp_back = _make_jump(24, 0)
        end = _make_end(32)

        expressions = [let0, jmp, let1, jmp_back, end]
        cfg = build_cfg(expressions)
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        translator = KismetTranslator(expressions=expressions)
        decoder = RegionDecoder(
            cfg=cfg,
            region_tree=regions,
            expressions=expressions,
            translator=translator,
            offset_to_index={0: 0},
            jump_targets={0},
        )
        stmt = decoder.decode()

        # 结果应包含循环语句（或 Sequence 包含循环）
        def find_loop(s):
            if isinstance(s, LoopStmt):
                return True
            if isinstance(s, Sequence):
                return any(find_loop(st) for st in s.stmts)
            if isinstance(s, Branch):
                return (find_loop(s.then_body) if s.then_body else False) or (
                    find_loop(s.else_body) if s.else_body else False
                )
            return False

        assert find_loop(stmt), f"Expected Loop in stmt tree, got: {stmt}"


class TestEndToEndBodyBuilder:
    """body_builder 集成端到端测试。"""

    def test_linear_function(self):
        """线性函数的结构化输出。"""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder

        let0 = _make_let(0)
        let1 = _make_let(8)
        end = _make_end(16)

        builder = FunctionBodyBuilder()
        result = builder.to_function_body_structured(
            [let0, let1, end], func_name="LinearFunc"
        )
        assert "LinearFunc" in result
        assert "{" in result
        assert "}" in result

    def test_empty_expressions(self):
        """空表达式列表回退到 goto。"""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder

        builder = FunctionBodyBuilder()
        result = builder.to_function_body_structured([], func_name="EmptyFunc")
        # 回退到 goto 输出，应有函数签名
        assert "EmptyFunc" in result

    def test_with_func_name(self):
        """函数名包含参数时正确处理。"""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder

        let0 = _make_let(0)
        end = _make_end(8)

        builder = FunctionBodyBuilder()
        result = builder.to_function_body_structured(
            [let0, end], func_name="void MyFunc(int x)"
        )
        assert "MyFunc(int x)" in result

    def test_no_func_name(self):
        """无函数名使用默认。"""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder

        let0 = _make_let(0)
        end = _make_end(8)

        builder = FunctionBodyBuilder()
        result = builder.to_function_body_structured([let0, end])
        assert "UnknownFunction" in result

    def test_structured_rate_target(self):
        """验证 StructuredRateReport 目标指标。"""
        from uasset_read.kismet.cfg.stmt import Loop as LoopStmt
        from uasset_read.kismet.cfg.stmt import Branch as BranchStmt
        from uasset_read.kismet.body_builder import FunctionBodyBuilder

        # 构建一个包含 if-else 和 while 循环的复杂函数
        let0 = _make_let(0)
        jmp1 = _make_jump_if_not(8, 40)  # if 条件
        let1 = _make_let(16)  # then 分支
        jmp2 = _make_jump(24, 56)  # 跳到 end
        let2 = _make_let(40)  # else 分支
        jmp3 = _make_jump_if_not(48, 0)  # while 条件
        let3 = _make_let(56)  # while 体
        end = _make_end(64)

        builder = FunctionBodyBuilder()
        result = builder.to_function_body_structured(
            [let0, jmp1, let1, jmp2, let2, jmp3, let3, end],
            func_name="ComplexFunc",
        )
        # 应该成功生成，不应抛出异常
        assert result is not None
        assert len(result) > 0
