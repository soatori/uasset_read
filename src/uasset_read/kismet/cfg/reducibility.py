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



