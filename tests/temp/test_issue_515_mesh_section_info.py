"""Regression test for #515 MeshSectionInfoMap struct parsing.

MeshSectionInfoMap stores per-section material and collision settings.
UE source: Engine/MeshSectionInfo.h
"""

from __future__ import annotations

import json
from pathlib import Path

from uasset_read import parse_single


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "samples" / "StarterContent_SM_Chair.uasset"


def _find_mesh_section_info_fields() -> list[dict]:
    """Find all MeshSectionInfoMap StructProperty fields in the fixture."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    results = []
    for export in payload["exports"]:
        props = export.get("properties", [])
        for prop in props:
            if prop.get("type") == "StructProperty":
                value = prop.get("value", {})
                if isinstance(value, dict) and value.get("struct_type") in ("MeshSectionInfoMap", "FMeshSectionInfoMap"):
                    results.append({
                        "export": export.get("object_name", "?"),
                        "name": prop.get("name", "?"),
                        "struct_type": value.get("struct_type"),
                        "parse_status": value.get("parse_status", "success"),
                        "fields": value.get("fields", {}),
                    })
    return results


def test_mesh_section_info_is_no_longer_opaque() -> None:
    """MeshSectionInfoMap structs must be parsed (not opaque)."""
    infos = _find_mesh_section_info_fields()
    assert len(infos) > 0, "Expected at least one MeshSectionInfoMap in fixture"

    for info in infos:
        assert info["parse_status"] != "opaque", (
            f"MeshSectionInfoMap '{info['name']}' in '{info['export']}' "
            f"should not be opaque; got '{info['parse_status']}'"
        )
