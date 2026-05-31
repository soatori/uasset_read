"""Helpers for lightweight asset export metadata extraction."""
from __future__ import annotations

from dataclasses import is_dataclass, asdict
from typing import Any


def prop_value(source: Any, *names: str, default: Any = None) -> Any:
    """Return the first matching property value from dict/dataclass/object sources."""
    for name in names:
        value = _get_one(source, name)
        if value is not None:
            return unwrap_property_value(value)
    return default


def unwrap_property_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return getattr(value, "value")
    return value


def as_mapping(value: Any) -> dict[str, Any]:
    value = unwrap_property_value(value)
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "fields") and isinstance(value.fields, dict):
        return value.fields
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def as_list(value: Any) -> list[Any]:
    value = unwrap_property_value(value)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if hasattr(value, "elements"):
        return list(value.elements)
    if hasattr(value, "entries"):
        return list(value.entries)
    return []


def _get_one(source: Any, name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        if name in source:
            return source[name]
        lowered = name.lower()
        for key, value in source.items():
            if str(key).lower() == lowered:
                return value
        return None
    if hasattr(source, "properties"):
        value = _get_one(getattr(source, "properties"), name)
        if value is not None:
            return value
    return getattr(source, name, None)
