"""控制流结构化增强测试。

覆盖 JumpAnalyzer 的增强功能：
- for 循环模式检测（赋值递增）
- switch/case 模式检测（EX_SwitchValue）
- 统一模式检测入口 detect_pattern
- 结构化率分析 analyze_structured_rate
- goto 回退原因分类
- goto 报告格式化
"""
from uasset_read.kismet.expressions.control_flow import (
    EX_Jump, EX_JumpIfNot, EX_ComputedJump,
)
from uasset_read.kismet.expressions.special import EX_SwitchValue, FKismetSwitchCase
from uasset_read.kismet.expressions.assignments import (
    EX_Let, EX_LetBool, EX_LetValueOnPersistentFrame,
)
from uasset_read.kismet.jump_analyzer import JumpAnalyzer, StructuredRateReport


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


def _make_let(statement_index: int, var_name: str = "i") -> EX_Let:
    """创建 mock EX_Let 赋值表达式。"""
    let = EX_Let()
    let.StatementIndex = statement_index
    let.Variable = _make_expr(0)
    let.Assignment = _make_expr(0)
    return let


def _make_let_bool(statement_index: int) -> EX_LetBool:
    """创建 mock EX_LetBool 赋值表达式。"""
    let = EX_LetBool()
    let.StatementIndex = statement_index
    let.Variable = _make_expr(0)
    let.Assignment = _make_expr(0)
    return let


def _make_switch_value(
    statement_index: int,
    end_offset: int = 100,
    case_count: int = 3,
) -> EX_SwitchValue:
    """创建 mock EX_SwitchValue 表达式。"""
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


def _make_computed_jump(statement_index: int) -> EX_ComputedJump:
    """创建 mock EX_ComputedJump 表达式。"""
    jmp = EX_ComputedJump(CodeOffsetExpression=_make_expr(0))
    jmp.StatementIndex = statement_index
    return jmp


# ================================================================
# for 循环检测
# ================================================================

