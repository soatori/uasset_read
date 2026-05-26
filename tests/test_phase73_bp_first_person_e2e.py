"""Phase 73 收敛验收：BP_FirstPersonCharacter 连接稳定性硬断言。"""
import os
from collections import Counter
from typing import Dict, List, Tuple

import pytest

from uasset_read import parse_uasset_with_linker
from uasset_read.formatters.blueprint_text_formatter import format_blueprint_translation_text
from uasset_read.formatters.json_formatter import format_json_full
from uasset_read.graph.flow_builder import (
    build_connections_map,
    build_data_flows,
    build_execution_flows,
    build_function_graphs,
)
from uasset_read.models.core import UEdGraph


SAMPLE_ASSET = "E:\\Develop\\lib\\UnrealEngine\\Samples\\FirstPerson\\Content\\FirstPerson\\Blueprints\\BP_FirstPersonCharacter.uasset"
REFERENCE_ASSET = "E:\\Develop\\uasset_read\\references\\BP_FirstPersonCharacter.uasset"

# 当前基线下限（资产存在时应满足）
MIN_EVENTGRAPH_LINKEDTO_REFS = 12
MIN_EVENTGRAPH_CONNECTIONS = 3
MAX_INVALID_GUID_RATIO = 0.40


@pytest.fixture(scope="module")
def parsed_asset():
    """加载 BP_FirstPersonCharacter.uasset（仅当文件存在时）。"""
    if not os.path.exists(SAMPLE_ASSET):
        pytest.skip(f"Sample asset not found: {SAMPLE_ASSET}")
    return parse_uasset_with_linker(SAMPLE_ASSET)


def _find_graph(graphs: List[UEdGraph], name: str) -> UEdGraph:
    graph = next((g for g in graphs if g.graph_name == name), None)
    assert graph is not None, f"{name} not found in parsed asset"
    return graph


def _node_names(graph: UEdGraph) -> Dict[str, str]:
    return {n.node_guid: f"{n.class_name}_{i}" for i, n in enumerate(graph.nodes)}


def _node_semantics(graph: UEdGraph) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for i, node in enumerate(graph.nodes):
        node_name = f"{node.class_name}_{i}"
        semantic = node.class_name
        data = node.node_data
        ref = None
        if isinstance(data, dict):
            ref = data.get("function_reference") or data.get("event_reference")
            if node.class_name == "K2Node_EnhancedInputAction":
                semantic = data.get("input_action_path") or semantic
        if ref is not None:
            semantic = getattr(ref, "member_name", semantic)
        result[node_name] = semantic
    return result


def _diagnose_graph(graph: UEdGraph) -> Tuple[List[Dict], List[str], int, int, int]:
    connections, warnings = build_connections_map(graph)
    total_linkedto_refs = sum(len(p.linked_to_raw or []) for n in graph.nodes for p in n.pins)
    invalid_guid_count = 0
    unresolved_count = 0
    pin_lookup = {p.pin_id for n in graph.nodes for p in n.pins}

    for node in graph.nodes:
        for pin in node.pins:
            for ref in (pin.linked_to_raw or []):
                target_pin_guid = ref.get("pin_guid") if isinstance(ref, dict) else ref
                if (
                    not isinstance(target_pin_guid, str)
                    or len(target_pin_guid) != 32
                    or target_pin_guid == ("0" * 32)
                    or not all(c in "0123456789ABCDEFabcdef" for c in target_pin_guid)
                ):
                    invalid_guid_count += 1
                elif target_pin_guid not in pin_lookup:
                    unresolved_count += 1

    print(f"\n=== {graph.graph_name} Baseline ===")
    print(f"Nodes: {len(graph.nodes)}")
    print(f"Pins: {sum(len(n.pins) for n in graph.nodes)}")
    print(f"LinkedTo refs: {total_linkedto_refs}")
    print(f"Resolved connections: {len(connections)}")
    print(f"Invalid guid refs: {invalid_guid_count}")
    print(f"Unresolved refs: {unresolved_count}")
    if warnings:
        print(f"Warnings: {warnings}")

    return connections, warnings, total_linkedto_refs, invalid_guid_count, unresolved_count


class TestPhase73E2EConnections:
    """EventGraph/函数图连接稳定性断言。"""

    def test_eventgraph_baseline_thresholds(self, parsed_asset):
        eventgraph = _find_graph(parsed_asset.graphs, "EventGraph")
        connections, _, linkedto_refs, invalid_guid_count, unresolved_count = _diagnose_graph(eventgraph)

        assert linkedto_refs >= MIN_EVENTGRAPH_LINKEDTO_REFS, (
            f"EventGraph LinkedTo refs below baseline: {linkedto_refs} < {MIN_EVENTGRAPH_LINKEDTO_REFS}"
        )
        assert len(connections) >= MIN_EVENTGRAPH_CONNECTIONS, (
            f"EventGraph resolved connections below baseline: {len(connections)} < {MIN_EVENTGRAPH_CONNECTIONS}"
        )
        invalid_ratio = (invalid_guid_count / linkedto_refs) if linkedto_refs else 1.0
        assert invalid_ratio <= MAX_INVALID_GUID_RATIO, (
            f"Invalid guid ratio too high: {invalid_ratio:.2%} > {MAX_INVALID_GUID_RATIO:.2%}"
        )
        assert unresolved_count >= 0  # 仅用于显式输出诊断维度

    def test_move_graph_has_connections(self, parsed_asset):
        move_graph = _find_graph(parsed_asset.graphs, "Move")
        connections, _, _, _, _ = _diagnose_graph(move_graph)
        assert len(connections) >= 1, "Move graph should have at least 1 resolved connection"

    def test_aim_graph_has_connections(self, parsed_asset):
        aim_graph = _find_graph(parsed_asset.graphs, "Aim")
        connections, _, _, _, _ = _diagnose_graph(aim_graph)
        assert len(connections) >= 1, "Aim graph should have at least 1 resolved connection"


