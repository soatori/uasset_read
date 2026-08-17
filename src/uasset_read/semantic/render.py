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
    content = raw.pop("content", {}) or {}

    # Merge content but do NOT overwrite common contract fields
    _COMMON_FIELDS = {"format", "format_version", "mode", "asset_type", "asset", "status",
                      "references", "coverage", "diagnostics", "evidence"}
    _OVERRIDABLE = {"references", "coverage", "diagnostics"}
    for key, value in content.items():
        if key in _COMMON_FIELDS and key not in _OVERRIDABLE:
            raise ValueError(f"Domain content collides with envelope key: '{key}'")
        if key in _OVERRIDABLE:
            raw[key] = value
        elif key not in raw:
            raw[key] = value
    if include_schema:
        format_to_schema = {
            "uasset_read.asset_semantic": "semantic.schema.json",
            "uasset_read.blueprint_semantic": "blueprint_semantic.schema.json",
            "uasset_read.anim_blueprint_semantic": "anim_blueprint_semantic.schema.json",
            "uasset_read.material_semantic": "material_semantic.schema.json",
            "uasset_read.data_table_semantic": "data_table_semantic.schema.json",
            "uasset_read.skeleton_semantic": "skeleton_semantic.schema.json",
            "uasset_read.mesh_semantic": "mesh_semantic.schema.json",
            "uasset_read.texture_semantic": "texture_semantic.schema.json",
            "uasset_read.sound_semantic": "sound_semantic.schema.json",
            "uasset_read.anim_semantic": "anim_semantic.schema.json",
            "uasset_read.curve_table_semantic": "curve_table_semantic.schema.json",
            "uasset_read.user_defined_semantic": "user_defined_semantic.schema.json",
            "uasset_read.standalone_semantic": "standalone_semantic.schema.json",
            "uasset_read.niagara_semantic": "niagara_semantic.schema.json",
            "uasset_read.movie_semantic": "movie_semantic.schema.json",
        }
        schema_file = format_to_schema.get(ir.format, "semantic.schema.json")
        raw["$schema"] = f"https://github.com/soatori/uasset_read/schemas/{schema_file}"
    raw = canonical_sort(raw)
    cleaned = _strip_none_and_empty(raw)
    return json.dumps(
        cleaned,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
