"""Push/Pop 检测统一化测试。

覆盖 JumpAnalyzer 新增的 Push/Pop 模式检测能力：
- Push/Pop 与 JumpIfNot 结果一致性验证
- for/switch 在主流程中的可检测性
- structured_rate 指标集成
- structured_rate 字段在 KismetDecompiledResult 中的传递

对应 Issue #249 M-15/M-16。
"""
from uasset_read.kismet.expressions.control_flow import (
    EX_Jump, EX_JumpIfNot, EX_PushExecutionFlow, EX_PopExecutionFlow,
    EX_EndOfScript,
)
from uasset_read.kismet.expressions.special import EX_SwitchValue, FKismetSwitchCase
from uasset_read.kismet.expressions.assignments import EX_Let
from uasset_read.kismet.jump_analyzer import JumpAnalyzer, StructuredRateReport
from uasset_read.kismet.result import KismetDecompiledResult


# ================================================================
# 测试辅助工厂
# ================================================================

def _make_expr(statement_index: int):
    """创建最简 mock，仅携带 StatementIndex。"""
    class _Stub:
        StatementIndex = statement_index
    return _Stub()


def _make_jump(statement_index: int, code_offset: int) -> EX_Jump:
    jmp = EX_Jump(CodeOffset=code_offset)
    jmp.StatementIndex = statement_index
    return jmp


def _make_jump_if_not(
    statement_index: int,
    code_offset: int,
    boolean_expression=None,
) -> EX_JumpIfNot:
    jmp = EX_JumpIfNot(CodeOffset=code_offset, BooleanExpression=boolean_expression)
    jmp.StatementIndex = statement_index
    return jmp


def _make_push(pushing_address: int = 50) -> EX_PushExecutionFlow:
    push = EX_PushExecutionFlow(PushingAddress=pushing_address)
    push.StatementIndex = 0
    return push


def _make_pop() -> EX_PopExecutionFlow:
    pop = EX_PopExecutionFlow()
    pop.StatementIndex = 0
    return pop


def _make_let(statement_index: int) -> EX_Let:
    let = EX_Let()
    let.StatementIndex = statement_index
    let.Variable = _make_expr(0)
    let.Assignment = _make_expr(0)
    return let


def _make_switch_value(
    statement_index: int,
    end_offset: int = 100,
    case_count: int = 3,
) -> EX_SwitchValue:
    index_term = _make_expr(0)
    cases = []
    for i in range(case_count):
        case = FKismetSwitchCase()
        case.CaseIndexValueTerm = _make_expr(i)
        case.NextOffset = end_offset
        case.CaseTerm = _make_expr(i * 10)
        cases.append(case)
    default_term = _make_expr(999)
    switch = EX_SwitchValue(
        EndGotoOffset=end_offset,
        IndexTerm=index_term,
        Cases=cases,
        DefaultTerm=default_term,
    )
    switch.StatementIndex = statement_index
    return switch


# ================================================================
# Push/Pop 模式检测
# ================================================================

