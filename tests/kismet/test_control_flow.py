"""控制流结构化测试。

合并自:
- test_control_flow_enhanced.py: JumpAnalyzer 增强功能 + 基础模式检测
- test_kismet_control_flow.py: Push/Pop 模式检测统一化

覆盖:
- JumpAnalyzer 的增强功能（for 循环、switch/case、统一模式检测、结构化率分析）
- Push/Pop 模式检测与优先级
- goto 回退原因分类与报告格式化
- structured_rate 字段在 KismetDecompiledResult 中的传递
- 基础模式检测（if/else、while、label 映射）
"""
from uasset_read.kismet.expressions.control_flow import (
    EX_Jump, EX_JumpIfNot, EX_ComputedJump,
    EX_PushExecutionFlow, EX_PopExecutionFlow,
    EX_EndOfScript,
)
from uasset_read.kismet.expressions.special import EX_SwitchValue, FKismetSwitchCase
from uasset_read.kismet.expressions.assignments import (
    EX_Let, EX_LetBool, EX_LetValueOnPersistentFrame,
)
from uasset_read.kismet.jump_analyzer import JumpAnalyzer, StructuredRateReport
from uasset_read.kismet.result import KismetDecompiledResult


# ================================================================
# 测试辅助工厂 — 增强版
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
# 测试辅助工厂 — Push/Pop 版
# ================================================================

def _make_push(pushing_address: int = 50) -> EX_PushExecutionFlow:
    push = EX_PushExecutionFlow(PushingAddress=pushing_address)
    push.StatementIndex = 0
    return push


def _make_pop() -> EX_PopExecutionFlow:
    pop = EX_PopExecutionFlow()
    pop.StatementIndex = 0
    return pop


# ================================================================
# 测试辅助工厂 — 简单版（用于基础模式检测测试）
# ================================================================

def _make_expr_simple(statement_index: int):
    """创建一个最简 KismetExpression mock，仅携带 StatementIndex（简单版本）。"""
    class _Stub:
        StatementIndex = statement_index
    return _Stub()


def _make_jump_simple(statement_index: int, code_offset: int) -> EX_Jump:
    """创建 EX_Jump 并设置 StatementIndex（简单版本）。"""
    jmp = EX_Jump(CodeOffset=code_offset)
    jmp.StatementIndex = statement_index
    return jmp


def _make_jump_if_not_simple(
    statement_index: int,
    code_offset: int,
    boolean_expression=None,
) -> EX_JumpIfNot:
    """创建 EX_JumpIfNot 并设置 StatementIndex（简单版本）。"""
    jmp = EX_JumpIfNot(CodeOffset=code_offset, BooleanExpression=boolean_expression)
    jmp.StatementIndex = statement_index
    return jmp


def _make_let_simple(statement_index: int) -> EX_Let:
    """创建 mock EX_Let 赋值表达式（用于 for 循环递增）（简单版本）。"""
    let = EX_Let()
    let.StatementIndex = statement_index
    let.Variable = _make_expr_simple(0)
    let.Assignment = _make_expr_simple(0)
    return let


# ================================================================
# for 循环检测（增强版）
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
# Push/Pop 边界情况
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


# ================================================================
# 基础模式检测 — 偏移量映射
# ================================================================

class TestLabelMapping:
    """验证偏移量→索引映射。"""

    def test_label_mapping(self):
        exprs = [
            _make_expr_simple(0),   # idx 0 → offset 0
            _make_expr_simple(10),  # idx 1 → offset 10
            _make_expr_simple(20),  # idx 2 → offset 20
        ]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.find_label_index(0) == 0
        assert analyzer.find_label_index(10) == 1
        assert analyzer.find_label_index(20) == 2
        assert analyzer.find_label_index(99) is None

    def test_is_jump_target(self):
        cond = _make_expr_simple(100)
        jump_if_not = _make_jump_if_not_simple(statement_index=0, code_offset=30, boolean_expression=cond)
        exprs = [_make_expr_simple(0), _make_expr_simple(10), jump_if_not]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.is_jump_target(30) is True
        assert analyzer.is_jump_target(0) is False

    def test_get_jump_sources(self):
        cond = _make_expr_simple(100)
        jump_if_not = _make_jump_if_not_simple(statement_index=0, code_offset=30, boolean_expression=cond)
        exprs = [_make_expr_simple(0), _make_expr_simple(10), jump_if_not]
        analyzer = JumpAnalyzer(exprs)
        sources = analyzer.get_jump_sources(30)
        assert 2 in sources  # jump_if_not 在 index 2

    def test_empty_expressions(self):
        analyzer = JumpAnalyzer([])
        assert analyzer.find_label_index(0) is None
        assert analyzer.is_jump_target(0) is False
        assert analyzer.get_jump_sources(0) == []


