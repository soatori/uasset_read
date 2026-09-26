"""Property data classes — PropertyTag, PropertyValue and advanced property containers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from uasset_read.models.byte_ranges import ByteRegion


@dataclass
class PropertyTypeName:
    """Recursive FPropertyTypeName node."""

    name: str
    children: list[PropertyTypeName] = field(default_factory=list)

    def to_parts(self) -> list[tuple[str, int]]:
        parts: list[tuple[str, int]] = [(self.name, len(self.children))]
        for child in self.children:
            parts.extend(child.to_parts())
        return parts


@dataclass
class PropertyTag:
    """PropertyTag structure (PROP-01). From PropertyTag.h lines 37-105."""

    name: str  # Property name (FName)
    type: str  # Type name string (e.g. "IntProperty")
    size: int  # Serialized data size (bytes)
    array_index: int = 0  # Array element index (default 0)
    flags: int = 0  # EPropertyTagFlags bit flags
    bool_val: int = 0  # BoolProperty value (BoolTrue flag)
    serialize_type: str = "Property"  # Property / Skipped / BinaryOrNative
    enum_type: str | None = None  # ByteProperty/EnumProperty enum type (extracted from FPropertyTypeName)
    type_parts: list[tuple[str, int]] = field(default_factory=list)  # Complete FPropertyTypeName nodes
    struct_type: str | None = None  # StructProperty struct type name
    inner_type: str | None = None  # Array/Set inner type
    inner_type_struct: str | None = None  # Array/Set inner StructProperty struct type
    key_type: str | None = None  # Map key type
    key_type_struct: str | None = None  # Map key StructProperty struct type
    value_type: str | None = None  # Map value type
    value_type_struct: str | None = None  # Map value StructProperty struct type
    tag_start_offset: int | None = None  # PropertyTag start read position (archive.tell())
    value_start_offset: int | None = None  # Property value start position (after tag read)
    value_end_offset: int | None = None  # Property value expected end position (value_start + size)
    size_exceeded: bool = False  # True when tag.size exceeds remaining bytes (tolerant mode)


@dataclass
class PropertyValue:
    """Property value container (D-08/D-09)."""

    name: str
    type: str
    value: Any = None
    array_index: int = 0
    tag_start_offset: int | None = None
    value_start_offset: int | None = None
    value_end_offset: int | None = None


@dataclass
class SoftObjectPathValue:
    """Unified SoftObject/LazyObject/AssetObject parse result."""

    raw_kind: str
    asset_path: str = ""
    sub_path: str = ""
    guid: str | None = None


@dataclass
class StructValue:
    """StructProperty value container (D-01a)."""

    struct_type: str
    fields: dict[str, Any] = field(default_factory=dict)
    raw_size: int | None = None
    parse_status: str = "success"


@dataclass
class MapValue:
    """MapProperty value container (D-02a)."""

    key_type: str
    value_type: str
    entries: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SetValue:
    """SetProperty value container (D-03a)."""

    element_type: str
    elements: list[Any] = field(default_factory=list)


@dataclass
class EnumValue:
    """EnumProperty value container (D-04a)."""

    enum_type: str
    value_name: str


@dataclass
class TextValue:
    """TextProperty value container (D-05a)."""

    namespace: str = ""
    key: str = ""
    source_string: str = ""
    history_type: int | None = None  # ETextHistoryType seen; None when not decoded
    property_type: str = "TextProperty"  # read by legacy_reader TextValue serialization


@dataclass
class DelegateValue:
    """DelegateProperty value container (D-06a)."""

    object_ref: int
    function_name: str


@dataclass(frozen=True)
class PropertyEntry:
    """One lossless property occurrence with optional tag/value ranges."""

    name: str
    type_name: str
    value: Any
    array_index: int | None
    tag_region: ByteRegion | None
    value_region: ByteRegion | None


def _project_entry_value(entry: PropertyEntry) -> Any:
    return entry.value


@dataclass
class PropertyBag:
    """Ordered lossless occurrences; name lookup is only a derived view."""

    entries: list[PropertyEntry] = field(default_factory=list)
    diagnostics: list[Any] = field(default_factory=list)

    def get(self, name: str, default: Any = None) -> Any:
        for entry in reversed(self.entries):
            if entry.name == name:
                return _project_entry_value(entry)
        return default

    def get_all(self, name: str) -> list[PropertyEntry]:
        return [entry for entry in self.entries if entry.name == name]

    def items(self):
        for entry in self.entries:
            yield entry.name, _project_entry_value(entry)

    def keys(self):
        seen: set[str] = set()
        for entry in self.entries:
            if entry.name not in seen:
                seen.add(entry.name)
                yield entry.name

    def values(self):
        for _, value in self.items():
            yield value

    def __getitem__(self, name: str) -> Any:
        for entry in reversed(self.entries):
            if entry.name == name:
                return _project_entry_value(entry)
        raise KeyError(name)

    def __contains__(self, name: object) -> bool:
        return any(entry.name == name for entry in self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def __bool__(self) -> bool:
        return bool(self.entries)

    def __iter__(self):
        return iter(self.keys())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PropertyBag):
            return self.entries == other.entries
        if isinstance(other, dict):
            return project_property_bag(self) == other
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result


def project_property_value(value: Any) -> Any:
    """JSON-safe projection of a property value (typed containers preserved)."""
    from uasset_read.models.fallback import PropertyFallback, StructFallback
    from uasset_read.models.properties import (
        EnumValue,
        MapValue,
        SetValue,
        StructValue,
        TextValue,
    )

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {"kind": "bytes", "length": len(value)}
    if isinstance(value, PropertyFallback):
        return {
            "kind": "opaque",
            "type": value.type,
            "size": value.size,
            "reason": value.reason.value,
        }
    if isinstance(value, StructValue):
        return {
            "kind": "struct",
            "struct_type": value.struct_type,
            "fields": {k: project_property_value(v) for k, v in value.fields.items()},
        }
    if isinstance(value, StructFallback):
        return value.to_dict()
    if isinstance(value, TextValue):
        return {
            "kind": "text",
            "namespace": value.namespace,
            "key": value.key,
            "source_string": value.source_string,
            "history_type": value.history_type,
            "property_type": value.property_type,
        }
    if isinstance(value, EnumValue):
        return {"kind": "enum", "enum_type": value.enum_type, "value": value.value_name}
    if isinstance(value, SetValue):
        return {"kind": "set", "element_type": value.element_type, "elements": [project_property_value(e) for e in value.elements]}
    if isinstance(value, MapValue):
        return {
            "kind": "map",
            "key_type": value.key_type,
            "value_type": value.value_type,
            "entries": [
                {"key": project_property_value(e.get("key")), "value": project_property_value(e.get("value"))}
                for e in value.entries
            ],
        }
    if isinstance(value, list):
        return [project_property_value(v) for v in value]
    if isinstance(value, dict):
        if "kind" in value:
            out = dict(value)
            for key in ("value", "fields", "raw_data"):
                if key in out:
                    out[key] = project_property_value(out[key])
            return out
        return {k: project_property_value(v) for k, v in value.items()}
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return str(value)


def project_property_entries(bag: PropertyBag) -> list[dict[str, Any]]:
    return [
        {
            "name": entry.name,
            "type": entry.type_name,
            "array_index": entry.array_index,
            "value": project_property_value(entry.value),
            "tag_region": (
                None
                if entry.tag_region is None
                else {
                    "start": entry.tag_region.start,
                    "size": entry.tag_region.size,
                    "end": entry.tag_region.end,
                    "source_id": entry.tag_region.source_id,
                    "source_start": entry.tag_region.source_start,
                    "source_end": entry.tag_region.source_end,
                    "status": entry.tag_region.status,
                    "reason": entry.tag_region.reason,
                    "feature": entry.tag_region.feature,
                    "payload_ref": entry.tag_region.payload_ref,
                    "source_slices": [
                        {
                            "source_id": s.source_id,
                            "source_start": s.source_start,
                            "size": s.size,
                            "source_end": s.source_start + s.size,
                        }
                        for s in entry.tag_region.source_slices
                    ],
                }
            ),
            "value_region": (
                None
                if entry.value_region is None
                else {
                    "start": entry.value_region.start,
                    "size": entry.value_region.size,
                    "end": entry.value_region.end,
                    "source_id": entry.value_region.source_id,
                    "source_start": entry.value_region.source_start,
                    "source_end": entry.value_region.source_end,
                    "status": entry.value_region.status,
                    "reason": entry.value_region.reason,
                    "feature": entry.value_region.feature,
                    "payload_ref": entry.value_region.payload_ref,
                    "source_slices": [
                        {
                            "source_id": s.source_id,
                            "source_start": s.source_start,
                            "size": s.size,
                            "source_end": s.source_start + s.size,
                        }
                        for s in entry.value_region.source_slices
                    ],
                }
            ),
        }
        for entry in bag.entries
    ]


def project_property_bag(bag: PropertyBag) -> dict[str, Any]:
    """Presentation-only name-keyed map; ordered entries stay authoritative elsewhere."""
    out: dict[str, Any] = {}
    for entry in bag.entries:
        out[entry.name] = project_property_value(entry.value)
    return out
