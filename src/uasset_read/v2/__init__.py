"""uasset_read v2 — Package-First architecture.

This package implements the new PackageDocument-based architecture
defined in docs/designs/2026-08-26-package-first-uasset-parser-refactor.md.

It runs alongside the existing v1 pipeline during migration.
"""

__all__ = [
    "parse_package_document",
    "PackageDocument",
    "Source",
    "FileSource",
    "MemorySource",
    "SliceReader",
    # Agent tools
    "inspect_package",
    "list_objects",
    "get_object",
    "list_dependencies",
    "get_diagnostics",
    "extract_payload",
]

from .api import parse_package_document  # noqa: F401
from .document import PackageDocument  # noqa: F401
from .source import Source, FileSource, MemorySource, SliceReader  # noqa: F401
from .agent_tools import (  # noqa: F401
    inspect_package,
    list_objects,
    get_object,
    list_dependencies,
    get_diagnostics,
    extract_payload,
)
