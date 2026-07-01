"""CFG 数据结构定义。

定义基本块、控制流图、支配树、区域等核心数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression


class EdgeKind(Enum):
    """CFG 边类型。"""

    FALLTHROUGH = auto()  # fall-through 到下一条
    CONDITIONAL = auto()  # 条件为真（JumpIfNot 的 false 分支目标）
    FALSE_BRANCH = auto()  # 条件跳转的 fall-through（true 分支）
    UNCONDITIONAL = auto()  # 无条件跳转
    BACK_EDGE = auto()  # 回边（循环）


@dataclass
class BasicBlock:
    """控制流图基本块。

    基本块是从入口到出口的直线代码序列，内部无分支。
    """

    block_id: int  # 唯一标识
    start_idx: int  # 起始表达式索引（含）
    end_idx: int  # 结束表达式索引（含，闭区间）
    expressions: list[KismetExpression] = field(default_factory=list)
    successors: list[int] = field(default_factory=list)  # 后继块 ID
    predecessors: list[int] = field(default_factory=list)  # 前驱块 ID
    edge_kinds: dict[int, EdgeKind] = field(
        default_factory=dict
    )  # 后继 → 边类型

    @property
    def label(self) -> str:
        """块标签，格式 BB0, BB1, ..."""
        return f"BB{self.block_id}"

    @property
    def size(self) -> int:
        """块内表达式数量。"""
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
    """控制流图 (Control Flow Graph)。

    由基本块和边组成，包含入口块和合成 sink 块。
    """

    blocks: dict[int, BasicBlock] = field(default_factory=dict)
    entry_id: int = 0
    exit_id: int = -1  # 合成 sink 块 ID

    @property
    def entry(self) -> BasicBlock:
        """入口块。"""
        return self.blocks[self.entry_id]

    @property
    def exit(self) -> BasicBlock:
        """合成 sink 块（所有 fall-through 的目标）。"""
        return self.blocks[self.exit_id]

    @property
    def block_count(self) -> int:
        """基本块总数。"""
        return len(self.blocks)

    @property
    def edge_count(self) -> int:
        """边总数。"""
        total = 0
        for block in self.blocks.values():
            total += len(block.successors)
        return total

    def ordered_blocks(self) -> list[BasicBlock]:
        """按 block_id 升序返回所有基本块。"""
        return [self.blocks[bid] for bid in sorted(self.blocks.keys())]

    def add_block(self, block: BasicBlock) -> None:
        """添加基本块到 CFG。"""
        self.blocks[block.block_id] = block

    def __repr__(self) -> str:
        return f"CFG(blocks={self.block_count}, edges={self.edge_count})"


class RegionKind(Enum):
    """区域类型。"""

    BLOCK = auto()  # 直线序列（无分支）
    IF_THEN = auto()  # if-then（单分支）
    IF_THEN_ELSE = auto()  # if-then-else（双分支）
    WHILE_LOOP = auto()  # while 循环（head 有外部前驱）
    DO_WHILE = auto()  # do-while 循环（head 无外部前驱）
    FOR_LOOP = auto()  # for 循环（语法糖，由 while 识别）
    SELF_LOOP = auto()  # 自环（单块循环）
    IRREDUCIBLE = auto()  # 不可规约区域


@dataclass
class Region:
    """控制流区域（SESE 区间）。

    每个区域有唯一的 head（入口块）和 tail（出口块），
    满足单入口单出口 (SESE) 性质。
    """

    region_id: int
    kind: RegionKind
    head: int  # 入口块 ID
    tail: int  # 出口块 ID（SESE 的唯一出口）
    body_blocks: list[int] = field(default_factory=list)  # 区域内所有块
    exit_blocks: list[int] = field(default_factory=list)  # 区域退出块
    children: list[int] = field(default_factory=list)  # 子区域 ID
    loop_back_edges: list[tuple[int, int]] = field(
        default_factory=list
    )  # 回边 (src, dst)

    @property
    def block_count(self) -> int:
        """区域包含的块数。"""
        return len(self.body_blocks)

    def __repr__(self) -> str:
        return (
            f"Region(id={self.region_id}, kind={self.kind.name}, "
            f"head=BB{self.head}, tail=BB{self.tail}, "
            f"blocks={self.block_count})"
        )


@dataclass
class RegionTree:
    """区域树。

    存储所有区域及层次关系。
    """

    regions: dict[int, Region] = field(default_factory=dict)
    root_id: int = -1

    @property
    def root(self) -> Region:
        """根区域。"""
        return self.regions[self.root_id]

    def add_region(self, region: Region) -> None:
        """添加区域。"""
        self.regions[region.region_id] = region

    def get_region(self, region_id: int) -> Region | None:
        """根据 ID 获取区域。"""
        return self.regions.get(region_id)

    def __repr__(self) -> str:
        return f"RegionTree(regions={len(self.regions)})"


@dataclass
class DominatorTree:
    """支配树。

    存储立即支配者 (idom) 和完整支配关系。
    """

    idom: dict[int, int | None] = field(default_factory=dict)
    dominators: dict[int, set[int]] = field(default_factory=dict)
    dominated: dict[int, set[int]] = field(default_factory=dict)
    _frontiers: dict[int, set[int]] = field(default_factory=dict)

    def is_dominator(self, dom_id: int, node_id: int) -> bool:
        """判断 dom_id 是否支配 node_id。"""
        if node_id not in self.dominators:
            return False
        return dom_id in self.dominators[node_id]

    def immediate_dominator(self, block_id: int) -> int | None:
        """获取 block_id 的立即支配者。"""
        return self.idom.get(block_id)

    def dominator_frontier(self, block_id: int) -> set[int]:
        """获取 block_id 的支配前沿。"""
        return self._frontiers.get(block_id, set())

    def __repr__(self) -> str:
        return f"DominatorTree(blocks={len(self.idom)})"
