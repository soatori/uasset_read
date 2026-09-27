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


@dataclass
class PropertyBag:
    """Ordered lossless occurrences; name lookup is only a derived view."""

    entries: list[PropertyEntry] = field(default_factory=list)
    diagnostics: list[Any] = field(default_factory=list)

    def get(self, name: str, default: Any = None) -> Any:
        for entry in reversed(self.entries):
            if entry.name == name:
                return entry.value
        return default

    # Real consumers of the name-view pair: handlers_impl MaterialHandler.enrich,
    # material/graph.py expression decode (items + `in`), parse-hardening tests.
    def items(self):
        for entry in self.entries:
            yield entry.name, entry.value

    def __contains__(self, name: object) -> bool:
        return any(entry.name == name for entry in self.entries)

    def __getitem__(self, name: str) -> Any:
        for entry in reversed(self.entries):
            if entry.name == name:
                return entry.value
        raise KeyError(name)

    def __len__(self) -> int:
        return len(self.entries)

    def __bool__(self) -> bool:
        return bool(self.entries)


def project_property_value(value: Any) -> Any:
    """JSON-safe projection of a property value (typed containers preserved)."""
    from uasset_read.models.fallback import PropertyFallback, StructFallback

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
        return {
            "kind": "set",
            "element_type": value.element_type,
            "elements": [project_property_value(e) for e in value.elements],
        }
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


def project_property_bag(bag: PropertyBag) -> dict[str, Any]:
    """Presentation-only name-keyed map; ordered entries stay authoritative elsewhere."""
    out: dict[str, Any] = {}
    for entry in bag.entries:
        out[entry.name] = project_property_value(entry.value)
    return out
