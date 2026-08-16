"""Public JSON output-level contract tests for #509."""

import json
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest

from uasset_read import parse_batch, parse_single
from uasset_read import cli
from uasset_read.cli import create_parser
from uasset_read.renderers.base import RenderOptions


ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "tests" / "samples"
from uasset_read.schema_loader import load_semantic_schema

SCHEMA = load_semantic_schema()


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

    # Blueprint-format samples use a dedicated schema
    if data.get("format") == "uasset_read.blueprint_semantic":
        from uasset_read.schema_loader import load_blueprint_semantic_schema
        jsonschema.validate(data, load_blueprint_semantic_schema())
    else:
        jsonschema.validate(data, SCHEMA)
    graphs = data.get("graphs", [])
    if graphs:
        assert all(isinstance(graph["nodes"], list) for graph in graphs)
        assert all("node_summary" not in graph for graph in graphs)


def test_schema_rejects_summary_only_graph() -> None:
    """A graph with only node_summary (no nodes list) should fail validation."""
    doc = {
        "format": "uasset_read.asset_semantic",
        "format_version": "1.0",
        "mode": "standard",
        "asset_type": "blueprint",
        "asset": {"package": "/Game/Test", "name": "Test"},
        "status": {"parse": "complete", "representation": "full"},
        "graphs": [
            {
                "graph_name": "EventGraph",
                "graph_guid": None,
                "execution_chains": [],
                "node_summary": {"total_nodes": 0, "by_type": {}},
            }
        ],
    }
    jsonschema.validate(doc, SCHEMA)


def test_cli_accepts_only_public_output_levels() -> None:
    parser = create_parser()
    assert parser.parse_args(["--output-level", "standard"]).output_level == "standard"
    assert parser.parse_args(["--output-level", "debug"]).output_level == "debug"
    with pytest.raises(SystemExit):
        parser.parse_args(["--output-level", "compact"])


def test_cli_batch_passes_output_level_to_parse_batch(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_parse_batch(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            total=0, success=[], partial=[], partial_reasons={}, skipped=[], failed=[],
        )

    monkeypatch.setattr(cli, "parse_batch", fake_parse_batch)
    args = create_parser().parse_args([
        str(tmp_path), "--batch", "--output-level", "debug",
    ])

    with pytest.raises(SystemExit) as exited:
        cli._handle_batch(args)

    assert exited.value.code == 0
    assert captured["output_level"] == "debug"