class TestIfElseDetection:
    """if/else 模式检测。"""

    def test_if_else_detection(self):
        """if/else: JumpIfNot → then → Jump(end) → else → end"""
        # 布局:
        #   0: expr (condition target)
        #   1: JumpIfNot(cond, false_label=30) → index 1
        #   2: then body
        #   3: Jump(end_label=50) → index 3
        #   4: else body
        #   5: (end)
        cond = _make_expr_simple(0)
        jump_if_not = _make_jump_if_not_simple(statement_index=1, code_offset=30, boolean_expression=cond)
        then_body = _make_expr_simple(20)
        jump_end = _make_jump_simple(statement_index=25, code_offset=50)
        else_body = _make_expr_simple(30)
        end_expr = _make_expr_simple(50)
        exprs = [cond, jump_if_not, then_body, jump_end, else_body, end_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_if_else_pattern(1)
        assert result is not None
        assert result["type"] == "if_else"
        assert result["start"] == 1
        assert result["then_start"] == 2
        assert result["then_end"] == 3
        assert result["else_start"] == 4
        assert result["else_end"] == 5

    def test_simple_if_detection(self):
        """简单 if（无 else）：JumpIfNot → then → end"""
        cond = _make_expr_simple(0)
        jump_if_not = _make_jump_if_not_simple(statement_index=1, code_offset=30, boolean_expression=cond)
        then_body = _make_expr_simple(20)
        end_expr = _make_expr_simple(30)
        exprs = [cond, jump_if_not, then_body, end_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_if_else_pattern(1)
        assert result is not None
        assert result["type"] == "if"
        assert result["then_start"] == 2
        assert result["then_end"] == 2

    def test_if_else_not_jump_if_not(self):
        """start_idx 位置不是 JumpIfNot，应返回 None。"""
        exprs = [_make_expr_simple(0), _make_jump_simple(statement_index=1, code_offset=10)]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_if_else_pattern(1) is None

    def test_if_else_out_of_range(self):
        """索引越界应返回 None。"""
        analyzer = JumpAnalyzer([_make_expr_simple(0)])
        assert analyzer.detect_if_else_pattern(-1) is None
        assert analyzer.detect_if_else_pattern(5) is None


class TestWhileDetection:
    """while 循环模式检测。"""

    def test_while_detection(self):
        """while: JumpIfNot → body → Jump(back to start)"""
        cond = _make_expr_simple(0)
        jump_if_not = _make_jump_if_not_simple(statement_index=10, code_offset=50, boolean_expression=cond)
        body = _make_expr_simple(20)
        jump_back = _make_jump_simple(statement_index=30, code_offset=10)
        exit_expr = _make_expr_simple(50)
        exprs = [cond, jump_if_not, body, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_while_pattern(1)
        assert result is not None
        assert result["type"] == "while"
        assert result["start"] == 1
        assert result["body_start"] == 2
        assert result["body_end"] == 3  # jump_back 的索引
        assert result["exit_label"] == 50

    def test_while_backjump_to_before_start(self):
        """回跳目标在 start_idx 之前。"""
        pre_expr = _make_expr_simple(5)
        cond = _make_expr_simple(10)
        jump_if_not = _make_jump_if_not_simple(statement_index=15, code_offset=50, boolean_expression=cond)
        body = _make_expr_simple(30)
        jump_back = _make_jump_simple(statement_index=40, code_offset=5)
        exit_expr = _make_expr_simple(50)
        exprs = [pre_expr, cond, jump_if_not, body, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_while_pattern(2)
        assert result is not None
        assert result["type"] == "while"

    def test_while_no_backjump(self):
        """循环体内没有回跳，不是 while 模式。"""
        cond = _make_expr_simple(0)
        jump_if_not = _make_jump_if_not_simple(statement_index=1, code_offset=30, boolean_expression=cond)
        body = _make_expr_simple(10)
        # Jump 跳到 end 而非回跳
        jump_forward = _make_jump_simple(statement_index=20, code_offset=50)
        exit_expr = _make_expr_simple(30)
        exprs = [cond, jump_if_not, body, jump_forward, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.detect_while_pattern(1) is None

    def test_while_no_statement_index(self):
        """JumpIfNot 无 StatementIndex，应返回 None。"""
        cond = _make_expr_simple(0)
        jump_if_not = _make_jump_if_not_simple(statement_index=0, code_offset=30, boolean_expression=cond)
        # 覆盖 StatementIndex 为 None
        jump_if_not.StatementIndex = None
        jump_back = _make_jump_simple(statement_index=10, code_offset=0)
        exprs = [cond, jump_if_not, jump_back]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_while_pattern(1) is None


class TestNoPattern:
    """无法识别模式的情况。"""

    def test_no_pattern(self):
        """非条件跳转不匹配任何模式。"""
        jump = _make_jump_simple(statement_index=0, code_offset=10)
        target = _make_expr_simple(10)
        exprs = [jump, target]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_if_else_pattern(0) is None
        assert analyzer.detect_while_pattern(0) is None
        assert analyzer.detect_for_pattern(0) is None

    def test_is_while_backjump(self):
        """is_while_backjump 正确识别回跳。"""
        cond = _make_expr_simple(0)
        jump_if_not = _make_jump_if_not_simple(statement_index=10, code_offset=50, boolean_expression=cond)
        body = _make_expr_simple(20)
        jump_back = _make_jump_simple(statement_index=30, code_offset=10)
        exit_expr = _make_expr_simple(50)
        exprs = [cond, jump_if_not, body, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.is_while_backjump(3) is True  # jump_back 在 index 3
        assert analyzer.is_while_backjump(2) is False  # body 不是回跳
        assert analyzer.is_while_backjump(0) is False
