from __future__ import annotations

"""
Kismet Expression → Structured Control Flow Reconstruction.

Provides goto-based fallback output when JumpAnalyzer cannot match structured patterns.

Decision D-03: Algorithm does not need to be perfect — handles common patterns,
falls back to goto for edge cases.

Note: Pattern detection is handled by JumpAnalyzer (the unified detector).
StructuredControlFlow.reconstruct() delegates detection to JumpAnalyzer
and falls back to goto emission when no patterns match.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression
    from uasset_read.link.linker import PackageLinker
    from uasset_read.kismet.jump_analyzer import JumpAnalyzer


@dataclass
class _Block:
    """Represents a structured block of code."""
    lines: list[str] = field(default_factory=list)
    start: int = 0
    end: int = 0


class StructuredControlFlow:
    """
    Reconstructs structured control flow from Kismet expressions.

    Uses JumpAnalyzer as the unified pattern detector.
    Falls back to goto-based output for unrecognized patterns.

    For primary usage, prefer FunctionBodyBuilder.to_function_body_structured()
    which uses JumpAnalyzer directly.
    """

    def __init__(self, linker: "PackageLinker | None" = None) -> None:
        from uasset_read.kismet.translator import KismetTranslator
        self._translator = KismetTranslator(linker=linker)

    def reconstruct(self, expressions: list["KismetExpression"]) -> list[str]:
        """
        Reconstruct structured control flow from a list of expressions.

        Uses JumpAnalyzer for pattern detection, falls back to goto emission.

        Args:
            expressions: List of KismetExpression from bytecode parsing.

        Returns:
            List of C++ lines with structured control flow (if/while/etc)
            or goto-based fallback.
        """
        if not expressions:
            return []

        from uasset_read.kismet.jump_analyzer import JumpAnalyzer

        jump_analyzer = JumpAnalyzer(expressions)

        # Build offset → index map
        offset_map: dict[int, int] = {}
        for idx, expr in enumerate(expressions):
            if hasattr(expr, "CodeOffset"):
                offset_map[expr.CodeOffset] = idx
            stmt_idx = getattr(expr, "StatementIndex", None)
            if stmt_idx is not None:
                offset_map[stmt_idx] = idx

        # Collect all jump targets
        jump_targets: set[int] = set()
        for expr in expressions:
            if hasattr(expr, "CodeOffset"):
                jump_targets.add(expr.CodeOffset)

        # Use JumpAnalyzer for pattern detection (unified entry point)
        structured_regions = self._detect_patterns_via_jump_analyzer(
            expressions, jump_analyzer,
        )

        if structured_regions:
            return self._emit_structured(expressions, structured_regions, jump_targets)
        else:
            return self._emit_goto_fallback(expressions, jump_targets, offset_map)

    def _detect_patterns_via_jump_analyzer(
        self,
        expressions: list["KismetExpression"],
        jump_analyzer: "JumpAnalyzer",
    ) -> list[dict]:
        """Use JumpAnalyzer to detect structured patterns (unified entry point).

        Converts JumpAnalyzer detection results to the format needed by _emit_structured.
        """
        regions: list[dict] = []
        used_indices: set[int] = set()
        i = 0
        while i < len(expressions):
            if i in used_indices:
                i += 1
                continue

            result = jump_analyzer.detect_pattern(i)
            if result is not None:
                ptype = result["type"]
                if ptype in ("push_pop", "if_else"):
                    # Unify to if_else format for _emit_structured
                    region = {
                        "type": "if_else",
                        "start": result["start"],
                        "cond": result["condition"],
                        "then_start": result["then_start"],
                        "then_end": result["then_end"],
                        "else_start": result["else_start"],
                        "else_end": result["else_end"],
                    }
                    regions.append(region)
                    for j in range(result["start"], result["else_end"] + 1):
                        used_indices.add(j)
                elif ptype == "while":
                    region = {
                        "type": "while",
                        "start": result["start"],
                        "cond": result["condition"],
                        "body_start": result["body_start"],
                        "body_end": result["body_end"],
                        "exit": result["exit_label"],
                    }
                    regions.append(region)
                    for j in range(result["start"], result["body_end"] + 1):
                        used_indices.add(j)
                elif ptype == "for":
                    # for loops also output as while format (simplified handling)
                    region = {
                        "type": "while",
                        "start": result["start"],
                        "cond": result["condition"],
                        "body_start": result["body_start"],
                        "body_end": result["body_end"],
                        "exit": result["exit_label"],
                    }
                    regions.append(region)
                    for j in range(result["start"], result["body_end"] + 1):
                        used_indices.add(j)
                # switch handled as independent expression, no region created
            i += 1

        return regions

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

        Use offset_to_index mapping (consistent with body_builder.py) to precisely match jump targets.
        """
        # Build mapping if not provided
        if offset_to_index is None:
            offset_to_index = {}
            for idx, expr in enumerate(expressions):
                stmt_idx = getattr(expr, "StatementIndex", None)
                if stmt_idx is not None:
                    offset_to_index[stmt_idx] = idx
                if hasattr(expr, "CodeOffset"):
                    offset_to_index[expr.CodeOffset] = idx

        result: list[str] = []
        label_set: set[int] = set()  # Already emitted labels, prevent duplicates
        for i, expr in enumerate(expressions):
            # Check if current index corresponds to a jump target — emit label
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
