"""Acceptance coverage for compact graphs and structured diagnostics (#507, #509)."""

import json
from pathlib import Path

from uasset_read import parse_single
from uasset_read.renderers.json_renderer import JSONRenderer


SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def _render_sample(name: str, output_level: str = "standard") -> str:
    return parse_single(
        str(SAMPLES_DIR / name),
        format="json",
        tolerant=True,
        output_level=output_level,
    )


def test_repeated_structured_diagnostics_are_aggregated_with_evidence() -> None:
    renderer = JSONRenderer()
    diagnostics = [
        {
            "code": "invalid_serial_size",
            "severity": "warning",
            "stage": "read_export_map",
            "fallback": "set_to_zero",
            "raw_value": value,
            "offset": offset,
        }
        for value, offset in ((-5, 10), (-2, 20), (-9, 30), (-1, 40))
    ]

    aggregated = renderer._aggregate_structured_diagnostics(diagnostics)

    assert aggregated == [{
        "code": "invalid_serial_size",
        "severity": "warning",
        "stage": "read_export_map",
        "fallback": "set_to_zero",
        "count": 4,
        "raw_value_range": {"min": -9, "max": -1},
        "offset_examples": [10, 20, 30],
    }]


def test_als_repeated_serial_diagnostics_are_compact() -> None:
    output = _render_sample("ALS_AnimBP.uasset")
    data = json.loads(output)
    matches = [
        item for item in data["diagnostics"]
        if item.get("code") == "invalid_serial_size"
    ]

    assert len(matches) == 1
    assert matches[0]["count"] > 1
    assert len(output.splitlines()) < 30_000
    assert len(output.encode("utf-8")) < 3 * 1024 * 1024


def test_compact_graph_output_uses_summaries_without_changing_standard_nodes() -> None:
    standard = json.loads(_render_sample("FirstPerson_BP_FirstPersonCharacter.uasset"))
    compact = json.loads(_render_sample("FirstPerson_BP_FirstPersonCharacter.uasset", "compact"))
    standard_graphs = [graph for export in standard["exports"] for graph in export.get("graphs", [])]
    compact_graphs = [graph for export in compact["exports"] for graph in export.get("graphs", [])]

    assert standard_graphs and all("nodes" in graph for graph in standard_graphs)
    assert compact_graphs and all("nodes" not in graph and "node_summary" in graph for graph in compact_graphs)
    assert all({"total_nodes", "by_type"} <= graph["node_summary"].keys() for graph in compact_graphs)
