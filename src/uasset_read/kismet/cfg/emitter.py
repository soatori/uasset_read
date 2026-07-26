from __future__ import annotations

"""CFG structured pseudocode emitter.

Decodes CFG region structure from RegionTree, generates structured statement tree,
then renders to pseudocode.
Algorithm:
1. DFS traverse RegionTree, call corresponding emit function per RegionKind
2. emit_body() recursively renders Stmt tree with indentation management
"""


import logging
from typing import TYPE_CHECKING

from uasset_read.kismet.cfg.data import BasicBlock, CFG, EdgeKind, Region, RegionKind, RegionTree
from uasset_read.kismet.cfg.stmt import (
    Assignment,
    Branch,
    Call,
    GotoLabel,
    Loop,
    Return,
    Sequence,
    Stmt,
    Switch,
)

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression
    from uasset_read.kismet.translator import KismetTranslator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Region decoder
# ---------------------------------------------------------------------------

class RegionDecoder:
    """DFS traverse RegionTree, decompose regions into structured statement tree.

    Call corresponding emit method for each RegionKind, generating Stmt nodes.
    """

    def __init__(
        self,
        cfg: CFG,
        region_tree: RegionTree,
        expressions: list[KismetExpression],
        translator: KismetTranslator,
        offset_to_index: dict[int, int],
        jump_targets: set[int],
    ) -> None:
        self.cfg = cfg
        self.region_tree = region_tree
        self.expressions = expressions
        self.translator = translator
        self.offset_to_index = offset_to_index
        self.jump_targets = jump_targets
        self._decoded_regions: set[int] = set()  # decoded region IDs, prevent recursion

    # ------------------------------------------------------------------
    # Public entry
    # ------------------------------------------------------------------

    def decode(self) -> Stmt:
        """Decode starting from root region, return full statement tree."""
        self._decoded_regions.clear()
        root = self.region_tree.root
        if root is None:
            return Sequence()
        return self._decode_region(root)

    # ------------------------------------------------------------------
    # Dispatch by RegionKind
    # ------------------------------------------------------------------

    def _decode_region(self, region: Region) -> Stmt:
        """Decode a single region."""
        if region.region_id in self._decoded_regions:
            # Already decoded, fallback to basic block output
            return self._emit_block(region)
        self._decoded_regions.add(region.region_id)
        kind = region.kind

        if kind == RegionKind.BLOCK:
            return self._emit_block(region)
        elif kind == RegionKind.IF_THEN:
            return self._emit_if_then(region)
        elif kind == RegionKind.IF_THEN_ELSE:
            return self._emit_if_then_else(region)
        elif kind in (RegionKind.WHILE_LOOP, RegionKind.DO_WHILE):
            return self._emit_loop(region, kind)
        elif kind == RegionKind.FOR_LOOP:
            return self._emit_loop(region, kind)
        elif kind == RegionKind.SELF_LOOP:
            return self._emit_self_loop(region)
        elif kind == RegionKind.IRREDUCIBLE:
            return self._emit_block(region)
        else:
            return self._emit_block(region)

    # ------------------------------------------------------------------
    # BLOCK: straight-line sequence
    # ------------------------------------------------------------------

    def _emit_block(self, region: Region) -> Sequence:
        """Emit BLOCK region (straight-line sequence)."""
        stmts: list[Stmt] = []
        for bid in region.body_blocks:
            block = self.cfg.blocks.get(bid)
            if block is None:
                continue
            stmts.extend(self._emit_basic_block(block))
        return Sequence(stmts=stmts)

    def _emit_basic_block(self, block: BasicBlock) -> list[Stmt]:
        """Emit statements for a single basic block."""
        stmts: list[Stmt] = []
        for idx in range(block.start_idx, block.end_idx + 1):
            if idx >= len(self.expressions):
                continue
            expr = self.expressions[idx]
            cpp_line = self.translator.line_cpp(expr, index=idx)
            if not cpp_line or not cpp_line.strip():
                continue
            stripped = cpp_line.strip()
            stmts.append(self._line_to_stmt(stripped))
        return stmts

    def _line_to_stmt(self, line: str) -> Stmt:
        """Convert a single line of C++ pseudocode to Stmt."""
        # Jump label
        if line.startswith("Label_"):
            return GotoLabel(label=line)
        # Assignment detection: contains = but doesn't start with if/for/while/switch,
        # and LHS has no parentheses (excludes named parameter function calls like FRotator(Pitch=90))
        if (
            "=" in line
            and not line.startswith("if ")
            and not line.startswith("for ")
            and not line.startswith("while ")
            and not line.startswith("switch ")
            and not line.startswith("else")
        ):
            parts = line.split("=", 1)
            lhs = parts[0].strip()
            rhs = parts[1].strip().rstrip(";")
            if lhs and rhs and "(" not in lhs:
                return Assignment(lhs=lhs, rhs=rhs)
        # return
        if line.startswith("return"):
            value = line.removeprefix("return").strip().rstrip(";")
            return Return(value=value)
        # Others as call or statement
        return Call(text=line)

    # ------------------------------------------------------------------
    # IF_THEN: single branch
    # ------------------------------------------------------------------

    def _emit_if_then(self, region: Region) -> Branch:
        """Emit IF_THEN region."""
        condition = self._get_head_condition(region)
        then_body = self._emit_body_for_blocks(region, region.body_blocks)
        return Branch(condition=condition, then_body=then_body, else_body=None)

    # ------------------------------------------------------------------
    # IF_THEN_ELSE: dual branches
    # ------------------------------------------------------------------

    def _emit_if_then_else(self, region: Region) -> Branch:
        """Emit IF_THEN_ELSE region."""
        condition = self._get_head_condition(region)

        # Distinguish then/else branch blocks
        head = region.head
        then_blocks: list[int] = []
        else_blocks: list[int] = []

        block = self.cfg.blocks.get(head)
        if block is not None and len(block.successors) >= 2:
            # Distinguish then/else by edge type
            for succ in block.successors:
                kind = block.edge_kinds.get(succ)
                if kind == EdgeKind.TRUE_BRANCH:
                    # TRUE_BRANCH → then branch (fall-through when condition is TRUE)
                    then_blocks.append(succ)
                elif kind == EdgeKind.FALSE_BRANCH:
                    # FALSE_BRANCH → else branch (jump target when condition is FALSE)
                    else_blocks.append(succ)
                else:
                    then_blocks.append(succ)
        else:
            # Fallback: determine branch membership based on dominance and region tail block.
            # Use CFG dominator tree info to assign region body blocks to corresponding branches.
            body = [b for b in region.body_blocks if b != head]
            if len(body) == 1:
                # Single block: all go to then
                then_blocks = body
            elif len(body) >= 2:
                # Trace back from tail block, assign reachable blocks to else branch
                tail = region.tail
                visited: set[int] = set()
                worklist = [tail]
                while worklist:
                    bid = worklist.pop()
                    if bid in visited or bid == head:
                        continue
                    visited.add(bid)
                    blk = self.cfg.blocks.get(bid)
                    if blk:
                        for pred in blk.predecessors:
                            if pred not in visited and pred != head:
                                worklist.append(pred)
                # else branch = region body blocks reachable from tail (excluding head)
                else_blocks = [b for b in body if b in visited]
                # then branch = remaining body blocks
                then_blocks = [b for b in body if b not in visited]
                # If else is empty (tail unreachable), assign second half to else
                if not else_blocks and body:
                    mid = len(body) // 2
                    then_blocks = body[:mid] if mid > 0 else body
                    else_blocks = body[mid:]
            # If body is empty, keep empty list

        then_body = self._emit_body_for_blocks(region, then_blocks)
        else_body = self._emit_body_for_blocks(region, else_blocks)
        return Branch(condition=condition, then_body=then_body, else_body=else_body)

    # ------------------------------------------------------------------
    # LOOP
    # ------------------------------------------------------------------

    def _emit_loop(self, region: Region, kind: RegionKind) -> Loop:
        """Emit loop region."""
        condition = self._get_head_condition(region)
        body_blocks = [b for b in region.body_blocks if b != region.head]
        if not body_blocks:
            body_blocks = region.body_blocks
        body = self._emit_body_for_blocks(region, body_blocks)

        if kind == RegionKind.DO_WHILE:
            loop_kind = "do_while"
        elif kind == RegionKind.FOR_LOOP:
            loop_kind = "for"
        else:
            loop_kind = "while"

        return Loop(kind=loop_kind, condition=condition, body=body)

    # ------------------------------------------------------------------
    # SELF_LOOP: single-block self-loop
    # ------------------------------------------------------------------

    def _emit_self_loop(self, region: Region) -> Loop:
        """Emit self-loop region."""
        condition = self._get_head_condition(region)
        stmts = self._emit_basic_block_for_region(region, region.head)
        body = Sequence(stmts=stmts) if stmts else Sequence(stmts=[])
        return Loop(kind="while", condition=condition, body=body)

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _get_head_condition(self, region: Region) -> str:
        """Get the condition expression of the region head block."""
        block = self.cfg.blocks.get(region.head)
        if block is None:
            return "true"
        for idx in range(block.start_idx, block.end_idx + 1):
            if idx >= len(self.expressions):
                continue
            expr = self.expressions[idx]
            if hasattr(expr, "CodeOffset"):
                cpp_line = self.translator.line_cpp(expr, index=idx)
                if cpp_line and cpp_line.strip():
                    line = cpp_line.strip()
                    # Strip trailing semicolon
                    line = line.rstrip(";")
                    return line
        return "true"

    def _emit_body_for_blocks(
        self, region: Region, block_ids: list[int]
    ) -> Sequence:
        """Emit statement sequence for a given set of blocks."""
        stmts: list[Stmt] = []
        for bid in block_ids:
            if bid == self.cfg.exit_id:
                continue
            block = self.cfg.blocks.get(bid)
            if block is None:
                continue
            # Recursively decode child regions
            child_region = self._find_child_region(bid)
            if child_region is not None:
                stmts.append(self._decode_region(child_region))
            else:
                stmts.extend(self._emit_basic_block(block))
        return Sequence(stmts=stmts)

    def _emit_basic_block_for_region(
        self, region: Region, bid: int
    ) -> list[Stmt]:
        """Emit statements for a given block."""
        block = self.cfg.blocks.get(bid)
        if block is None:
            return []
        return self._emit_basic_block(block)

    def _find_child_region(self, block_id: int) -> Region | None:
        """Find the undecoded child region containing the given block (prefer more precise regions)."""
        best: Region | None = None
        for region in self.region_tree.regions.values():
            if region.region_id in self._decoded_regions:
                continue
            if block_id in region.body_blocks and region.block_count > 1:
                if best is None or region.block_count < best.block_count:
                    best = region
        return best


