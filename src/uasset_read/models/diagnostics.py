"""src/uasset_read/models/diagnostics.py — Diagnostic data models.

Structured diagnostics emitted during parsing: stable-code structured
records and PackageDocument diagnostics.
"""

from dataclasses import dataclass, asdict
from typing import Any, Literal


# Stable diagnostic codes for structured warnings
DIAGNOSTIC_CODE_INVALID_SERIAL_SIZE = "invalid_serial_size"
DIAGNOSTIC_CODE_INVALID_SERIAL_OFFSET = "invalid_serial_offset"


@dataclass
class Diagnostic:
    """Structured diagnostic for the PackageDocument."""

    severity: Literal["info", "warning", "error", "critical"] = "warning"
    code: str = ""
    message: str = ""
    stage: str = ""  # "package.summary", "properties.tagged", "objects.export", etc.
    object_id: str | None = None  # "export:3"
    offset: int | None = None
    size: int | None = None
    effect: Literal["semantic_loss", "data_loss", "parse_failure", "recovery"] | None = None
    recoverable: bool = True
    fallback: str | None = None  # fallback action for structured diagnostics

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # recoverable is always included (False is explicit, True is default)
        return {k: v for k, v in d.items() if v is not None and (k == "recoverable" or (not isinstance(v, bool) or v))}


def make_diagnostic(
    code: str,
    message: str,
    stage: str,
    *,
    object_id: str | None = None,
    severity: Literal["info", "warning", "error", "critical"] = "warning",
    effect: Literal["semantic_loss", "data_loss", "parse_failure", "recovery"] | None = "semantic_loss",
) -> Diagnostic:
    """Build a Diagnostic with common defaults."""
    return Diagnostic(
        severity=severity,
        code=code,
        message=message,
        stage=stage,
        object_id=object_id,
        effect=effect,
    )
