"""Blueprint C++ declaration/migration projection + type-aware registry (Tasks 10 / 10A).

Public entries are the two names ``uasset_read`` itself consumes:
``build_canonical_document`` / ``write_projected_document`` (R3).

Typed-IR helpers stay internal to the projection layer and never reopen package
bytes; callers import them from the concrete submodules
(``uasset_read.projections.registry``, ``.cpp_render``, ``.bundle``, ...).
"""

from __future__ import annotations

from uasset_read.projections.bundle import (
    build_canonical_document,
    write_projected_document,
)

__all__ = [
    "build_canonical_document",
    "write_projected_document",
]
