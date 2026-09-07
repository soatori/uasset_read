"""src/uasset_read/models/fallback.py — Structured fallback model for unknown assets.

Reference: CUE4Parse: FStructFallback, generic UObject, FPropertyTag fallback.
Goal: allow unknown property/struct/export to retain diagnostic structured information.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any


class FallbackReason(str, Enum):
    """Fallback reason."""

    UNSUPPORTED_TYPE = "unsupported_type"
    UNSUPPORTED_STRUCT = "unsupported_struct"
    PARSE_ERROR = "parse_error"
    PARTIAL_PARSE = "partial_parse"
    MISSING_MAPPING = "missing_mapping"
    CUSTOM_PAYLOAD = "custom_payload"
    SIZE_EXCEEDED = "size_exceeded"


from uasset_read.models.properties import PropertyValue


class PropertyFallback(PropertyValue):
    """Structured fallback for unknown/corrupted properties (replaces original None return)."""

    def __init__(
        self,
        name: str,
        type: str,
        size: int = 0,
        raw_bytes: bytes = b"",
        reason: FallbackReason = FallbackReason.UNSUPPORTED_TYPE,
        array_index: int = 0,
        error_message: Optional[str] = None,
        value: Any = None,
    ):
        super().__init__(name=name, type=type, value=value, array_index=array_index)
        self.size = size
        self.raw_bytes = raw_bytes
        self.reason = reason
        self.error_message = error_message

    @property
    def kind(self) -> str:
        return "unknown_property"

    @classmethod
    def from_tag(cls, tag, reason: "FallbackReason", *, error_message: str = "", raw_bytes: bytes = b"") -> "PropertyFallback":
        """Build a fallback from a property tag (shared name/type/size/array_index plumbing)."""
        return cls(
            name=tag.name, type=tag.type, size=tag.size, raw_bytes=raw_bytes,
            reason=reason,
            array_index=getattr(tag, "array_index", 0),
            error_message=error_message or None,
        )


@dataclass
class StructFallback:
    """Structured fallback for unknown structs (reference: CUE4Parse FStructFallback)."""

    struct_type: str
    size: int
    raw_bytes: bytes = b""
    reason: FallbackReason = FallbackReason.UNSUPPORTED_STRUCT
    fields: Dict[str, Any] = field(default_factory=dict)

    @property
    def kind(self) -> str:
        return "struct_fallback"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind
        if self.raw_bytes:
            d["raw_data"] = self.raw_bytes[:256].hex()
            if len(self.raw_bytes) > 256:
                d["raw_data_truncated"] = True
        del d["raw_bytes"]
        return d
