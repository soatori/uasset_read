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

from .config import ParseConfig, LogConfig
from .v2.api import parse_package_document
from .project_logging import (
    ProjectLogSession,
    configure_project_logging,
    project_logging_session,
    shutdown_project_logging,
)
from .exceptions import ParseError
from .archive import FArchive

__all__ = [
    "__version__",
    # Configuration
    "ParseConfig",
    "LogConfig",
    # v2 package-first API
    "parse_package_document",
    # Logging
    "configure_project_logging",
    "ProjectLogSession",
    "project_logging_session",
    "shutdown_project_logging",
    # Exceptions
    "ParseError",
    # Binary reader
    "FArchive",
]
