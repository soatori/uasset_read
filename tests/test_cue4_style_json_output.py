from __future__ import annotations

from uasset_read.formatters import format_json_full


def test_blueprint_nodes_are_flattened_for_cue4_style_diff(sample_result) -> None:
    data = format_json_full(sample_result)
    blueprint = data["blueprint"]

    assert blueprint["node_count"] == sum(
        len(graph["nodes"]) for graph in blueprint["graphs"]
    )
    assert blueprint["graph_names"]
    assert blueprint["nodes"]

    first_node = blueprint["nodes"][0]
    assert {
        "graph_name",
        "type",
        "name",
        "node_pos_x",
        "node_pos_y",
        "pins",
    } <= set(first_node)


def test_graph_nodes_use_cue4_style_node_and_pin_fields(sample_result) -> None:
    data = format_json_full(sample_result)
    first_graph = data["blueprint"]["graphs"][0]
    first_node = first_graph["nodes"][0]

    assert "node_type" not in first_node
    assert "node_name" not in first_node
    assert {"type", "name", "node_pos_x", "node_pos_y", "pins"} <= set(first_node)

    if first_node["pins"]:
        first_pin = first_node["pins"][0]
        assert {
            "PinId",
            "PinName",
            "Direction",
            "PinCategory",
            "LinkedTo",
        } <= set(first_pin)
