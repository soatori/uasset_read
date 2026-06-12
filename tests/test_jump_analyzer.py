"""JumpAnalyzer 单元测试。"""
from uasset_read.kismet.expressions.control_flow import EX_Jump, EX_JumpIfNot
from uasset_read.kismet.expressions.assignments import EX_Let
from uasset_read.kismet.jump_analyzer import JumpAnalyzer


def _make_expr(statement_index: int):
    """创建一个最简 KismetExpression mock，仅携带 StatementIndex。"""
    class _Stub:
        StatementIndex = statement_index
    return _Stub()


def _make_jump(statement_index: int, code_offset: int) -> EX_Jump:
    """创建 EX_Jump 并设置 StatementIndex。"""
    jmp = EX_Jump(CodeOffset=code_offset)
    jmp.StatementIndex = statement_index
    return jmp


def _make_jump_if_not(
    statement_index: int,
    code_offset: int,
    boolean_expression=None,
) -> EX_JumpIfNot:
    """创建 EX_JumpIfNot 并设置 StatementIndex。"""
    jmp = EX_JumpIfNot(CodeOffset=code_offset, BooleanExpression=boolean_expression)
    jmp.StatementIndex = statement_index
    return jmp


def _make_let(statement_index: int) -> EX_Let:
    """创建 mock EX_Let 赋值表达式（用于 for 循环递增）。"""
    let = EX_Let()
    let.StatementIndex = statement_index
    let.Variable = _make_expr(0)
    let.Assignment = _make_expr(0)
    return let


