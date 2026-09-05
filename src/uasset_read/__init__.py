"""
uasset_read - Unreal Engine .uasset file parser

Version 0.6.0-dev

Public API is controlled via __all__.
The v1 pipeline was removed in the package-first refactor; the package
document API (parse_package_document) is the only parse entry point.
"""

__version__ = "0.6.0-dev"

# ============================================================================
# Stable Public API (direct imports)
# ============================================================================

from .config import LogConfig
from .v2.api import parse_package_document
from .exceptions import ParseError
from .archive import FArchive

__all__ = [
    "__version__",
    # Configuration
    "LogConfig",
    # v2 package-first API
    "parse_package_document",
    # Exceptions
    "ParseError",
    # Binary reader
    "FArchive",
]
