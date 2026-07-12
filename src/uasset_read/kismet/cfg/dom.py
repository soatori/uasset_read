"""支配树计算。

实现 Cooper-Harvey-Kennedy (CHK) 迭代支配者算法。
参考: "A Simple, Fast Dominance Algorithm" (Cooper, Harvey, Kennedy, 2001)

该算法在大多数情况下 2-3 轮迭代即可收敛，时间复杂度接近 O(N)。
"""


from uasset_read.kismet.cfg.data import CFG, DominatorTree


def _reverse_postorder(cfg: CFG) -> list[int]:
    """计算 CFG 的逆后序 (reverse post-order)。

    逆后序保证：如果节点 A 支配 B，则 A 在逆后序中先于 B。
    这是 CHK 算法正确收敛的前提条件。
    """
    visited: set[int] = set()
    postorder: list[int] = []

    def dfs(bid: int) -> None:
        if bid in visited:
            return
        visited.add(bid)
        block = cfg.blocks.get(bid)
        if block is None:
            return
        for succ in block.successors:
            if succ in cfg.blocks:
                dfs(succ)
        postorder.append(bid)

    dfs(cfg.entry_id)
    return list(reversed(postorder))


def compute_dominator_tree(cfg: CFG) -> DominatorTree:
    """使用 Cooper-Harvey-Kennedy 算法计算支配树。

    算法步骤:
    1. 计算逆后序编号
    2. 初始化: entry 支配自身，其余未确定
    3. 迭代: 对每个节点，用 intersect 求前驱的最近公共支配者
    4. 直到无变化

    Args:
        cfg: 控制流图。

    Returns:
        支配树，包含 idom、dominators、dominated 和支配前沿。
    """
    rpo = _reverse_postorder(cfg)
    if not rpo:
        return DominatorTree()

    # 建立逆后序索引
    rpo_index: dict[int, int] = {bid: i for i, bid in enumerate(rpo)}

    # 初始化 idom
    idom: dict[int, int | None] = {}
    for bid in rpo:
        idom[bid] = None
    idom[cfg.entry_id] = cfg.entry_id  # type: ignore[assignment]

    def _intersect(b1: int, b2: int) -> int | None:
        """求 b1 和 b2 的最近公共支配者。"""
        finger1 = b1
        finger2 = b2
        while finger1 != finger2:
            if finger1 is None or finger2 is None:
                return None
            idx1 = rpo_index.get(finger1, -1)
            idx2 = rpo_index.get(finger2, -1)
            if idx1 < 0 or idx2 < 0:
                return None
            while idx1 > idx2:
                finger1 = idom.get(finger1)
                if finger1 is None:
                    return None
                idx1 = rpo_index.get(finger1, -1)
            while idx2 > idx1:
                finger2 = idom.get(finger2)
                if finger2 is None:
                    return None
                idx2 = rpo_index.get(finger2, -1)
        return finger1

    # 迭代求解
    changed = True
    while changed:
        changed = False
        for bid in rpo:
            if bid == cfg.entry_id:
                continue

            block = cfg.blocks.get(bid)
            if block is None:
                continue

            # 找到第一个已确定的前驱
            new_idom: int | None = None
            for pred in block.predecessors:
                if pred in idom and idom[pred] is not None:
                    new_idom = pred
                    break

            if new_idom is None:
                continue

            # 与其余前驱取 intersect
            for pred in block.predecessors:
                if pred == bid:
                    continue
                if pred not in rpo_index:
                    continue
                if pred not in idom or idom[pred] is None:
                    continue
                intersected = _intersect(new_idom, pred)
                if intersected is not None:
                    new_idom = intersected

            if new_idom != idom.get(bid):
                idom[bid] = new_idom
                changed = True

    # 构建完整支配集合: 从每个节点沿 idom 链向上收集
    dominators: dict[int, set[int]] = {}
    for bid in rpo:
        chain: set[int] = set()
        node: int | None = bid
        visited_nodes: set[int] = set()
        while node is not None and node not in visited_nodes:
            visited_nodes.add(node)
            chain.add(node)
            parent = idom.get(node)
            if parent is None or parent == node:
                break
            node = parent
        dominators[bid] = chain

    # 构建被支配集合
    dominated: dict[int, set[int]] = {bid: set() for bid in rpo}
    for bid in rpo:
        for d in dominators.get(bid, set()):
            if d != bid:
                dominated.setdefault(d, set()).add(bid)

    # 计算支配前沿
    frontiers: dict[int, set[int]] = {bid: set() for bid in rpo}

    for bid in rpo:
        block = cfg.blocks.get(bid)
        if block is None:
            continue
        if len(block.predecessors) < 2:
            continue
        # 多前驱块: 检查每个前驱的 runner
        for pred in block.predecessors:
            if pred not in rpo_index:
                continue
            runner = pred
            idom_bid = idom.get(bid)
            while runner != idom_bid and runner is not None:
                runner_idx = rpo_index.get(runner, -1)
                if runner_idx < 0:
                    break
                frontiers.setdefault(runner, set()).add(bid)
                runner_parent = idom.get(runner)
                if runner_parent is None:
                    break
                runner = runner_parent

    result = DominatorTree(
        idom=idom,
        dominators=dominators,
        dominated=dominated,
    )
    result._frontiers = frontiers  # type: ignore[attr-defined]
    return result
