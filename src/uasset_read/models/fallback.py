"""src/uasset_read/models/fallback.py — 未知资产结构化 Fallback 模型。

参考 CUE4Parse: FStructFallback, generic UObject, FPropertyTag fallback.
目标：让未知的 property/struct/export 仍能保留可诊断的结构化信息。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.exceptions import ErrorContext
    from uasset_read.models.properties import PropertyValue


class ExportParseStatus(str, Enum):
    """Export 级解析状态。"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FALLBACK = "fallback"
    SKIPPED = "skipped"
    FAILED = "failed"


class FallbackReason(str, Enum):
    """Fallback 原因。"""
    UNSUPPORTED_TYPE = "unsupported_type"
    UNSUPPORTED_STRUCT = "unsupported_struct"
    PARSE_ERROR = "parse_error"
    PARTIAL_PARSE = "partial_parse"
    MISSING_MAPPING = "missing_mapping"
    CUSTOM_PAYLOAD = "custom_payload"


@dataclass
class PropertyFallback:
    """未知/损坏 property 的结构化 fallback（替代原 None 返回）。"""
    name: str
    type: str
    size: int
    raw_bytes: bytes = b""
    reason: FallbackReason = FallbackReason.UNSUPPORTED_TYPE
    array_index: int = 0
    tag_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_context: Optional["ErrorContext"] = None

    @property
    def kind(self) -> str:
        return "unknown_property"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "kind": self.kind,
            "name": self.name,
            "type": self.type,
            "size": self.size,
            "array_index": self.array_index,
            "reason": self.reason.value if isinstance(self.reason, Enum) else self.reason,
        }
        if self.raw_bytes:
            raw = self.raw_bytes[:256]
            d["raw_data"] = raw.hex()
            if len(self.raw_bytes) > 256:
                d["raw_data_truncated"] = True
                d["raw_data_full_size"] = len(self.raw_bytes)
        if self.tag_data:
            d["tag_data"] = self.tag_data
        if self.error_message:
            d["error_message"] = self.error_message
        if self.error_context is not None:
            d["error_context"] = self._serialize_error_context()
        return d

    def _serialize_error_context(self) -> Dict[str, Any]:
        """将 ErrorContext 序列化为字典。"""
        ctx = self.error_context
        d: Dict[str, Any] = {
            "offset": ctx.offset,
            "phase": ctx.phase,
            "operation": ctx.operation,
        }
        if ctx.context_name:
            d["context_name"] = ctx.context_name
        if ctx.export_index is not None:
            d["export_index"] = ctx.export_index
        if ctx.expected_offset is not None:
            d["expected_offset"] = ctx.expected_offset
        if ctx.actual_offset is not None:
            d["actual_offset"] = ctx.actual_offset
        if ctx.field_name:
            d["field_name"] = ctx.field_name
        if ctx.version_info:
            d["version_info"] = ctx.version_info
        return d


@dataclass
class StructFallback:
    """未知 struct 的结构化 fallback（参考 CUE4Parse FStructFallback）。"""
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
    """通用 UObject fallback（参考 CUE4Parse generic UObject）。"""
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
