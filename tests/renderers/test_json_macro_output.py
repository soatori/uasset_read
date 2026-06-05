"""验证 JSON 输出包含宏展开数据。"""
import json
import pytest

from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.models.ir import (
    PackageIR, PackageHeaderIR, ExportIR, GraphIR, NodeIR, PinIR,
)
from uasset_read.renderers.base import RenderOptions


class TestJsonMacroExpansionOutput:
    """测试 JSON 渲染器正确传递 macro_expansion 字段。"""

    def _make_minimal_ir(self, nodes):
        """创建包含指定节点列表的最小 IR。"""
        graph = GraphIR(
            graph_guid="guid0001", graph_name="EventGraph",
            graph_class="EdGraph", nodes=nodes, execution_chains=[],
        )
        export = ExportIR(
            index=0, object_name="Default__TestBP_C",
            object_class="BlueprintGeneratedClass", serial_size=256,
            outer_index_resolved=None, super_index_resolved=None,
            parent_class="Actor", properties=[], graphs=[graph], bulk_data=None,
        )
        header = PackageHeaderIR(
            package_name="/Game/TestBP", package_class="TestBP_C",
            package_flags=0, total_export_count=1, total_import_count=0,
            ue_version="5.3",
        )
        return PackageIR(
            header=header, name_map=["TestBP"], imports=[],
            exports=[export], linker=None,
        )

    def test_node_to_dict_includes_macro_expansion(self):
        """_node_to_dict 应包含 macro_expansion 字段（非 None 时）。"""
        macro_data = {
            "macro_name": "ForLoop",
            "macro_guid": "",
            "is_standard": True,
            "pin_mapping": {"Entry": {"instance_direction": "EGPD_Input"}},
        }
        node = NodeIR(
            node_guid="abcd1234567890abcdef1234567890ab",
            node_class="K2Node_MacroInstance",
            node_comment=None,
            pins=[],
            execution_flow=[],
            macro_expansion=macro_data,
        )

        renderer = JSONRenderer()
        result = renderer._node_to_dict(node)

        assert "macro_expansion" in result
        assert result["macro_expansion"]["macro_name"] == "ForLoop"
        assert result["macro_expansion"]["is_standard"] is True

    def test_node_to_dict_excludes_empty_macro_expansion(self):
        """_node_to_dict 不应包含 macro_expansion 字段（为 None 时）。"""
        node = NodeIR(
            node_guid="abcd1234567890abcdef1234567890ab",
            node_class="K2Node_CallFunction",
            node_comment=None,
            pins=[],
            execution_flow=[],
            macro_expansion=None,
        )

        renderer = JSONRenderer()
        result = renderer._node_to_dict(node)

        assert "macro_expansion" not in result

    def test_full_json_output_includes_macro_expansion(self):
        """完整 JSON 渲染输出中，宏实例节点应包含 macro_expansion。"""
        macro_data = {
            "macro_name": "ForLoop",
            "macro_guid": "",
            "is_standard": True,
            "pin_mapping": {
                "Entry": {"instance_direction": "EGPD_Input"},
                "LastIndex": {"instance_direction": "EGPD_Input"},
                "Completed": {"instance_direction": "EGPD_Output"},
            },
        }
        event_node = NodeIR(
            node_guid="event_guid_1234567890abcdef12345678",
            node_class="K2Node_Event",
            node_comment="BeginPlay",
            pins=[],
            execution_flow=[],
            macro_expansion=None,
        )
        macro_node = NodeIR(
            node_guid="macro_guid_1234567890abcdef12345678",
            node_class="K2Node_MacroInstance",
            node_comment=None,
            pins=[],
            execution_flow=[],
            macro_expansion=macro_data,
        )
        call_node = NodeIR(
            node_guid="call_guid_1234567890abcdef12345678",
            node_class="K2Node_CallFunction",
            node_comment=None,
            pins=[],
            execution_flow=[],
            macro_expansion=None,
        )

        ir = self._make_minimal_ir([event_node, macro_node, call_node])
        renderer = JSONRenderer()
        output = renderer.render(ir, RenderOptions())
        data = json.loads(output)

        # 验证宏实例节点包含 macro_expansion
        graph_nodes = data["exports"][0]["graphs"][0]["nodes"]
        macro_result = next(
            n for n in graph_nodes if n["node_class"] == "K2Node_MacroInstance"
        )
        assert "macro_expansion" in macro_result
        assert macro_result["macro_expansion"]["macro_name"] == "ForLoop"
        assert macro_result["macro_expansion"]["is_standard"] is True
        assert "Entry" in macro_result["macro_expansion"]["pin_mapping"]

        # 验证非宏节点不包含 macro_expansion
        event_result = next(
            n for n in graph_nodes if n["node_class"] == "K2Node_Event"
        )
        assert "macro_expansion" not in event_result

    def test_macro_expansion_with_full_fields(self):
        """macro_expansion 包含完整字段时应全部传递。"""
        macro_data = {
            "macro_name": "Branch",
            "macro_guid": "00000000000000000000000000000000",
            "is_standard": True,
            "pin_mapping": {
                "ExecuteEntry": {"instance_direction": "EGPD_Input"},
                "Condition": {"instance_direction": "EGPD_Input"},
                "True": {"instance_direction": "EGPD_Output"},
                "False": {"instance_direction": "EGPD_Output"},
            },
            "expanded_nodes_count": 0,
        }
        node = NodeIR(
            node_guid="abcd1234567890abcdef1234567890ab",
            node_class="K2Node_MacroInstance",
            node_comment=None,
            pins=[],
            execution_flow=[],
            macro_expansion=macro_data,
        )

        renderer = JSONRenderer()
        result = renderer._node_to_dict(node)

        assert result["macro_expansion"]["macro_name"] == "Branch"
        assert result["macro_expansion"]["macro_guid"] == "00000000000000000000000000000000"
        assert len(result["macro_expansion"]["pin_mapping"]) == 4
