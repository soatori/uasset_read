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


class DecompressionError(UAssetError):
    """Decompression failure (zlib/Oodle/LZ4, etc.)"""
    pass


class LinkerError(UAssetError):
    """Linker phase error (import/export parsing failure)"""
    pass


class SemanticContractError(UAssetError):
    """Semantic JSON contract violation — output was blocked.

    Raised when a SemanticIR fails validation before rendering; invalid
    documents must never be emitted.
    """
    pass


@dataclass
class ErrorContext:
    """
    Error context information.

    Records the parsing state at the time of an error to aid in diagnosis.
    """

    offset: int           # File offset position
    phase: str            # Parsing phase: header/name_table/import_map/export_map/properties/blueprint
    operation: str        # Operation type: read_i32/read_name/seek, etc.
    context_name: str = ""  # Related object or property name
    # Export table parsing stage information
    export_index: Optional[int] = None    # Current export index (0-based)
    expected_offset: Optional[int] = None  # Expected offset
    actual_offset: Optional[int] = None    # Actual offset
    field_name: str = ""                  # Field name (e.g. "TemplateIndex")
    version_info: Dict[str, int] = field(default_factory=dict)  # Version check failure info


class ParseError(UAssetError):
    """Parse error (can carry partial results, context, and rich diagnostic info).

    Attributes:
        partial_result: Partial parsing result (error-tolerant scenarios)
        context: Legacy ErrorContext (backward compatibility)
        reader_name: Reader name (e.g. FArchive, ByteArchive)
        position: Current read position
        length: Total file length
        export_name: Current export name (if applicable)
    """

    def __init__(self, message: str, partial_result: Optional[Dict] = None, context: Optional[ErrorContext] = None):
        super().__init__(message)
        self.partial_result = partial_result
        self.context = context
        # Additional context information
        self.reader_name: str = ""
        self.position: int = 0
        self.length: int = 0
        self.export_name: str = ""

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.reader_name:
            parts.append(f"Reader: {self.reader_name}")
        if self.length > 0:
            pct = (self.position / self.length * 100) if self.length > 0 else 0
            parts.append(f"Position: {self.position} / {self.length} ({pct:.1f}% done)")
        if self.export_name:
            parts.append(f"Export: {self.export_name}")
        return "\n".join(parts)