"""
uasset_read exception class definitions

Contains all exception classes for error handling and graceful degradation.
Extracted from uasset_read.py (per D-13).
"""

import struct
from typing import Any


# ============================================================================
# Custom exceptions (graceful degradation)
# ============================================================================


class UAssetError(Exception):
    """uasset parsing error base class"""


class VersionError(UAssetError):
    """Unsupported version error"""


class ParseError(UAssetError):
    """Parse error."""

    # Attached by the layout-rejection path (package.py); declared so the
    # dynamic enrichment type-checks while staying absent on ordinary raises.
    code: str
    diagnostics: list[Any]


class StreamPoisonedError(ParseError):
    """Raised when a poison diagnostic aborts a nested multi-entry value parse.

    Subclasses ParseError so the export property loop's tolerant recovery path
    can catch it, but parsers re-raise it before their general ParseError
    fallback so Map/Set/Array entry loops stop instead of retrying the same
    misaligned position for every remaining entry.
    """


class ExportBoundsExceeded(ParseError):
    """Raised when a read or seek would exceed the current export bound."""


# Shared catch tuples for tolerant binary / reference recovery paths.
BINARY_READ_ERRORS: tuple[type[BaseException], ...] = (struct.error, OSError, ValueError)
# Table-level recovery: include ParseError (archive truncation). Property loops
# keep StreamPoisonedError re-raise semantics and must not use this blindly.
RECOVERY_READ_ERRORS: tuple[type[BaseException], ...] = BINARY_READ_ERRORS + (ParseError,)
REFERENCE_RESOLVE_ERRORS: tuple[type[BaseException], ...] = (KeyError, IndexError, AttributeError)
