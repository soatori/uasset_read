"""Helpers for safe asset-type metadata projection."""

from __future__ import annotations

import dataclasses
from typing import Any


_DROP = object()
_RAW_PAYLOAD_KEYS = frozenset({"raw_bytes", "raw_data"})


def _sanitize(value: Any) -> Any:
    if isinstance(value, bytes):
        return _DROP
    if dataclasses.is_dataclass(value):
        value = dataclasses.asdict(value)
    if isinstance(value, dict):
        cleaned: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in _RAW_PAYLOAD_KEYS:
                continue
            sanitized = _sanitize(item)
            if sanitized is not _DROP:
                cleaned[key] = sanitized
        return cleaned
    if isinstance(value, (list, tuple)):
        return [sanitized for item in value if (sanitized := _sanitize(item)) is not _DROP]
    return value


def sanitize_asset_metadata(value: Any) -> Any:
    """Recursively remove raw byte payloads and their conventional keys."""
    sanitized = _sanitize(value)
    return None if sanitized is _DROP else sanitized


def has_meaningful_metadata(value: Any) -> bool:
    """Return whether a projected value contains actual business metadata."""
    return value is not None and value != "" and value != {} and value != []
