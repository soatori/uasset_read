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
    EdgeKind,
    Region,
    RegionKind,
    RegionTree,
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


def decompose_regions(
    cfg: CFG,
    dom_tree: DominatorTree,
) -> RegionTree:
    """Decompose CFG into SESE regions.

    Steps:
    1. Identify back edges
    2. Create loop regions for each back edge
    3. Create if-then / if-then-else regions for branches
    4. Remaining blocks form BLOCK regions
    5. Assemble region tree

    Args:
        cfg: Control flow graph.
        dom_tree: Dominator tree.

    Returns:
        Region tree.
    """
    region_tree = RegionTree()
    region_id_counter = 0

    # --- Step 1: Identify back edges ---
    back_edges = find_back_edges(cfg, dom_tree)

    # --- Step 2: Create loop regions ---
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

    # --- Step 3: Create branch regions ---
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

            # Determine then/else branches
            then_block: int = -1
            else_block: int = -1

            if kind0 == EdgeKind.TRUE_BRANCH:
                then_block, else_block = s0, s1
            elif kind1 == EdgeKind.TRUE_BRANCH:
                then_block, else_block = s1, s0
            elif kind0 == EdgeKind.FALSE_BRANCH:
                else_block, then_block = s0, s1
            elif kind1 == EdgeKind.FALSE_BRANCH:
                else_block, then_block = s1, s0

            if then_block >= 0 and else_block >= 0:
                # Check if two branches join
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
                    # if-then (no else or else goes to sink)
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

    # --- Step 4: Remaining blocks as BLOCK regions ---
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

    # --- Step 5: Set root ---
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
