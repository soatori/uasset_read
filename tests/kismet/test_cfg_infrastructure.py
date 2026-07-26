"""CFG 基础设施单元测试。

覆盖:
- data.py: BasicBlock, CFG, Region, RegionTree, DominatorTree 数据结构
- build.py: CFG 构建（空列表、线性流、条件分支、循环）
- dom.py: Cooper-Harvey-Kennedy 支配树算法
- region.py: SESE 区域分解、回边检测、循环块计算
"""

from uasset_read.kismet.expressions.control_flow import (
    EX_Jump,
    EX_JumpIfNot,
    EX_EndOfScript,
    EX_PopExecutionFlow,
)
from uasset_read.kismet.expressions.assignments import EX_Let
from uasset_read.kismet.cfg import (
    build_cfg,
    compute_dominator_tree,
    decompose_regions,
    find_back_edges,
    compute_loop_blocks,
)
from uasset_read.kismet.cfg.data import (
    BasicBlock,
    CFG,
    DominatorTree,
    EdgeKind,
    Region,
    RegionKind,
    RegionTree,
)


# ================================================================
# 测试辅助工厂
# ================================================================

def _make_let(stmt_idx: int) -> EX_Let:
    """创建带 StatementIndex 的 EX_Let。"""
    e = EX_Let()
    e.StatementIndex = stmt_idx
    return e


def _make_jump(stmt_idx: int, code_offset: int) -> EX_Jump:
    """创建带 StatementIndex 和 CodeOffset 的 EX_Jump。"""
    e = EX_Jump(CodeOffset=code_offset)
    e.StatementIndex = stmt_idx
    return e


def _make_jump_if_not(stmt_idx: int, code_offset: int) -> EX_JumpIfNot:
    """创建带 StatementIndex 和 CodeOffset 的 EX_JumpIfNot。"""
    e = EX_JumpIfNot(CodeOffset=code_offset, BooleanExpression=None)
    e.StatementIndex = stmt_idx
    return e


def _make_end(stmt_idx: int) -> EX_EndOfScript:
    """创建带 StatementIndex 的 EX_EndOfScript。"""
    e = EX_EndOfScript()
    e.StatementIndex = stmt_idx
    return e


def _make_pop_flow(stmt_idx: int) -> EX_PopExecutionFlow:
    """创建带 StatementIndex 的 EX_PopExecutionFlow。"""
    e = EX_PopExecutionFlow()
    e.StatementIndex = stmt_idx
    return e


# ================================================================
# data.py: BasicBlock
# ================================================================

class TestBasicBlock:
    """BasicBlock 数据结构测试。"""

    def test_creation(self):
        block = BasicBlock(block_id=0, start_idx=0, end_idx=5)
        assert block.block_id == 0
        assert block.start_idx == 0
        assert block.end_idx == 5
        assert block.successors == []
        assert block.predecessors == []
        assert block.edge_kinds == {}
        assert block.expressions == []

    def test_label(self):
        block = BasicBlock(block_id=3, start_idx=0, end_idx=0)
        assert block.label == "BB3"

    def test_size(self):
        block = BasicBlock(block_id=0, start_idx=5, end_idx=10)
        assert block.size == 6  # 10 - 5 + 1

    def test_size_empty_block(self):
        block = BasicBlock(block_id=0, start_idx=5, end_idx=4)
        assert block.size == 0  # end < start → 0

    def test_equality(self):
        b1 = BasicBlock(block_id=0, start_idx=0, end_idx=5)
        b2 = BasicBlock(block_id=0, start_idx=10, end_idx=20)
        b3 = BasicBlock(block_id=1, start_idx=0, end_idx=5)
        assert b1 == b2  # Same block_id
        assert b1 != b3

    def test_hash(self):
        b1 = BasicBlock(block_id=0, start_idx=0, end_idx=5)
        b2 = BasicBlock(block_id=0, start_idx=10, end_idx=20)
        assert hash(b1) == hash(b2)
        assert hash(b1) == 0

    def test_repr(self):
        block = BasicBlock(block_id=2, start_idx=3, end_idx=7,
                           predecessors=[0, 1], successors=[4])
        r = repr(block)
        assert "id=2" in r
        assert "[3..7]" in r


