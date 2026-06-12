"""宏展开引擎测试。"""
import pytest
from uasset_read.graph.macro_expander import (
    MacroExpander,
    MacroExpansion,
    MacroExpansionContext,
    MacroCycleError,
    STANDARD_MACROS,
)


def test_standard_macros_recognized():
    """标准宏应被识别且不尝试展开内部节点。"""
    ctx = {"graphs": []}
    expander = MacroExpander(ctx)

    instance = {
        "macro_graph_reference": {
            "graph_name": "ForLoop",
            "graph_guid": "",
        }
    }

    expansion = expander.expand_macro_instance(instance)
    assert expansion.context.macro_name == "ForLoop"
    assert expansion.context.macro_name in STANDARD_MACROS


def test_unresolved_macro():
    """宏图未找到时应标记 unresolved。"""
    ctx = {"graphs": []}
    expander = MacroExpander(ctx)

    instance = {
        "macro_graph_reference": {
            "graph_name": "MissingMacro",
            "graph_guid": "nonexistent-guid",
        }
    }

    expansion = expander.expand_macro_instance(instance)
    assert expansion.unresolved is True


def test_macro_cycle_detection():
    """嵌套宏循环应抛出 MacroCycleError。"""
    # 构造 A -> B -> A 的循环
    graph_a = {
        "guid": "guid-a",
        "name": "MacroA",
        "nodes": [
            {
                "node_type": "K2Node_MacroInstance",
                "macro_graph_reference": {
                    "graph_name": "MacroB",
                    "graph_guid": "guid-b",
                },
            }
        ],
    }
    graph_b = {
        "guid": "guid-b",
        "name": "MacroB",
        "nodes": [
            {
                "node_type": "K2Node_MacroInstance",
                "macro_graph_reference": {
                    "graph_name": "MacroA",
                    "graph_guid": "guid-a",
                },
            }
        ],
    }

    ctx = {"graphs": [graph_a, graph_b]}
    expander = MacroExpander(ctx)

    instance = {
        "macro_graph_reference": {
            "graph_name": "MacroA",
            "graph_guid": "guid-a",
        }
    }

    with pytest.raises(MacroCycleError) as exc_info:
        expander.expand_macro_instance(instance)

    assert "MacroA" in str(exc_info.value)
    assert "MacroB" in str(exc_info.value)


def test_pin_mapping_from_tunnels():
    """Tunnel 引脚应正确映射到 Instance 引脚。"""
    macro_graph = {
        "guid": "guid-macro",
        "name": "TestMacro",
        "nodes": [
            # 入口 Tunnel (bCanHaveInputs=True) — 定义宏的输入引脚
            {
                "node_type": "K2Node_Tunnel",
                "exact_class": "UK2Node_Tunnel",
                "b_can_have_inputs": True,
                "b_can_have_outputs": False,
                "pins": [
                    {"pin_name": "exec", "direction": "EGPD_Input", "parent_pin": None, "pin_type": {}, "default_value": ""},
                    {"pin_name": "Target", "direction": "EGPD_Input", "parent_pin": None, "pin_type": {"pin_category": "Object"}, "default_value": ""},
                ],
            },
            # 出口 Tunnel (bCanHaveOutputs=True) — 定义宏的输出引脚
            {
                "node_type": "K2Node_Tunnel",
                "exact_class": "UK2Node_Tunnel",
                "b_can_have_inputs": False,
                "b_can_have_outputs": True,
                "pins": [
                    {"pin_name": "Then", "direction": "EGPD_Output", "parent_pin": None, "pin_type": {}, "default_value": ""},
                ],
            },
        ],
    }

    ctx = {"graphs": [macro_graph]}
    expander = MacroExpander(ctx)

    instance = {
        "macro_graph_reference": {
            "graph_name": "TestMacro",
            "graph_guid": "guid-macro",
        }
    }

    expansion = expander.expand_macro_instance(instance)

    # 入口 Tunnel 的 EGPD_Input 引脚 → Instance 的 EGPD_Output
    assert "exec" in expansion.pin_mapping
    assert expansion.pin_mapping["exec"]["instance_direction"] == "EGPD_Output"
    assert expansion.pin_mapping["exec"]["tunnel_type"] == "entry"

    # 出口 Tunnel 的 EGPD_Output 引脚 → Instance 的 EGPD_Input
    assert "Then" in expansion.pin_mapping
    assert expansion.pin_mapping["Then"]["instance_direction"] == "EGPD_Input"
    assert expansion.pin_mapping["Then"]["tunnel_type"] == "exit"


def test_all_standard_macros_documented():
    """所有已知标准宏应在 STANDARD_MACROS 中定义。"""
    expected_macros = {
        "ForLoop", "ForLoopWithBreak", "WhileLoop",
        "Gate", "Do N", "DoOnce", "IsValid",
        "FlipFlop", "ForEachLoop", "ForEachLoopWithBreak",
        "Branch", "Delay", "RetriggerableDelay",
        "Select", "SwitchOnInt",
    }
    assert set(STANDARD_MACROS.keys()) == expected_macros