class TestForDetection:
    """for 循环模式检测增强测试。"""

    def test_for_with_single_assignment_increment(self):
        """单个赋值递增的 for 循环。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=10, code_offset=60, boolean_expression=cond,
        )
        body_call = _make_expr(20)
        increment = _make_let(30)
        jump_back = _make_jump(statement_index=40, code_offset=10)
        exit_expr = _make_expr(60)
        exprs = [cond, jump_if_not, body_call, increment, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_for_pattern(1)
        assert result is not None
        assert result["type"] == "for"
        assert result["start"] == 1
        assert result["body_start"] == 2
        assert result["body_end"] == 4
        assert result["increment_start"] == 3
        assert result["increment_end"] == 3
        assert result["exit_label"] == 60

    def test_for_with_multiple_assignment_increments(self):
        """多个连续赋值递增的 for 循环。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=10, code_offset=70, boolean_expression=cond,
        )
        body = _make_expr(20)
        inc1 = _make_let(30)
        inc2 = _make_let_bool(40)
        jump_back = _make_jump(statement_index=50, code_offset=10)
        exit_expr = _make_expr(70)
        exprs = [cond, jump_if_not, body, inc1, inc2, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_for_pattern(1)
        assert result is not None
        assert result["type"] == "for"
        assert result["increment_start"] == 3
        assert result["increment_end"] == 4

    def test_for_body_too_short_no_increment(self):
        """循环体只有回跳无递增，不满足 for 模式。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=1, code_offset=20, boolean_expression=cond,
        )
        jump_back = _make_jump(statement_index=10, code_offset=1)
        exit_expr = _make_expr(20)
        exprs = [cond, jump_if_not, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        # body_start=2, body_end=2 → body_end <= body_start
        assert analyzer.detect_for_pattern(1) is None

    def test_for_no_assignment_before_backjump(self):
        """回跳前没有赋值表达式，不满足 for 模式。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=10, code_offset=50, boolean_expression=cond,
        )
        body = _make_expr(20)
        non_assign = _make_expr(30)  # 非赋值表达式
        jump_back = _make_jump(statement_index=40, code_offset=10)
        exit_expr = _make_expr(50)
        exprs = [cond, jump_if_not, body, non_assign, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.detect_for_pattern(1) is None

    def test_for_entire_body_is_increment(self):
        """整个循环体都是递增（无实际循环体），不满足 for 模式。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=10, code_offset=40, boolean_expression=cond,
        )
        inc = _make_let(20)  # 递增从 body_start 就开始
        jump_back = _make_jump(statement_index=30, code_offset=10)
        exit_expr = _make_expr(40)
        exprs = [cond, jump_if_not, inc, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        # inc_start == body_start → 不满足 for
        assert analyzer.detect_for_pattern(1) is None

    def test_for_not_jump_if_not(self):
        """起始位置不是 JumpIfNot，返回 None。"""
        exprs = [_make_expr(0), _make_let(10)]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_for_pattern(0) is None

    def test_for_out_of_range(self):
        """索引越界返回 None。"""
        analyzer = JumpAnalyzer([_make_expr(0)])
        assert analyzer.detect_for_pattern(-1) is None
        assert analyzer.detect_for_pattern(5) is None


# ================================================================
# switch/case 检测
# ================================================================

class TestSwitchDetection:
    """switch/case 模式检测。"""

    def test_switch_detection_basic(self):
        """基本 switch 检测。"""
        switch = _make_switch_value(statement_index=0, end_offset=100, case_count=3)
        exprs = [switch]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_switch_pattern(0)
        assert result is not None
        assert result["type"] == "switch"
        assert result["start"] == 0
        assert result["end_offset"] == 100
        assert len(result["cases"]) == 3
        assert result["default_term"] is not None

    def test_switch_with_two_cases(self):
        """两分支 switch（可能被编译为三元表达式，但仍可检测）。"""
        switch = _make_switch_value(statement_index=0, end_offset=50, case_count=2)
        exprs = [_make_expr(999), switch]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_switch_pattern(1)
        assert result is not None
        assert len(result["cases"]) == 2

    def test_switch_with_zero_cases(self):
        """零 case 的 switch（仅 default）。"""
        switch = _make_switch_value(statement_index=0, end_offset=30, case_count=0)
        exprs = [switch]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_switch_pattern(0)
        assert result is not None
        assert len(result["cases"]) == 0
        assert result["default_term"] is not None

    def test_switch_not_at_index(self):
        """指定索引不是 EX_SwitchValue，返回 None。"""
        exprs = [_make_expr(0), _make_switch_value(statement_index=10)]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.detect_switch_pattern(0) is None

    def test_switch_out_of_range(self):
        """索引越界返回 None。"""
        analyzer = JumpAnalyzer([_make_expr(0)])
        assert analyzer.detect_switch_pattern(-1) is None
        assert analyzer.detect_switch_pattern(5) is None

    def test_switch_index_term_preserved(self):
        """验证 index_term 正确保留。"""
        index_term = _make_expr(42)
        switch = EX_SwitchValue(
            EndGotoOffset=100,
            IndexTerm=index_term,
            Cases=[],
            DefaultTerm=None,
        )
        switch.StatementIndex = 0
        analyzer = JumpAnalyzer([switch])

        result = analyzer.detect_switch_pattern(0)
        assert result is not None
        assert result["index_term"] is index_term


# ================================================================
# 统一模式检测入口
# ================================================================

class TestDetectPattern:
    """detect_pattern 统一入口测试。"""

    def test_detect_pattern_for_priority_over_while(self):
        """for 优先于 while 检测。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=10, code_offset=60, boolean_expression=cond,
        )
        body = _make_expr(20)
        inc = _make_let(30)
        jump_back = _make_jump(statement_index=40, code_offset=10)
        exit_expr = _make_expr(60)
        exprs = [cond, jump_if_not, body, inc, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_pattern(1)
        assert result is not None
        assert result["type"] == "for"

    def test_detect_pattern_while_when_no_increment(self):
        """无递增时回退到 while。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=10, code_offset=50, boolean_expression=cond,
        )
        body = _make_expr(20)
        jump_back = _make_jump(statement_index=30, code_offset=10)
        exit_expr = _make_expr(50)
        exprs = [cond, jump_if_not, body, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_pattern(1)
        assert result is not None
        assert result["type"] == "while"

    def test_detect_pattern_if_else(self):
        """if/else 模式。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=1, code_offset=30, boolean_expression=cond,
        )
        then_body = _make_expr(20)
        jump_end = _make_jump(statement_index=25, code_offset=50)
        else_body = _make_expr(30)
        end_expr = _make_expr(50)
        exprs = [cond, jump_if_not, then_body, jump_end, else_body, end_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_pattern(1)
        assert result is not None
        assert result["type"] == "if_else"

    def test_detect_pattern_switch(self):
        """switch 模式。"""
        switch = _make_switch_value(statement_index=0)
        exprs = [switch]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_pattern(0)
        assert result is not None
        assert result["type"] == "switch"

    def test_detect_pattern_none_for_no_match(self):
        """无法匹配时返回 None。"""
        exprs = [_make_expr(0), _make_expr(10)]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_pattern(0) is None


# ================================================================
# is_while_backjump 缓存
# ================================================================

class TestBackjumpCache:
    """回跳缓存测试。"""

    def test_backjump_cache_basic(self):
        """基本回跳缓存。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(
            statement_index=10, code_offset=50, boolean_expression=cond,
        )
        body = _make_expr(20)
        jump_back = _make_jump(statement_index=30, code_offset=10)
        exit_expr = _make_expr(50)
        exprs = [cond, jump_if_not, body, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.is_while_backjump(3) is True
        assert analyzer.is_while_backjump(2) is False

    def test_backjump_cache_multiple_loops(self):
        """多循环的回跳缓存。"""
        # 循环 1
        cond1 = _make_expr(0)
        jin1 = _make_jump_if_not(statement_index=10, code_offset=50, boolean_expression=cond1)
        body1 = _make_expr(20)
        jb1 = _make_jump(statement_index=30, code_offset=10)
        exit1 = _make_expr(50)
        # 循环 2
        cond2 = _make_expr(60)
        jin2 = _make_jump_if_not(statement_index=70, code_offset=110, boolean_expression=cond2)
        body2 = _make_expr(80)
        jb2 = _make_jump(statement_index=90, code_offset=70)
        exit2 = _make_expr(110)

        exprs = [cond1, jin1, body1, jb1, exit1, cond2, jin2, body2, jb2, exit2]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.is_while_backjump(3) is True   # jb1
        assert analyzer.is_while_backjump(8) is True   # jb2
        assert analyzer.is_while_backjump(2) is False


# ================================================================
# 结构化率分析
# ================================================================

class TestStructuredRateAnalysis:
    """结构化率分析测试。"""

    def test_all_structured(self):
        """全部可结构化的表达式。"""
        cond = _make_expr(0)
        jin = _make_jump_if_not(statement_index=10, code_offset=30, boolean_expression=cond)
        then_body = _make_expr(20)
        end = _make_expr(30)
        exprs = [cond, jin, then_body, end]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        assert report.rate == 1.0
        assert report.goto_count == 0
        assert "if" in report.pattern_counts

    def test_all_goto(self):
        """全部 goto 回退。"""
        jump1 = _make_jump(statement_index=0, code_offset=20)
        target = _make_expr(20)
        exprs = [jump1, target]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        assert report.rate == 0.0
        assert report.goto_count == 1
        assert len(report.goto_reasons) == 1

    def test_mixed_patterns(self):
        """混合模式：if + goto。"""
        cond = _make_expr(0)
        jin = _make_jump_if_not(statement_index=10, code_offset=30, boolean_expression=cond)
        then_body = _make_expr(20)
        end_if = _make_expr(30)
        # 独立 goto
        jump = _make_jump(statement_index=40, code_offset=100)
        target = _make_expr(100)
        exprs = [cond, jin, then_body, end_if, jump, target]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        assert report.structured_count >= 1
        assert report.goto_count >= 1
        assert report.rate < 1.0
        assert report.rate > 0.0

    def test_empty_expressions(self):
        """空表达式列表。"""
        analyzer = JumpAnalyzer([])
        report = analyzer.analyze_structured_rate()
        assert report.rate == 1.0
        assert report.total_jump_exprs == 0

    def test_no_jump_expressions(self):
        """无跳转指令的表达式列表。"""
        exprs = [_make_expr(0), _make_expr(10)]
        analyzer = JumpAnalyzer(exprs)
        report = analyzer.analyze_structured_rate()
        assert report.rate == 1.0
        assert report.total_jump_exprs == 0

    def test_switch_in_report(self):
        """switch 模式计入报告。"""
        switch = _make_switch_value(statement_index=0)
        exprs = [switch]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        assert report.pattern_counts.get("switch", 0) >= 1
        assert report.rate == 1.0

    def test_computed_jump_goto_reason(self):
        """ComputedJump 的 goto 原因。"""
        cj = _make_computed_jump(statement_index=0)
        exprs = [cj]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        assert report.goto_count == 1
        assert "computed_jump" in report.goto_reasons[0]["reason"]

    def test_forward_jump_goto_reason(self):
        """前跳 goto 原因。"""
        jump = _make_jump(statement_index=0, code_offset=20)
        target = _make_expr(20)
        exprs = [jump, target]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        assert report.goto_count == 1
        assert "forward_jump" in report.goto_reasons[0]["reason"]

    def test_unmatched_conditional_goto_reason(self):
        """未匹配条件跳转的 goto 原因。"""
        # JumpIfNot 但没有回跳 → 不是 while/for，false_label 不存在 → 不是 if
        jin = _make_jump_if_not(
            statement_index=0, code_offset=999,
            boolean_expression=_make_expr(100),
        )
        exprs = [jin]
        analyzer = JumpAnalyzer(exprs)

        report = analyzer.analyze_structured_rate()
        assert report.goto_count == 1
        assert "unmatched_conditional" in report.goto_reasons[0]["reason"]


# ================================================================
# goto 报告格式化
# ================================================================

class TestGotoReport:
    """goto 报告格式化测试。"""

    def test_format_goto_report_basic(self):
        """基本报告格式化。"""
        jump = _make_jump(statement_index=0, code_offset=20)
        target = _make_expr(20)
        analyzer = JumpAnalyzer([jump, target])

        report_text = analyzer.format_goto_report()
        assert "控制流结构化率报告" in report_text
        assert "总跳转指令数" in report_text
        assert "goto 回退原因" in report_text

    def test_format_goto_report_with_precomputed_report(self):
        """使用预计算报告。"""
        report = StructuredRateReport(
            total_jump_exprs=10,
            structured_count=7,
            goto_count=3,
            rate=0.7,
            pattern_counts={"if": 3, "while": 2, "for": 1, "switch": 1},
            goto_reasons=[
                {"index": 5, "reason": "test_reason", "expr_type": "EX_Jump"},
            ],
        )
        analyzer = JumpAnalyzer([])
        text = analyzer.format_goto_report(report)
        assert "70.0%" in text
        assert "if: 3" in text
        assert "test_reason" in text

    def test_format_goto_report_no_goto(self):
        """无 goto 时不显示回退原因。"""
        cond = _make_expr(0)
        jin = _make_jump_if_not(statement_index=10, code_offset=30, boolean_expression=cond)
        then_body = _make_expr(20)
        end = _make_expr(30)
        analyzer = JumpAnalyzer([cond, jin, then_body, end])

        report_text = analyzer.format_goto_report()
        assert "goto 回退原因" not in report_text


# ================================================================
# get_structured_indices
# ================================================================

class TestStructuredIndices:
    """结构化索引集合测试。"""

    def test_while_structured_indices(self):
        """while 循环的结构化索引。"""
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=50, boolean_expression=cond,
        )
        body = _make_expr(20)
        jump_back = _make_jump(statement_index=30, code_offset=10)
        exit_expr = _make_expr(50)
        exprs = [cond, jin, body, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        indices = analyzer.get_structured_indices()
        assert 1 in indices  # jin
        assert 2 in indices  # body
        assert 3 in indices  # jump_back

    def test_for_structured_indices(self):
        """for 循环的结构化索引。"""
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=60, boolean_expression=cond,
        )
        body = _make_expr(20)
        inc = _make_let(30)
        jump_back = _make_jump(statement_index=40, code_offset=10)
        exit_expr = _make_expr(60)
        exprs = [cond, jin, body, inc, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        indices = analyzer.get_structured_indices()
        assert 1 in indices  # jin
        assert 2 in indices  # body
        assert 3 in indices  # inc
        assert 4 in indices  # jump_back

    def test_switch_structured_indices(self):
        """switch 的结构化索引。"""
        switch = _make_switch_value(statement_index=0)
        exprs = [switch]
        analyzer = JumpAnalyzer(exprs)

        indices = analyzer.get_structured_indices()
        assert 0 in indices

    def test_if_else_structured_indices(self):
        """if/else 的结构化索引。"""
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=1, code_offset=30, boolean_expression=cond,
        )
        then_body = _make_expr(20)
        jump_end = _make_jump(statement_index=25, code_offset=50)
        else_body = _make_expr(30)
        end_expr = _make_expr(50)
        exprs = [cond, jin, then_body, jump_end, else_body, end_expr]
        analyzer = JumpAnalyzer(exprs)

        indices = analyzer.get_structured_indices()
        assert 1 in indices  # jin
        assert 2 in indices  # then
        assert 3 in indices  # jump_end
        assert 4 in indices  # else
        assert 5 in indices  # end


# ================================================================
# 边界情况
# ================================================================

class TestEdgeCases:
    """边界情况测试。"""

    def test_empty_expressions_all_methods(self):
        """空表达式列表不抛异常。"""
        analyzer = JumpAnalyzer([])
        assert analyzer.detect_pattern(0) is None
        assert analyzer.detect_if_else_pattern(0) is None
        assert analyzer.detect_while_pattern(0) is None
        assert analyzer.detect_for_pattern(0) is None
        assert analyzer.detect_switch_pattern(0) is None
        assert analyzer.is_while_backjump(0) is False

    def test_single_expression(self):
        """单表达式列表。"""
        exprs = [_make_expr(0)]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_pattern(0) is None
        assert analyzer.find_label_index(0) == 0

    def test_mixed_for_and_switch(self):
        """混合 for 和 switch 模式。"""
        # for 循环
        cond = _make_expr(0)
        jin = _make_jump_if_not(
            statement_index=10, code_offset=60, boolean_expression=cond,
        )
        body = _make_expr(20)
        inc = _make_let(30)
        jump_back = _make_jump(statement_index=40, code_offset=10)
        exit_for = _make_expr(60)
        # switch
        switch = _make_switch_value(statement_index=70)
        exprs = [cond, jin, body, inc, jump_back, exit_for, switch]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.detect_pattern(1)["type"] == "for"
        assert analyzer.detect_pattern(6)["type"] == "switch"

    def test_backward_jump_not_loop(self):
        """回跳目标在 start 之前但不是循环结构（非 JumpIfNot 起始）。"""
        # 直接的回跳，前面没有 JumpIfNot
        pre = _make_expr(5)
        body = _make_expr(10)
        jump_back = _make_jump(statement_index=20, code_offset=5)
        exprs = [pre, body, jump_back]
        analyzer = JumpAnalyzer(exprs)

        # index 2 是 EX_Jump 不是 JumpIfNot，检测返回 None
        assert analyzer.detect_while_pattern(2) is None
        assert analyzer.detect_for_pattern(2) is None
