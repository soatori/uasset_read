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


def _opaque(type_name: str, size: int, reason: str, *, struct_type: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": "opaque", "type": type_name, "size": size, "reason": reason}
    if struct_type is not None:
        out["struct_type"] = struct_type
    return out


def _delegate_entry(value: Any) -> dict[str, Any] | None:
    """DelegateValue model or the parser's {object, function} entry dict."""
    if isinstance(value, DelegateValue):
        return {"kind": "delegate", "object_ref": value.object_ref, "function_name": value.function_name}
    if isinstance(value, dict) and set(value) == {"object", "function"}:
        return {"kind": "delegate", "object_ref": value["object"], "function_name": value["function"]}
    return None


def _is_delegate_list(value: list[Any]) -> bool:
    return bool(value) and all(_delegate_entry(item) is not None for item in value)


def _project_soft_path(value: Any) -> dict[str, Any]:
    if isinstance(value, SoftObjectPathValue):
        raw_kind, asset_path, sub_path, guid = value.raw_kind, value.asset_path, value.sub_path, value.guid
    else:
        raw_kind = value.get("raw_kind") if isinstance(value.get("raw_kind"), str) else ""
        asset_path = value.get("asset_path") if isinstance(value.get("asset_path"), str) else ""
        sub_path = value.get("sub_path") if isinstance(value.get("sub_path"), str) else ""
        guid = value.get("guid") if isinstance(value.get("guid"), str) else None
    out: dict[str, Any] = {
        "kind": "soft_object_path",
        "raw_kind": raw_kind,
        "asset_path": asset_path,
        "sub_path": sub_path,
    }
    if raw_kind == "LazyObjectProperty":
        out["guid"] = guid or ""
    return out


def _project_frozen_dict(kind: str, value: dict[str, Any], seen: frozenset[int]) -> dict[str, Any] | None:
    """Rebuild one already-projected frozen shape, recursing through children."""
    if kind == "value":
        return {"kind": "value", "type": value.get("type") or "", "value": _project(value.get("value"), seen)}
    if kind == "struct":
        fields = value.get("fields")
        return {
            "kind": "struct",
            "struct_type": value.get("struct_type") or "",
            "fields": {str(k): _project(v, seen) for k, v in fields.items()} if isinstance(fields, dict) else {},
        }
    if kind == "array":
        elements = value.get("elements")
        return {"kind": "array", "elements": [_project(e, seen) for e in elements] if isinstance(elements, list) else []}
    if kind == "map":
        entries = value.get("entries")
        out_entries = []
        for item in entries if isinstance(entries, list) else []:
            key = item.get("key") if isinstance(item, dict) else None
            val = item.get("value") if isinstance(item, dict) else None
            out_entries.append({"key": _project(key, seen), "value": _project(val, seen)})
        return {
            "kind": "map",
            "key_type": value.get("key_type") or "",
            "value_type": value.get("value_type") or "",
            "entries": out_entries,
        }
    if kind == "set":
        elements = value.get("elements")
        return {
            "kind": "set",
            "element_type": value.get("element_type") or "",
            "elements": [_project(e, seen) for e in elements] if isinstance(elements, list) else [],
        }
    if kind == "enum":
        return {"kind": "enum", "enum_type": value.get("enum_type") or "", "value": value.get("value") or ""}
    if kind == "text":
        history = value.get("history_type")
        return {
            "kind": "text",
            "namespace": value.get("namespace") if isinstance(value.get("namespace"), str) else None,
            "key": value.get("key") if isinstance(value.get("key"), str) else None,
            "source_string": value.get("source_string") if isinstance(value.get("source_string"), str) else None,
            "history_type": history if isinstance(history, int) and not isinstance(history, bool) else None,
        }
    if kind == "opaque":
        out = _opaque(
            value.get("type") if isinstance(value.get("type"), str) else "",
            value.get("size") if isinstance(value.get("size"), int) and not isinstance(value.get("size"), bool) else 0,
            value.get("reason") if isinstance(value.get("reason"), str) else "",
            struct_type=value.get("struct_type") if isinstance(value.get("struct_type"), str) else None,
        )
        return out
    if kind == "soft_object_path":
        return _project_soft_path(value)
    if kind == "object_ref":
        table = value.get("table")
        index = value.get("index")
        if isinstance(table, str) and isinstance(index, int) and not isinstance(index, bool):
            return {"kind": "object_ref", "table": table, "index": index, "id": f"{table}:{index}"}
        return None
    if kind == "delegate":
        entry = _delegate_entry(value)
        if entry is not None:
            return entry
        return {
            "kind": "delegate",
            "object_ref": value.get("object_ref") if isinstance(value.get("object_ref"), int) else 0,
            "function_name": value.get("function_name") if isinstance(value.get("function_name"), str) else "",
        }
    return None


def _project(value: Any, seen: frozenset[int]) -> Any:
    # Lazy imports: object_model and fallback both depend on this module.
    from uasset_read.models.fallback import PropertyFallback, StructFallback
    from uasset_read.models.object_model import ObjectRef

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (bytes, bytearray)):
        return _opaque("bytes", len(value), "raw_bytes")
    if isinstance(value, PropertyFallback):
        return _opaque(value.type, value.size, value.reason.value)
    if isinstance(value, StructFallback):
        return _opaque("StructProperty", value.size, value.reason.value, struct_type=value.struct_type)
    if isinstance(value, SoftObjectPathValue):
        return _project_soft_path(value)
    if isinstance(value, ObjectRef):
        return {"kind": "object_ref", "table": value.table, "index": value.index, "id": f"{value.table}:{value.index}"}
    if isinstance(value, DelegateValue):
        return {"kind": "delegate", "object_ref": value.object_ref, "function_name": value.function_name}
    if isinstance(value, PropertyValue):
        return {"kind": "value", "type": value.type, "value": _project(value.value, seen)}
    if isinstance(value, StructValue):
        return {
            "kind": "struct",
            "struct_type": value.struct_type,
            "fields": {str(k): _project(v, seen) for k, v in value.fields.items()},
        }
    if isinstance(value, MapValue):
        return {
            "kind": "map",
            "key_type": value.key_type,
            "value_type": value.value_type,
            "entries": [
                {"key": _project(e.get("key"), seen), "value": _project(e.get("value"), seen)}
                for e in value.entries
            ],
        }
    if isinstance(value, SetValue):
        return {
            "kind": "set",
            "element_type": value.element_type,
            "elements": [_project(e, seen) for e in value.elements],
        }
    if isinstance(value, EnumValue):
        return {"kind": "enum", "enum_type": value.enum_type, "value": value.value_name}
    if isinstance(value, TextValue):
        return {
            "kind": "text",
            "namespace": value.namespace,
            "key": value.key,
            "source_string": value.source_string,
            "history_type": value.history_type,
        }
    if isinstance(value, list):
        if id(value) in seen:
            return _opaque(type(value).__name__, 0, "recursive")
        seen = seen | {id(value)}
        if _is_delegate_list(value):
            entries = [_delegate_entry(item) for item in value]
            return [entry for entry in entries if entry is not None]
        return {"kind": "array", "elements": [_project(e, seen) for e in value]}
    if isinstance(value, dict):
        if id(value) in seen:
            return _opaque(type(value).__name__, 0, "recursive")
        seen = seen | {id(value)}
        kind = value.get("kind")
        if isinstance(kind, str):
            rebuilt = _project_frozen_dict(kind, value, seen)
            if rebuilt is not None:
                return rebuilt
        # Parser enum dicts (make_enum_value) carry value_name instead of a kind.
        if set(value) == {"enum_type", "value_name"}:
            return {
                "kind": "enum",
                "enum_type": value.get("enum_type") if isinstance(value.get("enum_type"), str) else "",
                "value": value.get("value_name") if isinstance(value.get("value_name"), str) else "",
            }
        return {
            "kind": "struct",
            "struct_type": value.get("struct_type") if isinstance(value.get("struct_type"), str) else "",
            "fields": {str(k): _project(v, seen) for k, v in value.items()},
        }
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        if id(value) in seen:
            return _opaque(type(value).__name__, 0, "recursive")
        try:
            dumped = to_dict()
        except Exception:
            return _opaque(type(value).__name__, 0, "unsupported_type")
        return _project(dumped, seen | {id(value)})
    return _opaque(type(value).__name__, 0, "unsupported_type")


def project_property_value(value: Any) -> Any:
    """JSON-safe projection of one property value using only frozen v4 shapes.

    Scalars stay scalars; typed containers carry a kind discriminator. Fallbacks,
    bytes and unsupported values become opaque descriptors. There is no
    str()/repr() fallback anywhere in this path.
    """
    return _project(value, frozenset())


def project_property_bag(bag: PropertyBag) -> list[dict[str, Any]]:
    """Ordered occurrence array: every entry keeps its name, order and duplicates."""
    occurrences: dict[str, int] = {}
    out: list[dict[str, Any]] = []
    for entry in bag.entries:
        occurrence = occurrences.get(entry.name, 0)
        occurrences[entry.name] = occurrence + 1
        out.append(
            {
                "name": entry.name,
                "type": entry.type_name,
                "occurrence": occurrence,
                "array_index": entry.array_index,
                "value": project_property_value(entry.value),
            }
        )
    return out
