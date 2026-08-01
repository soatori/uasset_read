import json
from pathlib import Path

import jsonschema
import pytest

from uasset_read import parse_single


ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "tests" / "samples"
SCHEMA = json.loads((ROOT / "schemas" / "package.schema.json").read_text(encoding="utf-8"))


def _render(sample_name: str, output_level: str, *, force_full_parse: bool = False) -> dict:
    return json.loads(parse_single(
        str(SAMPLES / sample_name),
        format="json",
        output_level=output_level,
        force_full_parse=force_full_parse,
        log_enabled=False,
    ))


@pytest.mark.parametrize("output_level", ["standard", "debug"])
def test_als_full_parse_keeps_schema_declared_truncation_count(output_level: str) -> None:
    data = _render("ALS_AnimBP.uasset", output_level, force_full_parse=True)

    assert data["diagnostics_truncated_count"] > 0
    jsonschema.validate(data, SCHEMA)


@pytest.mark.parametrize("output_level", ["standard", "debug"])
def test_guidless_nodes_remain_schema_valid(output_level: str) -> None:
    data = _render("ABP_RifleAnimLayers.uasset", output_level)
    nodes = [
        node
        for export in data["exports"]
        for graph in export.get("graphs", [])
        for node in graph["nodes"]
    ]

    assert any(node["node_guid"] is None for node in nodes)
    jsonschema.validate(data, SCHEMA)
