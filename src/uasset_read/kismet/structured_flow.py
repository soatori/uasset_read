"""
Kismet Expression → Structured Control Flow Reconstruction.

Identifies if/else, while/for patterns from
PushExecutionFlow / PopExecutionFlow / JumpIfNot sequences and
produces structured C++ output. Falls back to goto for unrecognized patterns.

Decision D-03: Algorithm does not need to be perfect — handles common patterns,
falls back to goto for edge cases.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression
    from uasset_read.link.linker import PackageLinker


@dataclass
class _Block:
    """Represents a structured block of code."""
    lines: list[str] = field(default_factory=list)
    start: int = 0
    end: int = 0


class StructuredControlFlow:
    """
    Reconstructs structured control flow from Kismet expressions.

    Algorithm: work-list + Push/Pop pattern matching.
    - PushExecutionFlow + JumpIfNot + PopExecutionFlow → if/else
    - Back-jump to earlier offset → while/for loop
    - Unrecognized → goto fallback
    """

    def __init__(self, linker: "PackageLinker | None" = None) -> None:
        from uasset_read.kismet.translator import KismetTranslator
        self._translator = KismetTranslator(linker=linker)

    def reconstruct(self, expressions: list["KismetExpression"]) -> list[str]:
        """
        Reconstruct structured control flow from a list of expressions.

        Args:
            expressions: List of KismetExpression from bytecode parsing.

        Returns:
            List of C++ lines with structured control flow (if/while/etc)
            or goto-based fallback.
        """
        if not expressions:
            return []

        # Build offset → index map
        offset_map: dict[int, int] = {}
        for idx, expr in enumerate(expressions):
            if hasattr(expr, "CodeOffset"):
                offset_map[expr.CodeOffset] = idx
            byte_offset = getattr(expr, "byte_offset", None)
            if byte_offset is not None:
                offset_map[byte_offset] = idx

        # Collect all jump targets
        jump_targets: set[int] = set()
        for expr in expressions:
            if hasattr(expr, "CodeOffset"):
                jump_targets.add(expr.CodeOffset)

        # Detect structured patterns
        structured_regions = self._detect_patterns(expressions, offset_map, jump_targets)

        if structured_regions:
            return self._emit_structured(expressions, structured_regions, jump_targets)
        else:
            return self._emit_goto_fallback(expressions, jump_targets, offset_map)

    def _detect_patterns(
        self,
        expressions: list["KismetExpression"],
        offset_map: dict[int, int],
        jump_targets: set[int],
    ) -> list[dict]:
        """
        Detect if/else and while patterns in the expression list.

        Returns a list of region dicts: {type, start, end, else_start, condition, ...}
        """
        from uasset_read.kismet.expressions import (
            EX_PushExecutionFlow, EX_PopExecutionFlow,
            EX_PopExecutionFlowIfNot, EX_JumpIfNot, EX_Jump, EX_EndOfScript,
        )

        regions: list[dict] = []
        i = 0
        while i < len(expressions):
            expr = expressions[i]

            # --- if/else pattern: Push + (optional exprs) + JumpIfNot → then body → Pop → else body ---
            # Allow up to 3 instructions between Push and JumpIfNot (condition loading).
            if isinstance(expr, EX_PushExecutionFlow):
                jump_if_not_idx = None
                for k in range(i + 1, min(i + 4, len(expressions))):
                    if isinstance(expressions[k], EX_JumpIfNot):
                        jump_if_not_idx = k
                        break
                    # Stop if we hit another Push, Jump, or EndOfScript
                    if isinstance(expressions[k], (EX_PushExecutionFlow, EX_Jump, EX_EndOfScript)):
                        break
                if jump_if_not_idx is not None:
                    cond = expressions[jump_if_not_idx].BooleanExpression

                    # Find the Pop that ends the then-block
                    # Search from jump_if_not_idx+1 until we find a Pop
                    pop_idx = None
                    for j in range(jump_if_not_idx + 1, len(expressions)):
                        if isinstance(expressions[j], EX_PopExecutionFlow):
                            pop_idx = j
                            break
                        # Stop if we hit another Push or EndOfScript
                        if isinstance(expressions[j], (EX_PushExecutionFlow, EX_EndOfScript)):
                            break

                    if pop_idx is not None:
                        # Else block: from pop_idx+1 until next label/jump target or end
                        else_start = pop_idx + 1
                        else_end = self._find_block_end(expressions, else_start, offset_map, jump_targets)

                        regions.append({
                            "type": "if_else",
                            "start": i,
                            "cond": cond,
                            "then_start": i + 2,
                            "then_end": pop_idx,
                            "else_start": else_start,
                            "else_end": else_end,
                        })
                        i = else_end + 1
                        continue

            # --- while pattern: JumpIfNot(exit) → body → Jump(back) ---
            if isinstance(expr, EX_JumpIfNot):
                exit_offset = expr.CodeOffset if hasattr(expr, 'CodeOffset') else None
                if exit_offset is not None:
                    # Look for a back-jump (Jump to an offset <= current)
                    back_jump_idx = self._find_back_jump(expressions, i + 1, exit_offset)
                    if back_jump_idx is not None:
                        regions.append({
                            "type": "while",
                            "start": i,
                            "cond": expr.BooleanExpression,
                            "body_start": i + 1,
                            "body_end": back_jump_idx,
                            "exit": exit_offset,
                        })
                        i = back_jump_idx + 1
                        continue

            i += 1

        return regions

    def _find_matching_pop(
        self,
        expressions: list["KismetExpression"],
        search_from: int,
        before_idx: int,
    ) -> int | None:
        """Find EX_PopExecutionFlow between search_from and before_idx."""
        from uasset_read.kismet.expressions import EX_PopExecutionFlow
        for i in range(search_from, min(before_idx, len(expressions))):
            if isinstance(expressions[i], EX_PopExecutionFlow):
                return i
        return None

    def _find_back_jump(
        self,
        expressions: list["KismetExpression"],
        search_from: int,
        exit_offset: int,
    ) -> int | None:
        """Find an EX_Jump that jumps back to before exit_offset."""
        from uasset_read.kismet.expressions import EX_Jump
        for i in range(search_from, len(expressions)):
            if isinstance(expressions[i], EX_Jump):
                target = expressions[i].CodeOffset if hasattr(expressions[i], 'CodeOffset') else None
                if target is not None and target <= exit_offset:
                    return i
        return None

    def _find_block_end(
        self,
        expressions: list["KismetExpression"],
        start: int,
        offset_map: dict[int, int],
        jump_targets: set[int],
    ) -> int:
        """Find the end of a block (next label or end of list)."""
        for i in range(start + 1, len(expressions)):
            byte_off = getattr(expressions[i], "byte_offset", None)
            if byte_off is not None and byte_off in jump_targets:
                return i - 1
        return len(expressions) - 1

    def _emit_structured(
        self,
        expressions: list["KismetExpression"],
        regions: list[dict],
        jump_targets: set[int],
    ) -> list[str]:
        """Emit structured C++ output based on detected regions."""
        result: list[str] = []
        i = 0
        region_map: dict[int, dict] = {}
        for r in regions:
            region_map[r["start"]] = r

        while i < len(expressions):
            if i in region_map:
                region = region_map[i]
                if region["type"] == "if_else":
                    cond_str = self._translator.line_cpp(region["cond"])
                    result.append(f"if ({cond_str}) {{")
                    # Then block
                    for j in range(region["then_start"], region["then_end"]):
                        line = self._translator.line_cpp(expressions[j])
                        if line and line.strip():
                            result.append(f"    {line}")
                    result.append("} else {")
                    # Else block
                    for j in range(region["else_start"], region["else_end"] + 1):
                        line = self._translator.line_cpp(expressions[j])
                        if line and line.strip():
                            result.append(f"    {line}")
                    result.append("}")
                    i = region["else_end"] + 1
                    continue

                elif region["type"] == "while":
                    cond_str = self._translator.line_cpp(region["cond"])
                    result.append(f"while ({cond_str}) {{")
                    for j in range(region["body_start"], region["body_end"]):
                        line = self._translator.line_cpp(expressions[j])
                        if line and line.strip():
                            result.append(f"    {line}")
                    result.append("}")
                    i = region["body_end"] + 1
                    continue

            # Default: translate line
            line = self._translator.line_cpp(expressions[i])
            if line and line.strip():
                result.append(line)
            i += 1

        return result

    def _emit_goto_fallback(
        self,
        expressions: list["KismetExpression"],
        jump_targets: set[int],
        offset_to_index: dict[int, int] | None = None,
    ) -> list[str]:
        """
        Emit goto-based output as fallback when no structured patterns detected.

        使用 offset_to_index 映射（与 body_builder.py 一致）精确匹配跳转目标。
        """
        # 若未传入映射则自行构建
        if offset_to_index is None:
            offset_to_index = {}
            for idx, expr in enumerate(expressions):
                byte_offset = getattr(expr, "byte_offset", None)
                if byte_offset is not None:
                    offset_to_index[byte_offset] = idx
                if hasattr(expr, "CodeOffset"):
                    offset_to_index[expr.CodeOffset] = idx

        result: list[str] = []
        label_set: set[int] = set()  # 已输出的标签，防止重复
        for i, expr in enumerate(expressions):
            # 检查当前索引是否对应某个跳转目标 — 输出标签
            for target in sorted(jump_targets):
                if offset_to_index.get(target) == i and target not in label_set:
                    result.append(f"Label_{target}:")
                    label_set.add(target)

            line = self._translator.line_cpp(expr, index=i)
            if line and line.strip():
                result.append(line)

        return result


# ===========================================================================
# Module-level convenience exports
# ===========================================================================

# Re-export dataclass as StructuredBlock for cleaner API
from dataclasses import dataclass as _dataclass


@_dataclass
class StructuredBlock:
    """A structured control flow block (if/else/for/while)."""
    kind: str  # "if", "if_else", "for", "while"
    condition: str | None  # C++ condition expression
    then_body: list[str]  # indented lines
    else_body: list[str] | None  # indented lines (None for if-only)


__all__ = ["StructuredControlFlow", "StructuredBlock"]
