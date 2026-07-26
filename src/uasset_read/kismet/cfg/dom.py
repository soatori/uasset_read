"""Dominator tree computation.

Implements the Cooper-Harvey-Kennedy (CHK) iterative dominator algorithm.
Reference: "A Simple, Fast Dominance Algorithm" (Cooper, Harvey, Kennedy, 2001)

The algorithm converges in 2-3 iterations in most cases, with near O(N) time complexity.
"""


from uasset_read.kismet.cfg.data import CFG, DominatorTree


def _reverse_postorder(cfg: CFG) -> list[int]:
    """Compute the reverse post-order of the CFG.

    Reverse post-order guarantees: if node A dominates B, then A precedes B
    in the reverse post-order. This is a prerequisite for correct CHK convergence.
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
    """Compute dominator tree using Cooper-Harvey-Kennedy algorithm.

    Algorithm steps:
    1. Compute reverse post-order numbering
    2. Initialize: entry dominates itself, others undefined
    3. Iterate: for each node, use intersect to find nearest common dominator of predecessors
    4. Until no changes

    Args:
        cfg: Control flow graph.

    Returns:
        Dominator tree containing idom, dominators, dominated, and dominator frontiers.
    """
    rpo = _reverse_postorder(cfg)
    if not rpo:
        return DominatorTree()

    # Build reverse post-order index
    rpo_index: dict[int, int] = {bid: i for i, bid in enumerate(rpo)}

    # Initialize idom
    idom: dict[int, int | None] = {}
    for bid in rpo:
        idom[bid] = None
    idom[cfg.entry_id] = cfg.entry_id  # type: ignore[assignment]

    def _intersect(b1: int, b2: int) -> int | None:
        """Find the nearest common dominator of b1 and b2."""
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

    # Iterative solving
    changed = True
    while changed:
        changed = False
        for bid in rpo:
            if bid == cfg.entry_id:
                continue

            block = cfg.blocks.get(bid)
            if block is None:
                continue

            # Find first predecessor with known dominator
            new_idom: int | None = None
            for pred in block.predecessors:
                if pred in idom and idom[pred] is not None:
                    new_idom = pred
                    break

            if new_idom is None:
                continue

            # Intersect with remaining predecessors
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

    # Build full dominance sets: collect from each node up the idom chain
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

    # Build dominated sets
    dominated: dict[int, set[int]] = {bid: set() for bid in rpo}
    for bid in rpo:
        for d in dominators.get(bid, set()):
            if d != bid:
                dominated.setdefault(d, set()).add(bid)

    # Compute dominator frontiers
    frontiers: dict[int, set[int]] = {bid: set() for bid in rpo}

    for bid in rpo:
        block = cfg.blocks.get(bid)
        if block is None:
            continue
        if len(block.predecessors) < 2:
            continue
        # Multi-predecessor block: check runner for each predecessor
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