class TestFirstPersonGoldenSemantics:
    """完整 FirstPerson 样本与蓝图文本参考的语义对齐。"""

    def test_golden_graph_topology(self, parsed_asset):
        graph_names = {g.graph_name for g in parsed_asset.graphs}
        assert graph_names == {"Aim", "EventGraph", "Move", "UserConstructionScript"}

        event_graph = _find_graph(parsed_asset.graphs, "EventGraph")
        assert len(event_graph.nodes) == 18
        assert Counter(n.class_name for n in event_graph.nodes) == {
            "EdGraphNode_Comment": 3,
            "K2Node_CallFunction": 7,
            "K2Node_EnhancedInputAction": 4,
            "K2Node_Event": 4,
        }

        move_graph = _find_graph(parsed_asset.graphs, "Move")
        assert len(move_graph.nodes) == 11
        move_functions = Counter(
            getattr((n.node_data or {}).get("function_reference"), "member_name", "")
            for n in move_graph.nodes
            if isinstance(n.node_data, dict)
        )
        assert move_functions["AddMovementInput"] == 2
        assert move_functions["GetActorRightVector"] == 1
        assert move_functions["GetActorForwardVector"] == 1
        assert Counter(n.class_name for n in move_graph.nodes)["K2Node_Knot"] == 4

    def test_eventgraph_execution_and_data_edges(self, parsed_asset):
        graph = _find_graph(parsed_asset.graphs, "EventGraph")
        semantics = _node_semantics(graph)
        connections, _ = build_connections_map(graph)

        semantic_edges = {
            (semantics.get(c["from"]["node"]), c["from"]["pin"], semantics.get(c["to"]["node"]))
            for c in connections
        }
        assert ("IA_Move", "Triggered", "Move") in semantic_edges
        assert ("IA_Look", "Triggered", "Aim") in semantic_edges
        assert ("IA_MouseLook", "Triggered", "Aim") in semantic_edges
        assert ("IA_Jump", "Started", "Jump") in semantic_edges
        assert ("IA_Jump", "Completed", "StopJumping") in semantic_edges
        assert ("Touch Jump Start", "then", "Jump") in semantic_edges
        assert ("Touch Jump End", "then", "StopJumping") in semantic_edges

        data_flows = build_data_flows(graph)
        semantic_data = {
            (semantics.get(d["source"]["node"]), d["source"]["pin"], semantics.get(d["target"]["node"]), d["target"]["pin"])
            for d in data_flows
        }
        assert ("IA_Move", "ActionValue_X", "Move", "Left / Right") in semantic_data
        assert ("IA_Move", "ActionValue_Y", "Move", "Forward / Backward") in semantic_data
        assert ("Primary Thumbstick", "Axis_X", "Move", "Left / Right") in semantic_data
        assert ("Secondary Thumbstick", "Axis_Y", "Aim", "Pitch") in semantic_data

    def test_function_graphs_include_function_implementation(self, parsed_asset):
        move_graph = _find_graph(parsed_asset.graphs, "Move")
        move_flows = build_execution_flows(move_graph)
        assert any(
            [n.get("function_name") for n in flow["nodes"]] == ["Move", "AddMovementInput", "AddMovementInput"]
            for flow in move_flows
        )

        move_data = build_data_flows(move_graph)
        move_semantics = _node_semantics(move_graph)
        semantic_data = {
            (move_semantics.get(d["source"]["node"]), d["source"]["pin"], move_semantics.get(d["target"]["node"]), d["target"]["pin"])
            for d in move_data
        }
        assert ("GetActorRightVector", "ReturnValue", "AddMovementInput", "WorldDirection") in semantic_data
        assert ("Move", "Left / Right", "AddMovementInput", "ScaleValue") in semantic_data
        assert ("GetActorForwardVector", "ReturnValue", "AddMovementInput", "WorldDirection") in semantic_data
        assert ("Move", "Forward / Backward", "AddMovementInput", "ScaleValue") in semantic_data

        function_graphs = build_function_graphs(parsed_asset.graphs, parsed_asset.blueprint.functions if parsed_asset.blueprint else None)
        assert {"Aim", "Move", "UserConstructionScript"} <= {fg["function_name"] for fg in function_graphs}

    def test_outputs_are_readable(self, parsed_asset):
        output = format_json_full(parsed_asset, include_function_graphs=True)
        assert {"Aim", "Move"} <= {fg["function_name"] for fg in output["function_graphs"]}

        text = format_blueprint_translation_text(parsed_asset)
        assert "InputAction: IA_Move" in text
        assert "InputAction: IA_Jump" in text
        assert "_parse_error" not in text
        assert "\x00" not in text


def test_reference_asset_is_a_smaller_version():
    """references 下的资产不是完整金标准，只验收其真实存在的图。"""
    if not os.path.exists(REFERENCE_ASSET):
        pytest.skip(f"Reference asset not found: {REFERENCE_ASSET}")
    result = parse_uasset_with_linker(REFERENCE_ASSET)
    assert {g.graph_name for g in result.graphs} == {"EventGraph", "UserConstructionScript"}
    event_graph = _find_graph(result.graphs, "EventGraph")
    assert Counter(n.class_name for n in event_graph.nodes) == {
        "EdGraphNode_Comment": 1,
        "K2Node_CallFunction": 4,
        "K2Node_Event": 4,
    }
