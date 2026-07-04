"""宏展开引擎测试。"""
import pytest
from uasset_read.graph.macro_expander import (
    MacroExpander,
    MacroExpansion,
    MacroExpansionContext,
    MacroCycleError,
    STANDARD_MACROS,
)
from uasset_read.models.core import UEdGraph, UEdGraphNode, UEdGraphPin, FEdGraphPinType


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


# ============================================================================
# _build_graph_dict: 完整 pin 数据和 tunnel 属性
# ============================================================================

def _make_pin(
    pin_id: str,
    pin_name: str,
    direction: int = 0,
    category: str = "float",
    linked_to=None,
    parent_pin=None,
    default_value: str = "",
) -> UEdGraphPin:
    """构造 UEdGraphPin 测试夹具。"""
    return UEdGraphPin(
        pin_id=pin_id,
        pin_name=pin_name,
        direction=direction,
        pin_type=FEdGraphPinType(pin_category=category) if category else None,
        linked_to_raw=linked_to or [],
        parent_pin=parent_pin,
        default_value=default_value or None,
    )


def _make_node(
    guid: str,
    class_name: str = "K2Node_CallFunction",
    pins=None,
    node_data=None,
) -> UEdGraphNode:
    """构造 UEdGraphNode 测试夹具。"""
    return UEdGraphNode(
        node_guid=guid,
        class_name=class_name,
        pins=pins or [],
        node_data=node_data,
    )


def _make_graph(
    name: str = "TestGraph",
    guid: str = "",
    nodes=None,
    subgraphs=None,
    graph_class: str = "EdGraph",
) -> UEdGraph:
    """构造 UEdGraph 测试夹具。"""
    return UEdGraph(
        graph_name=name,
        graph_class=graph_class,
        graph_guid=guid or None,
        nodes=nodes or [],
        subgraphs=subgraphs or [],
    )


class TestBuildGraphDictPinData:
    """验证 _build_graph_dict 生成的 pin 数据完整。"""

    def test_pin_includes_id_and_linked_to_raw(self):
        """pin 字典应包含 pin_id 和 linked_to_raw。"""
        from uasset_read.graph.flow_builder import _build_graph_dict

        pin = _make_pin(
            pin_id="abc123",
            pin_name="Value",
            direction=0,
            linked_to=[{"pin_guid": "def456"}],
        )
        node = _make_node(guid="node1", pins=[pin])
        graph = _make_graph(name="G", guid="g1", nodes=[node])

        result = _build_graph_dict(graph)
        pin_dict = result["nodes"][0]["pins"][0]

        assert pin_dict["pin_id"] == "abc123"
        assert pin_dict["linked_to_raw"] == [{"pin_guid": "def456"}]

    def test_pin_includes_parent_pin(self):
        """pin 字典应包含 parent_pin。"""
        from uasset_read.graph.flow_builder import _build_graph_dict

        parent_ref = {"pin_guid": "parent1"}
        pin = _make_pin(
            pin_id="sub1",
            pin_name="SubPin",
            parent_pin=parent_ref,
        )
        node = _make_node(guid="node1", pins=[pin])
        graph = _make_graph(name="G", nodes=[node])

        result = _build_graph_dict(graph)
        pin_dict = result["nodes"][0]["pins"][0]

        assert pin_dict["parent_pin"] == parent_ref

    def test_pin_direction_as_string(self):
        """pin direction 应转为 EGPD_Input/EGPD_Output 字符串。"""
        from uasset_read.graph.flow_builder import _build_graph_dict

        pin_in = _make_pin(pin_id="p1", pin_name="In", direction=0)
        pin_out = _make_pin(pin_id="p2", pin_name="Out", direction=1)
        node = _make_node(guid="n1", pins=[pin_in, pin_out])
        graph = _make_graph(name="G", nodes=[node])

        result = _build_graph_dict(graph)
        pins = result["nodes"][0]["pins"]

        assert pins[0]["direction"] == "EGPD_Input"
        assert pins[1]["direction"] == "EGPD_Output"

    def test_pin_includes_default_value(self):
        """pin 字典应包含 default_value。"""
        from uasset_read.graph.flow_builder import _build_graph_dict

        pin = _make_pin(pin_id="p1", pin_name="Val", default_value="42")
        node = _make_node(guid="n1", pins=[pin])
        graph = _make_graph(name="G", nodes=[node])

        result = _build_graph_dict(graph)
        assert result["nodes"][0]["pins"][0]["default_value"] == "42"


