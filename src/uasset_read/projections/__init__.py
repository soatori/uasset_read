"""Type-aware projection records and the deterministic JSON writer.

Public entry: ``write_projected_document`` (v4). The envelope producer itself
lives in ``uasset_read.projection``; typed-IR helpers stay internal to the
projection layer and never reopen package bytes.
"""

from __future__ import annotations

from uasset_read.projections.bundle import write_projected_document

__all__ = [
    "write_projected_document",
]