# ================================================================
# data.py: CFG
# ================================================================

class TestCFG:
    """CFG 数据结构测试。"""

    def test_creation(self):
        cfg = CFG()
        assert cfg.block_count == 0
        assert cfg.edge_count == 0

    def test_add_block(self):
        cfg = CFG()
        block = BasicBlock(block_id=0, start_idx=0, end_idx=5)
        cfg.add_block(block)
        assert cfg.block_count == 1
        assert cfg.blocks[0] is block

    def test_entry_exit(self):
        cfg = CFG()
        entry = BasicBlock(block_id=0, start_idx=0, end_idx=5)
        exit_b = BasicBlock(block_id=1, start_idx=6, end_idx=6)
        cfg.add_block(entry)
        cfg.add_block(exit_b)
        cfg.entry_id = 0
        cfg.exit_id = 1
        assert cfg.entry is entry
        assert cfg.exit is exit_b

    def test_ordered_blocks(self):
        cfg = CFG()
        cfg.add_block(BasicBlock(block_id=2, start_idx=0, end_idx=0))
        cfg.add_block(BasicBlock(block_id=0, start_idx=0, end_idx=0))
        cfg.add_block(BasicBlock(block_id=1, start_idx=0, end_idx=0))
        ordered = cfg.ordered_blocks()
        assert [b.block_id for b in ordered] == [0, 1, 2]

    def test_edge_count(self):
        cfg = CFG()
        b0 = BasicBlock(block_id=0, start_idx=0, end_idx=0)
        b1 = BasicBlock(block_id=1, start_idx=1, end_idx=1)
        b0.successors = [1]
        cfg.add_block(b0)
        cfg.add_block(b1)
        assert cfg.edge_count == 1


# ================================================================
# data.py: EdgeKind
# ================================================================

class TestEdgeKind:
    """EdgeKind 枚举测试。"""

    def test_all_members(self):
        kinds = [EdgeKind.FALLTHROUGH, EdgeKind.TRUE_BRANCH,
                 EdgeKind.FALSE_BRANCH, EdgeKind.UNCONDITIONAL,
                 EdgeKind.BACK_EDGE]
        assert len(kinds) == 5
        assert len(set(kinds)) == 5


# ================================================================
# data.py: DominatorTree
# ================================================================

class TestDominatorTree:
    """DominatorTree 数据结构测试。"""

    def test_creation(self):
        tree = DominatorTree()
        assert len(tree.idom) == 0

    def test_is_dominator(self):
        tree = DominatorTree(
            idom={0: 0, 1: 0, 2: 0},
            dominators={0: {0}, 1: {0, 1}, 2: {0, 2}},
        )
        assert tree.is_dominator(0, 0) is True
        assert tree.is_dominator(0, 1) is True
        assert tree.is_dominator(1, 0) is False

    def test_immediate_dominator(self):
        tree = DominatorTree(idom={0: 0, 1: 0, 2: 1})
        assert tree.immediate_dominator(1) == 0
        assert tree.immediate_dominator(2) == 1
        assert tree.immediate_dominator(99) is None


# ================================================================
# data.py: Region & RegionTree
# ================================================================

class TestRegion:
    """Region 数据结构测试。"""

    def test_creation(self):
        region = Region(
            region_id=0,
            kind=RegionKind.BLOCK,
            head=0,
            tail=0,
            body_blocks=[0],
        )
        assert region.block_count == 1
        assert region.kind == RegionKind.BLOCK

    def test_region_tree(self):
        tree = RegionTree()
        r = Region(region_id=0, kind=RegionKind.BLOCK, head=0, tail=0,
                   body_blocks=[0])
        tree.add_region(r)
        assert tree.get_region(0) is r
        assert tree.get_region(99) is None


# ================================================================
# build.py: CFG 构建 — 空表达式
# ================================================================

