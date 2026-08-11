# src/uasset_read/semantic/canonical.py
"""Canonical key ordering for deterministic JSON output.

Ensures same input -> byte-identical JSON regardless of dict insertion order.
Top-level keys follow the public contract order.
"""
from __future__ import annotations

from typing import Any

# Public contract top-level key order
_TOP_LEVEL_ORDER = [
    "format",
    "format_version",
    "mode",
    "asset",
    "references",
    "content",
    "coverage",
    "diagnostics",
]

# Asset sub-key order (alphabetical)
_ASSET_ORDER = ["class_name", "kind", "object_name", "package_path", "parse_status"]

# Coverage sub-key order
_COVERAGE_ORDER = ["fields_expected", "fields_parsed", "coverage_pct", "unparsed_fields"]

# Diagnostic sub-key order
_DIAGNOSTIC_ORDER = ["severity", "code", "message"]

# Reference sub-key order
_REFERENCE_ORDER = ["index", "kind", "class_name", "object_name", "package_path"]


def _order_keys(data: dict, key_order: list[str]) -> dict:
    """Order dict keys according to a predefined order, alphabetically for extras."""
    ordered = {}
    for key in key_order:
        if key in data:
            ordered[key] = data[key]
    # Append remaining keys alphabetically
    for key in sorted(data.keys()):
        if key not in ordered:
            ordered[key] = data[key]
    return ordered


def canonical_sort(data: Any) -> Any:
    """Recursively sort dict keys for deterministic JSON output.

    Top-level keys follow the public contract order.
    Nested dicts are sorted alphabetically unless they have a specific order.

    Args:
        data: Any JSON-serializable value

    Returns:
        Same value with all dict keys in deterministic order
    """
    if isinstance(data, list):
        return [canonical_sort(item) for item in data]
    if not isinstance(data, dict):
        return data

    # Determine key order for this level
    if set(data.keys()).issubset(set(_TOP_LEVEL_ORDER)):
        ordered = _order_keys(data, _TOP_LEVEL_ORDER)
    elif set(data.keys()).issubset(set(_ASSET_ORDER)):
        ordered = _order_keys(data, _ASSET_ORDER)
    elif set(data.keys()).issubset(set(_COVERAGE_ORDER)):
        ordered = _order_keys(data, _COVERAGE_ORDER)
    elif set(data.keys()).issubset(set(_DIAGNOSTIC_ORDER)):
        ordered = _order_keys(data, _DIAGNOSTIC_ORDER)
    elif set(data.keys()).issubset(set(_REFERENCE_ORDER)):
        ordered = _order_keys(data, _REFERENCE_ORDER)
    else:
        ordered = dict(sorted(data.items()))

    # Recurse into values
    return {k: canonical_sort(v) for k, v in ordered.items()}
