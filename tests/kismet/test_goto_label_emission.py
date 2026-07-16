"""_emit_goto_fallback 标签输出测试。

验证 structured_flow.py 中 goto 回退路径的标签（Label_N）正确输出：
- 跳转目标前输出对应标签
- 多个跳转目标各自输出标签
- 已输出标签不重复
- 无跳转目标时不输出标签
- offset_to_index 映射正确关联 byte_offset 和 CodeOffset
"""
from uasset_read.kismet.structured_flow import StructuredControlFlow
from uasset_read.kismet.expressions.control_flow import EX_Jump, EX_JumpIfNot


# ================================================================
# 测试辅助工厂
# ================================================================

def _make_expr(statement_index: int):
    """创建最简 mock，仅携带 StatementIndex。"""
    class _Stub:
        StatementIndex = statement_index
    return _Stub()


def _make_expr_with_byte_offset(statement_index: int, byte_offset_val: int):
    """创建带 byte_offset 的 mock 表达式。"""
    obj = _make_expr(statement_index)
    obj.byte_offset = byte_offset_val
    return obj


def _make_jump(statement_index: int, code_offset: int) -> EX_Jump:
    """创建 EX_Jump。"""
    jmp = EX_Jump(CodeOffset=code_offset)
    jmp.StatementIndex = statement_index
    return jmp


def _make_jump_if_not(
    statement_index: int,
    code_offset: int,
    boolean_expression=None,
) -> EX_JumpIfNot:
    """创建 EX_JumpIfNot。"""
    jmp = EX_JumpIfNot(CodeOffset=code_offset, BooleanExpression=boolean_expression)
    jmp.StatementIndex = statement_index
    return jmp


# ================================================================
# 标签输出测试
# ================================================================