# ---------------------------------------------------------------------------
# Pseudocode emitter
# ---------------------------------------------------------------------------

class StmtEmitter:
    """Recursively render Stmt tree as indented pseudocode."""

    def __init__(self, indent: str = "    ") -> None:
        self._indent = indent

    def emit_body(self, stmt: Stmt) -> str:
        """Render Stmt tree as indented pseudocode string."""
        return self._emit(stmt, depth=0)

    def emit_lines(self, stmt: Stmt) -> list[str]:
        """Render Stmt tree as list of lines."""
        text = self.emit_body(stmt)
        return text.split("\n") if text else []

    # ------------------------------------------------------------------
    # Recursive rendering
    # ------------------------------------------------------------------

    def _emit(self, stmt: Stmt, depth: int) -> str:
        """Recursively render a single statement."""
        prefix = self._indent * depth

        if isinstance(stmt, Sequence):
            return self._emit_sequence(stmt, depth)
        elif isinstance(stmt, Branch):
            return self._emit_branch(stmt, depth)
        elif isinstance(stmt, Loop):
            return self._emit_loop(stmt, depth)
        elif isinstance(stmt, Switch):
            return self._emit_switch(stmt, depth)
        elif isinstance(stmt, Assignment):
            return f"{prefix}{stmt.lhs} = {stmt.rhs};"
        elif isinstance(stmt, Call):
            text = stmt.text.rstrip(";")
            return f"{prefix}{text};"
        elif isinstance(stmt, Return):
            if stmt.value:
                return f"{prefix}return {stmt.value};"
            return f"{prefix}return;"
        elif isinstance(stmt, GotoLabel):
            return f"{prefix}{stmt.label}:"
        else:
            return f"{prefix}/* unknown stmt: {type(stmt).__name__} */"

    def _emit_sequence(self, seq: Sequence, depth: int) -> str:
        """Render statement sequence."""
        lines: list[str] = []
        for s in seq.stmts:
            rendered = self._emit(s, depth)
            if rendered:
                lines.append(rendered)
        return "\n".join(lines)

    def _emit_branch(self, branch: Branch, depth: int) -> str:
        """Render if/else branch."""
        prefix = self._indent * depth
        cond = branch.condition.rstrip(";")
        lines: list[str] = []

        lines.append(f"{prefix}if ({cond}) {{")
        if branch.then_body is not None:
            body_text = self._emit(branch.then_body, depth + 1)
            if body_text:
                lines.append(body_text)
        lines.append(f"{prefix}}}")

        if branch.else_body is not None:
            lines.append(f"{prefix}else {{")
            body_text = self._emit(branch.else_body, depth + 1)
            if body_text:
                lines.append(body_text)
            lines.append(f"{prefix}}}")

        return "\n".join(lines)

    def _emit_loop(self, loop: Loop, depth: int) -> str:
        """Render loop statement."""
        prefix = self._indent * depth
        cond = loop.condition.rstrip(";")
        lines: list[str] = []

        if loop.kind == "do_while":
            lines.append(f"{prefix}do {{")
            if loop.body is not None:
                body_text = self._emit(loop.body, depth + 1)
                if body_text:
                    lines.append(body_text)
            lines.append(f"{prefix}}} while ({cond});")
        elif loop.kind == "for":
            lines.append(f"{prefix}for (;;) {{")
            if loop.body is not None:
                body_text = self._emit(loop.body, depth + 1)
                if body_text:
                    lines.append(body_text)
            lines.append(f"{prefix}}}")
        else:
            # while
            lines.append(f"{prefix}while ({cond}) {{")
            if loop.body is not None:
                body_text = self._emit(loop.body, depth + 1)
                if body_text:
                    lines.append(body_text)
            lines.append(f"{prefix}}}")

        return "\n".join(lines)

    def _emit_switch(self, switch: Switch, depth: int) -> str:
        """Render switch/case statement."""
        prefix = self._indent * depth
        expr = switch.expression.rstrip(";")
        lines: list[str] = []

        lines.append(f"{prefix}switch ({expr}) {{")
        for case_val, case_body in switch.cases:
            lines.append(f"{prefix}    case {case_val}: {{")
            body_text = self._emit(case_body, depth + 2)
            if body_text:
                lines.append(body_text)
            lines.append(f"{prefix}        break;")
            lines.append(f"{prefix}    }}")
        if switch.default_body is not None:
            lines.append(f"{prefix}    default: {{")
            body_text = self._emit(switch.default_body, depth + 2)
            if body_text:
                lines.append(body_text)
            lines.append(f"{prefix}    }}")
        lines.append(f"{prefix}}}")

        return "\n".join(lines)


__all__ = ["RegionDecoder", "StmtEmitter"]
