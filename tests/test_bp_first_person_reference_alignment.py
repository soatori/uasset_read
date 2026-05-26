"""BP_FirstPersonCharacter 参考资产对齐测试。

目标：
1. 锁定仓库内参考资产的基础解析结果。
2. 验证 EventGraph 中的关键触控事件和调用函数可稳定恢复。
3. 验证关键组件名/类可读，避免后续回归。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read import parse_uasset_with_linker


def _find_reference_asset() -> Path:
    """优先使用测试对照 C++ 目录中的参考资产。"""
    repo_root = Path(__file__).resolve().parent.parent
    references_dir = repo_root / "references"

    candidates = sorted(references_dir.rglob("BP_FirstPersonCharacter.uasset"))
    assert candidates, f"Reference asset not found under {references_dir}"

    for candidate in candidates:
        if candidate.parent != references_dir:
            return candidate
    return candidates[0]


@pytest.fixture(scope="module")
def parsed_reference_asset():
    """解析仓库内参考资产。"""
    return parse_uasset_with_linker(str(_find_reference_asset()), tolerant=True)


class TestReferenceAssetBaseline:
    """锁定当前参考资产的基础结构。"""

    def test_reference_asset_parses_successfully(self, parsed_reference_asset):
        assert parsed_reference_asset.is_success, parsed_reference_asset.errors
        assert parsed_reference_asset.errors == []

    def test_reference_asset_graph_names(self, parsed_reference_asset):
        graph_names = [graph.graph_name for graph in parsed_reference_asset.graphs]
        assert graph_names == ["EventGraph", "UserConstructionScript"]

    def test_reference_asset_component_names_and_classes(self, parsed_reference_asset):
        component_pairs = {
            (component["name"], component["class"])
            for component in parsed_reference_asset.components
        }
        expected = {
            ("First Person Camera", "CameraComponent"),
            ("First Person Mesh", "SkeletalMeshComponent"),
            ("CharacterMesh0", "SkeletalMeshComponent"),
            ("CharMoveComp", "CharacterMovementComponent"),
        }
        assert expected.issubset(component_pairs), component_pairs


class TestReferenceEventGraphAlignment:
    """验证 EventGraph 与对照 C++ / 节点文本中的关键语义一致。"""

    @pytest.fixture(scope="class")
    def event_graph(self, parsed_reference_asset):
        graph = next(
            (graph for graph in parsed_reference_asset.graphs if graph.graph_name == "EventGraph"),
            None,
        )
        assert graph is not None, "EventGraph not found"
        return graph

    def test_event_graph_contains_expected_comment(self, event_graph):
        comments = {
            node.node_comment
            for node in event_graph.nodes
            if node.class_name == "EdGraphNode_Comment"
        }
        assert "Touch Inputs for First Person Character" in comments

    def test_event_graph_contains_expected_call_functions(self, event_graph):
        function_names = set()
        for node in event_graph.nodes:
            if node.class_name != "K2Node_CallFunction" or not isinstance(node.node_data, dict):
                continue
            function_reference = node.node_data.get("function_reference")
            if function_reference and function_reference.member_name:
                function_names.add(function_reference.member_name)

        assert {"DoMove", "DoAim", "DoJumpStart", "DoJumpEnd"}.issubset(function_names)

    def test_event_graph_contains_expected_touch_events(self, event_graph):
        event_names = set()
        for node in event_graph.nodes:
            if node.class_name != "K2Node_Event" or not isinstance(node.node_data, dict):
                continue
            event_reference = node.node_data.get("event_reference")
            if event_reference and event_reference.member_name:
                event_names.add(event_reference.member_name)

        expected = {
            "Primary Thumbstick",
            "Secondary Thumbstick",
            "Touch Jump Start",
            "Touch Jump End",
        }
        assert expected.issubset(event_names), event_names
