"""
uasset_read exception class definitions

Contains all exception classes for error handling and graceful degradation.
Extracted from uasset_read.py (per D-13).
"""


# ============================================================================
# Custom exceptions (graceful degradation)
# ============================================================================


class UAssetError(Exception):
    """uasset parsing error base class"""


class VersionError(UAssetError):
    """Unsupported version error"""


class ParseError(UAssetError):
    """Parse error."""


class ExportBoundsExceeded(ParseError):
    """Raised when a read or seek would exceed the current export bound."""
