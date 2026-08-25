"""SESE region decomposition.

Decomposes CFG into structured regions (Single-Entry Single-Exit) based on
dominator tree and back edge identification.

Algorithm:
1. Identify back edges
2. Create loop regions for each back edge
3. Create if-then / if-then-else regions for branches
4. Remaining blocks form BLOCK regions
5. Assemble region tree
"""


from uasset_read.kismet.cfg.data import (
    CFG,
    DominatorTree,
    RegionKind,
)


def find_back_edges(cfg: CFG, dom_tree: DominatorTree) -> list[tuple[int, int]]:
    """Identify all back edges.

    Back edge definition: edge (src, dst) is a back edge if the destination
    node dominates the source node.

    Args:
        cfg: Control flow graph.
        dom_tree: Dominator tree.

    Returns:
        List of back edges, each as (source_id, destination_id).
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
    """Compute all blocks in the loop body defined by a back edge.

    Reverse BFS from back_edge_src until back_edge_dst.

    Args:
        cfg: Control flow graph.
        back_edge_src: Back edge source node (jump statement block inside loop body).
        back_edge_dst: Back edge destination node (loop head).

    Returns:
        Set of block IDs in the loop body.
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
    """Classify loop type.

    - SELF_LOOP: back_edge_dst is the only block (self-loop)
    - WHILE_LOOP: back_edge_dst (head) has external predecessor
    - DO_WHILE: back_edge_dst has no external predecessor (all predecessors in loop body)

    Args:
        cfg: Control flow graph.
        loop_blocks: Set of loop body block IDs.
        back_edge_src: Back edge source.
        back_edge_dst: Back edge destination.

    Returns:
        Loop type.
    """
    if len(loop_blocks) == 1 and back_edge_src == back_edge_dst:
        return RegionKind.SELF_LOOP

    head_block = cfg.blocks.get(back_edge_dst)
    if head_block is None:
        return RegionKind.WHILE_LOOP

    # Check if head has external predecessor (pre-header)
    head_has_external_pred = any(
        pred not in loop_blocks for pred in head_block.predecessors
    )

    if head_has_external_pred:
        return RegionKind.WHILE_LOOP
    return RegionKind.DO_WHILE


