"""CFG (Control Flow Graph) 基础设施。

提供基本块构建、支配树计算、区域分解、结构化语句输出功能。
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
