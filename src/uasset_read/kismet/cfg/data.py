"""CFG data structure definitions.

Defines core data structures: basic blocks, control flow graph, dominator tree, regions.
"""
from __future__ import annotations


from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression


class EdgeKind(Enum):
    """CFG edge types."""

    FALLTHROUGH = auto()  # fall-through to next (non-conditional)
    TRUE_BRANCH = auto()  # EX_JumpIfNot true path (fall-through when condition is TRUE)
    FALSE_BRANCH = auto()  # EX_JumpIfNot false path (jump target when condition is FALSE)
    UNCONDITIONAL = auto()  # unconditional jump
    BACK_EDGE = auto()  # back edge (loop)


@dataclass
class BasicBlock:
    """Control flow graph basic block.

    A basic block is a straight-line code sequence from entry to exit with no branches.
    """

    block_id: int  # unique identifier
    start_idx: int  # start expression index (inclusive)
    end_idx: int  # end expression index (inclusive, closed interval)
    expressions: list[KismetExpression] = field(default_factory=list)
    successors: list[int] = field(default_factory=list)  # successor block IDs
    predecessors: list[int] = field(default_factory=list)  # predecessor block IDs
    edge_kinds: dict[int, EdgeKind] = field(
        default_factory=dict
    )  # successor → edge type

    @property
    def label(self) -> str:
        """Block label, format BB0, BB1, ..."""
        return f"BB{self.block_id}"

    @property
    def size(self) -> int:
        """Number of expressions in block."""
        return self.end_idx - self.start_idx + 1

    def __repr__(self) -> str:
        return (
            f"BasicBlock(id={self.block_id}, "
            f"[{self.start_idx}..{self.end_idx}], "
            f"preds={self.predecessors}, succs={self.successors})"
        )

    def __hash__(self) -> int:
        return self.block_id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BasicBlock):
            return NotImplemented
        return self.block_id == other.block_id


@dataclass
class CFG:
    """Control Flow Graph.

    Composed of basic blocks and edges, contains entry block and synthetic sink block.
    """

    blocks: dict[int, BasicBlock] = field(default_factory=dict)
    entry_id: int = 0
    exit_id: int = -1  # synthetic sink block ID

    @property
    def entry(self) -> BasicBlock:
        """Entry block."""
        return self.blocks[self.entry_id]

    @property
    def exit(self) -> BasicBlock:
        """Synthetic sink block (target of all fall-throughs)."""
        return self.blocks[self.exit_id]

    @property
    def block_count(self) -> int:
        """Total number of basic blocks."""
        return len(self.blocks)

    @property
    def edge_count(self) -> int:
        """Total number of edges."""
        total = 0
        for block in self.blocks.values():
            total += len(block.successors)
        return total

    def ordered_blocks(self) -> list[BasicBlock]:
        """Return all basic blocks in ascending block_id order."""
        return [self.blocks[bid] for bid in sorted(self.blocks.keys())]

    def add_block(self, block: BasicBlock) -> None:
        """Add a basic block to the CFG."""
        self.blocks[block.block_id] = block

    def __repr__(self) -> str:
        return f"CFG(blocks={self.block_count}, edges={self.edge_count})"


class RegionKind(Enum):
    """Region types."""

    BLOCK = auto()  # straight-line sequence (no branches)
    IF_THEN = auto()  # if-then (single branch)
    IF_THEN_ELSE = auto()  # if-then-else (dual branches)
    WHILE_LOOP = auto()  # while loop (head has external predecessor)
    DO_WHILE = auto()  # do-while loop (head has no external predecessor)
    FOR_LOOP = auto()  # for loop (syntactic sugar, identified as while)
    SELF_LOOP = auto()  # self-loop (single-block cycle)
    IRREDUCIBLE = auto()  # irreducible region


@dataclass
class Region:
    """Control flow region (SESE interval).

    Each region has a unique head (entry block) and tail (exit block),
    satisfying the single-entry single-exit (SESE) property.
    """

    region_id: int
    kind: RegionKind
    head: int  # entry block ID
    tail: int  # exit block ID (unique exit of SESE)
    body_blocks: list[int] = field(default_factory=list)  # all blocks in region
    exit_blocks: list[int] = field(default_factory=list)  # region exit blocks
    children: list[int] = field(default_factory=list)  # child region IDs
    loop_back_edges: list[tuple[int, int]] = field(
        default_factory=list
    )  # back edges (src, dst)

    @property
    def block_count(self) -> int:
        """Number of blocks in the region."""
        return len(self.body_blocks)

    def __repr__(self) -> str:
        return (
            f"Region(id={self.region_id}, kind={self.kind.name}, "
            f"head=BB{self.head}, tail=BB{self.tail}, "
            f"blocks={self.block_count})"
        )


@dataclass
class RegionTree:
    """Region tree.

    Stores all regions and their hierarchical relationships.
    """

    regions: dict[int, Region] = field(default_factory=dict)
    root_id: int = -1

    @property
    def root(self) -> Region:
        """Root region."""
        return self.regions[self.root_id]

    def add_region(self, region: Region) -> None:
        """Add a region."""
        self.regions[region.region_id] = region

    def get_region(self, region_id: int) -> Region | None:
        """Get a region by ID."""
        return self.regions.get(region_id)

    def __repr__(self) -> str:
        return f"RegionTree(regions={len(self.regions)})"


@dataclass
class DominatorTree:
    """Dominator tree.

    Stores immediate dominators (idom) and full dominance relationships.
    """

    idom: dict[int, int | None] = field(default_factory=dict)
    dominators: dict[int, set[int]] = field(default_factory=dict)
    dominated: dict[int, set[int]] = field(default_factory=dict)
    _frontiers: dict[int, set[int]] = field(default_factory=dict)

    def is_dominator(self, dom_id: int, node_id: int) -> bool:
        """Check if dom_id dominates node_id."""
        if node_id not in self.dominators:
            return False
        return dom_id in self.dominators[node_id]

    def immediate_dominator(self, block_id: int) -> int | None:
        """Get the immediate dominator of block_id."""
        return self.idom.get(block_id)

    def dominator_frontier(self, block_id: int) -> set[int]:
        """Get the dominator frontier of block_id."""
        return self._frontiers.get(block_id, set())

    def __repr__(self) -> str:
        return f"DominatorTree(blocks={len(self.idom)})"
