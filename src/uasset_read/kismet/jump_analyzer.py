"""Kismet jump instruction pre-scanner.

Pre-analyzes EX_Jump / EX_JumpIfNot / EX_SwitchValue instructions to build a mapping from
byte offsets to expression indices, and provides detection of if/else, while, for, and
switch/case control flow patterns.

Usage:
    analyzer = JumpAnalyzer(expressions)
    pattern = analyzer.detect_pattern(start_idx=0)
    rate = analyzer.analyze_structured_rate()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression


# Assignment expression types, used to identify for-loop increment statements
_ASSIGNMENT_TYPES: tuple[type, ...] = ()


def _get_assignment_types() -> tuple[type, ...]:
    """Lazy-load assignment type tuple to avoid circular imports."""
    global _ASSIGNMENT_TYPES
    if not _ASSIGNMENT_TYPES:
        from uasset_read.kismet.expressions.assignments import (
            EX_Let,
            EX_LetBool,
            EX_LetObj,
            EX_LetWeakObjPtr,
            EX_LetValueOnPersistentFrame,
        )

        _ASSIGNMENT_TYPES = (
            EX_Let,
            EX_LetBool,
            EX_LetObj,
            EX_LetWeakObjPtr,
            EX_LetValueOnPersistentFrame,
        )
    return _ASSIGNMENT_TYPES


def _is_assignment(expr: object) -> bool:
    """Check whether the expression is an assignment type."""
    return isinstance(expr, _get_assignment_types())


class JumpAnalyzer:
    """Jump instruction pre-scanner providing offset lookup and control flow pattern detection.

    On initialization, all expressions are pre-scanned to build the following mappings:
    - offset_to_index: byte offset -> expression list index
    - jump_sources: jump target offset -> list of source indices

    Supported control flow patterns:
    - if / if_else: EX_JumpIfNot conditional branches
    - while: EX_JumpIfNot + backward EX_Jump
    - for: while + assignment increment expression
    - switch/case: EX_SwitchValue multi-branch selection

    All detection methods return None when no pattern matches, without raising exceptions.
    """

    def __init__(self, expressions: list[KismetExpression]) -> None:
        self._expressions = expressions
        self._offset_to_index: dict[int, int] = {}
        self._jump_targets: set[int] = set()
        self._jump_sources: dict[int, list[int]] = {}
        self._structured_indices: set[int] = set()
        self._backjump_indices: set[int] = set()
        self._analyze()

    def _analyze(self) -> None:
        """Pre-scan all expressions to build offset and jump source mappings."""
        for idx, expr in enumerate(self._expressions):
            # Expression position (StatementIndex) -> index
            stmt_idx = getattr(expr, "StatementIndex", None)
            if stmt_idx is not None:
                self._offset_to_index[stmt_idx] = idx

            # EX_Jump / EX_JumpIfNot target offset
            code_offset = getattr(expr, "CodeOffset", None)
            if code_offset is not None:
                self._jump_targets.add(code_offset)
                self._jump_sources.setdefault(code_offset, []).append(idx)

    def find_label_index(self, offset: int) -> int | None:
        """Find the expression index for a given byte offset.

        Args:
            offset: Target byte offset (typically EX_Jump/EX_JumpIfNot CodeOffset).

        Returns:
            The corresponding expression list index, or None if not found.
        """
        return self._offset_to_index.get(offset)

    # ================================================================
    # Unified pattern detection entry point
    # ================================================================

    def detect_pattern(self, start_idx: int) -> dict | None:
        """Unified pattern detection entry point. Tries all control flow patterns by priority.

        Priority order:
        1. for (while + increment expression)
        2. while (condition + backward jump)
        3. push_pop (Push/Pop + JumpIfNot, precise if/else marker)
        4. if_else / if (conditional branch)
        5. switch/case (EX_SwitchValue)

        Args:
            start_idx: Starting expression index.

        Returns:
            Pattern detection result dictionary, or None if no match.
        """
        result = self.detect_for_pattern(start_idx)
        if result is not None:
            return result
        result = self.detect_while_pattern(start_idx)
        if result is not None:
            return result
        result = self.detect_push_pop_pattern(start_idx)
        if result is not None:
            return result
        result = self.detect_if_else_pattern(start_idx)
        if result is not None:
            return result
        result = self.detect_switch_pattern(start_idx)
        if result is not None:
            return result
        return None

    # ================================================================
    # if / if_else detection
    # ================================================================

    def detect_if_else_pattern(self, start_idx: int) -> dict | None:
        """Detect if/else control flow patterns.

        Pattern characteristics:
        - start_idx is EX_JumpIfNot
        - Search the then branch for EX_Jump (jumping to end_label)
        - Found -> if/else pattern; not found -> simple if pattern

        Returns:
            {
                "type": "if_else" | "if",
                "start": start_idx,
                "condition": BooleanExpression,
                "then_start": int,
                "then_end": int,       # if/else only
                "else_start": int,     # if/else only
                "else_end": int,       # if/else only
                "end_label": int,      # if/else only
            }
            None if no match.
        """
        from uasset_read.kismet.expressions.control_flow import EX_JumpIfNot, EX_Jump

        if start_idx < 0 or start_idx >= len(self._expressions):
            return None

        expr = self._expressions[start_idx]
        if not isinstance(expr, EX_JumpIfNot):
            return None

        condition = expr.BooleanExpression
        false_label = expr.CodeOffset

        # Find the expression index for false_label
        false_label_idx = self.find_label_index(false_label)
        if false_label_idx is None:
            return None

        # Search the then branch for EX_Jump (jumping to end_label)
        # The then branch starts at start_idx+1 and ends before false_label_idx
        for j in range(start_idx + 1, false_label_idx):
            jmp = self._expressions[j]
            if isinstance(jmp, EX_Jump):
                end_label = jmp.CodeOffset
                end_label_idx = self.find_label_index(end_label)
                if end_label_idx is not None and end_label_idx >= false_label_idx:
                    return {
                        "type": "if_else",
                        "start": start_idx,
                        "condition": condition,
                        "then_start": start_idx + 1,
                        "then_end": j,
                        "else_start": false_label_idx,
                        "else_end": end_label_idx,
                        "end_label": end_label,
                    }

        # No EX_Jump found; treat as a simple if pattern
        return {
            "type": "if",
            "start": start_idx,
            "condition": condition,
            "then_start": start_idx + 1,
            "then_end": false_label_idx - 1,
        }

    # ================================================================
    # Push/Pop if/else detection
    # ================================================================

    def detect_push_pop_pattern(self, start_idx: int) -> dict | None:
        """Detect Push/Pop marked if/else control flow patterns.

        In UE Blueprints, if/else compiles to:
        - EX_PushExecutionFlow (save return address)
        - EX_JumpIfNot (skip then branch when condition is false)
        - then branch code
        - EX_PopExecutionFlow (end of then branch)
        - else branch code
        - PushingAddress target (merge point)

        Difference from JumpIfNot detection: Push/Pop uses explicit stack operations
        to mark branch boundaries, making it a precise compilation artifact of if/else
        that is more reliable to detect.

        Returns:
            {
                "type": "push_pop",
                "start": start_idx,
                "condition": BooleanExpression,
                "then_start": int,
                "then_end": int,
                "else_start": int,
                "else_end": int,
                "pushing_address": int,
            }
            None if no match.
        """
        from uasset_read.kismet.expressions.control_flow import (
            EX_PushExecutionFlow,
            EX_JumpIfNot,
            EX_PopExecutionFlow,
            EX_EndOfScript,
        )

        if start_idx < 0 or start_idx >= len(self._expressions):
            return None

        expr = self._expressions[start_idx]
        if not isinstance(expr, EX_PushExecutionFlow):
            return None

        pushing_address = expr.PushingAddress

        # Scan subsequent instructions (up to 3) for JumpIfNot
        jump_if_not_idx = None
        for k in range(start_idx + 1, min(start_idx + 4, len(self._expressions))):
            if isinstance(self._expressions[k], EX_JumpIfNot):
                jump_if_not_idx = k
                break
            if isinstance(
                self._expressions[k],
                (
                    EX_PushExecutionFlow,
                    EX_EndOfScript,
                ),
            ):
                break

        if jump_if_not_idx is None:
            return None

        jump_if_not = self._expressions[jump_if_not_idx]
        condition = jump_if_not.BooleanExpression

        # Search for PopExecutionFlow after JumpIfNot
        pop_idx = None
        for j in range(jump_if_not_idx + 1, len(self._expressions)):
            if isinstance(self._expressions[j], EX_PopExecutionFlow):
                pop_idx = j
                break
            if isinstance(
                self._expressions[j],
                (
                    EX_PushExecutionFlow,
                    EX_EndOfScript,
                ),
            ):
                break

        if pop_idx is None:
            return None

        # Find the expression index for pushing_address (else block end)
        else_end_idx = self.find_label_index(pushing_address)
        if else_end_idx is None:
            # When pushing_address cannot be mapped, use the end of else block
            else_end_idx = pop_idx

        return {
            "type": "push_pop",
            "start": start_idx,
            "condition": condition,
            "then_start": jump_if_not_idx + 1,
            "then_end": pop_idx,
            "else_start": pop_idx + 1,
            "else_end": else_end_idx,
            "pushing_address": pushing_address,
        }

    # ================================================================
    # while detection
    # ================================================================

    def detect_while_pattern(self, start_idx: int) -> dict | None:
        """Detect while loop control flow patterns.

        Pattern characteristics:
        - start_idx is EX_JumpIfNot with CodeOffset pointing to the loop exit
        - The loop body contains an EX_Jump with target offset <= start_idx offset (backward jump)

        Returns:
            {
                "type": "while",
                "start": start_idx,
                "condition": BooleanExpression,
                "body_start": int,
                "body_end": int,       # index of backward EX_Jump
                "exit_label": int,     # loop exit offset
            }
            None if no match.
        """
        from uasset_read.kismet.expressions.control_flow import EX_JumpIfNot, EX_Jump

        if start_idx < 0 or start_idx >= len(self._expressions):
            return None

        expr = self._expressions[start_idx]
        if not isinstance(expr, EX_JumpIfNot):
            return None

        condition = expr.BooleanExpression
        exit_label = expr.CodeOffset

        # Get the offset of the start_idx expression, used to determine the backward jump target
        start_offset = getattr(expr, "StatementIndex", None)
        if start_offset is None:
            return None

        # Search for backward EX_Jump within the loop body
        for j in range(start_idx + 1, len(self._expressions)):
            jmp = self._expressions[j]
            if isinstance(jmp, EX_Jump):
                target_offset = jmp.CodeOffset
                # Backward jump target must be at or before start_idx
                target_idx = self.find_label_index(target_offset)
                if target_idx is not None and target_idx <= start_idx:
                    return {
                        "type": "while",
                        "start": start_idx,
                        "condition": condition,
                        "body_start": start_idx + 1,
                        "body_end": j,
                        "exit_label": exit_label,
                    }

        return None

    # ================================================================
    # for loop detection
    # ================================================================

    def detect_for_pattern(self, start_idx: int) -> dict | None:
        """Detect for-loop control flow patterns.

        In UE Blueprints, for-loops compile to:
        - Condition check (JumpIfNot -> exit)
        - Loop body (function calls, etc.)
        - Increment expression (assignment statement)
        - Backward jump to condition check (EX_Jump)

        Detection strategy:
        1. First match the while pattern (JumpIfNot + backward jump)
        2. Scan backward from the jump position to identify assignment increment expressions
        3. Separate the increment region from the loop body

        Returns:
            {
                "type": "for",
                "start": int,
                "condition": BooleanExpression,
                "body_start": int,
                "body_end": int,
                "increment_start": int,  # increment expression start index
                "increment_end": int,    # increment expression end index (before backward jump)
                "exit_label": int,
            }
            None if no match.
        """
        while_result = self.detect_while_pattern(start_idx)
        if while_result is None:
            return None

        body_start = while_result["body_start"]
        body_end = while_result["body_end"]

        # Need at least body_start < body_end (loop body content exists)
        if body_end <= body_start:
            return None

        # Scan backward from the position before the backward EX_Jump for assignment increment expressions
        inc_end = body_end - 1
        inc_start = inc_end

        # Consecutive assignment expressions form the increment region
        while inc_start > body_start and _is_assignment(self._expressions[inc_start - 1]):
            inc_start -= 1

        # No assignment expression found at inc_start; does not match for-loop pattern
        if not _is_assignment(self._expressions[inc_start]):
            return None

        # Ensure the loop body has actual content before the increment
        if inc_start <= body_start:
            # Increment starts at body_start -> entire loop body is increment, not a for-loop
            return None

        return {
            "type": "for",
            "start": while_result["start"],
            "condition": while_result["condition"],
            "body_start": body_start,
            "body_end": body_end,
            "increment_start": inc_start,
            "increment_end": inc_end,
            "exit_label": while_result["exit_label"],
        }

    # ================================================================
    # switch/case detection
    # ================================================================

    def detect_switch_pattern(self, start_idx: int) -> dict | None:
        """Detect switch/case control flow patterns.

        In UE Blueprints, switch statements compile to EX_SwitchValue expressions, which contain:
        - IndexTerm: switch expression
        - Cases: case list (each with CaseIndexValueTerm + CaseTerm)
        - DefaultTerm: default branch expression

        Returns:
            {
                "type": "switch",
                "start": start_idx,
                "index_term": KismetExpression,
                "cases": [{"index_term": expr, "case_term": expr}, ...],
                "default_term": KismetExpression | None,
                "end_offset": int,
            }
            None if no match.
        """
        from uasset_read.kismet.expressions.special import EX_SwitchValue

        if start_idx < 0 or start_idx >= len(self._expressions):
            return None

        expr = self._expressions[start_idx]
        if not isinstance(expr, EX_SwitchValue):
            return None

        cases = []
        if expr.Cases:
            for case_item in expr.Cases:
                cases.append(
                    {
                        "index_term": case_item.CaseIndexValueTerm,
                        "case_term": case_item.CaseTerm,
                    }
                )

        return {
            "type": "switch",
            "start": start_idx,
            "index_term": expr.IndexTerm,
            "cases": cases,
            "default_term": expr.DefaultTerm,
            "end_offset": expr.EndGotoOffset,
        }

    # ================================================================
    # Backward jump / structured index queries
    # ================================================================

    def is_while_backjump(self, idx: int) -> bool:
        """Check whether the given index is a backward EX_Jump of a while/for loop.

        Uses lazy initialization cache; scans all JumpIfNot-started while patterns on first call.

        Args:
            idx: Expression index to check.

        Returns:
            True if idx is a backward jump instruction of a while/for loop.
        """
        if not self._backjump_indices:
            self._build_backjump_cache()
        return idx in self._backjump_indices

    def _build_backjump_cache(self) -> None:
        """Build backward jump index cache (lazy initialization).

        Optimization: built in a single scan to avoid calling detect_while_pattern
        for every JumpIfNot (O(n^2)).
        Strategy: scan all EX_Jumps, find those whose backward jump target is before JumpIfNot.
        """
        from uasset_read.kismet.expressions.control_flow import EX_JumpIfNot, EX_Jump

        # Pre-compute JumpIfNot index set
        jump_if_not_indices: set[int] = set()
        for idx, expr in enumerate(self._expressions):
            if isinstance(expr, EX_JumpIfNot):
                jump_if_not_indices.add(idx)

        # Scan all EX_Jumps, find those with backward target before JumpIfNot
        for idx, expr in enumerate(self._expressions):
            if not isinstance(expr, EX_Jump):
                continue
            target_offset = expr.CodeOffset
            target_idx = self.find_label_index(target_offset)
            if target_idx is None:
                continue
            # Backward jump target must be at or before a JumpIfNot
            if target_idx in jump_if_not_indices:
                self._backjump_indices.add(idx)

    def get_structured_indices(self) -> set[int]:
        """Get the set of expression indices belonging to structured control flow blocks.

        Includes all indices within while/for loop bodies, if/else branches, and
        switch/case internals. Used by the translator to skip already-structured expressions.

        Returns:
            Set of structured indices.
        """
        if not self._structured_indices:
            self._build_structured_indices()
        return set(self._structured_indices)

    def _build_structured_indices(self) -> None:
        """Build structured index set (lazy initialization).

        Optimization: skip indices already marked as structured to avoid redundant detection.
        """
        from uasset_read.kismet.expressions.control_flow import (
            EX_JumpIfNot,
            EX_PushExecutionFlow,
        )
        from uasset_read.kismet.expressions.special import EX_SwitchValue

        skip_until = -1
        for idx in range(len(self._expressions)):
            # Skip indices already marked as structured
            if idx <= skip_until:
                continue

            expr = self._expressions[idx]

            # Pattern: EX_SwitchValue itself
            if isinstance(expr, EX_SwitchValue):
                self._structured_indices.add(idx)
                continue

            # Pattern: PushExecutionFlow start
            if isinstance(expr, EX_PushExecutionFlow):
                push_pop_result = self.detect_push_pop_pattern(idx)
                if push_pop_result is not None:
                    end = push_pop_result.get(
                        "else_end",
                        push_pop_result.get("then_end", push_pop_result["start"]),
                    )
                    for j in range(push_pop_result["start"], end + 1):
                        self._structured_indices.add(j)
                    skip_until = end
                    continue

            # JumpIfNot-started patterns
            if isinstance(expr, EX_JumpIfNot):
                # for > while > if_else > if (priority order)
                for_result = self.detect_for_pattern(idx)
                if for_result is not None:
                    for j in range(for_result["start"], for_result["body_end"] + 1):
                        self._structured_indices.add(j)
                    skip_until = for_result["body_end"]
                    continue

                while_result = self.detect_while_pattern(idx)
                if while_result is not None:
                    for j in range(while_result["start"], while_result["body_end"] + 1):
                        self._structured_indices.add(j)
                    skip_until = while_result["body_end"]
                    continue

                if_else_result = self.detect_if_else_pattern(idx)
                if if_else_result is not None:
                    end = if_else_result.get(
                        "else_end",
                        if_else_result.get("then_end", if_else_result["start"]),
                    )
                    for j in range(if_else_result["start"], end + 1):
                        self._structured_indices.add(j)
                    skip_until = end

    # ================================================================
    # Structured rate analysis
    # ================================================================

    def analyze_structured_rate(self) -> float:
        """Compute the structured control-flow rate: structured_count / total_jump_exprs.

        Returns 1.0 when there are no jump expressions.
        """
        from uasset_read.kismet.expressions.control_flow import (
            EX_Jump,
            EX_JumpIfNot,
            EX_ComputedJump,
        )
        from uasset_read.kismet.expressions.special import EX_SwitchValue

        jump_indices = [
            idx
            for idx, expr in enumerate(self._expressions)
            if isinstance(expr, (EX_Jump, EX_JumpIfNot, EX_ComputedJump, EX_SwitchValue))
        ]
        if not jump_indices:
            return 1.0

        jump_set = set(jump_indices)
        structured_set: set[int] = set()
        for idx in jump_indices:
            expr = self._expressions[idx]

            # switch pattern
            if isinstance(expr, EX_SwitchValue):
                structured_set.add(idx)
                continue

            # Skip while/for backward jumps (already covered by loop structures)
            if isinstance(expr, EX_Jump) and self.is_while_backjump(idx):
                structured_set.add(idx)
                continue

            # Try for > while > if_else > if
            pattern = self.detect_pattern(idx)
            if pattern is None:
                continue
            if pattern["type"] in ("for", "while"):
                end = pattern["body_end"]
            elif pattern["type"] in ("if_else", "if"):
                end = pattern.get("else_end", pattern.get("then_end", pattern["start"]))
            else:
                continue
            structured_set.update(j for j in range(pattern["start"], end + 1) if j in jump_set)

        return len(structured_set) / len(jump_indices)