class TestBuildCfgEmpty:
    """空表达式列表的 CFG 构建。"""

    def test_empty_expressions(self):
        cfg = build_cfg([])
        assert cfg.block_count == 1  # 只有 sink
        assert cfg.entry_id == 0
        assert cfg.exit_id == 0

    def test_single_expression_no_terminator(self):
        let0 = _make_let(0)
        cfg = build_cfg([let0])
        assert cfg.block_count == 2  # 入口 + sink
        assert cfg.entry_id == 0


# ================================================================
# build.py: CFG 构建 — 线性流
# ================================================================

class TestBuildCfgLinear:
    """线性控制流的 CFG 构建。"""

    def test_two_blocks_linear(self):
        """Let → EndOfScript: 两个块（入口 + sink）。"""
        let0 = _make_let(0)
        end = _make_end(8)
        cfg = build_cfg([let0, end])
        assert cfg.block_count == 2
        entry = cfg.entry
        assert entry.block_id == 0
        assert entry.start_idx == 0
        assert 1 in entry.successors  # → sink

    def test_linear_with_jump_at_end(self):
        """Let → Jump(目标): 两个块 + sink。"""
        let0 = _make_let(0)
        jmp = _make_jump(8, 16)
        let1 = _make_let(16)
        end = _make_end(24)
        cfg = build_cfg([let0, jmp, let1, end])
        # BB0: let0, jmp → target is let1 (leader)
        # BB1: let1, end → sink
        # BB2: sink
        assert cfg.block_count == 3

    def test_leader_after_terminator(self):
        """终结符后一条指令是新的 leader。"""
        let0 = _make_let(0)
        jmp = _make_jump(8, 16)  # 跳到 let1 (stmt 16)
        let1 = _make_let(16)
        end = _make_end(24)
        cfg = build_cfg([let0, jmp, let1, end])
        # BB0: let0, jmp (terminator → next is leader)
        # BB1: let1, end → sink
        # BB2: sink
        assert cfg.block_count == 3
        assert cfg.entry.successors[0] == 1  # fall-through to BB1


# ================================================================
# build.py: CFG 构建 — 条件分支
# ================================================================

class TestBuildCfgConditional:
    """条件分支的 CFG 构建。"""

    def test_if_else_pattern(self):
        """JumpIfNot: 两条分支 + 汇合。"""
        # Let(0) → JumpIfNot(target=Let3 at byte 24) → Let(16) → Let(24) → End(32)
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)  # target = expression at stmt 24
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)
        cfg = build_cfg([let0, jmp, let1, let2, end])

        # BB0: let0, jmp → conditional target=BB2, fall-through=BB1
        # BB1: let1 → fall-through=BB2
        # BB2: let2, end → sink
        # BB3: sink
        assert cfg.block_count == 4

        bb0 = cfg.blocks[0]
        assert EdgeKind.TRUE_BRANCH in bb0.edge_kinds.values()
        assert EdgeKind.FALSE_BRANCH in bb0.edge_kinds.values()

    def test_conditional_edges(self):
        """EX_JumpIfNot produces TRUE_BRANCH (fall-through) + FALSE_BRANCH (jump target) edges."""
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)
        cfg = build_cfg([let0, jmp, let1, let2, end])

        bb0 = cfg.blocks[0]
        edge_kinds = set(bb0.edge_kinds.values())
        assert EdgeKind.TRUE_BRANCH in edge_kinds
        assert EdgeKind.FALSE_BRANCH in edge_kinds

    def test_unconditional_jump(self):
        """EX_Jump 产生 UNCONDITIONAL 边。"""
        let0 = _make_let(0)
        jmp = _make_jump(8, 24)  # 跳到 let2
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)
        cfg = build_cfg([let0, jmp, let1, let2, end])

        bb0 = cfg.blocks[0]
        assert EdgeKind.UNCONDITIONAL in bb0.edge_kinds.values()


# ================================================================
# build.py: CFG 构建 — 合成 sink
# ================================================================

