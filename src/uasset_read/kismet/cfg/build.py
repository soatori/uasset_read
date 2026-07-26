from __future__ import annotations

"""CFG builder.

Builds basic blocks and control flow graphs from KismetExpression sequences.

Algorithm:
1. Leader identification: jump targets + instruction after jump/termination statements
2. Assign basic blocks: each leader is the start of a block
3. Build edges: construct inter-block edges based on jump instruction types
4. Synthetic sink: the terminal block that all fall-throughs point to
"""


from typing import TYPE_CHECKING

from uasset_read.kismet.cfg.data import BasicBlock, CFG, EdgeKind

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression


def _get_statement_index(expr: KismetExpression) -> int | None:
    """Get the statement index of the expression."""
    return getattr(expr, "StatementIndex", None)


def _get_code_offset(expr: KismetExpression) -> int | None:
    """Get the target offset of the jump instruction."""
    return getattr(expr, "CodeOffset", None)


def _get_token_name(expr: KismetExpression) -> str | None:
    """Get the token name of the expression."""
    token = getattr(expr, "Token", None)
    if token is None:
        return None
    return token.name if hasattr(token, "name") else str(token)


def _is_terminator(expr: KismetExpression) -> bool:
    """Determine if the expression is a basic block terminator."""
    name = _get_token_name(expr)
    if name is None:
        return False
    return name in {
        "EX_Jump",
        "EX_JumpIfNot",
        "EX_EndOfScript",
        "EX_PopExecutionFlow",
        "EX_PopExecutionFlowIfNot",
        "EX_ComputedJump",
    }


def _is_unconditional_jump(expr: KismetExpression) -> bool:
    """Determine if this is an unconditional jump."""
    name = _get_token_name(expr)
    if name is None:
        return False
    return name in {"EX_Jump", "EX_PopExecutionFlow", "EX_ComputedJump"}


def _is_conditional_jump(expr: KismetExpression) -> bool:
    """Determine if this is a conditional jump."""
    name = _get_token_name(expr)
    if name is None:
        return False
    return name in {"EX_JumpIfNot", "EX_PopExecutionFlowIfNot"}


def _is_end_of_script(expr: KismetExpression) -> bool:
    """Determine if this is an end-of-script marker."""
    return _get_token_name(expr) == "EX_EndOfScript"


