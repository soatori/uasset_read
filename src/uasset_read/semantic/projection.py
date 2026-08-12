"""Standard/debug projection — the only mode boundary.

``project_semantic(ir, "standard")`` recursively removes evidence and debug
extension fields. ``project_semantic(ir, "debug")`` is a passthrough.

Contract: ``project_semantic(build_semantic_ir(pkg), "standard")``
must produce the same result as ``build_semantic_ir(pkg)`` stamped with
``mode="standard"`` (for fields controlled by the common model; domain
content is exempt).
"""
from __future__ import annotations

from uasset_read.semantic.models import SemanticIR


def project_semantic(ir: SemanticIR, mode: str) -> SemanticIR:
    """Project a SemanticIR to the target mode.

    Args:
        ir: Source SemanticIR (any mode)
        mode: Target mode — "standard" or "debug"

    Returns:
        New SemanticIR with the target mode applied.
    """
    if mode == ir.mode:
        return ir

    if mode == "standard":
        return SemanticIR(
            format=ir.format,
            format_version=ir.format_version,
            mode="standard",
            asset_type=ir.asset_type,
            asset=ir.asset,
            status=ir.status,
            references=ir.references,
            content=ir.content,
            coverage=ir.coverage,
            diagnostics=ir.diagnostics,
            evidence=(),  # strip all evidence
        )

    # debug — passthrough (evidence already present if built in debug mode)
    return SemanticIR(
        format=ir.format,
        format_version=ir.format_version,
        mode="debug",
        asset_type=ir.asset_type,
        asset=ir.asset,
        status=ir.status,
        references=ir.references,
        content=ir.content,
        coverage=ir.coverage,
        diagnostics=ir.diagnostics,
        evidence=ir.evidence,
    )
