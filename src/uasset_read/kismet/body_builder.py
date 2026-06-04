"""
Kismet Expression → C++ Function Body Builder.

Assembles a list of KismetExpression into a complete
C++ function body with proper indentation, semicolons, braces, and labels.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression
    from uasset_read.kismet.translator import TypeRegistry
    from uasset_read.link.linker import PackageLinker


# Statements that already end with ';' internally or shouldn't get one added.
_STATEMENT_TERMINATED = {
    "goto ", "if ", "return;", "}", "{", "switch ", "case ", "default:",
    "assert(", "/*",
}


def _needs_semicolon(line: str) -> bool:
    """Check if a C++ line needs a semicolon appended."""
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.endswith(";"):
        return False
    if stripped.endswith("{") or stripped.endswith("}"):
        return False
    for prefix in _STATEMENT_TERMINATED:
        if stripped.startswith(prefix):
            return False
    return True


def _is_structured_block_start(jump_analyzer, idx: int) -> bool:
    """判断指定索引是否是结构化块（while/if/for/switch）的起始位置。"""
    return jump_analyzer.detect_pattern(idx) is not None


def _get_structured_block_end(jump_analyzer, idx: int) -> int:
    """获取从 idx 开始的结构化块的结束索引（含）。"""
    result = jump_analyzer.detect_pattern(idx)
    if result is None:
        return idx

    ptype = result["type"]
    if ptype in ("while", "for"):
        return result["body_end"]
    if ptype == "if_else":
        return result["else_end"]
    if ptype == "if":
        return result["then_end"]
    if ptype == "switch":
        # switch 自身是单个表达式
        return idx
    return idx


def _emit_structured_block(
    jump_analyzer,
    translator,
    expressions: list,
    start_idx: int,
    jump_targets: set[int],
    offset_to_index: dict[int, int],
    label_set: set[int],
) -> list[str]:
    """检测并输出从 start_idx 开始的结构化控制流块。"""

    # --- for 模式（优先于 while） ---
    for_result = jump_analyzer.detect_for_pattern(start_idx)
    if for_result is not None:
        return _emit_for_block(
            for_result, translator, expressions,
            jump_targets, offset_to_index, label_set,
        )

    # --- while 模式 ---
    while_result = jump_analyzer.detect_while_pattern(start_idx)
    if while_result is not None:
        return _emit_while_block(
            while_result, translator, expressions,
            jump_targets, offset_to_index, label_set,
        )

    # --- if/else 模式 ---
    if_else_result = jump_analyzer.detect_if_else_pattern(start_idx)
    if if_else_result is not None:
        return _emit_if_else_block(
            if_else_result, translator, expressions,
            jump_targets, offset_to_index, label_set,
        )

    # --- switch/case 模式 ---
    switch_result = jump_analyzer.detect_switch_pattern(start_idx)
    if switch_result is not None:
        return _emit_switch_block(
            switch_result, translator, expressions,
        )

    return []


def _emit_for_block(
    for_result: dict,
    translator,
    expressions: list,
    jump_targets: set[int],
    offset_to_index: dict[int, int],
    label_set: set[int],
) -> list[str]:
    """输出 for 循环块。"""
    start_idx = for_result["start"]
    body_start = for_result["body_start"]
    body_end = for_result["body_end"]
    condition = for_result["condition"]
    inc_start = for_result["increment_start"]
    inc_end = for_result["increment_end"]

    cond_str = translator.line_cpp(condition)

    # 生成递增表达式字符串
    inc_parts: list[str] = []
    for j in range(inc_start, inc_end + 1):
        line = translator.line_cpp(expressions[j], index=j)
        if line and line.strip():
            inc_parts.append(line.strip().rstrip(";"))
    inc_str = ", ".join(inc_parts) if inc_parts else ""

    result: list[str] = [f"for (; {cond_str}; {inc_str}) {{" ]

    # 输出循环体（不含递增和回跳）
    for j in range(body_start, inc_start):
        byte_off = getattr(expressions[j], "byte_offset", None)
        if byte_off is not None and byte_off in jump_targets:
            target_idx = offset_to_index.get(byte_off)
            if target_idx is not None and target_idx not in label_set:
                result.append(f"    Label_{byte_off}:")
                label_set.add(target_idx)

        line = translator.line_cpp(expressions[j], index=j)
        if line and line.strip():
            result.append(f"    {line}")

    result.append("}")
    return result


def _emit_switch_block(
    switch_result: dict,
    translator,
    expressions: list,
) -> list[str]:
    """输出 switch/case 块。"""
    index_term = switch_result["index_term"]
    cases = switch_result["cases"]
    default_term = switch_result["default_term"]

    index_str = translator.line_cpp(index_term) if index_term else "?"
    result: list[str] = [f"switch ({index_str}) {{" ]

    for case_item in cases:
        case_idx = case_item["index_term"]
        case_term = case_item["case_term"]
        case_idx_str = translator.line_cpp(case_idx) if case_idx else "?"
        case_val_str = translator.line_cpp(case_term) if case_term else "?"
        result.append(f"    case {case_idx_str}:")
        result.append(f"        {case_val_str};")
        result.append("        break;")

    if default_term:
        default_str = translator.line_cpp(default_term)
        result.append("    default:")
        result.append(f"        {default_str};")

    result.append("}")
    return result


def _emit_while_block(
    while_result: dict,
    translator,
    expressions: list,
    jump_targets: set[int],
    offset_to_index: dict[int, int],
    label_set: set[int],
) -> list[str]:
    """输出 while 循环块。"""
    start_idx = while_result["start"]
    body_start = while_result["body_start"]
    body_end = while_result["body_end"]
    condition = while_result["condition"]

    cond_str = translator.line_cpp(condition)
    result: list[str] = [f"while ({cond_str}) {{"]

    # 输出循环体（跳过回跳 EX_Jump，由 while 结构处理）
    for j in range(body_start, body_end):
        # 检查是否是跳转目标（标签）
        byte_off = getattr(expressions[j], "byte_offset", None)
        if byte_off is not None and byte_off in jump_targets:
            target_idx = offset_to_index.get(byte_off)
            if target_idx is not None and target_idx not in label_set:
                result.append(f"    Label_{byte_off}:")
                label_set.add(target_idx)

        line = translator.line_cpp(expressions[j], index=j)
        if line and line.strip():
            result.append(f"    {line}")

    result.append("}")
    return result


def _emit_if_else_block(
    if_else_result: dict,
    translator,
    expressions: list,
    jump_targets: set[int],
    offset_to_index: dict[int, int],
    label_set: set[int],
) -> list[str]:
    """输出 if/else 块。"""
    condition = if_else_result["condition"]
    cond_str = translator.line_cpp(condition)
    result: list[str] = [f"if ({cond_str}) {{"]

    if if_else_result["type"] == "if_else":
        # then 分支
        then_start = if_else_result["then_start"]
        then_end = if_else_result["then_end"]
        for j in range(then_start, then_end):
            line = translator.line_cpp(expressions[j], index=j)
            if line and line.strip():
                result.append(f"    {line}")

        result.append("} else {")

        # else 分支
        else_start = if_else_result["else_start"]
        else_end = if_else_result["else_end"]
        for j in range(else_start, else_end + 1):
            # 跳过 PopExecutionFlow（由 if/else 结构处理）
            line = translator.line_cpp(expressions[j], index=j)
            if line and line.strip():
                result.append(f"    {line}")
    else:
        # 简单 if 模式
        then_start = if_else_result["then_start"]
        then_end = if_else_result["then_end"]
        for j in range(then_start, then_end + 1):
            line = translator.line_cpp(expressions[j], index=j)
            if line and line.strip():
                result.append(f"    {line}")

    result.append("}")
    return result


class FunctionBodyBuilder:
    """
    Assembles KismetExpression list into a readable C++ function body.

    Usage:
        builder = FunctionBodyBuilder(type_registry)
        cpp = builder.to_function_body(expressions, func_name="MyFunction")
    """

    def __init__(self, type_registry: "TypeRegistry | None" = None, linker: "PackageLinker | None" = None) -> None:
        from uasset_read.kismet.translator import KismetTranslator, TypeRegistry
        self.type_registry = type_registry or TypeRegistry()
        self._linker = linker
        self._translator = KismetTranslator(self.type_registry, linker=linker)

    def to_function_body(
        self,
        expressions: list["KismetExpression"],
        func_name: str | None = None,
    ) -> str:
        """
        Translate a list of KismetExpression into a C++ function body.

        Args:
            expressions: List of expressions from bytecode parsing.
            func_name: Optional function name for the output wrapper.

        Returns:
            Formatted C++ function body string.
        """
        from uasset_read.kismet.jump_analyzer import JumpAnalyzer
        from uasset_read.kismet.translator import KismetTranslator

        # 创建带 JumpAnalyzer 的翻译器用于结构化检测
        jump_analyzer = JumpAnalyzer(expressions)
        translator = KismetTranslator(self.type_registry, linker=self._linker, expressions=expressions)

        # Build byte_offset → expression index map for label generation
        offset_to_index: dict[int, int] = {}
        for idx, expr in enumerate(expressions):
            byte_offset = getattr(expr, "byte_offset", None)
            if byte_offset is not None:
                offset_to_index[byte_offset] = idx
            # Also track CodeOffset attributes for jump targets
            if hasattr(expr, "CodeOffset"):
                offset_to_index[expr.CodeOffset] = idx

        # Collect pending labels (offsets that are jump targets)
        jump_targets: set[int] = set()
        for expr in expressions:
            if hasattr(expr, "CodeOffset"):
                jump_targets.add(expr.CodeOffset)

        # Translate each expression
        lines: list[str] = []
        label_set: set[int] = set()
        skip_until: int = -1  # 结构化块结束索引，跳过内部表达式

        for idx, expr in enumerate(expressions):
            # 跳过结构化块内部的表达式（已由块处理）
            if idx <= skip_until:
                continue

            # 检查是否开始一个结构化块
            if _is_structured_block_start(jump_analyzer, idx):
                block_lines = _emit_structured_block(
                    jump_analyzer, translator, expressions, idx,
                    jump_targets, offset_to_index, label_set,
                )
                lines.extend(block_lines)
                # 确定跳过范围
                skip_until = _get_structured_block_end(jump_analyzer, idx)
                continue

            cpp_line = translator.line_cpp(expr, index=idx)

            # Skip empty lines (EX_EndOfScript, EX_PushExecutionFlow, etc.)
            if not cpp_line or cpp_line.strip() == "":
                continue

            # Check if this index is a jump target — emit label
            for target in sorted(jump_targets):
                if offset_to_index.get(target) == idx and target not in label_set:
                    lines.append(f"Label_{target}:")
                    label_set.add(target)

            # Handle multi-line output (e.g., BreakVector)
            for sub_line in cpp_line.split("\n"):
                sub_line = sub_line.strip()
                if not sub_line:
                    continue
                if _needs_semicolon(sub_line):
                    sub_line += ";"
                lines.append(sub_line)

        # Wrap in function signature
        signature = func_name if func_name else "void UnknownFunction"
        if "(" not in signature:
            signature += "()"

        body = "\n".join(f"    {line}" for line in lines)
        return f"{signature} {{\n{body}\n}}"

    def to_function_body_structured(
        self,
        expressions: list["KismetExpression"],
        func_name: str | None = None,
    ) -> str:
        """
        Translate expressions using structured control flow reconstruction.

        Tries StructuredControlFlow first; falls back to goto-based output
        if no structured patterns are detected.

        Args:
            expressions: List of KismetExpression from bytecode parsing.
            func_name: Optional function name for the wrapper.

        Returns:
            Formatted C++ function body string.
        """
        from uasset_read.kismet.structured_flow import StructuredControlFlow

        flow = StructuredControlFlow(linker=self._linker)
        structured_lines = flow.reconstruct(expressions)

        if not structured_lines:
            # No patterns detected, use goto fallback
            return self.to_function_body(expressions, func_name)

        # Add semicolons and indentation to structured lines
        processed: list[str] = []
        for line in structured_lines:
            stripped = line.strip()
            if not stripped:
                continue
            if _needs_semicolon(stripped):
                stripped += ";"
            processed.append(stripped)

        signature = func_name if func_name else "void UnknownFunction"
        if "(" not in signature:
            signature += "()"

        body = "\n".join(f"    {line}" for line in processed)
        return f"{signature} {{\n{body}\n}}"


# ===========================================================================
# Module-level convenience functions (D-01 dual API)
# ===========================================================================

def to_function_body(
    expressions: list["KismetExpression"],
    func_name: str | None = None,
) -> str:
    """
    Module-level convenience wrapper for FunctionBodyBuilder.to_function_body().

    Usage:
        from uasset_read.kismet import to_function_body

        expressions = [...]  # list of KismetExpression from bytecode parsing
        cpp = to_function_body(expressions, func_name="MyFunction")
    """
    builder = FunctionBodyBuilder()
    return builder.to_function_body(expressions, func_name)