class TestBuildGraphDictTunnelProps:
    """验证 _build_graph_dict 提取 Tunnel 节点属性。"""

    def test_tunnel_node_has_exact_class_and_caps(self):
        """Tunnel 节点应包含 exact_class、b_can_have_inputs、b_can_have_outputs。"""
        from uasset_read.graph.flow_builder import _build_graph_dict

        tunnel = _make_node(
            guid="tunnel1",
            class_name="K2Node_Tunnel",
            node_data={
                "_raw_properties": {
                    "bCanHaveInputs": True,
                    "bCanHaveOutputs": False,
                }
            },
        )
        graph = _make_graph(name="G", nodes=[tunnel])

        result = _build_graph_dict(graph)
        nd = result["nodes"][0]

        assert nd["exact_class"] == "UK2Node_Tunnel"
        assert nd["b_can_have_inputs"] is True
        assert nd["b_can_have_outputs"] is False

    def test_non_tunnel_node_no_exact_class(self):
        """非 Tunnel 节点不应有 exact_class 字段。"""
        from uasset_read.graph.flow_builder import _build_graph_dict

        node = _make_node(guid="n1", class_name="K2Node_CallFunction")
        graph = _make_graph(name="G", nodes=[node])

        result = _build_graph_dict(graph)
        assert "exact_class" not in result["nodes"][0]

    def test_tunnel_without_raw_properties(self):
        """Tunnel 节点缺少 _raw_properties 时使用默认值。"""
        from uasset_read.graph.flow_builder import _build_graph_dict

        tunnel = _make_node(
            guid="t1",
            class_name="K2Node_Tunnel",
            node_data={},
        )
        graph = _make_graph(name="G", nodes=[tunnel])

        result = _build_graph_dict(graph)
        nd = result["nodes"][0]

        assert nd["exact_class"] == "UK2Node_Tunnel"
        assert nd["b_can_have_inputs"] is False
        assert nd["b_can_have_outputs"] is False


class TestBuildAssetContextSubgraphs:
    """验证 _build_asset_context_from_graph 遍历 subgraphs。"""

    def test_top_level_graph_included(self):
        """顶层图应包含在结果中。"""
        from uasset_read.graph.flow_builder import _build_asset_context_from_graph

        graph = _make_graph(name="Main", guid="g1")
        ctx = _build_asset_context_from_graph(graph)

        names = [g["name"] for g in ctx["graphs"]]
        assert "Main" in names

    def test_subgraph_included(self):
        """subgraph 应包含在结果中。"""
        from uasset_read.graph.flow_builder import _build_asset_context_from_graph

        child = _make_graph(name="MacroGraph", guid="mg1")
        parent = _make_graph(name="Parent", guid="p1", subgraphs=[child])

        ctx = _build_asset_context_from_graph(parent)
        names = [g["name"] for g in ctx["graphs"]]

        assert "Parent" in names
        assert "MacroGraph" in names

    def test_nested_subgraph_included(self):
        """嵌套子图（两层深度）应包含在结果中。"""
        from uasset_read.graph.flow_builder import _build_asset_context_from_graph

        grandchild = _make_graph(name="Deep", guid="d1")
        child = _make_graph(name="Mid", guid="m1", subgraphs=[grandchild])
        parent = _make_graph(name="Top", guid="t1", subgraphs=[child])

        ctx = _build_asset_context_from_graph(parent)
        names = [g["name"] for g in ctx["graphs"]]

        assert "Top" in names
        assert "Mid" in names
        assert "Deep" in names


