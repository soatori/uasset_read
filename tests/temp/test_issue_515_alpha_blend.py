"""Regression test for #515 AlphaBlend struct parsing.

AlphaBlend is used in animation montage blend parameters.
UE source: Engine/Animation/AlphaBlend.h
"""

from __future__ import annotations

import json
from pathlib import Path

from uasset_read import parse_single


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "samples" / "ALS_CLF_GetUp_Back_Montage_Default.uasset"


def _find_alpha_blend_fields() -> list[dict]:
    """Find all AlphaBlend StructProperty fields in the fixture."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    results = []
    for export in payload["exports"]:
        props = export.get("properties", [])
        for prop in props:
            if prop.get("type") == "StructProperty":
                value = prop.get("value", {})
                if isinstance(value, dict) and value.get("struct_type") in ("AlphaBlend", "FAlphaBlend"):
                    results.append({
                        "export": export.get("object_name", "?"),
                        "name": prop.get("name", "?"),
                        "struct_type": value.get("struct_type"),
                        "parse_status": value.get("parse_status", "success"),
                        "fields": value.get("fields", {}),
                    })
    return results


def test_alpha_blend_is_no_longer_opaque() -> None:
    """AlphaBlend structs must be parsed (not opaque)."""
    blends = _find_alpha_blend_fields()
    assert len(blends) > 0, "Expected at least one AlphaBlend in fixture"

    for blend in blends:
        assert blend["parse_status"] != "opaque", (
            f"AlphaBlend '{blend['name']}' in '{blend['export']}' "
            f"should not be opaque; got '{blend['parse_status']}'"
        )
