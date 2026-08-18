"""CFG reducibility analysis.

Determines if a control flow graph is reducible (all back edges target
dominators) or irreducible (has cross edges that cannot be structured).

A reducible CFG can be decomposed into nested structured regions (if-then,
while, do-while). An irreducible CFG requires special handling.

Reference: "Compilers: Principles, Techniques, and Tools" (Aho et al.)
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BackEdge:
    """A back edge in the CFG (source -> destination where destination dominates source)."""

    source: int
    """Source block ID (inside loop body)."""

    destination: int
    """Destination block ID (loop header, dominates source)."""


@dataclass
class LoopInfo:
    """Information about a natural loop."""

    header: int
    """Loop header block ID."""

    back_edges: list[BackEdge] = field(default_factory=list)
    """Back edges targeting this header."""

    body: set[int] = field(default_factory=set)
    """Set of block IDs in the loop body."""

    @property
    def is_single_back_edge(self) -> bool:
        """True if loop has exactly one back edge."""
        return len(self.back_edges) == 1


@dataclass
class ReducibilityResult:
    """Result of reducibility analysis."""

    is_reducible: bool
    """True if the CFG is reducible."""

    back_edges: list[BackEdge] = field(default_factory=list)
    """All back edges in the CFG."""

    loops: dict[int, LoopInfo] = field(default_factory=dict)
    """Loop information keyed by header block ID."""

    cross_edges: list[tuple[int, int]] = field(default_factory=list)
    """Cross edges (non-back, non-tree edges) — present only in irreducible CFGs."""

    @property
    def loop_count(self) -> int:
        """Number of natural loops."""
        return len(self.loops)

    def get_loop(self, header: int) -> Optional[LoopInfo]:
        """Get loop info for a given header."""
        return self.loops.get(header)


def compute_reducibility(cfg, dom_tree=None) -> ReducibilityResult:
    """Analyze CFG reducibility.

    A CFG is reducible if and only if every back edge's destination
    dominates its source. If any back edge violates this, the CFG
    is irreducible.

    Args:
        cfg: Control flow graph (CFG instance)
        dom_tree: Dominator tree (optional, will compute if not provided)

    Returns:
        ReducibilityResult with analysis results
    """
    if dom_tree is None:
        from uasset_read.kismet.cfg.dom import compute_dominator_tree
        dom_tree = compute_dominator_tree(cfg)

    # Find all back edges: (src, dst) where dst dominates src
    back_edges: list[BackEdge] = []
    cross_edges: list[tuple[int, int]] = []

    for bid, block in cfg.blocks.items():
        for succ in block.successors:
            if succ not in cfg.blocks:
                continue
            if succ == bid:
                # Self-loop
                back_edges.append(BackEdge(source=bid, destination=succ))
            elif dom_tree.is_dominator(succ, bid):
                # Back edge: successor dominates this block
                back_edges.append(BackEdge(source=bid, destination=succ))
            elif not dom_tree.is_dominator(bid, succ):
                # Cross edge: neither dominates the other
                cross_edges.append((bid, succ))

    # Check reducibility: all back edges must target dominators
    is_reducible = True
    for be in back_edges:
        if not dom_tree.is_dominator(be.destination, be.source):
            is_reducible = False
            break

    # Also irreducible if there are cross edges in an irreducible graph
    if cross_edges:
        is_reducible = False

    # Build loop info
    loops: dict[int, LoopInfo] = {}
    for be in back_edges:
        if be.destination not in loops:
            loops[be.destination] = LoopInfo(header=be.destination)
        loops[be.destination].back_edges.append(be)

    # Compute loop bodies
    for header, loop_info in loops.items():
        body: set[int] = {header}
        worklist = [be.source for be in loop_info.back_edges]

        while worklist:
            bid = worklist.pop()
            if bid in body:
                continue
            body.add(bid)
            block = cfg.blocks.get(bid)
            if block is None:
                continue
            for pred in block.predecessors:
                if pred not in body:
                    worklist.append(pred)

        loop_info.body = body

    return ReducibilityResult(
        is_reducible=is_reducible,
        back_edges=back_edges,
        loops=loops,
        cross_edges=cross_edges,
    )
