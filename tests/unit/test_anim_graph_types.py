"""动画图类型识别测试"""
from uasset_read.ir_builder import _build_graph_ir
from unittest.mock import MagicMock


def test_animation_state_machine_graph():
    """应该识别 AnimationStateMachineGraph"""
    graph = MagicMock()
    graph.graph_class = "UAnimationStateMachineGraph"
    graph.graph_name = "TestStateMachine"
    graph.graph_guid = "00000000-0000-0000-0000-000000000001"
    graph.nodes = []
    graph.execution_chains = []
    graph.subgraphs = []

    result = _build_graph_ir(graph)
    assert result.graph_type == "state_machine"


def test_animation_state_graph():
    """应该识别 AnimationStateGraph"""
    graph = MagicMock()
    graph.graph_class = "UAnimationStateGraph"
    graph.graph_name = "TestState"
    graph.graph_guid = "00000000-0000-0000-0000-000000000002"
    graph.nodes = []
    graph.execution_chains = []
    graph.subgraphs = []

    result = _build_graph_ir(graph)
    assert result.graph_type == "state"


def test_animation_transition_graph():
    """应该识别 AnimationTransitionGraph"""
    graph = MagicMock()
    graph.graph_class = "UAnimationTransitionGraph"
    graph.graph_name = "TestTransition"
    graph.graph_guid = "00000000-0000-0000-0000-000000000003"
    graph.nodes = []
    graph.execution_chains = []
    graph.subgraphs = []

    result = _build_graph_ir(graph)
    assert result.graph_type == "transition"


def test_animation_conduit_graph():
    """应该识别 AnimationConduitGraph"""
    graph = MagicMock()
    graph.graph_class = "UAnimationConduitGraph"
    graph.graph_name = "TestConduit"
    graph.graph_guid = "00000000-0000-0000-0000-000000000004"
    graph.nodes = []
    graph.execution_chains = []
    graph.subgraphs = []

    result = _build_graph_ir(graph)
    assert result.graph_type == "conduit"


def test_animation_graph():
    """应该识别 AnimationGraph"""
    graph = MagicMock()
    graph.graph_class = "UAnimationGraph"
    graph.graph_name = "TestAnimGraph"
    graph.graph_guid = "00000000-0000-0000-0000-000000000005"
    graph.nodes = []
    graph.execution_chains = []
    graph.subgraphs = []

    result = _build_graph_ir(graph)
    assert result.graph_type == "animation"
