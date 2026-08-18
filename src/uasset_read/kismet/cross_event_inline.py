"""Cross-event inlining optimization.

Analyzes multiple event handlers to identify shared code blocks
and reduce duplication in decompiled output.

This module detects common patterns across events:
- Identical code blocks that appear in multiple handlers
- Similar function calls with different parameters
- Shared setup/teardown sequences
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SharedBlock:
    """A code block shared across multiple events."""

    block_hash: str
    """Hash of the block's content for deduplication."""

    event_names: list[str] = field(default_factory=list)
    """Names of events containing this block."""

    expressions: list = field(default_factory=list)
    """The shared expression content."""

    similarity_score: float = 1.0
    """Similarity score (1.0 = identical, lower = similar)."""

    @property
    def event_count(self) -> int:
        return len(self.event_names)


@dataclass
class CrossEventResult:
    """Result of cross-event analysis."""

    shared_blocks: list[SharedBlock] = field(default_factory=list)
    total_events_analyzed: int = 0
    total_shared_blocks: int = 0

    @property
    def deduplication_potential(self) -> float:
        """Estimated percentage of code that could be deduplicated."""
        if self.total_events_analyzed <= 1:
            return 0.0
        return min(1.0, self.total_shared_blocks / max(1, self.total_events_analyzed))


def _hash_expressions(exprs: list) -> str:
    """Create a hash for a list of expressions."""
    import hashlib
    parts = []
    for expr in exprs:
        # Use expression class name and key attributes for hashing
        cls_name = type(expr).__name__
        value = getattr(expr, "Value", None) or getattr(expr, "Name", None) or ""
        parts.append(f"{cls_name}:{value}")
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def _compute_similarity(exprs_a: list, exprs_b: list) -> float:
    """Compute similarity score between two expression lists."""
    if not exprs_a or not exprs_b:
        return 0.0

    if len(exprs_a) != len(exprs_b):
        return 0.0

    matching = 0
    for a, b in zip(exprs_a, exprs_b):
        if type(a) == type(b):
            # Compare key attributes
            val_a = getattr(a, "Value", None) or getattr(a, "Name", None)
            val_b = getattr(b, "Value", None) or getattr(b, "Name", None)
            if val_a == val_b:
                matching += 1

    return matching / len(exprs_a)


def analyze_cross_event_sharing(events: list) -> CrossEventResult:
    """Analyze multiple events for shared code blocks.

    Args:
        events: List of event-like objects with name and expressions

    Returns:
        CrossEventResult with shared block information
    """
    result = CrossEventResult(total_events_analyzed=len(events))

    if len(events) <= 1:
        return result

    # Collect all blocks with their hashes
    block_hashes: dict[str, list[tuple[str, list]]] = {}

    for event in events:
        event_name = getattr(event, "name", "Unknown")
        expressions = getattr(event, "expressions", None) or []
        body_ir = getattr(event, "body_ir", None)
        if body_ir and not expressions:
            expressions = getattr(body_ir, "expressions", []) or []

        # Hash expression blocks (chunk into groups of 5 for better matching)
        chunk_size = 5
        for i in range(0, len(expressions), chunk_size):
            chunk = expressions[i:i + chunk_size]
            if len(chunk) < 2:
                continue
            block_hash = _hash_expressions(chunk)
            if block_hash not in block_hashes:
                block_hashes[block_hash] = []
            block_hashes[block_hash].append((event_name, chunk))

    # Find blocks shared across multiple events
    for block_hash, occurrences in block_hashes.items():
        unique_events = list(set(name for name, _ in occurrences))
        if len(unique_events) > 1:
            # Use first occurrence as representative
            representative = occurrences[0][1]
            result.shared_blocks.append(SharedBlock(
                block_hash=block_hash,
                event_names=unique_events,
                expressions=representative,
                similarity_score=1.0,
            ))

    result.total_shared_blocks = len(result.shared_blocks)
    return result


def format_cross_event_report(result: CrossEventResult) -> str:
    """Format cross-event analysis results as a readable report.

    Args:
        result: CrossEventResult from analyze_cross_event_sharing

    Returns:
        Formatted text report
    """
    lines: list[str] = [
        f"Cross-Event Analysis: {result.total_events_analyzed} events analyzed",
        f"Shared blocks found: {result.total_shared_blocks}",
        f"Deduplication potential: {result.deduplication_potential:.0%}",
        "",
    ]

    if not result.shared_blocks:
        lines.append("No shared code blocks detected.")
        return "\n".join(lines)

    for i, block in enumerate(result.shared_blocks[:10], 1):
        lines.append(f"  Block {i}: shared by {block.event_count} events")
        for event_name in block.event_names:
            lines.append(f"    - {event_name}")
        lines.append("")

    if len(result.shared_blocks) > 10:
        lines.append(f"  ... and {len(result.shared_blocks) - 10} more blocks")

    return "\n".join(lines)
