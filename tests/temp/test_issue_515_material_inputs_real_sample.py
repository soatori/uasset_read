"""Real-fixture acceptance for the FExpressionInput family decoder (#515)."""

from __future__ import annotations

import json
from pathlib import Path

from uasset_read import parse_single

SAMPLE = Path(__file__).resolve().parents[2] / "tests" / "samples" / "StarterContent_M_Wood_Walnut.uasset"

FAMILY = {"ExpressionInput", "ScalarMaterialInput", "VectorMaterialInput", "ColorMaterialInput"}


def _struct_values(node):
    if isinstance(node, dict):
        if node.get("type") == "StructProperty" and isinstance(node.get("value"), dict):
            yield node["value"]
        for v in node.values():
            yield from _struct_values(v)
    elif isinstance(node, list):
        for item in node:
            yield from _struct_values(item)


def test_material_input_family_decodes_in_real_material() -> None:
    data = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True,
        log_enabled=False, output_level="debug",
    ))
    family = [
        v for exp in data.get("exports", [])
        for v in _struct_values(exp.get("properties", []))
        if v.get("struct_type") in FAMILY
    ]
    assert family, "expected ExpressionInput-family structs in the fixture"
    for v in family:
        assert v["parse_status"] == "success", v
        assert v["fields"].get("InputName") is not None
        if v["struct_type"] != "ExpressionInput":
            assert "bUseConstant" in v["fields"]
            assert "Constant" in v["fields"]
    # The fixture previously reported 25 opaque family members (22 + 3).
    assert len(family) >= 25
