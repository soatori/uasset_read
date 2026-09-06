"""
uasset_read exception class definitions

Contains all exception classes for error handling and graceful degradation.
Extracted from uasset_read.py (per D-13).
"""

from dataclasses import dataclass, field
from typing import Optional, Dict


# ============================================================================
# Custom exceptions (graceful degradation)
# ============================================================================


class UAssetError(Exception):
    """uasset parsing error base class"""

    pass


class VersionError(UAssetError):
    """Unsupported version error"""

    pass


@dataclass
class ErrorContext:
    """
    Error context information.

    Records the parsing state at the time of an error to aid in diagnosis.
    """

    offset: int  # File offset position
    phase: str  # Parsing phase: header/name_table/import_map/export_map/properties/blueprint
    operation: str  # Operation type: read_i32/read_name/seek, etc.
    context_name: str = ""  # Related object or property name
    # Export table parsing stage information
    export_index: Optional[int] = None  # Current export index (0-based)
    expected_offset: Optional[int] = None  # Expected offset
    actual_offset: Optional[int] = None  # Actual offset
    field_name: str = ""  # Field name (e.g. "TemplateIndex")
    version_info: Dict[str, int] = field(default_factory=dict)  # Version check failure info


class ParseError(UAssetError):
    """Parse error (can carry an ErrorContext)."""

    def __init__(self, message: str, context: Optional[ErrorContext] = None):
        super().__init__(message)
        self.context = context


class ExportBoundsExceeded(ParseError):
    """Raised when a read or seek would exceed the current export bound."""

    pass