class TestPushPopDetection:
    """Push/Pop if/else 模式检测。"""

    def test_push_pop_if_else_basic(self):
        """基本 Push/Pop if/else：Push + JumpIfNot + then + Pop + else"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 20
        else_body = _make_expr(40)
        end = _make_expr(50)
        exprs = [push, jin, then_body, pop, else_body, end]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_push_pop_pattern(0)
        assert result is not None
        assert result["type"] == "push_pop"
        assert result["start"] == 0
        assert result["condition"] is cond
        assert result["then_start"] == 2  # jin_idx + 1
        assert result["then_end"] == 3    # pop_idx
        assert result["else_start"] == 4  # pop_idx + 1
        assert result["else_end"] == 5    # pushing_address → idx 5

    def test_push_pop_with_condition_loading(self):
        """Push 和 JumpIfNot 之间有额外条件加载指令。"""
        push = _make_push(pushing_address=60)
        push.StatementIndex = 0
        load_cond = _make_expr(5)
        cond = _make_expr(10)
        jin = _make_jump_if_not(
            statement_index=15, code_offset=50,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(25)
        pop = _make_pop()
        pop.StatementIndex = 30
        else_body = _make_expr(50)
        end = _make_expr(60)
        exprs = [push, load_cond, jin, then_body, pop, else_body, end]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_push_pop_pattern(0)
        assert result is not None
        assert result["type"] == "push_pop"
        assert result["then_start"] == 3   # jin_idx + 1
        assert result["then_end"] == 4     # pop_idx
        assert result["else_start"] == 5   # pop_idx + 1
        assert result["else_end"] == 6     # pushing_address → idx 6

    def test_push_pop_no_jump_if_not(self):
        """Push 后没有 JumpIfNot，不匹配 Push/Pop 模式。"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        other = _make_expr(10)
        end = _make_expr(50)
        exprs = [push, other, end]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_push_pop_pattern(0)
        assert result is None

    def test_push_pop_no_pop(self):
        """Push + JumpIfNot 但没有 Pop，不匹配 Push/Pop 模式。"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=50,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        end = _make_expr(50)
        exprs = [push, jin, end]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_push_pop_pattern(0)
        assert result is None

    def test_push_pop_not_push_at_start(self):
        """起始位置不是 PushExecutionFlow，返回 None。"""
        jin = _make_jump_if_not(
            statement_index=0, code_offset=50,
            boolean_expression=_make_expr(0),
        )
        exprs = [jin]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_push_pop_pattern(0)
        assert result is None

    def test_push_pop_out_of_range(self):
        """索引越界返回 None。"""
        push = _make_push()
        exprs = [push]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.detect_push_pop_pattern(-1) is None
        assert analyzer.detect_push_pop_pattern(5) is None

    def test_push_pop_else_end_without_pushing_address(self):
        """pushing_address 无法映射时，else_end 为 pop_idx。"""
        push = _make_push(pushing_address=999)  # 无法映射
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 20
        else_body = _make_expr(40)
        exprs = [push, jin, then_body, pop, else_body]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_push_pop_pattern(0)
        assert result is not None
        assert result["else_end"] == 3  # pop_idx (999 无法映射)


# ================================================================
# Push/Pop 通过统一 detect_pattern 入口
# ================================================================

class TestPushPopViaDetectPattern:
    """Push/Pop 通过 detect_pattern 统一入口检测。"""

    def test_push_pop_detected_via_unified_entry(self):
        """Push/Pop 模式通过 detect_pattern 统一入口检测。"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 20
        else_body = _make_expr(40)
        end = _make_expr(50)
        exprs = [push, jin, then_body, pop, else_body, end]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_pattern(0)
        assert result is not None
        assert result["type"] == "push_pop"

    def test_push_pop_priority_over_jump_if_not(self):
        """Push/Pop 优先于 JumpIfNot 检测（更精确的 if/else）。"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 20
        else_body = _make_expr(40)
        end = _make_expr(50)
        exprs = [push, jin, then_body, pop, else_body, end]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_pattern(0)
        assert result is not None
        assert result["type"] == "push_pop"


# ================================================================
# Push/Pop 结构化索引
# ================================================================

class TestPushPopStructuredIndices:
    """Push/Pop 模式的结构化索引。"""

    def test_push_pop_structured_indices(self):
        """Push/Pop 模式的所有表达式索引被标记为结构化。"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 20
        else_body = _make_expr(40)
        end = _make_expr(50)
        exprs = [push, jin, then_body, pop, else_body, end]
        analyzer = JumpAnalyzer(exprs)

        indices = analyzer.get_structured_indices()
        # Push/Pop 区间内所有索引都应被标记
        assert 0 in indices   # push
        assert 1 in indices   # jin
        assert 2 in indices   # then_body
        assert 3 in indices   # pop
        assert 4 in indices   # else_body
        assert 5 in indices   # end (pushing_address)


# ================================================================
# Push/Pop 结构化率
# ================================================================

