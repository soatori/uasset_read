"""src/uasset_read/models/diagnostics.py — Diagnostic data models.

Structured diagnostics emitted during parsing: stable-code structured
records and PackageDocument diagnostics.
"""

from dataclasses import dataclass, asdict
from typing import Any, Literal


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
