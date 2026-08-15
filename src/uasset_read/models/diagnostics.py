"""src/uasset_read/models/diagnostics.py — Offset range diagnostic data model.

Records offset/range anomalies encountered during parsing, including
serial offset out-of-bounds, script offset overflow, CodeOffset anomalies, etc.
"""

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any


class DiagnosticSeverity(Enum):
    """Diagnostic severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class OffsetRangeDiagnostic:
    """Offset range diagnostic record — captures offset anomalies during parsing."""

    kind: str = "offset_range_diagnostic"
    severity: DiagnosticSeverity = DiagnosticSeverity.WARNING
    asset_path: str = ""
    asset_type: str = ""
    module: str = ""  # linker|property|graph|pin|kismet|pak|iostore
    object_name: str = ""
    export_index: int | None = None
    import_index: int | None = None
    field: str = ""  # serial_offset|script_serial_offset|ValueEndOffset|CodeOffset|LinkedTo
    current_pos: int = 0
    target_offset: int = 0
    read_size: int = 0
    file_size: int = 0
    range_start: int | None = None
    range_end: int | None = None
    source: str = ""
    error: str = ""
    fallback_used: bool = False
    fallback_result: str = ""  # failed|partial|success

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-compatible dict. None-valued fields are omitted."""
        d: dict[str, Any] = {
            "kind": self.kind,
            "severity": self.severity.value,
        }
        # String fields: output when non-empty
        for str_field in (
            "asset_path", "asset_type", "module", "object_name",
            "field", "source", "error", "fallback_result",
        ):
            val = getattr(self, str_field)
            if val:
                d[str_field] = val
        # Integer fields: always output (including 0)
        for int_field in ("current_pos", "target_offset", "read_size", "file_size"):
            d[int_field] = getattr(self, int_field)
        # Optional integer fields: output when not None
        for opt_field in ("export_index", "import_index", "range_start", "range_end"):
            val = getattr(self, opt_field)
            if val is not None:
                d[opt_field] = val
        # Boolean fields: output when True
        if self.fallback_used:
            d["fallback_used"] = True
        return d

    def is_structural(self) -> bool:
        """Check if this is a structural diagnostic (affects status)."""
        return self.severity in (DiagnosticSeverity.ERROR, DiagnosticSeverity.CRITICAL)


# Stable diagnostic codes for structured warnings
DIAGNOSTIC_CODE_NAME_INDEX_OUT_OF_RANGE = "name_index_out_of_range"
DIAGNOSTIC_CODE_FSTRING_ALL_NULL = "fstring_all_null"
DIAGNOSTIC_CODE_FSTRING_LENGTH_EXCEEDS_LIMIT = "fstring_length_exceeds_limit"
DIAGNOSTIC_CODE_INVALID_SERIAL_SIZE = "invalid_serial_size"
DIAGNOSTIC_CODE_INVALID_SERIAL_OFFSET = "invalid_serial_offset"
DIAGNOSTIC_CODE_UNKNOWN_SERIALIZATION_CONTROL_BITS = "unknown_serialization_control_bits"


@dataclass
class StructuredDiagnostic:
    """Structured diagnostic record with stable codes.

    Each diagnostic carries asset context, read stage, offset, raw value,
    UE version, and fallback action for auditability.
    """

    code: str
    severity: str = "warning"  # "warning" | "error" | "info"
    asset: str = ""
    stage: str = ""
    offset: int = 0
    raw_value: Any = None
    ue_version: str = ""
    fallback: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-compatible dict."""
        return asdict(self)
