import json
from pathlib import Path

import jsonschema
import pytest

from uasset_read import parse_single
from uasset_read.graph.chain_builder import build_execution_chains
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
    chains = [chain for graph in graphs for chain in graph["execution_chains"]]
    branch_paths = [path for chain in chains for path in chain.get("branch_paths", [])]

    assert any(
        node["node_class"] == "K2Node_IfThenElse"
        for graph in graphs for node in graph["nodes"]
    )
    assert branch_paths
    assert {"then", "else"} <= {path["output_pin"] for path in branch_paths}
    assert all(
        path["from_node_guid"] and path["output_pin"] and path["to_node_guid"]
        for path in branch_paths
    )
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
