"""验证链式输出显示执行引脚名称。"""
from uasset_read.graph.chain_builder import build_execution_chains


class MockNode:
    """模拟 UEdGraphNode，仅保留链构建所需的属性。"""
    def __init__(self, guid, class_name=""):
        self.node_guid = guid
        self.class_name = class_name


class MockGraph:
    """模拟 UEdGraph，仅保留链构建所需的属性。"""
    def __init__(self, nodes):
        self.nodes = nodes


def test_chain_shows_exec_pin_names():
    """链式字符串应包含执行引脚名称。"""
    mock_flows = [
        {
            "start_event": "Event.BeginPlay",
            "nodes": [
                {"node_guid": "g1", "node_type": "K2Node_Event", "used_exec_pin_name": "exec"},
                {"node_guid": "g2", "node_type": "K2Node_CallFunction", "used_exec_pin_name": "Then"},
                {"node_guid": "g3", "node_type": "K2Node_CallFunction", "used_exec_pin_name": "Completed"},
            ],
        }
    ]

    mock_graph = MockGraph([
        MockNode("g1", "K2Node_Event"),
        MockNode("g2", "K2Node_CallFunction"),
        MockNode("g3", "K2Node_CallFunction"),
    ])

    chains = build_execution_chains(mock_graph, mock_flows)
    assert len(chains) > 0
    chain_str = chains[0].get("chains", [""])[0]
    # 链应包含引脚名称: N0--Then-->N1--Completed-->N2
    assert "Then" in chain_str, f"链应包含 'Then' 引脚名称: {chain_str}"
    assert "Completed" in chain_str, f"链应包含 'Completed' 引脚名称: {chain_str}"


def test_chain_fallback_to_arrow_without_pin_names():
    """无引脚名称时应使用简单的箭头格式。"""
    mock_flows = [
        {
            "start_event": "Event.BeginPlay",
            "nodes": [
                {"node_guid": "g1", "node_type": "K2Node_Event"},
                {"node_guid": "g2", "node_type": "K2Node_CallFunction"},
            ],
        }
    ]

    mock_graph = MockGraph([
        MockNode("g1", "K2Node_Event"),
        MockNode("g2", "K2Node_CallFunction"),
    ])

    chains = build_execution_chains(mock_graph, mock_flows)
    chain_str = chains[0].get("chains", [""])[0]
    assert "->" in chain_str, f"链应包含箭头: {chain_str}"
    # 不应包含 -- 引脚名称格式
    assert "--" not in chain_str, f"无引脚名称时不应包含 '--': {chain_str}"


def test_chain_mixed_pin_names():
    """部分节点有引脚名称、部分没有时应正确混合。"""
    mock_flows = [
        {
            "start_event": "Event.BeginPlay",
            "nodes": [
                {"node_guid": "g1", "node_type": "K2Node_Event", "used_exec_pin_name": "exec"},
                {"node_guid": "g2", "node_type": "K2Node_CallFunction"},  # 无引脚名称
                {"node_guid": "g3", "node_type": "K2Node_CallFunction", "used_exec_pin_name": "Completed"},
            ],
        }
    ]

    mock_graph = MockGraph([
        MockNode("g1", "K2Node_Event"),
        MockNode("g2", "K2Node_CallFunction"),
        MockNode("g3", "K2Node_CallFunction"),
    ])

    chains = build_execution_chains(mock_graph, mock_flows)
    chain_str = chains[0].get("chains", [""])[0]
    # g2 无引脚名称 -> 应使用简单箭头，g3 有 Completed
    assert "Completed" in chain_str, f"链应包含 'Completed': {chain_str}"
    # g2 到 g3 之间应该有 Completed 引脚
    assert "--Completed-->" in chain_str, f"g2->g3 应使用 Completed 引脚: {chain_str}"


def test_single_node_chain():
    """单节点链不应包含任何箭头。"""
    mock_flows = [
        {
            "start_event": "Event.BeginPlay",
            "nodes": [
                {"node_guid": "g1", "node_type": "K2Node_Event", "used_exec_pin_name": "exec"},
            ],
        }
    ]

    mock_graph = MockGraph([MockNode("g1", "K2Node_Event")])

    chains = build_execution_chains(mock_graph, mock_flows)
    chain_str = chains[0].get("chains", [""])[0]
    assert chain_str == "N0", f"单节点链应为 'N0': {chain_str}"
    assert "->" not in chain_str, f"单节点链不应包含箭头: {chain_str}"


def test_chain_with_branch_split():
    """分支点应将链分割为多个片段。"""
    mock_flows = [
        {
            "start_event": "Event.BeginPlay",
            "nodes": [
                {"node_guid": "g1", "node_type": "K2Node_Event", "used_exec_pin_name": "exec"},
                {"node_guid": "g2", "node_type": "K2Node_IfThenElse", "branch_type": "branch"},
                {"node_guid": "g3", "node_type": "K2Node_CallFunction", "used_exec_pin_name": "Completed"},
            ],
        }
    ]

    mock_graph = MockGraph([
        MockNode("g1", "K2Node_Event"),
        MockNode("g2", "K2Node_IfThenElse"),
        MockNode("g3", "K2Node_CallFunction"),
    ])

    chains = build_execution_chains(mock_graph, mock_flows)
    assert len(chains) > 0
    entry = chains[0]
    # 分支点会将链分割
    chain_list = entry.get("chains", [])
    assert len(chain_list) >= 2, f"分支应产生至少 2 条链: {chain_list}"
    # 元数据应记录分支数
    assert entry.get("chain_metadata", {}).get("branch_count", 0) >= 1
