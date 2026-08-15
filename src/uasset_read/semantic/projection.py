"""Standard/debug projection — the only mode boundary.

``project_semantic(ir, "standard")`` recursively removes evidence and debug
extension fields. ``project_semantic(ir, "debug")`` is a passthrough.

Contract: ``project_semantic(build_semantic_ir(pkg), "standard")``
must produce the same result as ``build_semantic_ir(pkg)`` stamped with
``mode="standard"`` (for fields controlled by the common model; domain
content is exempt).
"""
from __future__ import annotations

from typing import Any

from uasset_read.semantic.models import SemanticIR


def _recursive_strip_evidence(data: Any) -> Any:
    """Recursively remove evidence and extensions keys from nested structures."""
    if isinstance(data, dict):
        return {
            k: _recursive_strip_evidence(v)
            for k, v in data.items()
            if k not in ("evidence", "extensions")
        }
    if isinstance(data, list):
        return [_recursive_strip_evidence(item) for item in data]
    return data


def project_semantic(ir: SemanticIR, mode: str) -> SemanticIR:
    """Project a SemanticIR to the target mode.

    Args:
        ir: Source SemanticIR (any mode)
        mode: Target mode — "standard" or "debug"

    Returns:
        New SemanticIR with the target mode applied.
    """
    _VALID_MODES = {"standard", "debug"}
    if mode not in _VALID_MODES:
        raise ValueError(f"Invalid mode: expected one of {_VALID_MODES}, got '{mode}'")

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
            content=_recursive_strip_evidence(ir.content),
            coverage=ir.coverage,
            diagnostics=ir.diagnostics,
            evidence=(),
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
