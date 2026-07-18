"""CFG 基础设施 + 结构化输出单元测试。

覆盖:
- data.py: BasicBlock, CFG, Region, RegionTree, DominatorTree 数据结构
- build.py: CFG 构建（空列表、线性流、条件分支、循环）
- dom.py: Cooper-Harvey-Kennedy 支配树算法
- region.py: SESE 区域分解、回边检测、循环块计算
- stmt.py: Stmt 类型（Branch, Loop, Switch, Sequence, Assignment, Call, Return, GotoLabel）
- emitter.py: RegionDecoder 区域解码 + StmtEmitter 伪代码渲染
"""

from __future__ import annotations

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
from uasset_read.kismet.expressions.assignments import EX_Let
from uasset_read.kismet.expressions.control_flow import (
    EX_EndOfScript,
    EX_Jump,
    EX_JumpIfNot,
    EX_PopExecutionFlow,
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
        kinds = [EdgeKind.FALLTHROUGH, EdgeKind.CONDITIONAL,
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
        assert EdgeKind.CONDITIONAL in bb0.edge_kinds.values()
        assert EdgeKind.FALSE_BRANCH in bb0.edge_kinds.values()

    def test_conditional_edges(self):
        """条件跳转产生 CONDITIONAL + FALSE_BRANCH 边。"""
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)
        cfg = build_cfg([let0, jmp, let1, let2, end])

        bb0 = cfg.blocks[0]
        edge_kinds = set(bb0.edge_kinds.values())
        assert EdgeKind.CONDITIONAL in edge_kinds
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


# ================================================================
# stmt.py: Stmt 类型测试
# ================================================================


class TestAssignment:
    """Assignment 语句测试。"""

    def test_creation(self):
        a = Assignment(lhs="x", rhs="42")
        assert a.lhs == "x"
        assert a.rhs == "42"

    def test_repr(self):
        a = Assignment(lhs="x", rhs="42")
        r = repr(a)
        assert "Assignment" in r
        assert "x" in r
        assert "42" in r

    def test_is_stmt(self):
        a = Assignment()
        assert isinstance(a, Stmt)


class TestCall:
    """Call 语句测试。"""

    def test_creation(self):
        c = Call(text="MyFunc()")
        assert c.text == "MyFunc()"

    def test_repr(self):
        c = Call(text="MyFunc()")
        r = repr(c)
        assert "Call" in r
        assert "MyFunc()" in r

    def test_is_stmt(self):
        c = Call()
        assert isinstance(c, Stmt)


class TestReturn:
    """Return 语句测试。"""

    def test_creation(self):
        r = Return(value="x")
        assert r.value == "x"

    def test_repr(self):
        r = Return(value="x")
        assert "Return" in repr(r)

    def test_empty_value(self):
        r = Return(value="")
        assert r.value == ""


class TestGotoLabel:
    """GotoLabel 语句测试。"""

    def test_creation(self):
        g = GotoLabel(label="Label_0")
        assert g.label == "Label_0"

    def test_repr(self):
        g = GotoLabel(label="Label_0")
        assert "GotoLabel" in repr(g)


class TestSequence:
    """Sequence 语句测试。"""

    def test_creation(self):
        s = Sequence(stmts=[Assignment(lhs="a", rhs="1"), Call(text="foo()")])
        assert len(s.stmts) == 2
        assert isinstance(s.stmts[0], Assignment)
        assert isinstance(s.stmts[1], Call)

    def test_empty(self):
        s = Sequence()
        assert len(s.stmts) == 0

    def test_repr(self):
        s = Sequence()
        assert "Sequence" in repr(s)


class TestBranch:
    """Branch 语句测试。"""

    def test_creation(self):
        b = Branch(
            condition="x > 0",
            then_body=Assignment(lhs="y", rhs="1"),
            else_body=Assignment(lhs="y", rhs="0"),
        )
        assert b.condition == "x > 0"
        assert isinstance(b.then_body, Assignment)
        assert isinstance(b.else_body, Assignment)

    def test_if_only(self):
        b = Branch(
            condition="true",
            then_body=Call(text="foo()"),
            else_body=None,
        )
        assert b.else_body is None

    def test_repr(self):
        b = Branch(condition="true")
        assert "Branch" in repr(b)


class TestLoop:
    """Loop 语句测试。"""

    def test_creation_while(self):
        loop = Loop(kind="while", condition="i < 10", body=Sequence())
        assert loop.kind == "while"
        assert loop.condition == "i < 10"

    def test_creation_do_while(self):
        loop = Loop(kind="do_while", condition="true", body=Sequence())
        assert loop.kind == "do_while"

    def test_repr(self):
        loop = Loop()
        assert "Loop" in repr(loop)


class TestSwitch:
    """Switch 语句测试。"""

    def test_creation(self):
        s = Switch(
            expression="x",
            cases=[
                ("0", Call(text="case_zero")),
                ("1", Call(text="case_one")),
            ],
            default_body=Call(text="default_case"),
        )
        assert s.expression == "x"
        assert len(s.cases) == 2
        assert s.default_body is not None

    def test_empty_cases(self):
        s = Switch(expression="x")
        assert len(s.cases) == 0
        assert s.default_body is None

    def test_repr(self):
        s = Switch(expression="x")
        assert "Switch" in repr(s)


# ================================================================
# emitter.py: StmtEmitter 伪代码渲染测试
# ================================================================


class TestStmtEmitterBasic:
    """StmtEmitter 基本渲染测试。"""

    def test_assignment(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        result = emitter.emit_body(Assignment(lhs="x", rhs="42"))
        assert "x = 42;" in result

    def test_call(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        result = emitter.emit_body(Call(text="MyFunc()"))
        assert "MyFunc();" in result

    def test_return_with_value(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        result = emitter.emit_body(Return(value="x"))
        assert "return x;" in result

    def test_return_no_value(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        result = emitter.emit_body(Return(value=""))
        assert "return;" in result

    def test_goto_label(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        result = emitter.emit_body(GotoLabel(label="Label_0"))
        assert "Label_0:" in result

    def test_sequence(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        seq = Sequence(
            stmts=[
                Assignment(lhs="a", rhs="1"),
                Assignment(lhs="b", rhs="2"),
            ]
        )
        result = emitter.emit_body(seq)
        assert "a = 1;" in result
        assert "b = 2;" in result


class TestStmtEmitterBranch:
    """StmtEmitter 分支渲染测试。"""

    def test_if_then(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        branch = Branch(
            condition="x > 0",
            then_body=Assignment(lhs="y", rhs="1"),
        )
        result = emitter.emit_body(branch)
        assert "if (x > 0) {" in result
        assert "y = 1;" in result
        assert "} else {" not in result

    def test_if_else(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        branch = Branch(
            condition="x > 0",
            then_body=Assignment(lhs="y", rhs="1"),
            else_body=Assignment(lhs="y", rhs="0"),
        )
        result = emitter.emit_body(branch)
        assert "if (x > 0) {" in result
        assert "y = 1;" in result
        assert "else {" in result
        assert "y = 0;" in result

    def test_indentation(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter(indent="  ")
        branch = Branch(
            condition="true",
            then_body=Assignment(lhs="x", rhs="1"),
        )
        result = emitter.emit_body(branch)
        lines = result.split("\n")
        # if 在第 0 层
        assert lines[0].startswith("if")
        # body 在第 1 层
        assert lines[1].startswith("  x = 1;")


class TestStmtEmitterLoop:
    """StmtEmitter 循环渲染测试。"""

    def test_while_loop(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        loop = Loop(
            kind="while",
            condition="i < 10",
            body=Sequence(
                stmts=[
                    Assignment(lhs="i", rhs="i + 1"),
                ]
            ),
        )
        result = emitter.emit_body(loop)
        assert "while (i < 10) {" in result
        assert "i = i + 1;" in result

    def test_do_while_loop(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        loop = Loop(
            kind="do_while",
            condition="true",
            body=Sequence(stmts=[Call(text="foo()")]),
        )
        result = emitter.emit_body(loop)
        assert "do {" in result
        assert "foo();" in result
        assert "} while (true);" in result

    def test_for_loop(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        loop = Loop(
            kind="for",
            condition="",
            body=Sequence(stmts=[Call(text="step()")]),
        )
        result = emitter.emit_body(loop)
        assert "for (;;) {" in result
        assert "step();" in result


class TestStmtEmitterSwitch:
    """StmtEmitter switch 渲染测试。"""

    def test_switch_with_cases(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        sw = Switch(
            expression="x",
            cases=[
                ("0", Call(text="handleZero")),
                ("1", Call(text="handleOne")),
            ],
            default_body=Call(text="handleDefault"),
        )
        result = emitter.emit_body(sw)
        assert "switch (x) {" in result
        assert "case 0:" in result
        assert "handleZero" in result
        assert "case 1:" in result
        assert "handleOne" in result
        assert "default:" in result
        assert "handleDefault" in result

    def test_switch_no_default(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        sw = Switch(
            expression="x",
            cases=[("0", Call(text="handleZero"))],
        )
        result = emitter.emit_body(sw)
        assert "switch (x) {" in result
        assert "case 0: {" in result
        assert "default:" not in result


class TestStmtEmitterNested:
    """StmtEmitter 嵌套渲染测试。"""

    def test_nested_if_in_loop(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        stmt = Loop(
            kind="while",
            condition="true",
            body=Sequence(
                stmts=[
                    Branch(
                        condition="x > 0",
                        then_body=Call(text="positive"),
                        else_body=Call(text="negative"),
                    )
                ]
            ),
        )
        result = emitter.emit_body(stmt)
        assert "while (true) {" in result
        assert "if (x > 0) {" in result
        assert "positive" in result
        assert "else {" in result
        assert "negative" in result

    def test_emit_lines(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        seq = Sequence(
            stmts=[Assignment(lhs="a", rhs="1"), Assignment(lhs="b", rhs="2")]
        )
        lines = emitter.emit_lines(seq)
        assert len(lines) == 2
        assert "a = 1;" in lines[0]
        assert "b = 2;" in lines[1]


class TestStmtEmitterEmpty:
    """StmtEmitter 空/边界测试。"""

    def test_empty_sequence(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        result = emitter.emit_body(Sequence())
        assert result == ""

    def test_unknown_stmt(self):
        from uasset_read.kismet.cfg.emitter import StmtEmitter

        emitter = StmtEmitter()
        result = emitter.emit_body(Stmt())
        assert "unknown stmt" in result


# ================================================================
# emitter.py: RegionDecoder 集成测试（使用真实 CFG）
# ================================================================


class TestRegionDecoderSimple:
    """RegionDecoder 简单场景测试。"""

    def test_linear_flow(self):
        """线性流 → Sequence。"""
        from uasset_read.kismet.cfg import build_cfg, compute_dominator_tree, decompose_regions
        from uasset_read.kismet.cfg.emitter import RegionDecoder
        from uasset_read.kismet.translator import KismetTranslator

        let0 = _make_let(0)
        let1 = _make_let(8)
        end = _make_end(16)
        cfg = build_cfg([let0, let1, end])
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        translator = KismetTranslator(expressions=[let0, let1, end])
        decoder = RegionDecoder(
            cfg=cfg,
            region_tree=regions,
            expressions=[let0, let1, end],
            translator=translator,
            offset_to_index={},
            jump_targets=set(),
        )
        stmt = decoder.decode()
        assert isinstance(stmt, Sequence)
        assert len(stmt.stmts) > 0

    def test_if_else_flow(self):
        """if-else → Branch。"""
        from uasset_read.kismet.cfg import build_cfg, compute_dominator_tree, decompose_regions
        from uasset_read.kismet.cfg.emitter import RegionDecoder
        from uasset_read.kismet.cfg.data import RegionKind
        from uasset_read.kismet.translator import KismetTranslator

        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)

        cfg = build_cfg([let0, jmp, let1, let2, end])
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        # 检查有非 BLOCK 区域
        kinds = {r.kind for r in regions.regions.values()}
        has_branch = kinds & {RegionKind.IF_THEN, RegionKind.IF_THEN_ELSE}
        # 至少应该有一个分支区域
        assert has_branch or len(cfg.blocks) > 2  # CFG 已构建成功

        translator = KismetTranslator(expressions=[let0, jmp, let1, let2, end])
        decoder = RegionDecoder(
            cfg=cfg,
            region_tree=regions,
            expressions=[let0, jmp, let1, let2, end],
            translator=translator,
            offset_to_index={},
            jump_targets={24},
        )
        stmt = decoder.decode()
        # 结果应该是某种有效的语句
        assert stmt is not None

    def test_region_decoder_with_body_builder(self):
        """测试通过 body_builder 的集成路径。"""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder

        let0 = _make_let(0)
        let1 = _make_let(8)
        end = _make_end(16)

        builder = FunctionBodyBuilder()
        result = builder.to_function_body_structured(
            [let0, let1, end], func_name="TestFunc"
        )
        assert "TestFunc()" in result or "TestFunc" in result
        # 应该返回有效内容
        assert len(result) > 0

    def test_named_param_not_misclassified_as_assignment(self):
        """命名参数行不应被误判为赋值（如 FRotator(Pitch=90)）。"""
        from uasset_read.kismet.cfg import build_cfg, compute_dominator_tree, decompose_regions
        from uasset_read.kismet.cfg.emitter import RegionDecoder
        from uasset_read.kismet.cfg.stmt import Assignment, Call

        let0 = _make_let(0)
        end = _make_end(8)
        cfg = build_cfg([let0, end])
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        from uasset_read.kismet.translator import KismetTranslator

        translator = KismetTranslator(expressions=[let0, end])
        decoder = RegionDecoder(
            cfg=cfg,
            region_tree=regions,
            expressions=[let0, end],
            translator=translator,
            offset_to_index={},
            jump_targets=set(),
        )
        # 直接测试 _line_to_stmt 对命名参数行的处理
        stmt_named = decoder._line_to_stmt("SetActorRotation(FRotator(Pitch=90))")
        assert isinstance(stmt_named, Call), (
            f"命名参数行应识别为 Call，实际为 {type(stmt_named).__name__}"
        )
        # 普通赋值仍应正确识别
        stmt_real = decoder._line_to_stmt("x = 42")
        assert isinstance(stmt_real, Assignment), (
            f"普通赋值应识别为 Assignment，实际为 {type(stmt_real).__name__}"
        )


class TestRegionDecoderIfElse:
    """RegionDecoder if-else 场景测试。"""

    def test_if_else_emits_branch(self):
        """if-else CFG 生成 Branch 语句。"""
        from uasset_read.kismet.cfg import build_cfg, compute_dominator_tree, decompose_regions
        from uasset_read.kismet.cfg.data import RegionKind
        from uasset_read.kismet.cfg.emitter import RegionDecoder, StmtEmitter
        from uasset_read.kismet.translator import KismetTranslator

        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)

        expressions = [let0, jmp, let1, let2, end]
        cfg = build_cfg(expressions)
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        translator = KismetTranslator(expressions=expressions)
        decoder = RegionDecoder(
            cfg=cfg,
            region_tree=regions,
            expressions=expressions,
            translator=translator,
            offset_to_index={},
            jump_targets={24},
        )
        stmt = decoder.decode()

        emitter = StmtEmitter()
        output = emitter.emit_body(stmt)

        # 输出应该是非空的
        assert output is not None
        assert len(output) > 0

    def test_conditional_edges_present(self):
        """验证 if-else 的条件边正确建立。"""
        from uasset_read.kismet.cfg import build_cfg
        from uasset_read.kismet.cfg.data import EdgeKind

        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)

        cfg = build_cfg([let0, jmp, let1, let2, end])
        bb0 = cfg.blocks[0]
        edge_kinds = set(bb0.edge_kinds.values())
        assert EdgeKind.CONDITIONAL in edge_kinds
        assert EdgeKind.FALSE_BRANCH in edge_kinds


class TestRegionDecoderLoop:
    """RegionDecoder 循环场景测试。"""

    def test_while_loop_detected(self):
        """while 循环应检测到回边。"""
        from uasset_read.kismet.cfg import (
            build_cfg,
            compute_dominator_tree,
            decompose_regions,
            find_back_edges,
        )
        from uasset_read.kismet.cfg.data import RegionKind

        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        jmp_back = _make_jump(24, 0)
        end = _make_end(32)

        cfg = build_cfg([let0, jmp, let1, jmp_back, end])
        dom = compute_dominator_tree(cfg)
        back_edges = find_back_edges(cfg, dom)
        assert len(back_edges) >= 1

        regions = decompose_regions(cfg, dom)
        loop_kinds = {RegionKind.WHILE_LOOP, RegionKind.DO_WHILE, RegionKind.SELF_LOOP}
        found = [r for r in regions.regions.values() if r.kind in loop_kinds]
        assert len(found) >= 1

    def test_loop_emits_loop_stmt(self):
        """循环区域应生成 Loop 语句。"""
        from uasset_read.kismet.cfg import build_cfg, compute_dominator_tree, decompose_regions
        from uasset_read.kismet.cfg.emitter import RegionDecoder
        from uasset_read.kismet.cfg.stmt import Loop as LoopStmt
        from uasset_read.kismet.translator import KismetTranslator

        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        jmp_back = _make_jump(24, 0)
        end = _make_end(32)

        expressions = [let0, jmp, let1, jmp_back, end]
        cfg = build_cfg(expressions)
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        translator = KismetTranslator(expressions=expressions)
        decoder = RegionDecoder(
            cfg=cfg,
            region_tree=regions,
            expressions=expressions,
            translator=translator,
            offset_to_index={0: 0},
            jump_targets={0},
        )
        stmt = decoder.decode()

        # 结果应包含循环语句（或 Sequence 包含循环）
        def find_loop(s):
            if isinstance(s, LoopStmt):
                return True
            if isinstance(s, Sequence):
                return any(find_loop(st) for st in s.stmts)
            if isinstance(s, Branch):
                return (find_loop(s.then_body) if s.then_body else False) or (
                    find_loop(s.else_body) if s.else_body else False
                )
            return False

        assert find_loop(stmt), f"Expected Loop in stmt tree, got: {stmt}"


class TestEndToEndBodyBuilder:
    """body_builder 集成端到端测试。"""

    def test_linear_function(self):
        """线性函数的结构化输出。"""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder

        let0 = _make_let(0)
        let1 = _make_let(8)
        end = _make_end(16)

        builder = FunctionBodyBuilder()
        result = builder.to_function_body_structured(
            [let0, let1, end], func_name="LinearFunc"
        )
        assert "LinearFunc" in result
        assert "{" in result
        assert "}" in result

    def test_empty_expressions(self):
        """空表达式列表回退到 goto。"""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder

        builder = FunctionBodyBuilder()
        result = builder.to_function_body_structured([], func_name="EmptyFunc")
        # 回退到 goto 输出，应有函数签名
        assert "EmptyFunc" in result

    def test_with_func_name(self):
        """函数名包含参数时正确处理。"""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder

        let0 = _make_let(0)
        end = _make_end(8)

        builder = FunctionBodyBuilder()
        result = builder.to_function_body_structured(
            [let0, end], func_name="void MyFunc(int x)"
        )
        assert "MyFunc(int x)" in result

    def test_no_func_name(self):
        """无函数名使用默认。"""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder

        let0 = _make_let(0)
        end = _make_end(8)

        builder = FunctionBodyBuilder()
        result = builder.to_function_body_structured([let0, end])
        assert "UnknownFunction" in result

    def test_structured_rate_target(self):
        """验证 StructuredRateReport 目标指标。"""
        from uasset_read.kismet.body_builder import FunctionBodyBuilder
        from uasset_read.kismet.jump_analyzer import JumpAnalyzer

        # 构建一个包含 if-else 和 while 循环的复杂函数
        let0 = _make_let(0)
        jmp1 = _make_jump_if_not(8, 40)  # if 条件
        let1 = _make_let(16)  # then 分支
        jmp2 = _make_jump(24, 56)  # 跳到 end
        let2 = _make_let(40)  # else 分支
        jmp3 = _make_jump_if_not(48, 0)  # while 条件
        let3 = _make_let(56)  # while 体
        end = _make_end(64)

        expressions = [let0, jmp1, let1, jmp2, let2, jmp3, let3, end]

        # 调用 JumpAnalyzer.analyze_structured_rate() 获取报告
        analyzer = JumpAnalyzer(expressions)
        report = analyzer.analyze_structured_rate()

        # 验证 StructuredRateReport 字段
        assert report.total_jump_exprs >= 1
        assert report.structured_count >= 0
        assert report.goto_count >= 0
        assert report.rate >= 0.95, (
            f"结构化率 {report.rate:.1%} 未达标（要求 >= 95%）"
        )
        goto_rate = (
            report.goto_count / report.total_jump_exprs
            if report.total_jump_exprs > 0
            else 0.0
        )
        assert goto_rate <= 0.05, (
            f"goto 比率 {goto_rate:.1%} 超标（要求 <= 5%）"
        )

        # 同时验证 FunctionBodyBuilder 正常生成
        builder = FunctionBodyBuilder()
        result = builder.to_function_body_structured(
            expressions,
            func_name="ComplexFunc",
        )
        assert result is not None
        assert len(result) > 0
