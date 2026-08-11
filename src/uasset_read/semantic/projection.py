"""Debug -> standard projection.

Projects a debug-mode SemanticIR to standard mode by:
1. Setting mode to "standard"
2. Preserving all data fields (asset, references, content, coverage, diagnostics)

This module is NOT called automatically in the render pipeline.
It is provided for callers who need to downgrade debug output to standard format.

Usage:
    from uasset_read.semantic.projection import project_debug
    standard_ir = project_debug(debug_ir)
"""
from __future__ import annotations

from uasset_read.semantic.ir import SemanticIR


def project_debug(debug_ir: SemanticIR) -> SemanticIR:
    """Project a debug-mode SemanticIR to standard mode.

    Args:
        debug_ir: SemanticIR with mode="debug"

    Returns:
        SemanticIR with mode="standard" and identical data fields
    """
    return SemanticIR(
        format=debug_ir.format,
        format_version=debug_ir.format_version,
        mode="standard",
        asset=debug_ir.asset,
        references=debug_ir.references,
        content=debug_ir.content,
        coverage=debug_ir.coverage,
        diagnostics=debug_ir.diagnostics,
    )
