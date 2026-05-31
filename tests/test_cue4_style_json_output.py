from __future__ import annotations

from uasset_read.formatters import format_json_full


def test_blueprint_nodes_are_flattened_for_standard_dto(sample_result) -> None:
    data = format_json_full(sample_result)
    blueprint = data["blueprint"]

    assert blueprint["NodeCount"] == len(blueprint["Nodes"])
    assert blueprint["PackageName"]
    assert "BlueprintClass" in blueprint
    assert blueprint["Graphs"]
    assert blueprint["Nodes"]
    assert "Warnings" in blueprint
    assert "graphs" not in blueprint
    assert "graphs_summary" not in data

    first_node = blueprint["Nodes"][0]
    assert {
        "GraphName",
        "Type",
        "Name",
        "NodePosX",
        "NodePosY",
        "Pins",
    } <= set(first_node)


def test_graph_nodes_use_standard_node_and_pin_fields(sample_result) -> None:
    data = format_json_full(sample_result)
    first_node = data["blueprint"]["Nodes"][0]

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
