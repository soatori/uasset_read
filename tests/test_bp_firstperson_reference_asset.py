from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from uasset_read import parse_uasset_with_linker
from uasset_read.formatters import format_json_full
from uasset_read.kismet.pipeline import decompile_uasset


ASSET = Path(__file__).resolve().parents[1] / "docs" / "references" / "BP_FirstPersonCharacter.uasset"


def _call_nodes(graph_payload: dict) -> dict[str, dict]:
    calls = {}
    for node in graph_payload["nodes"]:
        if node["node_type"] != "K2Node_CallFunction":
            continue
        ref = node.get("function_reference") or {}
        calls[ref.get("member_name", "")] = node
    return calls


def _event_nodes(graph_payload: dict) -> dict[str, dict]:
    events = {}
    for node in graph_payload["nodes"]:
        if node["node_type"] != "K2Node_Event":
            continue
        ref = node.get("event_reference") or {}
        events[ref.get("member_name", "")] = node
    return events


def _run_cli_json() -> dict:
    env = os.environ.copy()
    src_root = str(Path(__file__).resolve().parents[1] / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_root if not existing else f"{src_root}{os.pathsep}{existing}"
    proc = subprocess.run(
        [sys.executable, "-m", "uasset_read", str(ASSET), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8-sig",
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_reference_asset_graph_json_pin_contract() -> None:
    result = parse_uasset_with_linker(str(ASSET), tolerant=True)
    assert result.is_success

    payload = format_json_full(result)
    graphs = {graph["graph_name"]: graph for graph in payload["blueprint"]["graphs"]}
    assert set(graphs) == {"EventGraph", "UserConstructionScript"}
    assert [(graph.graph_name, len(graph.nodes), sum(len(node.pins) for node in graph.nodes)) for graph in result.graphs] == [
        ("EventGraph", 9, 30),
        ("UserConstructionScript", 1, 1),
    ]

    event_graph = graphs["EventGraph"]
    calls = _call_nodes(event_graph)
    events = _event_nodes(event_graph)
    assert set(calls) == {"DoMove", "DoJumpStart", "DoJumpEnd", "DoAim"}
    assert set(events) == {"Primary Thumbstick", "Touch Jump Start", "Touch Jump End", "Secondary Thumbstick"}

    for node in [*calls.values(), *events.values()]:
        assert "pins" in node
        assert "links" in node
        assert all("pin_type" in pin for pin in node["pins"])

    assert events["Primary Thumbstick"]["event_reference"]["member_parent"] == "BPI_TouchInterface_C"
    assert any(link["target"]["pin"] == "Right" for link in events["Primary Thumbstick"]["links"])
    assert any(link["target"]["pin"] == "Forward" for link in events["Primary Thumbstick"]["links"])
    assert any(link["target"]["pin"] == "Yaw" for link in events["Secondary Thumbstick"]["links"])
    assert any(link["target"]["pin"] == "Pitch" for link in events["Secondary Thumbstick"]["links"])


def test_reference_asset_cli_json_uses_linker_backed_graphs() -> None:
    payload = _run_cli_json()
    graphs = {graph["graph_name"]: graph for graph in payload["blueprint"]["graphs"]}
    event_graph = graphs["EventGraph"]
    events = _event_nodes(event_graph)

    assert len(event_graph["nodes"]) == 9
    assert events["Primary Thumbstick"]["event_reference"]["member_parent"] == "BPI_TouchInterface_C"
    assert any(node["pins"] for node in event_graph["nodes"] if node["node_type"] == "K2Node_CallFunction")


def test_reference_asset_component_structs_do_not_cascade_parse_errors() -> None:
    result = parse_uasset_with_linker(str(ASSET), tolerant=True)
    exports = {export.object_name: export for export in result.export_map}

    bp_props = {prop.name: prop for prop in exports["BP_FirstPersonCharacter"].properties}
    assert bp_props["BlueprintGuid"].value.struct_type == "Guid"

    mesh_props = {prop.name: prop for prop in exports["CharacterMesh0"].properties}
    assert mesh_props["RelativeLocation"].type == "StructProperty"
    assert mesh_props["RelativeLocation"].value.struct_type == "Vector"
    assert mesh_props["RelativeLocation"].value.fields == {"X": -20.0, "Y": 0.0, "Z": -96.0}
    assert mesh_props["RelativeRotation"].type == "StructProperty"
    assert mesh_props["RelativeRotation"].value.struct_type == "Rotator"


def test_reference_asset_kismet_fallback_produces_ir() -> None:
    results = decompile_uasset(str(ASSET), tolerant=True)
    by_name = {result.function_name: result for result in results}

    assert set(by_name) == {
        "ExecuteUbergraph_BP_FirstPersonCharacter",
        "Primary Thumbstick",
        "Secondary Thumbstick",
        "Touch Jump End",
        "Touch Jump Start",
    }
    assert all(result.bytecode_status == "parsed" for result in results)
    assert all(result.expressions for result in results)
