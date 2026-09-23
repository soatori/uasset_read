"""Blueprint C++ declaration/migration projection + type-aware registry (Tasks 10 / 10A).

Public entries:
- ``render_cpp(semantic_dict, mode) -> CppProjection`` (R2)
- ``ProjectorRegistry`` / ``build_canonical_document`` / ``write_projected_document`` (R3)

Typed-IR helpers stay internal to the projection layer and never reopen package bytes.
"""

from __future__ import annotations

from uasset_read.projections.cpp_ast import (
    CppClassDecl,
    CppComponentDecl,
    CppConstructorDecl,
    CppDispatcherDecl,
    CppFunctionDecl,
    CppParam,
    CppPropertyDecl,
    CppStmt,
    CppType,
    build_cpp_ast,
)
from uasset_read.projections.cpp_render import (
    CppProjection,
    render_cpp,
    render_cpp_ir,
)
from uasset_read.projections.bundle import (
    OutputBudgetError,
    build_canonical_document,
    minimum_canonical_envelope_bytes,
    write_projected_document,
)
from uasset_read.projections.records import (
    ProjectionRecord,
    SidecarRecord,
    dependency_ids,
)
from uasset_read.projections.registry import (
    CAPABILITY_MATRIX,
    BlueprintCppProjector,
    ProjectorRegistry,
)

__all__ = [
    "BlueprintCppProjector",
    "CAPABILITY_MATRIX",
    "CppClassDecl",
    "CppComponentDecl",
    "CppConstructorDecl",
    "CppDispatcherDecl",
    "CppFunctionDecl",
    "CppParam",
    "CppProjection",
    "CppPropertyDecl",
    "CppStmt",
    "CppType",
    "OutputBudgetError",
    "ProjectorRegistry",
    "ProjectionRecord",
    "SidecarRecord",
    "build_canonical_document",
    "build_cpp_ast",
    "dependency_ids",
    "minimum_canonical_envelope_bytes",
    "render_cpp",
    "render_cpp_ir",
    "write_projected_document",
]
