"""
uasset_read - Unreal Engine .uasset file parser

Version 0.6.0-dev

Public API is controlled via __all__.
The v1 pipeline was removed in the package-first refactor; the package
document API (parse_package_document) is the only parse entry point.
JSON, CLI, Python, and Agent tools project from the same PackageDocument
through the v4 projection layer.
"""

__version__ = "0.6.0-dev"

# ============================================================================
# Stable Public API (direct imports)
# ============================================================================

from .package import parse_package_document
from .projection import (
    FORMAT_VERSION,
    project_document,
)
from .projections import write_projected_document
from .exceptions import ParseError
from .archive import FArchive

__all__ = [
    "__version__",
    # package-first API
    "parse_package_document",
    # v4 projection layer (single full-document output)
    "FORMAT_VERSION",
    "project_document",
    "write_projected_document",
    # Exceptions
    "ParseError",
    # Binary reader
    "FArchive",
]
