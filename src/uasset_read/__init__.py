"""
uasset_read - Unreal Engine .uasset file parser

Version 0.5.5

Public API is controlled via __all__.
"""

__version__ = "0.5.5"

# ============================================================================
# Stable Public API (direct imports)
# ============================================================================

from .core import parse_single, parse_batch, diff_single, list_formats, BatchResult
from .config import ParseConfig, LogConfig
from .parse_uasset import parse_package, parse_uasset, parse_uasset_with_linker
from .project_logging import (
    ProjectLogSession,
    configure_project_logging,
    project_logging_session,
    shutdown_project_logging,
)
from .models import ParseResult
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
    # Core models
    "ParseResult",
    # Exceptions
    "ParseError",
    # Binary reader
    "FArchive",
]
