"""SESE 区域分解。

基于支配树和回边识别，将 CFG 划分为结构化区域 (Single-Entry Single-Exit)。

算法:
1. 识别回边 (back edges)
2. 为每条回边创建循环区域
3. 为分支创建 if-then / if-then-else 区域
4. 剩余块形成 BLOCK 区域
5. 组装区域树
"""


from uasset_read.kismet.cfg.data import (
    CFG,
    DominatorTree,
    EdgeKind,
    Region,
    RegionKind,
    RegionTree,
)


def find_back_edges(cfg: CFG, dom_tree: DominatorTree) -> list[tuple[int, int]]:
    """识别所有回边。

    回边定义: 如果目标节点支配源节点，则边 (src, dst) 是回边。

    Args:
        cfg: 控制流图。
        dom_tree: 支配树。

    Returns:
        回边列表，每条回边为 (source_id, destination_id)。
    """
    back_edges: list[tuple[int, int]] = []
    for bid, block in cfg.blocks.items():
        for succ in block.successors:
            if succ in cfg.blocks and dom_tree.is_dominator(succ, bid):
                back_edges.append((bid, succ))
    return back_edges


def compute_loop_blocks(
    cfg: CFG,
    back_edge_src: int,
    back_edge_dst: int,
) -> set[int]:
    """计算回边定义的循环体所有块。

    从 back_edge_src 开始反向 BFS，直到 back_edge_dst。

    Args:
        cfg: 控制流图。
        back_edge_src: 回边源节点（循环体内的跳转语句块）。
        back_edge_dst: 回边目标节点（循环头）。

    Returns:
        循环体内所有块的 ID 集合。
    """
    loop_blocks: set[int] = {back_edge_dst}
    worklist: list[int] = [back_edge_src]

    while worklist:
        bid = worklist.pop()
        if bid in loop_blocks:
            continue
        loop_blocks.add(bid)
        block = cfg.blocks.get(bid)
        if block is None:
            continue
        for pred in block.predecessors:
            if pred not in loop_blocks:
                worklist.append(pred)

    return loop_blocks


def classify_loop(
    cfg: CFG,
    loop_blocks: set[int],
    back_edge_src: int,
    back_edge_dst: int,
) -> RegionKind:
    """分类循环类型。

    - SELF_LOOP: back_edge_dst 是唯一块（自环）
    - WHILE_LOOP: back_edge_dst (head) 有外部前驱
    - DO_WHILE: back_edge_dst 无外部前驱（所有前驱都在循环体内）

    Args:
        cfg: 控制流图。
        loop_blocks: 循环体块集合。
        back_edge_src: 回边源。
        back_edge_dst: 回边目标。

    Returns:
        循环类型。
    """
    if len(loop_blocks) == 1 and back_edge_src == back_edge_dst:
        return RegionKind.SELF_LOOP

    head_block = cfg.blocks.get(back_edge_dst)
    if head_block is None:
        return RegionKind.WHILE_LOOP

    # 检查 head 是否有外部前驱（pre-header）
    head_has_external_pred = any(
        pred not in loop_blocks for pred in head_block.predecessors
    )

    if head_has_external_pred:
        return RegionKind.WHILE_LOOP
    else:
        return RegionKind.DO_WHILE


def decompose_regions(
    cfg: CFG,
    dom_tree: DominatorTree,
) -> RegionTree:
    """将 CFG 分解为 SESE 区域。

    步骤:
    1. 识别回边
    2. 为每条回边创建循环区域
    3. 为分支创建 if-then / if-then-else 区域
    4. 剩余块形成 BLOCK 区域
    5. 组装区域树

    Args:
        cfg: 控制流图。
        dom_tree: 支配树。

    Returns:
        区域树。
    """
    region_tree = RegionTree()
    region_id_counter = 0

    # --- Step 1: 识别回边 ---
    back_edges = find_back_edges(cfg, dom_tree)

    # --- Step 2: 创建循环区域 ---
    loop_blocks_used: set[int] = set()

    for src, dst in back_edges:
        loop_body = compute_loop_blocks(cfg, src, dst)
        loop_kind = classify_loop(cfg, loop_body, src, dst)

        region = Region(
            region_id=region_id_counter,
            kind=loop_kind,
            head=dst,
            tail=src,
            body_blocks=sorted(loop_body),
            loop_back_edges=[(src, dst)],
        )
        region_tree.add_region(region)
        loop_blocks_used.update(loop_body)
        region_id_counter += 1

    # --- Step 3: 为分支创建区域 ---
    for bid, block in cfg.blocks.items():
        if bid in loop_blocks_used:
            continue
        if bid == cfg.exit_id:
            continue
        if not block.successors:
            continue

        if len(block.successors) == 2:
            s0, s1 = block.successors[0], block.successors[1]
            kind0 = block.edge_kinds.get(s0)
            kind1 = block.edge_kinds.get(s1)

            # 判断 then/else 分支
            then_block: int = -1
            else_block: int = -1

            if kind0 == EdgeKind.CONDITIONAL:
                then_block, else_block = s0, s1
            elif kind1 == EdgeKind.CONDITIONAL:
                then_block, else_block = s1, s0
            elif kind0 == EdgeKind.FALSE_BRANCH:
                else_block, then_block = s0, s1
            elif kind1 == EdgeKind.FALSE_BRANCH:
                else_block, then_block = s1, s0

            if then_block >= 0 and else_block >= 0:
                # 检查两个分支是否汇合
                then_b = cfg.blocks.get(then_block)
                else_b = cfg.blocks.get(else_block)
                then_succs = set(then_b.successors) if then_b else set()
                else_succs = set(else_b.successors) if else_b else set()
                join = then_succs & else_succs

                if join:
                    join_id = next(iter(join))
                    region = Region(
                        region_id=region_id_counter,
                        kind=RegionKind.IF_THEN_ELSE,
                        head=bid,
                        tail=join_id,
                        body_blocks=[bid, then_block, else_block, join_id],
                        exit_blocks=[join_id],
                    )
                    region_tree.add_region(region)
                    region_id_counter += 1
                else:
                    # if-then（无 else 或 else 到 sink）
                    region = Region(
                        region_id=region_id_counter,
                        kind=RegionKind.IF_THEN,
                        head=bid,
                        tail=else_block if else_b else bid,
                        body_blocks=[bid, then_block, else_block],
                        exit_blocks=[else_block] if else_b else [],
                    )
                    region_tree.add_region(region)
                    region_id_counter += 1

    # --- Step 4: 剩余块作为 BLOCK 区域 ---
    for bid in sorted(cfg.blocks.keys()):
        if bid == cfg.exit_id:
            continue
        already_covered = any(
            bid in r.body_blocks for r in region_tree.regions.values()
        )
        if not already_covered:
            region = Region(
                region_id=region_id_counter,
                kind=RegionKind.BLOCK,
                head=bid,
                tail=bid,
                body_blocks=[bid],
            )
            region_tree.add_region(region)
            region_id_counter += 1

    # --- Step 5: 设置 root ---
    entry_region = None
    for region in region_tree.regions.values():
        if cfg.entry_id in region.body_blocks:
            entry_region = region
            break

    if entry_region is None:
        all_blocks = sorted(cfg.blocks.keys())
        entry_region = Region(
            region_id=region_id_counter,
            kind=RegionKind.BLOCK,
            head=cfg.entry_id,
            tail=cfg.exit_id,
            body_blocks=all_blocks,
        )
        region_tree.add_region(entry_region)
        region_id_counter += 1

    region_tree.root_id = entry_region.region_id
    return region_tree