def build_cfg(expressions: list[KismetExpression]) -> CFG:
    """Build a control flow graph from a list of expressions.

    Steps:
    1. Leader identification: jump targets + instruction after jump/termination statements
    2. Assign basic blocks
    3. Build edges
    4. Add synthetic sink (EX_EndOfScript / fall-through)

    Args:
        expressions: Parsed Kismet expression list.

    Returns:
        The constructed control flow graph.
    """
    if not expressions:
        cfg = CFG()
        sink = BasicBlock(block_id=0, start_idx=0, end_idx=-1)
        cfg.add_block(sink)
        cfg.entry_id = 0
        cfg.exit_id = 0
        return cfg

    # --- Step 1: Build offset→index mapping, identify leaders ---
    # Use StatementIndex to build authoritative offset → expression index mapping.
    # CodeOffset is jump target offset, look up target index via offset_to_index.
    offset_to_index: dict[int, int] = {}
    for idx, expr in enumerate(expressions):
        stmt_idx = _get_statement_index(expr)
        if stmt_idx is not None:
            offset_to_index[stmt_idx] = idx

    # Collect all jump target offsets
    jump_targets: set[int] = set()
    for expr in expressions:
        code_off = _get_code_offset(expr)
        if code_off is not None:
            jump_targets.add(code_off)

    # Leaders: first instruction + jump targets + instruction after jump/termination
    leaders: set[int] = {0}
    for target_offset in jump_targets:
        if target_offset in offset_to_index:
            leaders.add(offset_to_index[target_offset])

    for idx, expr in enumerate(expressions):
        if _is_terminator(expr) and idx + 1 < len(expressions):
            leaders.add(idx + 1)

    # --- Step 2: Assign basic blocks ---
    sorted_leaders = sorted(leaders)
    leader_to_block: dict[int, int] = {}
    block_id_counter = 0
    for leader in sorted_leaders:
        leader_to_block[leader] = block_id_counter
        block_id_counter += 1

    # Synthetic sink block ID
    sink_block_id = block_id_counter

    # Determine start/end range for each block
    blocks: dict[int, BasicBlock] = {}
    leader_list = sorted(leader_to_block.keys())
    for i, leader_idx in enumerate(leader_list):
        bid = leader_to_block[leader_idx]
        if i + 1 < len(leader_list):
            end_idx = leader_list[i + 1] - 1
        else:
            end_idx = len(expressions) - 1

        end_idx = min(end_idx, len(expressions) - 1)

        block = BasicBlock(
            block_id=bid,
            start_idx=leader_idx,
            end_idx=end_idx,
            expressions=expressions[leader_idx : end_idx + 1],
        )
        blocks[bid] = block

    # Synthetic sink (empty block, all fall-throughs point to it)
    sink = BasicBlock(
        block_id=sink_block_id,
        start_idx=len(expressions),
        end_idx=len(expressions) - 1,
    )
    blocks[sink_block_id] = sink

    # --- Step 3: Build edges ---
    for bid, block in blocks.items():
        if bid == sink_block_id:
            continue

        last_expr = expressions[block.end_idx]

        if _is_unconditional_jump(last_expr):
            code_off = _get_code_offset(last_expr)
            if code_off is not None and code_off in offset_to_index:
                target_idx = offset_to_index[code_off]
                if target_idx in leader_to_block:
                    target_bid = leader_to_block[target_idx]
                    if target_bid not in block.successors:
                        block.successors.append(target_bid)
                    if bid not in blocks[target_bid].predecessors:
                        blocks[target_bid].predecessors.append(bid)
                    block.edge_kinds[target_bid] = EdgeKind.UNCONDITIONAL

        elif _is_conditional_jump(last_expr):
            code_off = _get_code_offset(last_expr)
            # False branch → jump target
            if code_off is not None and code_off in offset_to_index:
                target_idx = offset_to_index[code_off]
                if target_idx in leader_to_block:
                    target_bid = leader_to_block[target_idx]
                    if target_bid not in block.successors:
                        block.successors.append(target_bid)
                    if bid not in blocks[target_bid].predecessors:
                        blocks[target_bid].predecessors.append(bid)
                    block.edge_kinds[target_bid] = EdgeKind.FALSE_BRANCH

            # True branch → fall-through (next block)
            next_leader_idx = block.end_idx + 1
            if next_leader_idx in leader_to_block:
                next_bid = leader_to_block[next_leader_idx]
                if next_bid not in block.successors:
                    block.successors.append(next_bid)
                if bid not in blocks[next_bid].predecessors:
                    blocks[next_bid].predecessors.append(bid)
                block.edge_kinds[next_bid] = EdgeKind.TRUE_BRANCH

        elif _is_end_of_script(last_expr):
            # Connect to sink
            if sink_block_id not in block.successors:
                block.successors.append(sink_block_id)
            if bid not in sink.predecessors:
                sink.predecessors.append(bid)
            block.edge_kinds[sink_block_id] = EdgeKind.UNCONDITIONAL

        else:
            # Fall-through to next
            next_idx = block.end_idx + 1
            if next_idx < len(expressions) and next_idx in leader_to_block:
                next_bid = leader_to_block[next_idx]
                if next_bid not in block.successors:
                    block.successors.append(next_bid)
                if bid not in blocks[next_bid].predecessors:
                    blocks[next_bid].predecessors.append(bid)
                block.edge_kinds[next_bid] = EdgeKind.FALLTHROUGH
            elif next_idx >= len(expressions):
                # Fall-through to sink
                if sink_block_id not in block.successors:
                    block.successors.append(sink_block_id)
                if bid not in sink.predecessors:
                    sink.predecessors.append(bid)
                block.edge_kinds[sink_block_id] = EdgeKind.FALLTHROUGH

    # --- Step 4: Build CFG ---
    cfg = CFG(
        blocks=blocks,
        entry_id=leader_to_block[0],
        exit_id=sink_block_id,
    )
    return cfg
