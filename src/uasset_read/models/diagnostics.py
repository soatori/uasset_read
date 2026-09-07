"""src/uasset_read/models/diagnostics.py — Offset range diagnostic data model.

Records offset/range anomalies encountered during parsing, including
serial offset out-of-bounds, script offset overflow, CodeOffset anomalies, etc.
"""

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Literal


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
    module: str = ""  # property|graph|pin|kismet|pak|iostore
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
        d = asdict(self)
        d["severity"] = self.severity.value
        result: dict[str, Any] = {}
        for key, val in d.items():
            if key == "severity":
                result[key] = val
                continue
            # Integer fields: always output (including 0)
            if key in ("current_pos", "target_offset", "read_size", "file_size"):
                result[key] = val
                continue
            if val is None:
                continue
            if isinstance(val, str) and val == "":
                continue
            if isinstance(val, bool) and not val:
                continue
            result[key] = val
        return result

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
    object_id: str = ""  # owning table slot (e.g. "export:3") when a read context is active
    offset: int = 0
    raw_value: Any = None
    ue_version: str = ""
    fallback: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-compatible dict."""
        return asdict(self)


@dataclass
class Diagnostic:
    """Structured diagnostic for the PackageDocument."""

    severity: Literal["info", "warning", "error", "critical"]
    code: str
    message: str
    stage: str  # "package.summary", "properties.tagged", "objects.export", etc.
    object_id: str | None = None  # "export:3"
    offset: int | None = None
    size: int | None = None
    effect: Literal["semantic_loss", "data_loss", "parse_failure", "recovery"] | None = None
    recoverable: bool = True

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # recoverable is always included (False is explicit, True is default)
        return {k: v for k, v in d.items() if v is not None and (k == "recoverable" or (not isinstance(v, bool) or v))}