class TestLabelMapping:
    """验证偏移量→索引映射。"""

    def test_label_mapping(self):
        exprs = [
            _make_expr(0),   # idx 0 → offset 0
            _make_expr(10),  # idx 1 → offset 10
            _make_expr(20),  # idx 2 → offset 20
        ]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.find_label_index(0) == 0
        assert analyzer.find_label_index(10) == 1
        assert analyzer.find_label_index(20) == 2
        assert analyzer.find_label_index(99) is None

    def test_is_jump_target(self):
        cond = _make_expr(100)
        jump_if_not = _make_jump_if_not(statement_index=0, code_offset=30, boolean_expression=cond)
        exprs = [_make_expr(0), _make_expr(10), jump_if_not]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.is_jump_target(30) is True
        assert analyzer.is_jump_target(0) is False

    def test_get_jump_sources(self):
        cond = _make_expr(100)
        jump_if_not = _make_jump_if_not(statement_index=0, code_offset=30, boolean_expression=cond)
        exprs = [_make_expr(0), _make_expr(10), jump_if_not]
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
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(statement_index=1, code_offset=30, boolean_expression=cond)
        then_body = _make_expr(20)
        jump_end = _make_jump(statement_index=25, code_offset=50)
        else_body = _make_expr(30)
        end_expr = _make_expr(50)
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
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(statement_index=1, code_offset=30, boolean_expression=cond)
        then_body = _make_expr(20)
        end_expr = _make_expr(30)
        exprs = [cond, jump_if_not, then_body, end_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_if_else_pattern(1)
        assert result is not None
        assert result["type"] == "if"
        assert result["then_start"] == 2
        assert result["then_end"] == 2

    def test_if_else_not_jump_if_not(self):
        """start_idx 位置不是 JumpIfNot，应返回 None。"""
        exprs = [_make_expr(0), _make_jump(statement_index=1, code_offset=10)]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_if_else_pattern(1) is None

    def test_if_else_out_of_range(self):
        """索引越界应返回 None。"""
        analyzer = JumpAnalyzer([_make_expr(0)])
        assert analyzer.detect_if_else_pattern(-1) is None
        assert analyzer.detect_if_else_pattern(5) is None


class TestWhileDetection:
    """while 循环模式检测。"""

    def test_while_detection(self):
        """while: JumpIfNot → body → Jump(back to start)"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(statement_index=10, code_offset=50, boolean_expression=cond)
        body = _make_expr(20)
        jump_back = _make_jump(statement_index=30, code_offset=10)
        exit_expr = _make_expr(50)
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
        pre_expr = _make_expr(5)
        cond = _make_expr(10)
        jump_if_not = _make_jump_if_not(statement_index=15, code_offset=50, boolean_expression=cond)
        body = _make_expr(30)
        jump_back = _make_jump(statement_index=40, code_offset=5)
        exit_expr = _make_expr(50)
        exprs = [pre_expr, cond, jump_if_not, body, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_while_pattern(2)
        assert result is not None
        assert result["type"] == "while"

    def test_while_no_backjump(self):
        """循环体内没有回跳，不是 while 模式。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(statement_index=1, code_offset=30, boolean_expression=cond)
        body = _make_expr(10)
        # Jump 跳到 end 而非回跳
        jump_forward = _make_jump(statement_index=20, code_offset=50)
        exit_expr = _make_expr(30)
        exprs = [cond, jump_if_not, body, jump_forward, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.detect_while_pattern(1) is None

    def test_while_no_statement_index(self):
        """JumpIfNot 无 StatementIndex，应返回 None。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(statement_index=0, code_offset=30, boolean_expression=cond)
        # 覆盖 StatementIndex 为 None
        jump_if_not.StatementIndex = None
        jump_back = _make_jump(statement_index=10, code_offset=0)
        exprs = [cond, jump_if_not, jump_back]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_while_pattern(1) is None


class TestForDetection:
    """for 循环模式检测。"""

    def test_for_detection(self):
        """for: JumpIfNot → body → increment → Jump(back to start)"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(statement_index=10, code_offset=50, boolean_expression=cond)
        body = _make_expr(20)
        increment = _make_let(30)
        jump_back = _make_jump(statement_index=40, code_offset=10)
        exit_expr = _make_expr(50)
        exprs = [cond, jump_if_not, body, increment, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_for_pattern(1)
        assert result is not None
        assert result["type"] == "for"
        assert result["start"] == 1
        assert result["body_start"] == 2
        assert result["body_end"] == 4
        assert result["increment_start"] == 3
        assert result["increment_end"] == 3

    def test_for_with_multiple_increments(self):
        """多个递增表达式。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(statement_index=10, code_offset=60, boolean_expression=cond)
        body = _make_expr(20)
        inc1 = _make_let(30)
        inc2 = _make_let(40)
        jump_back = _make_jump(statement_index=50, code_offset=10)
        exit_expr = _make_expr(60)
        exprs = [cond, jump_if_not, body, inc1, inc2, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        result = analyzer.detect_for_pattern(1)
        assert result is not None
        assert result["type"] == "for"
        assert result["increment_start"] == 3
        assert result["increment_end"] == 4

    def test_for_body_too_short(self):
        """body 只有 Jump 无递增，不满足 for 模式。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(statement_index=1, code_offset=20, boolean_expression=cond)
        # body_start=2, body_end=2 → body_end <= body_start → 不是 for
        jump_back = _make_jump(statement_index=10, code_offset=1)
        exit_expr = _make_expr(20)
        exprs = [cond, jump_if_not, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.detect_for_pattern(1) is None


class TestNoPattern:
    """无法识别模式的情况。"""

    def test_no_pattern(self):
        """非条件跳转不匹配任何模式。"""
        jump = _make_jump(statement_index=0, code_offset=10)
        target = _make_expr(10)
        exprs = [jump, target]
        analyzer = JumpAnalyzer(exprs)
        assert analyzer.detect_if_else_pattern(0) is None
        assert analyzer.detect_while_pattern(0) is None
        assert analyzer.detect_for_pattern(0) is None

    def test_is_while_backjump(self):
        """is_while_backjump 正确识别回跳。"""
        cond = _make_expr(0)
        jump_if_not = _make_jump_if_not(statement_index=10, code_offset=50, boolean_expression=cond)
        body = _make_expr(20)
        jump_back = _make_jump(statement_index=30, code_offset=10)
        exit_expr = _make_expr(50)
        exprs = [cond, jump_if_not, body, jump_back, exit_expr]
        analyzer = JumpAnalyzer(exprs)

        assert analyzer.is_while_backjump(3) is True  # jump_back 在 index 3
        assert analyzer.is_while_backjump(2) is False  # body 不是回跳
        assert analyzer.is_while_backjump(0) is False
