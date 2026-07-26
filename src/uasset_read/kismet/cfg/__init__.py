"""CFG (Control Flow Graph) infrastructure.

Provides basic block construction, dominator tree computation, region decomposition, and structured statement output.
"""

from uasset_read.kismet.cfg.build import build_cfg
from uasset_read.kismet.cfg.data import (
    BasicBlock,
    CFG,
    DominatorTree,
    EdgeKind,
    Region,
    RegionKind,
    RegionTree,
)
from uasset_read.kismet.cfg.dom import compute_dominator_tree
from uasset_read.kismet.cfg.emitter import RegionDecoder, StmtEmitter
from uasset_read.kismet.cfg.region import (
    compute_loop_blocks,
    decompose_regions,
    find_back_edges,
)
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

__all__ = [
    "Assignment",
    "BasicBlock",
    "Branch",
    "CFG",
    "Call",
    "DominatorTree",
    "EdgeKind",
    "GotoLabel",
    "Loop",
    "Region",
    "RegionDecoder",
    "RegionKind",
    "RegionTree",
    "Return",
    "Sequence",
    "Stmt",
    "StmtEmitter",
    "Switch",
    "build_cfg",
    "compute_dominator_tree",
    "compute_loop_blocks",
    "decompose_regions",
    "find_back_edges",
]
