"""src/uasset_read/models/fallback.py — Structured fallback model for unknown assets.

Reference: CUE4Parse: FStructFallback, generic UObject, FPropertyTag fallback.
Goal: allow unknown property/struct/export to retain diagnostic structured information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.exceptions import ErrorContext
    from uasset_read.models.properties import PropertyValue


class ExportParseStatus(str, Enum):
    """Export-level parse status."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    OPAQUE = "opaque"
    SKIPPED = "skipped"
    PARTIAL_METADATA = "partial_metadata"
    OPAQUE_UNVERSIONED = "opaque_unversioned"
    FALLBACK = "fallback"
    METADATA = "metadata"

    @property
    def is_partial(self) -> bool:
        return self.value.startswith("partial") or self.value in (
            "opaque",
            "skipped",
            "opaque_unversioned",
            "fallback",
            "metadata",
        )

    @property
    def is_failed(self) -> bool:
        return self.value == "failed"


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
        tag_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_context: Optional["ErrorContext"] = None,
        value: Any = None,
    ):
        super().__init__(name=name, type=type, value=value, array_index=array_index)
        self.size = size
        self.raw_bytes = raw_bytes
        self.reason = reason
        self.tag_data = tag_data
        self.error_message = error_message
        self.error_context = error_context

    @property
    def kind(self) -> str:
        return "unknown_property"


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

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "kind": self.kind,
            "struct_type": self.struct_type,
            "size": self.size,
            "reason": self.reason.value if isinstance(self.reason, Enum) else self.reason,
            "fields": self.fields,
        }
        if self.raw_bytes:
            raw = self.raw_bytes[:256]
            d["raw_data"] = raw.hex()
            if len(self.raw_bytes) > 256:
                d["raw_data_truncated"] = True
        return d


@dataclass
class GenericUObject:
    """Generic UObject fallback (reference: CUE4Parse generic UObject)."""

    name: str
    class_name: str
    serial_offset: int = 0
    serial_size: int = 0
    parse_status: ExportParseStatus = ExportParseStatus.FALLBACK
    super_name: str = ""
    outer_path: List[str] = field(default_factory=list)
    properties: List["PropertyValue"] = field(default_factory=list)
    fallback_data: Optional[StructFallback] = None
    requires_mappings: bool = False
    missing_mapping: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def kind(self) -> str:
        return "generic_uobject"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "kind": self.kind,
            "name": self.name,
            "class_name": self.class_name,
            "super_name": self.super_name,
            "outer_path": self.outer_path,
            "serial_offset": self.serial_offset,
            "serial_size": self.serial_size,
            "parse_status": self.parse_status.value if isinstance(self.parse_status, Enum) else self.parse_status,
            "property_count": len(self.properties),
            "requires_mappings": self.requires_mappings,
        }
        if self.fallback_data:
            d["fallback_data"] = self.fallback_data.to_dict()
        if self.missing_mapping:
            d["missing_mapping"] = self.missing_mapping
        if self.error_message:
            d["error_message"] = self.error_message
        return d
