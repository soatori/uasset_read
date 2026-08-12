"""Semantic JSON renderer — deterministic encoding, no business logic.

Only canonicalizes key ordering and encodes JSON. Does NOT perform
asset classification, field omission, or other semantic decisions.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from uasset_read.semantic.models import SemanticIR
from uasset_read.semantic.canonical import canonical_sort


def _strip_none_and_empty(data: Any) -> Any:
    """Recursively remove None values and empty containers."""
    if isinstance(data, dict):
        return {
            k: _strip_none_and_empty(v)
            for k, v in data.items()
            if v is not None and v != () and v != [] and v != {}
        }
    if isinstance(data, (list, tuple)):
        return [_strip_none_and_empty(item) for item in data]
    return data


def render_semantic_json(ir: SemanticIR, *, include_schema: bool = False) -> str:
    """Render SemanticIR to deterministic JSON string.

    Args:
        ir: Validated SemanticIR
        include_schema: If True, emit ``$schema`` URI in the output.
            Default False — do not emit ``$schema``.

    Returns:
        UTF-8 JSON string with LF line endings, ending with exactly one newline.
    """
    raw = asdict(ir)
    if include_schema:
        raw["$schema"] = "https://github.com/soatori/uasset_read/schemas/semantic.schema.json"
    raw = canonical_sort(raw)
    cleaned = _strip_none_and_empty(raw)
    return json.dumps(
        cleaned,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
