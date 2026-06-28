"""动画图类型识别测试"""
import pytest
from unittest.mock import MagicMock
from uasset_read.ir_builder import _build_graph_ir


GRAPH_CASES = [
    ("UAnimationStateMachineGraph", "state_machine"),
    ("UAnimationStateGraph", "state"),
    ("UAnimationTransitionGraph", "transition"),
    ("UAnimationConduitGraph", "conduit"),
    ("UAnimationGraph", "animation"),
]


@pytest.mark.parametrize("graph_class,expected_type", GRAPH_CASES,
                         ids=[c[0].removeprefix("U") for c in GRAPH_CASES])
def test_animation_graph_type_recognition(graph_class, expected_type):
    """应正确识别动画图类型"""
    graph = MagicMock()
    graph.graph_class = graph_class
    graph.graph_name = f"Test{graph_class.removeprefix('U')}"
    graph.graph_guid = "00000000-0000-0000-0000-000000000001"
    graph.nodes = []
    graph.execution_chains = []
    graph.subgraphs = []

    result = _build_graph_ir(graph)
    assert result.graph_type == expected_type