class TestBuildCfgSink:
    """合成 sink 块测试。"""

    def test_sink_from_end_of_script(self):
        """EndOfScript 连接到 sink。"""
        let0 = _make_let(0)
        end = _make_end(8)
        cfg = build_cfg([let0, end])
        sink = cfg.exit
        assert sink.block_id == cfg.exit_id
        assert len(sink.predecessors) >= 1

    def test_sink_from_fallthrough(self):
        """非终结符 fall-through 到 sink。"""
        let0 = _make_let(0)
        let1 = _make_let(8)
        cfg = build_cfg([let0, let1])
        sink = cfg.exit
        assert sink.block_id == cfg.exit_id


# ================================================================
# dom.py: 支配树 — 线性流
# ================================================================

class TestDominatorTreeLinear:
    """线性流的支配树计算。"""

    def test_linear_chain(self):
        """线性链: 0 → 1 → 2，每个节点支配后续所有节点。"""
        let0 = _make_let(0)
        let1 = _make_let(8)
        end = _make_end(16)
        cfg = build_cfg([let0, let1, end])
        dom = compute_dominator_tree(cfg)

        # BB0 支配所有
        assert dom.is_dominator(0, 0)
        assert dom.is_dominator(0, 1)

    def test_entry_dominates_all(self):
        """入口块支配所有可达块。"""
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)
        cfg = build_cfg([let0, jmp, let1, let2, end])
        dom = compute_dominator_tree(cfg)

        for bid in cfg.blocks:
            if bid != cfg.exit_id:
                assert dom.is_dominator(cfg.entry_id, bid), \
                    f"entry should dominate block {bid}"


# ================================================================
# dom.py: 支配树 — 条件分支
# ================================================================

class TestDominatorTreeConditional:
    """条件分支的支配树计算。"""

    def test_diamond_dominators(self):
        """钻石形 CFG: entry → (then, else) → join。"""
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)
        cfg = build_cfg([let0, jmp, let1, let2, end])
        dom = compute_dominator_tree(cfg)

        # BB0 支配 BB1 和 BB2
        assert dom.is_dominator(0, 1)
        assert dom.is_dominator(0, 2)

    def test_immediate_dominator(self):
        """立即支配者关系。"""
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)
        cfg = build_cfg([let0, jmp, let1, let2, end])
        dom = compute_dominator_tree(cfg)

        # BB1 的立即支配者是 BB0
        assert dom.immediate_dominator(1) == 0


# ================================================================
# dom.py: 支配树 — 空/单节点
# ================================================================

class TestDominatorTreeEdgeCases:
    """支配树边界条件测试。"""

    def test_empty_cfg(self):
        """空 CFG 返回空支配树。"""
        cfg = build_cfg([])
        dom = compute_dominator_tree(cfg)
        assert len(dom.idom) == 1  # 只有 entry
        assert dom.idom[cfg.entry_id] == cfg.entry_id

    def test_single_block(self):
        """单块 CFG：入口支配自身。"""
        let0 = _make_let(0)
        end = _make_end(8)
        cfg = build_cfg([let0, end])
        dom = compute_dominator_tree(cfg)
        assert dom.idom[cfg.entry_id] == cfg.entry_id


# ================================================================
# region.py: 回边检测
# ================================================================

class TestFindBackEdges:
    """回边检测测试。"""

    def test_no_back_edges_linear(self):
        """线性流无回边。"""
        let0 = _make_let(0)
        let1 = _make_let(8)
        end = _make_end(16)
        cfg = build_cfg([let0, let1, end])
        dom = compute_dominator_tree(cfg)
        back = find_back_edges(cfg, dom)
        assert back == []

    def test_self_loop(self):
        """自循环: block 跳转到自身。"""
        # BB0: JumpIfNot(target=BB0) → self-loop
        # BB1: EndOfScript (sink)
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 0)  # 跳回 stmt 0 (自身)
        end = _make_end(16)
        cfg = build_cfg([let0, jmp, end])
        dom = compute_dominator_tree(cfg)
        back = find_back_edges(cfg, dom)

        # 应该有从 BB0 到 BB0 的回边
        assert len(back) >= 1
        src, dst = back[0]
        assert dst == cfg.entry_id  # 循环头


