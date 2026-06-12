"""验证 CONTROL_FLOW_NODES 包含所有已知控制流节点类型。"""
from uasset_read.constants import CONTROL_FLOW_NODES, BRANCH_TYPE_MAP


REQUIRED_CONTROL_FLOW = {
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
    "K2Node_MacroInstance",
    # 新增
    "K2Node_ForLoop",
    "K2Node_WhileLoop",
    "K2Node_DoOnce",
    "K2Node_Sequence",
    "K2Node_MultiGate",
    "K2Node_Select",
    "K2Node_ExecutionSequence",
}

REQUIRED_BRANCH_TYPES = {
    "K2Node_IfThenElse",
    "K2Node_Switch",
    "K2Node_SwitchString",
    "K2Node_SwitchEnum",
    "K2Node_SwitchInteger",
    "K2Node_MacroInstance",
    # 新增
    "K2Node_ForLoop",
    "K2Node_WhileLoop",
    "K2Node_DoOnce",
    "K2Node_Sequence",
    "K2Node_MultiGate",
    "K2Node_Select",
}


def test_control_flow_nodes_complete():
    """CONTROL_FLOW_NODES 应包含所有已知控制流节点。"""
    missing = REQUIRED_CONTROL_FLOW - CONTROL_FLOW_NODES
    assert not missing, f"CONTROL_FLOW_NODES 缺少: {missing}"


def test_branch_type_map_complete():
    """BRANCH_TYPE_MAP 应包含所有控制流节点的分支类型。"""
    missing = REQUIRED_BRANCH_TYPES - set(BRANCH_TYPE_MAP.keys())
    assert not missing, f"BRANCH_TYPE_MAP 缺少: {missing}"