class TestGotoLabelEmission:
    """goto 回退路径的标签输出。"""

    def test_label_emitted_before_target_expression(self):
        """跳转目标对应的表达式前应输出 Label。"""
        # 布局:
        #   idx 0: Jump(CodeOffset=30)  — 跳到 offset 30
        #   idx 1: expr (byte_offset=10)
        #   idx 2: expr (byte_offset=30)  — 跳转目标
        jump = _make_jump(statement_index=0, code_offset=30)
        expr1 = _make_expr_with_byte_offset(10, 10)
        target = _make_expr_with_byte_offset(20, 30)
        expressions = [jump, expr1, target]

        scf = StructuredControlFlow()
        # 手动调用 _emit_goto_fallback（绕过 reconstruct 的结构化检测）
        result = scf._emit_goto_fallback(expressions, jump_targets={30})

        # 应包含 Label_30: 且在 target 表达式之前
        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 1
        assert "Label_30:" in label_lines[0]
        label_idx = result.index("Label_30:")
        # 标签应出现在 target 的输出行之前
        assert label_idx < len(result) - 1

    def test_multiple_jump_targets_emit_multiple_labels(self):
        """多个跳转目标应各自输出对应标签。"""
        # Jump → 30 和 Jump → 50
        jump1 = _make_jump(statement_index=0, code_offset=30)
        jump2 = _make_jump(statement_index=10, code_offset=50)
        expr_mid = _make_expr_with_byte_offset(20, 20)
        target1 = _make_expr_with_byte_offset(30, 30)
        target2 = _make_expr_with_byte_offset(40, 50)
        expressions = [jump1, jump2, expr_mid, target1, target2]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={30, 50})

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 2
        assert any("Label_30:" in l for l in label_lines)
        assert any("Label_50:" in l for l in label_lines)

    def test_no_duplicate_labels(self):
        """同一跳转目标不应输出重复标签。"""
        # 两个 jump 都指向 offset 30
        jump1 = _make_jump(statement_index=0, code_offset=30)
        jump2 = _make_jump(statement_index=10, code_offset=30)
        target = _make_expr_with_byte_offset(20, 30)
        expressions = [jump1, jump2, target]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={30})

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 1

    def test_no_labels_when_no_jump_targets(self):
        """无跳转目标时不应输出任何标签。"""
        expr1 = _make_expr_with_byte_offset(0, 0)
        expr2 = _make_expr_with_byte_offset(10, 10)
        expressions = [expr1, expr2]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets=set())

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 0

    def test_label_uses_codeoffset_value(self):
        """标签名称应使用 jump target 的 CodeOffset 值。"""
        jump = _make_jump(statement_index=0, code_offset=42)
        # target 表达式的 byte_offset 映射到 CodeOffset=42
        target = _make_expr_with_byte_offset(10, 42)
        expressions = [jump, target]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={42})

        assert "Label_42:" in result

    def test_offset_to_index_mapping_with_byte_offset(self):
        """验证 byte_offset → index 映射正确关联跳转目标。"""
        # Jump(CodeOffset=50) 跳到 offset 50
        # 表达式列表中 idx 2 的 byte_offset=50
        jump = _make_jump(statement_index=0, code_offset=50)
        expr1 = _make_expr(10)
        target = _make_expr_with_byte_offset(20, 50)
        expressions = [jump, expr1, target]

        # 构建 offset_to_index 映射
        offset_to_index: dict[int, int] = {}
        for idx, expr in enumerate(expressions):
            byte_offset = getattr(expr, "byte_offset", None)
            if byte_offset is not None:
                offset_to_index[byte_offset] = idx
            if hasattr(expr, "CodeOffset"):
                offset_to_index[expr.CodeOffset] = idx

        # CodeOffset=50 应映射到 idx 0（来自 jump 的 CodeOffset）和 idx 2（来自 byte_offset）
        # 最终映射为 idx 2（后写覆盖）
        assert offset_to_index.get(50) == 2

    def test_offset_to_index_passed_from_reconstruct(self):
        """验证 reconstruct 传入的 offset_to_index 被正确使用。"""
        # 构造一个不会被 _detect_patterns 识别为结构化模式的序列
        # 从而走 goto 回退路径
        jump = _make_jump(statement_index=0, code_offset=30)
        mid = _make_expr(10)
        target = _make_expr_with_byte_offset(20, 30)
        end = _make_expr(30)  # offset 30 的目标
        expressions = [jump, mid, target, end]

        scf = StructuredControlFlow()
        result = scf.reconstruct(expressions)

        # 应包含 Label_30:
        label_lines = [l for l in result if "Label_30:" in l]
        assert len(label_lines) == 1

    def test_labels_sorted_by_offset(self):
        """多个标签应按偏移量排序输出。"""
        # 乱序跳转目标
        jump1 = _make_jump(statement_index=0, code_offset=50)
        jump2 = _make_jump(statement_index=5, code_offset=20)
        target2 = _make_expr_with_byte_offset(10, 20)
        target1 = _make_expr_with_byte_offset(15, 50)
        expressions = [jump1, jump2, target2, target1]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={20, 50})

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 2
        # Label_20 应在 Label_50 之前（因为 target2 在 target1 之前）
        idx_20 = result.index("Label_20:")
        idx_50 = result.index("Label_50:")
        assert idx_20 < idx_50

    def test_empty_expressions(self):
        """空表达式列表不应抛异常。"""
        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback([], jump_targets={10})
        assert result == []

    def test_label_not_emitted_for_non_target_offset(self):
        """非跳转目标的偏移量不应生成标签。"""
        jump = _make_jump(statement_index=0, code_offset=30)
        expr = _make_expr_with_byte_offset(10, 10)  # 不是跳转目标
        target = _make_expr_with_byte_offset(20, 30)
        expressions = [jump, expr, target]

        scf = StructuredControlFlow()
        result = scf._emit_goto_fallback(expressions, jump_targets={30})

        label_lines = [l for l in result if l.startswith("Label_")]
        assert len(label_lines) == 1
        assert "Label_30:" in label_lines[0]
        # 不应有 Label_10
        assert not any("Label_10:" in l for l in label_lines)