class TestFindMacroGraphFallback:
    """验证 _find_macro_graph 的 GUID fallback 策略。"""

    def test_guid_exact_match(self):
        """GUID 精确匹配优先。"""
        expander = MacroExpander({"graphs": [
            {"guid": "g1", "name": "MacroA", "nodes": []},
            {"guid": "g2", "name": "MacroB", "nodes": []},
        ]})
        result = expander._find_macro_graph({"graph_guid": "g2", "graph_name": "MacroA"})
        assert result["name"] == "MacroB"

    def test_name_fallback_when_guid_empty(self):
        """GUID 为空时回退到名称匹配。"""
        expander = MacroExpander({"graphs": [
            {"guid": "g1", "name": "TargetMacro", "nodes": []},
        ]})
        result = expander._find_macro_graph({"graph_guid": "", "graph_name": "TargetMacro"})
        assert result is not None
        assert result["name"] == "TargetMacro"

    def test_case_insensitive_name_fallback(self):
        """GUID 和精确名称都失败时，回退到大小写不敏感名称匹配。"""
        expander = MacroExpander({"graphs": [
            {"guid": "g1", "name": "MyMacro", "nodes": []},
        ]})
        result = expander._find_macro_graph({"graph_guid": "wrong", "graph_name": "mymacro"})
        assert result is not None
        assert result["name"] == "MyMacro"

    def test_empty_guid_not_matched_against_empty(self):
        """空 GUID 不应匹配空 GUID 的图。"""
        expander = MacroExpander({"graphs": [
            {"guid": "", "name": "SomeGraph", "nodes": []},
        ]})
        result = expander._find_macro_graph({"graph_guid": "", "graph_name": "Nonexistent"})
        assert result is None

    def test_parent_assets_fallback(self):
        """当前资产未找到时，应在 resolved_parent_assets 中查找。"""
        expander = MacroExpander({
            "graphs": [],
            "resolved_parent_assets": [
                {"graphs": [{"guid": "pg1", "name": "ParentMacro", "nodes": []}]},
            ],
        })
        result = expander._find_macro_graph({"graph_guid": "pg1", "graph_name": "ParentMacro"})
        assert result is not None
        assert result["name"] == "ParentMacro"


