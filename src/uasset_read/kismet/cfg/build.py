from __future__ import annotations

"""CFG 构建器。

从 KismetExpression 序列构建基本块和控制流图。

算法:
1. Leader 识别: 跳转目标 + 跳转/结束语句后一条
2. 分配基本块: 每个 leader 是一个块的起点
3. 构建边: 根据跳转指令类型建立块间边
4. 合成 sink: 所有 fall-through 指向的终止块
"""


from typing import TYPE_CHECKING

from uasset_read.kismet.cfg.data import BasicBlock, CFG, EdgeKind

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression


def _get_statement_index(expr: KismetExpression) -> int | None:
    """获取表达式的语句索引。"""
    return getattr(expr, "StatementIndex", None)


def _get_code_offset(expr: KismetExpression) -> int | None:
    """获取跳转指令的目标偏移量。"""
    return getattr(expr, "CodeOffset", None)


def _get_token_name(expr: KismetExpression) -> str | None:
    """获取表达式的 token 名称。"""
    token = getattr(expr, "Token", None)
    if token is None:
        return None
    return token.name if hasattr(token, "name") else str(token)


def _is_terminator(expr: KismetExpression) -> bool:
    """判断表达式是否是基本块终结符。"""
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
    """判断是否是无条件跳转。"""
    name = _get_token_name(expr)
    if name is None:
        return False
    return name in {"EX_Jump", "EX_PopExecutionFlow", "EX_ComputedJump"}


def _is_conditional_jump(expr: KismetExpression) -> bool:
    """判断是否是条件跳转。"""
    name = _get_token_name(expr)
    if name is None:
        return False
    return name in {"EX_JumpIfNot", "EX_PopExecutionFlowIfNot"}


def _is_end_of_script(expr: KismetExpression) -> bool:
    """判断是否是脚本结束标记。"""
    return _get_token_name(expr) == "EX_EndOfScript"


def build_cfg(expressions: list[KismetExpression]) -> CFG:
    """从表达式列表构建控制流图。

    步骤:
    1. Leader 识别：跳转目标 + 跳转/结束语句后一条
    2. 分配基本块
    3. 构建边
    4. 添加合成 sink（EX_EndOfScript / fall-through）

    Args:
        expressions: 解析后的 Kismet 表达式列表。

    Returns:
        构建好的控制流图。
    """
    if not expressions:
        cfg = CFG()
        sink = BasicBlock(block_id=0, start_idx=0, end_idx=-1)
        cfg.add_block(sink)
        cfg.entry_id = 0
        cfg.exit_id = 0
        return cfg

    # --- Step 1: 构建偏移→索引映射，识别 leaders ---
    # 使用 StatementIndex 建立权威的 offset → expression index 映射。
    # CodeOffset 是跳转目标偏移，通过 offset_to_index 查找目标索引。
    offset_to_index: dict[int, int] = {}
    for idx, expr in enumerate(expressions):
        stmt_idx = _get_statement_index(expr)
        if stmt_idx is not None:
            offset_to_index[stmt_idx] = idx

    # 收集所有跳转目标偏移量
    jump_targets: set[int] = set()
    for expr in expressions:
        code_off = _get_code_offset(expr)
        if code_off is not None:
            jump_targets.add(code_off)

    # Leaders: 首条指令 + 跳转目标 + 跳转/结束语句的后一条
    leaders: set[int] = {0}
    for target_offset in jump_targets:
        if target_offset in offset_to_index:
            leaders.add(offset_to_index[target_offset])

    for idx, expr in enumerate(expressions):
        if _is_terminator(expr) and idx + 1 < len(expressions):
            leaders.add(idx + 1)

    # --- Step 2: 分配基本块 ---
    sorted_leaders = sorted(leaders)
    leader_to_block: dict[int, int] = {}
    block_id_counter = 0
    for leader in sorted_leaders:
        leader_to_block[leader] = block_id_counter
        block_id_counter += 1

    # 合成 sink block ID
    sink_block_id = block_id_counter

    # 确定每个块的起止范围
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

    # 合成 sink（空块，所有 fall-through 指向它）
    sink = BasicBlock(
        block_id=sink_block_id,
        start_idx=len(expressions),
        end_idx=len(expressions) - 1,
    )
    blocks[sink_block_id] = sink

    # --- Step 3: 构建边 ---
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
            # 连接到 sink
            if sink_block_id not in block.successors:
                block.successors.append(sink_block_id)
            if bid not in sink.predecessors:
                sink.predecessors.append(bid)
            block.edge_kinds[sink_block_id] = EdgeKind.UNCONDITIONAL

        else:
            # Fall-through 到下一条
            next_idx = block.end_idx + 1
            if next_idx < len(expressions) and next_idx in leader_to_block:
                next_bid = leader_to_block[next_idx]
                if next_bid not in block.successors:
                    block.successors.append(next_bid)
                if bid not in blocks[next_bid].predecessors:
                    blocks[next_bid].predecessors.append(bid)
                block.edge_kinds[next_bid] = EdgeKind.FALLTHROUGH
            elif next_idx >= len(expressions):
                # Fall-through 到 sink
                if sink_block_id not in block.successors:
                    block.successors.append(sink_block_id)
                if bid not in sink.predecessors:
                    sink.predecessors.append(bid)
                block.edge_kinds[sink_block_id] = EdgeKind.FALLTHROUGH

    # --- Step 4: 构建 CFG ---
    cfg = CFG(
        blocks=blocks,
        entry_id=leader_to_block[0],
        exit_id=sink_block_id,
    )
    return cfg
