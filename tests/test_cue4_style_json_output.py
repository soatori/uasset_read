from __future__ import annotations

from uasset_read.formatters import format_json_full


def test_blueprint_nodes_are_flattened_for_cue4_style_diff(sample_result) -> None:
    data = format_json_full(sample_result)
    blueprint = data["blueprint"]

    assert blueprint["NodeCount"] == sum(
        len(graph["nodes"]) for graph in blueprint["graphs"]
    )
    assert blueprint["PackageName"]
    assert "BlueprintClass" in blueprint
    assert blueprint["Graphs"]
    assert blueprint["Nodes"]
    assert "Warnings" in blueprint

    first_node = blueprint["Nodes"][0]
    assert {
        "GraphName",
        "Type",
        "Name",
        "NodePosX",
        "NodePosY",
        "Pins",
    } <= set(first_node)


def test_graph_nodes_use_cue4_style_node_and_pin_fields(sample_result) -> None:
    data = format_json_full(sample_result)
    first_graph = data["blueprint"]["graphs"][0]
    first_node = first_graph["nodes"][0]

    assert "node_type" not in first_node
    assert "node_name" not in first_node
    assert {"Type", "Name", "NodePosX", "NodePosY", "Pins"} <= set(first_node)

    if first_node["Pins"]:
        first_pin = first_node["Pins"][0]
        assert {
            "PinId",
            "PinName",
            "Direction",
            "PinCategory",
            "LinkedTo",
        } <= set(first_pin)
