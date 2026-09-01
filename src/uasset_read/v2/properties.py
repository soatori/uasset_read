"""Property bag normalization for v2 documents."""

from __future__ import annotations

from typing import Any, Sequence


def normalize_property_bag(properties: Sequence[Any]) -> dict[str, Any]:
    """Convert a list of parsed properties to a JSON-safe dict.

    - Known properties: name -> serialized value
    - PropertyFallback: name -> opaque descriptor (no raw bytes)
    - StructValue: name -> recursive dict
    - Other PropertyValue: name -> value attribute
    """
    from uasset_read.models.fallback import PropertyFallback
    from uasset_read.models.properties import StructValue, PropertyValue

    bag: dict[str, Any] = {}
    for prop in properties:
        name = getattr(prop, "name", None)
        if name is None:
            continue

        if isinstance(prop, PropertyFallback):
            bag[name] = {
                "kind": "opaque",
                "type": prop.type,
                "size": prop.size,
                "reason": prop.reason.value,
            }
        elif isinstance(prop, StructValue):
            bag[name] = _serialize_value(prop)
        elif isinstance(prop, PropertyValue):
            inner_val = prop.value
            if isinstance(inner_val, StructValue):
                bag[name] = _serialize_value(inner_val)
            else:
                bag[name] = {
                    "kind": "value",
                    "type": prop.type,
                    "value": _serialize_value(inner_val),
                }
    return bag


def _serialize_value(value: Any) -> Any:
    """Recursively serialize a property value to JSON-safe form."""
    from uasset_read.models.fallback import PropertyFallback, StructFallback
    from uasset_read.models.properties import (
        StructValue,
        SetValue,
        MapValue,
        TextValue,
    )

    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        if isinstance(value, bytes):
            return {"kind": "bytes", "length": len(value)}
        return value
    if isinstance(value, PropertyFallback):
        return {
            "kind": "opaque",
            "type": value.type,
            "size": value.size,
            "reason": value.reason.value,
        }
    if isinstance(value, StructValue):
        inner: dict[str, Any] = {}
        for k, v in value.fields.items():
            inner[k] = _serialize_value(v)
        return {"kind": "struct", "struct_type": value.struct_type, "fields": inner}
    if isinstance(value, StructFallback):
        return value.to_dict()
    if isinstance(value, TextValue):
        return {
            "kind": "text",
            "namespace": value.namespace,
            "key": value.key,
            "source_string": value.source_string,
            "property_type": value.property_type,
        }
    if isinstance(value, SetValue):
        return [_serialize_value(elem) for elem in value.elements]
    if isinstance(value, MapValue):
        return [
            {"key": _serialize_value(e.get("key")), "value": _serialize_value(e.get("value"))} for e in value.entries
        ]
    if isinstance(value, list):
        return [_serialize_value(elem) for elem in value]
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    # ObjectRef, other objects — repr as string
    return str(value)
