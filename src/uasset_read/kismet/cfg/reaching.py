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



@dataclass
class ReachingConditions:
    """Result of reaching conditions analysis."""

    conditions: dict[int, ReachingCondition] = field(default_factory=dict)

    def get(self, block_id: int) -> Optional[ReachingCondition]:
        """Get reaching condition for a block."""
        return self.conditions.get(block_id)



