"""Canonical key ordering and JSON encoding for deterministic output.

Ensures same input -> byte-identical JSON regardless of dict insertion order.
"""
from __future__ import annotations

from typing import Any

# Public contract top-level key order
_TOP_LEVEL_ORDER = [
    "format", "format_version", "mode", "asset_type",
    "asset", "status", "references", "content",
    "coverage", "diagnostics", "evidence",
]

_ASSET_ORDER = ["package", "name", "generated_class"]
_STATUS_ORDER = ["parse", "representation"]
_COVERAGE_ORDER = ["scopes_expected", "scopes_available", "scopes_unavailable", "notes"]
_DIAGNOSTIC_ORDER = ["severity", "code", "message"]
_REFERENCE_ORDER = ["index", "kind", "class_name", "object_name", "package_path"]
_EVIDENCE_ORDER = ["key", "value"]


def _order_keys(data: dict, key_order: list[str]) -> dict:
    ordered = {}
    for key in key_order:
        if key in data:
            ordered[key] = data[key]
    for key in sorted(data.keys()):
        if key not in ordered:
            ordered[key] = data[key]
    return ordered


def canonical_sort(data: Any) -> Any:
    """Recursively sort dict keys for deterministic JSON output."""
    if isinstance(data, list):
        return [canonical_sort(item) for item in data]
    if not isinstance(data, dict):
        return data

    keys = set(data.keys())
    if keys.issubset(set(_TOP_LEVEL_ORDER)):
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

    return {k: canonical_sort(v) for k, v in ordered.items()}
