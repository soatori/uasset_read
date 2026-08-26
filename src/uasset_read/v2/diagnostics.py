"""Structured diagnostics — v2 model.

Extends v1 OffsetRangeDiagnostic/StructuredDiagnostic with
stage, object_id, property_path, effect, and recoverable fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class Diagnostic:
    """Structured diagnostic for the v2 PackageDocument."""

    severity: Literal["info", "warning", "error", "critical"]
    code: str
    message: str
    stage: str  # "package.summary", "properties.tagged", "objects.export", etc.
    object_id: str | None = None  # "export:3"
    property_path: str | None = None
    offset: int | None = None
    size: int | None = None
    effect: Literal["semantic_loss", "data_loss", "parse_failure", "recovery"] | None = None
    recoverable: bool = True
    count: int = 1  # aggregation count for repeated identical diagnostics

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "stage": self.stage,
        }
        if self.object_id is not None:
            d["object_id"] = self.object_id
        if self.property_path is not None:
            d["property_path"] = self.property_path
        if self.offset is not None:
            d["offset"] = self.offset
        if self.size is not None:
            d["size"] = self.size
        if self.effect is not None:
            d["effect"] = self.effect
        if not self.recoverable:
            d["recoverable"] = False
        if self.count > 1:
            d["count"] = self.count
        return d


# Stable diagnostic codes
CODE_PROPERTY_REMAINDER = "PROPERTY_VALUE_REMAINDER"
CODE_SERIAL_SIZE_MISMATCH = "SERIAL_SIZE_MISMATCH"
CODE_NAME_INDEX_OUT_OF_RANGE = "NAME_INDEX_OUT_OF_RANGE"
CODE_UNRESOLVABLE_CLASS = "UNRESOLVABLE_CLASS"
CODE_EXPORT_PARSE_FAILED = "EXPORT_PARSE_FAILED"
CODE_EXPORT_PARTIAL = "EXPORT_PARTIAL"
CODE_UNKNOWN_PROPERTY_TYPE = "UNKNOWN_PROPERTY_TYPE"
CODE_PACKAGE_HEADER_ERROR = "PACKAGE_HEADER_ERROR"
