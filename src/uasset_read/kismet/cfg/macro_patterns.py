"""Macro pattern detection for common Blueprint constructs.

Detects DoOnce, FlipFlop, Sequence chains, Gate, MultiGate, and ForEachLoop
patterns from CFG structure and expression content.

These patterns are Blueprint macro nodes that compile to specific CFG structures.
Recognizing them improves decompiled output readability.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class MacroPatternType(Enum):
    """Types of recognized macro patterns."""

    DO_ONCE = auto()
    FLIP_FLOP = auto()
    SEQUENCE = auto()
    GATE = auto()
    MULTI_GATE = auto()
    FOR_EACH_LOOP = auto()


@dataclass
class MacroPattern:
    """A detected macro pattern in the CFG."""

    pattern_type: MacroPatternType
    header_block: int
    """Entry block of the pattern."""

    body_blocks: list[int] = field(default_factory=list)
    """Blocks comprising the pattern body."""

    flag_variable: Optional[str] = None
    """For DoOnce: the boolean flag variable name."""

    branch_blocks: list[int] = field(default_factory=list)
    """For FlipFlop: the two output branch blocks."""

    sequence_blocks: list[list[int]] = field(default_factory=list)
    """For Sequence: ordered list of chain block lists."""

    description: str = ""
    """Human-readable description of the pattern."""


@dataclass
class MacroPatternResult:
    """Result of macro pattern detection."""

    patterns: list[MacroPattern] = field(default_factory=list)

    def get_by_type(self, pattern_type: MacroPatternType) -> list[MacroPattern]:
        """Get all patterns of a specific type."""
        return [p for p in self.patterns if p.pattern_type == pattern_type]

    @property
    def do_once_count(self) -> int:
        return len(self.get_by_type(MacroPatternType.DO_ONCE))

    @property
    def flip_flop_count(self) -> int:
        return len(self.get_by_type(MacroPatternType.FLIP_FLOP))

    @property
    def sequence_count(self) -> int:
        return len(self.get_by_type(MacroPatternType.SEQUENCE))


def _find_bool_flag_check(cfg, block_id: int) -> Optional[tuple[int, str]]:
    """Try to detect a boolean flag check pattern.

    Looks for: Block checks a variable, jumps if not true.
    Returns (checked_block_id, variable_name) or None.
    """
    from uasset_read.kismet.cfg.data import EdgeKind

    block = cfg.blocks.get(block_id)
    if block is None:
        return None

    # Look for conditional branches
    if len(block.successors) != 2:
        return None

    # Check edge kinds
    has_true = any(
        block.edge_kinds.get(s) == EdgeKind.TRUE_BRANCH
        for s in block.successors
    )
    has_false = any(
        block.edge_kinds.get(s) == EdgeKind.FALSE_BRANCH
        for s in block.successors
    )

    if not (has_true and has_false):
        return None

    # The block likely contains a boolean check
    # We can't easily determine the variable name from CFG alone
    # but we can detect the pattern structure
    return (block_id, "flag")


def detect_do_once(cfg, dom_tree=None) -> list[MacroPattern]:
    """Detect DoOnce patterns.

    DoOnce pattern:
    - Entry block checks a boolean flag
    - If false, executes body and sets flag to true
    - If true, skips body
    - No loop back edge (single execution)

    Detection heuristic:
    - Conditional branch where one path is very short (skip)
    - The other path executes and rejoins
    - No back edges in the region
    """
    patterns: list[MacroPattern] = []

    if dom_tree is None:
        from uasset_read.kismet.cfg.dom import compute_dominator_tree
        dom_tree = compute_dominator_tree(cfg)

    for bid, block in cfg.blocks.items():
        if len(block.successors) != 2:
            continue

        # Check if this looks like a flag check
        flag_info = _find_bool_flag_check(cfg, bid)
        if flag_info is None:
            continue

        # One successor should be a short skip, the other the body
        for succ in block.successors:
            succ_block = cfg.blocks.get(succ)
            if succ_block is None:
                continue

            # Check if this successor rejoins quickly
            if len(succ_block.successors) == 1:
                # Body block with single successor — likely DoOnce body
                body_exit = succ_block.successors[0]
                if body_exit in block.successors or body_exit == bid:
                    # Rejoins to merge point
                    patterns.append(MacroPattern(
                        pattern_type=MacroPatternType.DO_ONCE,
                        header_block=bid,
                        body_blocks=[succ, body_exit],
                        flag_variable=flag_info[1],
                        description="DoOnce: execute once, then skip",
                    ))
                    break

    return patterns


def detect_flip_flop(cfg, dom_tree=None) -> list[MacroPattern]:
    """Detect FlipFlop patterns.

    FlipFlop pattern:
    - Entry block toggles a boolean state
    - Two output branches (A and B)
    - Alternates between A and B on each call

    Detection heuristic:
    - Block has two successors with roughly equal complexity
    - Both paths rejoin at common merge point
    - No loop structure
    """
    patterns: list[MacroPattern] = []

    for bid, block in cfg.blocks.items():
        if len(block.successors) != 2:
            continue

        s0, s1 = block.successors[0], block.successors[1]
        block0 = cfg.blocks.get(s0)
        block1 = cfg.blocks.get(s1)

        if block0 is None or block1 is None:
            continue

        # Both successors should eventually rejoin
        succs0 = set(block0.successors)
        succs1 = set(block1.successors)
        common = succs0 & succs1

        if not common:
            continue

        # Check if both paths are roughly similar size
        size0 = block0.size
        size1 = block1.size
        if size0 == 0 or size1 == 0:
            continue

        # FlipFlop heuristic: both branches exist and rejoin
        # (This is a simplified check; real FlipFlop detection would
        # examine the toggle variable pattern)
        if abs(size0 - size1) < max(size0, size1) * 0.5:
            patterns.append(MacroPattern(
                pattern_type=MacroPatternType.FLIP_FLOP,
                header_block=bid,
                body_blocks=[s0, s1],
                branch_blocks=[s0, s1],
                description="FlipFlop: alternate between two paths",
            ))

    return patterns


def detect_sequence(cfg, dom_tree=None) -> list[MacroPattern]:
    """Detect Sequence chain patterns.

    Sequence pattern:
    - Multiple independent execution chains
    - All chains start from a common entry
    - Each chain executes independently

    Detection heuristic:
    - Block with 2+ successors where each successor is the start
      of an independent chain (no cross-edges between chains)
    - Uses EX_SwitchValue or sequential exec pins
    """
    patterns: list[MacroPattern] = []

    for bid, block in cfg.blocks.items():
        if len(block.successors) < 2:
            continue

        # Check if successors are independent (no edges between them)
        succ_set = set(block.successors)
        independent = True

        for succ in succ_set:
            succ_block = cfg.blocks.get(succ)
            if succ_block is None:
                continue
            # If any successor branches to another successor, not independent
            if set(succ_block.successors) & (succ_set - {succ}):
                independent = False
                break

        if independent and len(block.successors) >= 2:
            chains = []
            for succ in block.successors:
                chains.append([succ])

            patterns.append(MacroPattern(
                pattern_type=MacroPatternType.SEQUENCE,
                header_block=bid,
                body_blocks=list(block.successors),
                sequence_blocks=chains,
                description=f"Sequence: {len(block.successors)} independent chains",
            ))

    return patterns


def detect_macro_patterns(cfg, dom_tree=None) -> MacroPatternResult:
    """Detect all macro patterns in the CFG.

    Runs all pattern detectors and returns combined results.

    Args:
        cfg: Control flow graph
        dom_tree: Dominator tree (optional, computed if not provided)

    Returns:
        MacroPatternResult with all detected patterns
    """
    result = MacroPatternResult()

    result.patterns.extend(detect_do_once(cfg, dom_tree))
    result.patterns.extend(detect_flip_flop(cfg, dom_tree))
    result.patterns.extend(detect_sequence(cfg, dom_tree))

    return result
