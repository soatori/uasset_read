"""Standard/debug projection — the only mode boundary.

``project_semantic(ir, "standard")`` recursively removes evidence fields.
``project_semantic(ir, "debug")`` is a passthrough. Domain extractors always
emit debug evidence; this module is the single place that prunes it.

Contract: ``project_semantic(build_semantic_ir(pkg), "standard")``
must produce the same result as ``build_semantic_ir(pkg)`` stamped with
``mode="standard"`` (for fields controlled by the common model; domain
content is exempt).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from uasset_read.semantic.models import SemanticIR

_VALID_MODES = {"standard", "debug"}


def _recursive_strip_evidence(data: Any) -> Any:
    """Recursively remove evidence keys from nested structures."""
    if isinstance(data, dict):
        return {k: _recursive_strip_evidence(v) for k, v in data.items() if k != "evidence"}
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
    if mode not in _VALID_MODES:
        raise ValueError(f"Invalid mode: expected one of {_VALID_MODES}, got '{mode}'")

    if mode == "debug":
        return replace(ir, mode="debug")

    return replace(ir, mode="standard", content=_recursive_strip_evidence(ir.content), evidence=())
