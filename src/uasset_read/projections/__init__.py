"""Blueprint C++ declaration and migration projection (plan Task 10 / R2).

Public document-boundary entry is ``render_cpp(semantic_dict, mode)``.
Typed-IR helpers (``build_cpp_ast``, ``render_cpp_ir``) stay internal to the
projection layer and never reopen package bytes.
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

__all__ = [
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
    "build_cpp_ast",
    "render_cpp",
    "render_cpp_ir",
]