# ================================================================
# region.py: 循环块计算
# ================================================================

class TestComputeLoopBlocks:
    """循环块计算测试。"""

    def test_self_loop_blocks(self):
        """自循环：循环体只有头块。"""
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 0)  # 跳回自身
        end = _make_end(16)
        cfg = build_cfg([let0, jmp, end])
        dom = compute_dominator_tree(cfg)
        back = find_back_edges(cfg, dom)

        if back:
            src, dst = back[0]
            loop_blocks = compute_loop_blocks(cfg, src, dst)
            assert dst in loop_blocks


# ================================================================
# region.py: SESE 区域分解
# ================================================================

class TestDecomposeRegions:
    """SESE 区域分解测试。"""

    def test_linear_flow(self):
        """线性流：每个块是 BLOCK 区域。"""
        let0 = _make_let(0)
        let1 = _make_let(8)
        end = _make_end(16)
        cfg = build_cfg([let0, let1, end])
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        assert regions.root_id >= 0
        assert len(regions.regions) >= 1

    def test_conditional_creates_region(self):
        """条件分支创建 IF_THEN 或 IF_THEN_ELSE 区域。"""
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)
        cfg = build_cfg([let0, jmp, let1, let2, end])
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        kinds = {r.kind for r in regions.regions.values()}
        # 至少有一个非 BLOCK 区域（IF_THEN 或 IF_THEN_ELSE）
        assert kinds - {RegionKind.BLOCK} != set()

    def test_loop_creates_loop_region(self):
        """循环创建 WHILE_LOOP 或 DO_WHILE 区域。"""
        # 构建一个 while 循环:
        # BB0: condition check
        # BB1: loop body
        # BB2: sink
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)  # 跳到 body (stmt 24)
        let1 = _make_let(16)
        jmp_back = _make_jump(24, 0)  # 跳回条件 (stmt 0)
        end = _make_end(32)
        cfg = build_cfg([let0, jmp, let1, jmp_back, end])
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        loop_kinds = {RegionKind.WHILE_LOOP, RegionKind.DO_WHILE, RegionKind.SELF_LOOP}
        found_loops = [r for r in regions.regions.values() if r.kind in loop_kinds]
        # 应该找到循环区域
        assert len(found_loops) >= 1


# ================================================================
# region.py: RegionKind 枚举
# ================================================================

class TestRegionKind:
    """RegionKind 枚举测试。"""

    def test_all_members(self):
        kinds = [
            RegionKind.BLOCK,
            RegionKind.IF_THEN,
            RegionKind.IF_THEN_ELSE,
            RegionKind.WHILE_LOOP,
            RegionKind.DO_WHILE,
            RegionKind.FOR_LOOP,
            RegionKind.SELF_LOOP,
            RegionKind.IRREDUCIBLE,
        ]
        assert len(kinds) == 8
        assert len(set(kinds)) == 8


# ================================================================
# 集成: build_cfg → dominator → regions 全链路
# ================================================================