class TestPushPopStructuredRate:
    """Push/Pop 模式的结构化率分析。"""

    def test_push_pop_in_structured_rate(self):
        """Push/Pop 模式在结构化率报告中被正确统计。"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 20
        else_body = _make_expr(40)
        end = _make_expr(50)
        exprs = [push, jin, then_body, pop, else_body, end]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        # JumpIfNot (jin) 通过 detect_pattern 被识别为 push_pop 模式
        # 注意：analyze_structured_rate 逐索引扫描，JumpIfNot 索引可能被识别为 push_pop
        # 或 if（取决于 detect_pattern 的优先级路径），关键是无 goto 回退
        assert report.goto_count == 0
        assert report.structured_count >= 1
        assert report.rate == 1.0


# ================================================================
# 结果字段传递
# ================================================================

class TestStructuredRateField:
    """structured_rate 字段在 KismetDecompiledResult 中的传递。"""

    def test_structured_rate_field_exists(self):
        """KismetDecompiledResult 包含 structured_rate 字段。"""
        result = KismetDecompiledResult(
            function_name="test",
            signature="void test()",
            local_variables=[],
            cpp_code="void test() {}",
            structured_rate=0.75,
        )
        assert result.structured_rate == 0.75

    def test_structured_rate_default_none(self):
        """structured_rate 默认值为 None。"""
        result = KismetDecompiledResult(
            function_name="test",
            signature="void test()",
            local_variables=[],
            cpp_code="void test() {}",
        )
        assert result.structured_rate is None

    def test_structured_rate_in_to_dict(self):
        """structured_rate 包含在 to_dict 输出中。"""
        result = KismetDecompiledResult(
            function_name="test",
            signature="void test()",
            local_variables=[],
            cpp_code="void test() {}",
            structured_rate=0.5,
        )
        d = result.to_dict()
        assert "structured_rate" in d
        assert d["structured_rate"] == 0.5

    def test_structured_rate_none_in_to_dict(self):
        """structured_rate 为 None 时仍包含在 to_dict 中。"""
        result = KismetDecompiledResult(
            function_name="test",
            signature="void test()",
            local_variables=[],
            cpp_code="void test() {}",
        )
        d = result.to_dict()
        assert "structured_rate" in d
        assert d["structured_rate"] is None


# ================================================================
# for/switch 在主流程中的可检测性
# ================================================================

class TestForSwitchDetectionInMainFlow:
    """验证 for/switch 在主流程中可检测（不被 StructuredControlFlow 死锁）。"""

    def test_for_detected_after_push_pop(self):
        """Push/Pop 之后的 for 循环仍可被检测。"""
        # Push/Pop if/else (使用唯一 offset 避免冲突)
        push = _make_push(pushing_address=200)
        push.StatementIndex = 0
        cond1 = _make_expr(0)
        jin1 = _make_jump_if_not(
            statement_index=10, code_offset=150,
            boolean_expression=cond1,
        )
        jin1.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 30
        else_body = _make_expr(150)
        # for 循环 (使用独立 offset 避免与 Push/Pop 冲突)
        # Layout: for_cond(200) for_jin(210,exit=260) for_body(220) for_inc(230) for_jback(240→210) for_exit(260)
        for_cond = _make_expr(200)
        for_jin = _make_jump_if_not(
            statement_index=210, code_offset=260,
            boolean_expression=for_cond,
        )
        for_body = _make_expr(220)
        for_inc = _make_let(230)
        for_jback = _make_jump(statement_index=240, code_offset=210)
        for_exit = _make_expr(260)

        exprs = [
            push, jin1, then_body, pop, else_body,
            for_cond, for_jin, for_body, for_inc, for_jback, for_exit,
        ]
        analyzer = JumpAnalyzer(exprs)

        # for 模式在 Push/Pop 之后仍可检测
        result = analyzer.detect_pattern(6)
        assert result is not None
        assert result["type"] == "for"

    def test_switch_detected_after_push_pop(self):
        """Push/Pop 之后的 switch 仍可被检测。"""
        push = _make_push(pushing_address=80)
        push.StatementIndex = 0
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=50,
            boolean_expression=cond,
        )
        jin.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 30
        else_body = _make_expr(50)
        # switch
        switch = _make_switch_value(statement_index=60)
        exprs = [push, jin, then_body, pop, else_body, switch]
        analyzer = JumpAnalyzer(exprs)

        # switch 在 Push/Pop 之后仍可检测
        result = analyzer.detect_pattern(5)
        assert result is not None
        assert result["type"] == "switch"

    def test_while_after_push_pop(self):
        """Push/Pop 之后的 while 循环仍可被检测。"""
        push = _make_push(pushing_address=200)
        push.StatementIndex = 0
        cond1 = _make_expr(0)
        jin1 = _make_jump_if_not(
            statement_index=10, code_offset=150,
            boolean_expression=cond1,
        )
        jin1.StatementIndex = 1
        then_body = _make_expr(20)
        pop = _make_pop()
        pop.StatementIndex = 30
        else_body = _make_expr(150)
        # while 循环 (独立 offset)
        # Layout: while_cond(200) while_jin(210,exit=250) while_body(220) while_jback(230→210) while_exit(250)
        while_cond = _make_expr(200)
        while_jin = _make_jump_if_not(
            statement_index=210, code_offset=250,
            boolean_expression=while_cond,
        )
        while_body = _make_expr(220)
        while_jback = _make_jump(statement_index=230, code_offset=210)
        while_exit = _make_expr(250)

        exprs = [
            push, jin1, then_body, pop, else_body,
            while_cond, while_jin, while_body, while_jback, while_exit,
        ]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_pattern(6)
        assert result is not None
        assert result["type"] == "while"


# ================================================================
# 边界情况
# ================================================================

class TestPushPopEdgeCases:
    """Push/Pop 边界情况。"""

    def test_empty_expressions(self):
        """空表达式列表。"""
        analyzer = JumpAnalyzer([])
        assert analyzer.detect_push_pop_pattern(0) is None

    def test_single_push_no_following(self):
        """单个 Push 无后续指令。"""
        push = _make_push()
        exprs = [push]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.detect_push_pop_pattern(0) is None

    def test_push_with_another_push_before_jump_if_not(self):
        """Push 后遇到另一个 Push（非 JumpIfNot），不匹配。"""
        push1 = _make_push(pushing_address=50)
        push1.StatementIndex = 0
        push2 = _make_push(pushing_address=60)
        push2.StatementIndex = 1
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=_make_expr(0),
        )
        jin.StatementIndex = 2
        end = _make_expr(50)
        exprs = [push1, push2, jin, end]
        analyzer = JumpAnalyzer(exprs)

        # push1 不匹配（遇到 push2 就停止扫描）
        result = analyzer.detect_push_pop_pattern(0)
        assert result is None

    def test_push_with_end_of_script_before_jump_if_not(self):
        """Push 后遇到 EndOfScript（非 JumpIfNot），不匹配。"""
        push = _make_push(pushing_address=50)
        push.StatementIndex = 0
        end_script = EX_EndOfScript()
        end_script.StatementIndex = 1
        jin = _make_jump_if_not(
            statement_index=10, code_offset=40,
            boolean_expression=_make_expr(0),
        )
        jin.StatementIndex = 2
        exprs = [push, end_script, jin]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_push_pop_pattern(0)
        assert result is None
