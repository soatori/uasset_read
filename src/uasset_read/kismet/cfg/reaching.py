"""Reaching conditions analysis.

Computes the boolean conditions that must hold to reach each basic block
in the CFG. Useful for understanding control flow paths and generating
condition guards in decompiled output.

Algorithm: Forward dataflow analysis with symbolic conditions.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ReachingCondition:
    """Condition that must hold to reach a specific block."""

    block_id: int
    condition: str
    """Symbolic boolean expression (e.g. "cond_x", "!cond_x & cond_y")."""

    @property
    def is_entry(self) -> bool:
        """True if this is the entry block (no condition)."""
        return self.condition == "true"


@dataclass
class ReachingConditions:
    """Result of reaching conditions analysis."""

    conditions: dict[int, ReachingCondition] = field(default_factory=dict)

    def get(self, block_id: int) -> Optional[ReachingCondition]:
        """Get reaching condition for a block."""
        return self.conditions.get(block_id)

    def get_condition(self, block_id: int) -> str:
        """Get condition string for a block (default: 'true')."""
        cond = self.conditions.get(block_id)
        return cond.condition if cond else "true"


def compute_reaching_conditions(cfg) -> ReachingConditions:
    """Compute reaching conditions for all blocks in the CFG.

    For each block, determines the boolean condition that must be true
    for execution to reach that block. The entry block always has condition "true".

    Algorithm:
    1. Entry block: condition = "true"
    2. For each edge (A -> B):
       - If edge is TRUE_BRANCH: B's condition includes A's condition & cond
       - If edge is FALSE_BRANCH: B's condition includes A's condition & !cond
       - If edge is UNCONDITIONAL/FALLTHROUGH: B's condition = A's condition
    3. Merge conditions at join points using OR (any path reaching the block)

    Args:
        cfg: Control flow graph (CFG instance)

    Returns:
        ReachingConditions with conditions for all blocks
    """
    from uasset_read.kismet.cfg.data import EdgeKind

    result = ReachingConditions()

    if not cfg.blocks:
        return result

    # Entry block has trivial condition
    result.conditions[cfg.entry_id] = ReachingCondition(
        block_id=cfg.entry_id,
        condition="true",
    )

    # Process blocks in topological order (block_id order works for most CFGs)
    for bid in sorted(cfg.blocks.keys()):
        if bid == cfg.entry_id:
            continue

        block = cfg.blocks.get(bid)
        if block is None:
            continue

        # Collect conditions from all predecessors
        incoming_conditions: list[str] = []

        for pred_id in block.predecessors:
            pred_block = cfg.blocks.get(pred_id)
            if pred_block is None:
                continue

            pred_cond = result.conditions.get(pred_id)
            pred_cond_str = pred_cond.condition if pred_cond else "true"

            # Determine edge condition
            edge_kind = pred_block.edge_kinds.get(bid)
            if edge_kind == EdgeKind.TRUE_BRANCH:
                # This block is reached when condition is TRUE
                incoming_conditions.append(pred_cond_str)
            elif edge_kind == EdgeKind.FALSE_BRANCH:
                # This block is reached when condition is FALSE
                incoming_conditions.append(f"!({pred_cond_str})")
            elif edge_kind == EdgeKind.BACK_EDGE:
                # Back edge (loop) — skip to avoid infinite loops
                continue
            else:
                # Unconditional / fallthrough
                incoming_conditions.append(pred_cond_str)

        if not incoming_conditions:
            # No known predecessors — may be unreachable
            condition = "unreachable"
        elif len(incoming_conditions) == 1:
            condition = incoming_conditions[0]
        else:
            # Multiple paths: OR the conditions
            condition = " | ".join(f"({c})" for c in incoming_conditions)

        result.conditions[bid] = ReachingCondition(
            block_id=bid,
            condition=condition,
        )

    return result
