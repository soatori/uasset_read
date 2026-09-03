"""
uasset_read - Unreal Engine .uasset file parser

Version 0.6.0-dev

Public API is controlled via __all__.
"""

__version__ = "0.6.0-dev"

# ============================================================================
# Stable Public API (direct imports)
# ============================================================================

from .core import parse_single, parse_batch, diff_single, list_formats, BatchResult
from .config import ParseConfig, LogConfig
from .pipeline.core import parse_package, parse_uasset, parse_uasset_with_linker
from .v2.api import parse_package_document
from .project_logging import (
    ProjectLogSession,
    configure_project_logging,
    project_logging_session,
    shutdown_project_logging,
)
from .models.result import ParseResult
from .exceptions import ParseError
from .archive import FArchive

__all__ = [
    "__version__",
    # Core API
    "parse_single",
    "parse_batch",
    "diff_single",
    "list_formats",
    "BatchResult",
    # Configuration
    "ParseConfig",
    "LogConfig",
    # Parsing pipeline
    "parse_package",
    "parse_uasset",
    "parse_uasset_with_linker",
    # Logging
    "configure_project_logging",
    "ProjectLogSession",
    "project_logging_session",
    "shutdown_project_logging",
    # v2 package-first API
    "parse_package_document",
    # Core models
    "ParseResult",
    # Exceptions
    "ParseError",
    # Binary reader
    "FArchive",
]
