import json
from pathlib import Path

import jsonschema
import pytest

from uasset_read import parse_single
from uasset_read.graph.chain_builder import build_execution_chains
from uasset_read.graph.flow_builder import build_normalized_edge_indexes
from uasset_read.graph.graph_utils import _iter_normalized_edges
from uasset_read.models.core import FEdGraphPinType, UEdGraph, UEdGraphNode, UEdGraphPin


ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "tests" / "samples"
SCHEMA = json.loads((ROOT / "schemas" / "package.schema.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("output_level", ["standard", "debug"])
def test_stackobot_if_then_else_chains_publish_resolved_successors(output_level: str) -> None:
    data = json.loads(parse_single(
        str(SAMPLES / "StackOBot_GI_StackOBot.uasset"),
        format="json", output_level=output_level, force_full_parse=True, log_enabled=False,
    ))
    graphs = [graph for export in data["exports"] for graph in export.get("graphs", [])]
    if_then_else_guids_by_graph = [
        {
            node["node_guid"]
            for node in graph["nodes"]
            if node["node_class"] == "K2Node_IfThenElse"
        }
        for graph in graphs
    ]
    assert any(if_then_else_guids_by_graph)

    branch_paths = [
        (graph, path)
        for graph, if_then_else_guids in zip(graphs, if_then_else_guids_by_graph)
        for chain in graph["execution_chains"]
        for path in chain.get("branch_paths", [])
        if path["from_node_guid"] in if_then_else_guids
    ]
    assert branch_paths
    assert {"then", "else"} <= {path["output_pin"] for _, path in branch_paths}
    assert all(
        path["from_node_guid"] and path["output_pin"] and path["to_node_guid"]
        for _, path in branch_paths
    )
    assert all(
        path["to_node_guid"] in {node["node_guid"] for node in graph["nodes"]}
        for graph, path in branch_paths
    )
    successors_by_output = {
        (from_node_guid, output_pin): {
            path["to_node_guid"]
            for _, path in branch_paths
            if path["from_node_guid"] == from_node_guid and path["output_pin"] == output_pin
        }
        for from_node_guid, output_pin in {
            (path["from_node_guid"], path["output_pin"])
            for _, path in branch_paths
        }
    }
    play_audio_else = successors_by_output[("ee0262e430b7fc47b587fb8183abe5f1", "else")]
    assert "395e6d5e1a85834484b40aab489fd315" in play_audio_else
    assert "1984d156b97e354b820a4c82633c0b0b" not in play_audio_else
    reset_save_game_then = successors_by_output[("9c81310e1263a2438a64864cc219d88a", "then")]
    assert "7305b0f44856774ab33cdce866f53a00" in reset_save_game_then
    assert "bae91e18f018704a9b8d2bd94bf3eb00" not in reset_save_game_then
    assert len(branch_paths) == 9
    jsonschema.validate(data, SCHEMA)


def _exec_pin(pin_id: str, pin_name: str, direction: int, linked_to_raw: list[dict] | None = None) -> UEdGraphPin:
    return UEdGraphPin(
        pin_id=pin_id,
        pin_name=pin_name,
        direction=direction,
        pin_type=FEdGraphPinType(pin_category="exec"),
        linked_to_raw=linked_to_raw or [],
    )


def test_execution_sequence_fan_out_publishes_resolved_successors() -> None:
    entry_guid = "1" * 32
    sequence_guid = "2" * 32
    target_zero_guid = "3" * 32
    target_one_guid = "4" * 32

    graph = UEdGraph(
        graph_name="SequenceFanOut",
        graph_class="EdGraph",
        nodes=[
            UEdGraphNode(
                node_guid=entry_guid,
                class_name="K2Node_FunctionEntry",
                pins=[_exec_pin("a" * 32, "then", 1, [{"pin_guid": "b" * 32}])],
            ),
            UEdGraphNode(
                node_guid=sequence_guid,
                class_name="K2Node_ExecutionSequence",
                pins=[
                    _exec_pin("b" * 32, "execute", 0),
                    _exec_pin("c" * 32, "then_0", 1, [{"pin_guid": "e" * 32}]),
                    _exec_pin("d" * 32, "then_1", 1, [{"pin_guid": "f" * 32}]),
                ],
            ),
            UEdGraphNode(
                node_guid=target_zero_guid,
                class_name="K2Node_CallFunction",
                pins=[_exec_pin("e" * 32, "execute", 0)],
            ),
            UEdGraphNode(
                node_guid=target_one_guid,
                class_name="K2Node_CallFunction",
                pins=[_exec_pin("f" * 32, "execute", 0)],
            ),
        ],
    )

    entries = build_execution_chains(graph)

    assert entries[0]["chain_metadata"]["branch_count"] == 1
    assert entries[0]["branch_paths"] == [
        {
            "from_node_guid": sequence_guid,
            "output_pin": "then_0",
            "to_node_guid": target_zero_guid,
        },
        {
            "from_node_guid": sequence_guid,
            "output_pin": "then_1",
            "to_node_guid": target_one_guid,
        },
    ]


def test_normalized_edges_disambiguate_duplicate_pin_ids_by_linked_to_owner() -> None:
    source_guid = "1" * 32
    target_a_guid = "2" * 32
    target_b_guid = "3" * 32
    source_pin_id = "a" * 32
    shared_target_pin_id = "b" * 32

    target_a = UEdGraphNode(
        node_guid=target_a_guid,
        class_name="K2Node_CallFunction",
        pins=[_exec_pin(shared_target_pin_id, "execute", 0)],
    )
    target_a._export_object_name = "Target_A"
    target_b = UEdGraphNode(
        node_guid=target_b_guid,
        class_name="K2Node_CallFunction",
        pins=[_exec_pin(shared_target_pin_id, "execute", 0)],
    )
    target_b._export_object_name = "Target_B"
    graph = UEdGraph(
        graph_name="DuplicatePinIds",
        graph_class="EdGraph",
        nodes=[
            UEdGraphNode(
                node_guid=source_guid,
                class_name="K2Node_IfThenElse",
                pins=[
                    _exec_pin(
                        source_pin_id,
                        "then",
                        1,
                        [{"pin_guid": shared_target_pin_id, "owning_node": "Target_A"}],
                    )
                ],
            ),
            target_a,
            target_b,
        ],
    )

    edges = list(_iter_normalized_edges(graph))

    assert [edge["to_node_guid"] for edge in edges] == [target_a_guid]


def _input_to_output_duplicate_pin_graph(
    owning_node: str | None,
    source_a_direction: int = 1,
) -> tuple[UEdGraph, str, str, str]:
    source_a_guid = "4" * 32
    source_b_guid = "5" * 32
    target_guid = "6" * 32
    shared_source_pin_id = "c" * 32
    target_pin_id = "d" * 32

    source_a = UEdGraphNode(
        node_guid=source_a_guid,
        class_name="K2Node_CallFunction",
        pins=[_exec_pin(shared_source_pin_id, "then", source_a_direction)],
    )
    source_a._export_object_name = "Source_A"
    source_b = UEdGraphNode(
        node_guid=source_b_guid,
        class_name="K2Node_CallFunction",
        pins=[_exec_pin(shared_source_pin_id, "then", 1)],
    )
    source_b._export_object_name = "Source_B"
    link = {"pin_guid": shared_source_pin_id}
    if owning_node is not None:
        link["owning_node"] = owning_node
    target = UEdGraphNode(
        node_guid=target_guid,
        class_name="K2Node_CallFunction",
        pins=[_exec_pin(target_pin_id, "execute", 0, [link])],
    )
    return (
        UEdGraph(
            graph_name="InputToOutputDuplicatePinIds",
            graph_class="EdGraph",
            nodes=[source_a, source_b, target],
        ),
        source_a_guid,
        source_b_guid,
        target_pin_id,
    )


def test_normalized_edge_indexes_input_to_output_prefer_declared_owner_for_duplicate_pin_ids() -> None:
    graph, source_a_guid, _, target_pin_id = _input_to_output_duplicate_pin_graph("Source_A")

    _, edges_by_to_pin = build_normalized_edge_indexes(graph)

    assert [edge["from_node_guid"] for edge in edges_by_to_pin[target_pin_id]] == [source_a_guid]


def test_normalized_edge_indexes_input_to_output_without_declared_owner_uses_global_lookup() -> None:
    graph, _, source_b_guid, target_pin_id = _input_to_output_duplicate_pin_graph(None)

    _, edges_by_to_pin = build_normalized_edge_indexes(graph)

    assert [edge["from_node_guid"] for edge in edges_by_to_pin[target_pin_id]] == [source_b_guid]


def test_normalized_edge_indexes_input_to_output_with_incompatible_owner_uses_global_lookup() -> None:
    graph, _, source_b_guid, target_pin_id = _input_to_output_duplicate_pin_graph(
        "Source_A", source_a_direction=0,
    )

    _, edges_by_to_pin = build_normalized_edge_indexes(graph)

    assert [edge["from_node_guid"] for edge in edges_by_to_pin[target_pin_id]] == [source_b_guid]


@pytest.mark.parametrize("branch_path", [
    {"from_node_guid": "", "output_pin": "then", "to_node_guid": "a" * 32},
    {"from_node_guid": "a" * 32, "output_pin": "", "to_node_guid": "b" * 32},
    {"from_node_guid": "a" * 32, "output_pin": "then", "to_node_guid": ""},
])
def test_graph_branch_path_schema_rejects_empty_required_fields(branch_path: dict) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            branch_path,
            {"$ref": "#/$defs/GraphBranchPath", "$defs": SCHEMA["$defs"]},
        )
