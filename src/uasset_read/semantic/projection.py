"""Debug -> standard projection.

Projects a debug-mode SemanticIR to standard mode by:
1. Setting mode to "standard"
2. Preserving all data fields (asset, references, content, coverage, diagnostics)

The projection invariant: project_debug(debug_document) == standard_document
when both contain the same data.
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
