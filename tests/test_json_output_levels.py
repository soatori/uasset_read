"""Public JSON output-level contract tests for #509."""

import json
from pathlib import Path

import jsonschema
import pytest

from uasset_read import parse_batch, parse_single
from uasset_read.cli import create_parser
from uasset_read.renderers.base import RenderOptions


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "tests" / "samples"
SCHEMA = json.loads((ROOT / "schemas" / "package.schema.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("level", ["compact", "verbose", ""])
def test_render_options_reject_unknown_output_levels(level: str) -> None:
    with pytest.raises(ValueError, match=rf"{level!r}.*standard.*debug"):
        RenderOptions(output_level=level)


def test_parse_single_rejects_compact_output_level() -> None:
    with pytest.raises(ValueError, match="'compact'.*standard.*debug"):
        parse_single(
            str(SAMPLES / "FirstPerson_BP_FirstPersonCharacter.uasset"),
            format="json",
            output_level="compact",
            log_enabled=False,
        )


def test_parse_batch_rejects_compact_before_scanning_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="'compact'.*standard.*debug"):
        parse_batch(str(tmp_path), output_level="compact", log_enabled=False)


@pytest.mark.parametrize("level", ["standard", "debug"])
def test_graphs_use_nodes_only_and_validate(level: str) -> None:
    data = json.loads(parse_single(
        str(SAMPLES / "FirstPerson_BP_FirstPersonCharacter.uasset"),
        format="json",
        output_level=level,
        log_enabled=False,
    ))

    jsonschema.validate(data, SCHEMA)
    graphs = [graph for export in data["exports"] for graph in export.get("graphs", [])]
    assert graphs
    assert all(isinstance(graph["nodes"], list) for graph in graphs)
    assert all("node_summary" not in graph for graph in graphs)


def test_schema_rejects_summary_only_graph() -> None:
    graph = {
        "graph_name": "EventGraph",
        "graph_guid": None,
        "execution_chains": [],
        "node_summary": {"total_nodes": 0, "by_type": {}},
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            graph,
            {"$ref": "#/$defs/GraphEntry", "$defs": SCHEMA["$defs"]},
        )


def test_cli_accepts_only_public_output_levels() -> None:
    parser = create_parser()
    assert parser.parse_args(["--output-level", "standard"]).output_level == "standard"
    assert parser.parse_args(["--output-level", "debug"]).output_level == "debug"
    with pytest.raises(SystemExit):
        parser.parse_args(["--output-level", "compact"])
