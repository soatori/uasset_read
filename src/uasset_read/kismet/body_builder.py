from __future__ import annotations

"""
Kismet Expression → C++ Function Body Builder.

Assembles a list of KismetExpression into a complete
C++ function body with proper indentation, semicolons, braces, and labels.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression
    from uasset_read.link.linker import PackageLinker


# Statements that already end with ';' internally or shouldn't get one added.
_STATEMENT_TERMINATED = {
    "goto ",
    "if ",
    "return;",
    "}",
    "{",
    "switch ",
    "case ",
    "default:",
    "assert(",
    "/*",
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
    """Check if the specified index is the start of a structured block (while/if/for/switch)."""
    return jump_analyzer.detect_pattern(idx) is not None


def _get_structured_block_end(jump_analyzer, idx: int) -> int:
    """Get the end index (inclusive) of the structured block starting at idx."""
    result = jump_analyzer.detect_pattern(idx)
    if result is None:
        return idx

    ptype = result["type"]
    if ptype in ("while", "for"):
        return result["body_end"]
    if ptype in ("if_else", "push_pop"):
        return result["else_end"]
    if ptype == "if":
        return result["then_end"]
    if ptype == "switch":
        # switch itself is a single expression
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
    """Detect and emit the structured control flow block starting at start_idx."""

    # --- for pattern (higher priority than while) ---
    for_result = jump_analyzer.detect_for_pattern(start_idx)
    if for_result is not None:
        return _emit_for_block(
            for_result,
            translator,
            expressions,
            jump_targets,
            offset_to_index,
            label_set,
        )

    # --- while pattern ---
    while_result = jump_analyzer.detect_while_pattern(start_idx)
    if while_result is not None:
        return _emit_while_block(
            while_result,
            translator,
            expressions,
            jump_targets,
            offset_to_index,
            label_set,
        )

    # --- Push/Pop if/else pattern ---
    push_pop_result = jump_analyzer.detect_push_pop_pattern(start_idx)
    if push_pop_result is not None:
        return _emit_push_pop_block(
            push_pop_result,
            translator,
            expressions,
        )

    # --- if/else pattern (JumpIfNot start) ---
    if_else_result = jump_analyzer.detect_if_else_pattern(start_idx)
    if if_else_result is not None:
        return _emit_if_else_block(
            if_else_result,
            translator,
            expressions,
            jump_targets,
            offset_to_index,
            label_set,
        )

    # --- switch/case pattern ---
    switch_result = jump_analyzer.detect_switch_pattern(start_idx)
    if switch_result is not None:
        return _emit_switch_block(
            switch_result,
            translator,
            expressions,
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
    """Emit a for loop block."""
    body_start = for_result["body_start"]
    condition = for_result["condition"]
    inc_start = for_result["increment_start"]
    inc_end = for_result["increment_end"]

    cond_str = translator.line_cpp(condition)

    # Generate increment expression string
    inc_parts: list[str] = []
    for j in range(inc_start, inc_end + 1):
        line = translator.line_cpp(expressions[j], index=j)
        if line and line.strip():
            inc_parts.append(line.strip().rstrip(";"))
    inc_str = ", ".join(inc_parts) if inc_parts else ""

    result: list[str] = [f"for (; {cond_str}; {inc_str}) {{"]

    # Emit loop body (excluding increment and back jump)
    for j in range(body_start, inc_start):
        byte_off = getattr(expressions[j], "StatementIndex", None)
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
    """Emit a switch/case block."""
    index_term = switch_result["index_term"]
    cases = switch_result["cases"]
    default_term = switch_result["default_term"]

    index_str = translator.line_cpp(index_term) if index_term else "?"
    result: list[str] = [f"switch ({index_str}) {{"]

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
    """Emit a while loop block."""
    body_start = while_result["body_start"]
    body_end = while_result["body_end"]
    condition = while_result["condition"]

    cond_str = translator.line_cpp(condition)
    result: list[str] = [f"while ({cond_str}) {{"]

    # Emit loop body (skip back jump EX_Jump, handled by while structure)
    for j in range(body_start, body_end):
        # Check if this is a jump target (label)
        byte_off = getattr(expressions[j], "StatementIndex", None)
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
    """Emit an if/else block."""
    condition = if_else_result["condition"]
    cond_str = translator.line_cpp(condition)
    result: list[str] = [f"if ({cond_str}) {{"]

    if if_else_result["type"] == "if_else":
        # then branch
        then_start = if_else_result["then_start"]
        then_end = if_else_result["then_end"]
        for j in range(then_start, then_end):
            line = translator.line_cpp(expressions[j], index=j)
            if line and line.strip():
                result.append(f"    {line}")

        result.append("} else {")

        # else branch
        else_start = if_else_result["else_start"]
        else_end = if_else_result["else_end"]
        for j in range(else_start, else_end + 1):
            # Skip PopExecutionFlow (handled by if/else structure)
            line = translator.line_cpp(expressions[j], index=j)
            if line and line.strip():
                result.append(f"    {line}")
    else:
        # Simple if pattern
        then_start = if_else_result["then_start"]
        then_end = if_else_result["then_end"]
        for j in range(then_start, then_end + 1):
            line = translator.line_cpp(expressions[j], index=j)
            if line and line.strip():
                result.append(f"    {line}")

    result.append("}")
    return result


def _emit_push_pop_block(
    push_pop_result: dict,
    translator,
    expressions: list,
) -> list[str]:
    """Emit Push/Pop-tagged if/else block.

    Push/Pop pattern: PushExecutionFlow + JumpIfNot + then + PopExecutionFlow + else
    """
    condition = push_pop_result["condition"]
    cond_str = translator.line_cpp(condition)
    result: list[str] = [f"if ({cond_str}) {{"]

    # then branch
    then_start = push_pop_result["then_start"]
    then_end = push_pop_result["then_end"]
    for j in range(then_start, then_end):
        line = translator.line_cpp(expressions[j], index=j)
        if line and line.strip():
            result.append(f"    {line}")

    result.append("} else {")

    # else branch
    else_start = push_pop_result["else_start"]
    else_end = push_pop_result["else_end"]
    for j in range(else_start, else_end + 1):
        line = translator.line_cpp(expressions[j], index=j)
        if line and line.strip():
            result.append(f"    {line}")

    result.append("}")
    return result


class FunctionBodyBuilder:
    """
    Assembles KismetExpression list into a readable C++ function body.

    Usage:
        builder = FunctionBodyBuilder()
        cpp = builder.to_function_body(expressions, func_name="MyFunction")
    """

    def __init__(self, linker: "PackageLinker | None" = None) -> None:
        from uasset_read.kismet.translator import KismetTranslator

        self._linker = linker
        self._translator = KismetTranslator(linker=linker)

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

        # Create translator with JumpAnalyzer for structured detection
        jump_analyzer = JumpAnalyzer(expressions)
        translator = KismetTranslator(linker=self._linker, expressions=expressions)

        # Build StatementIndex → expression index map for label generation
        offset_to_index: dict[int, int] = {}
        for idx, expr in enumerate(expressions):
            stmt_idx = getattr(expr, "StatementIndex", None)
            if stmt_idx is not None:
                offset_to_index[stmt_idx] = idx
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
        skip_until: int = -1  # Structured block end index, skip internal expressions

        for idx, expr in enumerate(expressions):
            # Skip expressions inside structured blocks (already handled by block)
            if idx <= skip_until:
                continue

            # Check if starting a structured block
            if _is_structured_block_start(jump_analyzer, idx):
                block_lines = _emit_structured_block(
                    jump_analyzer,
                    translator,
                    expressions,
                    idx,
                    jump_targets,
                    offset_to_index,
                    label_set,
                )
                lines.extend(block_lines)
                # Determine skip range
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
