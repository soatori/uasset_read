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


def test_repeated_structured_diagnostics_preserve_bounded_audit_context() -> None:
    diagnostics = [
        {
            "code": "invalid_serial_size", "severity": "warning",
            "asset": "ALS_AnimBP.uasset", "stage": "read_export_map",
            "offset": offset, "raw_value": value, "ue_version": "5.x",
            "fallback": "set_to_zero", "message": message,
        }
        for value, offset, message in (
            (-5, 10, "export 0 has invalid serial size"),
            (-2, 20, "export 1 has invalid serial size"),
            (-9, 30, "export 2 has invalid serial size"),
            (-1, 40, "export 3 has invalid serial size"),
        )
    ]

    assert JSONRenderer()._aggregate_structured_diagnostics(diagnostics) == [{
        "code": "invalid_serial_size",
        "severity": "warning",
        "asset": "ALS_AnimBP.uasset",
        "stage": "read_export_map",
        "ue_version": "5.x",
        "fallback": "set_to_zero",
        "count": 4,
        "message_examples": [
            "export 0 has invalid serial size", "export 1 has invalid serial size",
            "export 2 has invalid serial size",
        ],
        "raw_value_range": {"min": -9, "max": -1},
        "offset_range": {"min": 10, "max": 40},
        "offset_examples": [10, 20, 30],
    }]


def test_structured_diagnostic_fallback_none_and_empty_string_do_not_merge() -> None:
    diagnostics = [
        {
            "code": "invalid_serial_size", "severity": "warning",
            "stage": "read_export_map", "fallback": fallback,
        }
        for fallback in (None, "")
    ]

    aggregated = JSONRenderer()._aggregate_structured_diagnostics(diagnostics)

    assert len(aggregated) == 2
    assert [item["fallback"] for item in aggregated] == [None, ""]


def test_als_repeated_serial_diagnostics_are_compact_and_auditable() -> None:
    output = _render_sample("ALS_AnimBP.uasset")
    data = json.loads(output)
    aggregate = next(item for item in data["diagnostics"]
                     if item.get("code") == "invalid_serial_size")
    assert aggregate["count"] == 92
    assert aggregate["asset"].endswith("ALS_AnimBP.uasset")
    assert aggregate["ue_version"] == data["summary"]["ue_version"] == "5.x"
    assert len(aggregate["message_examples"]) == 3
    assert aggregate["offset_range"]["min"] <= min(aggregate["offset_examples"])
    assert aggregate["offset_range"]["max"] >= max(aggregate["offset_examples"])
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