class TestMacroExpansionPreservesTunnelPinData:
    """端到端验证宏展开保留 tunnel/pin 数据。"""

    def test_expansion_preserves_pin_id_and_linked_to(self):
        """展开结果应保留 tunnel pin 的 pin_id 和 linked_to_raw。"""
        macro_graph = {
            "guid": "guid-macro",
            "name": "TestMacro",
            "nodes": [
                {
                    "node_type": "K2Node_Tunnel",
                    "node_guid": "tunnel_entry",
                    "exact_class": "UK2Node_Tunnel",
                    "b_can_have_inputs": True,
                    "b_can_have_outputs": False,
                    "pins": [
                        {
                            "pin_id": "pin_exec_in",
                            "pin_name": "exec",
                            "direction": "EGPD_Input",
                            "parent_pin": None,
                            "pin_type": {"pin_category": "exec"},
                            "linked_to_raw": [],
                            "default_value": "",
                        },
                        {
                            "pin_id": "pin_val_in",
                            "pin_name": "Value",
                            "direction": "EGPD_Input",
                            "parent_pin": None,
                            "pin_type": {"pin_category": "float"},
                            "linked_to_raw": [],
                            "default_value": "0.0",
                        },
                    ],
                },
                {
                    "node_type": "K2Node_Tunnel",
                    "node_guid": "tunnel_exit",
                    "exact_class": "UK2Node_Tunnel",
                    "b_can_have_inputs": False,
                    "b_can_have_outputs": True,
                    "pins": [
                        {
                            "pin_id": "pin_exec_out",
                            "pin_name": "Then",
                            "direction": "EGPD_Output",
                            "parent_pin": None,
                            "pin_type": {"pin_category": "exec"},
                            "linked_to_raw": [],
                            "default_value": "",
                        },
                    ],
                },
                {
                    "node_type": "K2Node_CallFunction",
                    "node_guid": "call1",
                    "pins": [
                        {
                            "pin_id": "call_in",
                            "pin_name": "exec",
                            "direction": "EGPD_Input",
                            "parent_pin": None,
                            "pin_type": {"pin_category": "exec"},
                            "linked_to_raw": ["pin_exec_in"],
                            "default_value": "",
                        },
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

        # pin_mapping 应包含入口/出口 tunnel 引脚
        assert "exec" in expansion.pin_mapping
        assert "Value" in expansion.pin_mapping
        assert "Then" in expansion.pin_mapping

        # entry tunnel 引脚方向取反
        assert expansion.pin_mapping["exec"]["instance_direction"] == "EGPD_Output"
        assert expansion.pin_mapping["Value"]["instance_direction"] == "EGPD_Output"
        # exit tunnel 引脚方向取反
        assert expansion.pin_mapping["Then"]["instance_direction"] == "EGPD_Input"

        # default_value 应保留
        assert expansion.pin_mapping["Value"]["default_value"] == "0.0"

    def test_internal_flows_use_linked_to_raw(self):
        """内部执行流应通过 linked_to_raw 追踪节点。"""
        macro_graph = {
            "guid": "guid-macro2",
            "name": "FlowMacro",
            "nodes": [
                {
                    "node_type": "K2Node_Tunnel",
                    "node_guid": "entry",
                    "exact_class": "UK2Node_Tunnel",
                    "b_can_have_inputs": True,
                    "b_can_have_outputs": False,
                    "pins": [
                        {
                            "pin_id": "entry_out",
                            "pin_name": "exec",
                            "direction": "EGPD_Output",
                            "parent_pin": None,
                            "pin_type": {"pin_category": "exec"},
                            "linked_to_raw": ["node1_in"],
                            "default_value": "",
                        },
                    ],
                },
                {
                    "node_type": "K2Node_CallFunction",
                    "node_guid": "node1",
                    "pins": [
                        {
                            "pin_id": "node1_in",
                            "pin_name": "exec",
                            "direction": "EGPD_Input",
                            "parent_pin": None,
                            "pin_type": {"pin_category": "exec"},
                            "linked_to_raw": [],
                            "default_value": "",
                        },
                        {
                            "pin_id": "node1_out",
                            "pin_name": "then",
                            "direction": "EGPD_Output",
                            "parent_pin": None,
                            "pin_type": {"pin_category": "exec"},
                            "linked_to_raw": ["exit_in"],
                            "default_value": "",
                        },
                    ],
                },
                {
                    "node_type": "K2Node_Tunnel",
                    "node_guid": "exit",
                    "exact_class": "UK2Node_Tunnel",
                    "b_can_have_inputs": False,
                    "b_can_have_outputs": True,
                    "pins": [
                        {
                            "pin_id": "exit_in",
                            "pin_name": "exec",
                            "direction": "EGPD_Input",
                            "parent_pin": None,
                            "pin_type": {"pin_category": "exec"},
                            "linked_to_raw": [],
                            "default_value": "",
                        },
                    ],
                },
            ],
        }

        ctx = {"graphs": [macro_graph]}
        expander = MacroExpander(ctx)

        instance = {
            "macro_graph_reference": {
                "graph_name": "FlowMacro",
                "graph_guid": "guid-macro2",
            }
        }

        expansion = expander.expand_macro_instance(instance)

        # 应有一条执行流
        assert len(expansion.internal_flows) == 1
        flow = expansion.internal_flows[0]
        assert flow["entry_tunnel"] == "exec"
        # 执行流应包含 node1
        node_guids = [n.get("node_guid") for n in flow["nodes"]]
        assert "node1" in node_guids