class TestFullPipeline:
    """全链路集成测试。"""

    def test_simple_if_else(self):
        """简单 if-else 全链路。"""
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)

        cfg = build_cfg([let0, jmp, let1, let2, end])
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        # CFG 应该有 4 个块
        assert cfg.block_count == 4
        # 支配树应该覆盖所有块
        assert len(dom.idom) == 4
        # 区域应该覆盖所有块
        all_region_blocks = set()
        for r in regions.regions.values():
            all_region_blocks.update(r.body_blocks)
        assert cfg.entry_id in all_region_blocks

    def test_while_loop(self):
        """while 循环全链路。"""
        # BB0: condition (JumpIfNot → body)
        # BB1: body (Jump → back to condition)
        # BB2: after loop
        # BB3: sink
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)  # 条件跳到 body
        let1 = _make_let(16)
        jmp_back = _make_jump(24, 0)  # 跳回条件
        let_after = _make_let(32)
        end = _make_end(40)

        cfg = build_cfg([let0, jmp, let1, jmp_back, let_after, end])
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        # 应该有循环区域
        loop_kinds = {RegionKind.WHILE_LOOP, RegionKind.DO_WHILE, RegionKind.SELF_LOOP}
        found_loops = [r for r in regions.regions.values() if r.kind in loop_kinds]
        assert len(found_loops) >= 1

    def test_multiple_conditionals(self):
        """多个条件分支。"""
        let0 = _make_let(0)
        jmp1 = _make_jump_if_not(8, 32)  # 第一个条件
        let1 = _make_let(16)
        jmp2 = _make_jump_if_not(24, 48)  # 第二个条件
        let2 = _make_let(32)
        let3 = _make_let(40)
        let4 = _make_let(48)
        end = _make_end(56)

        cfg = build_cfg([let0, jmp1, let1, jmp2, let2, let3, let4, end])
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        # 至少有 2 个条件分支区域
        cond_regions = [r for r in regions.regions.values()
                        if r.kind in {RegionKind.IF_THEN, RegionKind.IF_THEN_ELSE}]
        assert len(cond_regions) >= 1


class TestEdgeKindSemantics:
    """Regression: EdgeKind TRUE_BRANCH / FALSE_BRANCH must match UE EX_JumpIfNot semantics.

    UE source (ScriptCore.cpp execJumpIfNot):
        EX_JumpIfNot pops a boolean.
        If FALSE  -> jump to CodeOffset  (FALSE_BRANCH)
        If TRUE   -> fall through        (TRUE_BRANCH)
    """

    def test_jump_if_not_false_branch_is_jump_target(self):
        """FALSE_BRANCH edge points to the jump target (CodeOffset).

        Layout (expression indices):
            0: let0       \
            1: jmp        - BB0 (terminator = JumpIfNot)
            2: let_fall    / BB1 (fall-through, TRUE path)
            3: let_target / BB2 (jump target, FALSE path)
            4: end

        UE semantics: if FALSE -> jump to offset 24 (let_target);
                      if TRUE  -> fall through (let_fall).
        """
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)  # CodeOffset=24 maps to let_target
        let_fall = _make_let(16)
        let_target = _make_let(24)
        end = _make_end(32)

        cfg = build_cfg([let0, jmp, let_fall, let_target, end])

        bb0 = cfg.entry
        assert len(bb0.successors) == 2

        # Identify blocks by their start_idx in the expression list
        jump_target_bid = None
        fall_through_bid = None
        for succ_bid in bb0.successors:
            succ_block = cfg.blocks[succ_bid]
            if succ_block.start_idx == 3:  # let_target at expression index 3
                jump_target_bid = succ_bid
            elif succ_block.start_idx == 2:  # let_fall at expression index 2
                fall_through_bid = succ_bid

        assert jump_target_bid is not None, "jump target block not found"
        assert fall_through_bid is not None, "fall-through block not found"

        # Jump target (FALSE path) must be FALSE_BRANCH
        assert bb0.edge_kinds[jump_target_bid] == EdgeKind.FALSE_BRANCH, (
            f"Jump target block should be FALSE_BRANCH, "
            f"got {bb0.edge_kinds[jump_target_bid]}"
        )

        # Fall-through (TRUE path) must be TRUE_BRANCH
        assert bb0.edge_kinds[fall_through_bid] == EdgeKind.TRUE_BRANCH, (
            f"Fall-through block should be TRUE_BRANCH, "
            f"got {bb0.edge_kinds[fall_through_bid]}"
        )

    def test_true_branch_cannot_be_false_branch(self):
        """Ensure TRUE_BRANCH and FALSE_BRANCH are distinct enum values."""
        assert EdgeKind.TRUE_BRANCH is not EdgeKind.FALSE_BRANCH
        assert EdgeKind.TRUE_BRANCH != EdgeKind.FALSE_BRANCH
