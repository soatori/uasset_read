"""Regression test for #515 MeshNaniteSettings struct parsing.

MeshNaniteSettings stores Nanite virtual geometry configuration.
UE source: Engine/StaticMesh.h
"""

from __future__ import annotations

import json
from pathlib import Path

from uasset_read import parse_single


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "samples" / "StarterContent_SM_Chair.uasset"


def _find_nanite_settings_fields() -> list[dict]:
    """Find all MeshNaniteSettings StructProperty fields in the fixture."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    results = []
    for export in payload["exports"]:
        props = export.get("properties", [])
        for prop in props:
            if prop.get("type") == "StructProperty":
                value = prop.get("value", {})
                if isinstance(value, dict) and value.get("struct_type") in ("MeshNaniteSettings", "FMeshNaniteSettings"):
                    results.append({
                        "export": export.get("object_name", "?"),
                        "name": prop.get("name", "?"),
                        "struct_type": value.get("struct_type"),
                        "parse_status": value.get("parse_status", "success"),
                        "fields": value.get("fields", {}),
                    })
    return results


def test_mesh_nanite_settings_is_no_longer_opaque() -> None:
    """MeshNaniteSettings structs must be parsed (not opaque)."""
    settings = _find_nanite_settings_fields()
    assert len(settings) > 0, "Expected at least one MeshNaniteSettings in fixture"

    for s in settings:
        assert s["parse_status"] != "opaque", (
            f"MeshNaniteSettings '{s['name']}' in '{s['export']}' "
            f"should not be opaque; got '{s['parse_status']}'"
        )
