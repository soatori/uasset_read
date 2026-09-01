"""Canonical key ordering and JSON encoding for deterministic output.

Ensures same input -> byte-identical JSON regardless of dict insertion order.
"""

from __future__ import annotations

import json
from typing import Any


def _canonical_value(value: Any) -> str:
    """Deterministic string form of an evidence value for tie-break sorting."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


# Public contract top-level key order
_TOP_LEVEL_ORDER = [
    "format",
    "format_version",
    "mode",
    "asset_type",
    "asset",
    "status",
    "references",
    "content",
    "coverage",
    "diagnostics",
    "evidence",
]

_ASSET_ORDER = ["package", "name", "generated_class"]
_STATUS_ORDER = ["parse", "representation"]
_COVERAGE_ORDER = ["scopes_expected", "scopes_available", "scopes_unavailable", "notes"]
_DIAGNOSTIC_ORDER = ["severity", "code", "message"]
_REFERENCE_ORDER = ["index", "kind", "class_name", "object_name", "package_path"]
_EVIDENCE_ORDER = ["key", "value"]

_ARRAY_SORT_KEYS = {
    "diagnostics": lambda d: (d.get("severity", ""), d.get("code", ""), d.get("message", "")),
    "references": lambda r: (
        r.get("kind", ""),
        r.get("index", 0),
        r.get("class_name", ""),
        r.get("object_name", ""),
        r.get("package_path", ""),
    ),
    "evidence": lambda e: (e.get("key", ""), _canonical_value(e.get("value"))),
}


def _order_keys(data: dict, key_order: list[str]) -> dict:
    """Order keys: contract keys in defined order, then remaining keys sorted."""
    ordered = {}
    for key in key_order:
        if key in data:
            ordered[key] = data[key]
    remaining = sorted(k for k in data.keys() if k not in ordered)
    for key in remaining:
        ordered[key] = data[key]
    return ordered


def canonical_sort(data: Any) -> Any:
    """Recursively sort dict keys for deterministic JSON output."""
    if isinstance(data, list):
        return [canonical_sort(item) for item in data]
    if not isinstance(data, dict):
        return data

    keys = set(data.keys())
    if "format" in keys and "format_version" in keys:
        # Top-level SemanticIR dict (may include merged domain content keys)
        # Contract keys in strict order, then domain keys sorted
        ordered = _order_keys(data, _TOP_LEVEL_ORDER)
    elif keys.issubset(set(_ASSET_ORDER)):
        ordered = _order_keys(data, _ASSET_ORDER)
    elif keys.issubset(set(_STATUS_ORDER)):
        ordered = _order_keys(data, _STATUS_ORDER)
    elif keys.issubset(set(_COVERAGE_ORDER)):
        ordered = _order_keys(data, _COVERAGE_ORDER)
    elif keys.issubset(set(_DIAGNOSTIC_ORDER)):
        ordered = _order_keys(data, _DIAGNOSTIC_ORDER)
    elif keys.issubset(set(_REFERENCE_ORDER)):
        ordered = _order_keys(data, _REFERENCE_ORDER)
    elif keys.issubset(set(_EVIDENCE_ORDER)):
        ordered = _order_keys(data, _EVIDENCE_ORDER)
    else:
        ordered = dict(sorted(data.items()))

    result = {}
    for key, value in ordered.items():
        if key in _ARRAY_SORT_KEYS and isinstance(value, list):
            sorted_items = sorted(value, key=_ARRAY_SORT_KEYS[key])
            result[key] = [canonical_sort(item) for item in sorted_items]
        else:
            result[key] = canonical_sort(value)

    return result
