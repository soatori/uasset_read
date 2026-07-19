"""图模块合并测试。

合并自 test_graph_core.py、test_graph_flow.py。
保留 4 个关键用例：核心图解析、流构建；新增 script_serial 容错测试。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.graph.flow_builder import (
    _resolve_knot_chain,
    _trace_execution_from_event,
    _get_start_event_name,
    build_execution_flow_entries,
)
from uasset_read.graph.graph_utils import _iter_normalized_edges
from uasset_read.graph.parser import extract_blueprint_graphs
from uasset_read.graph.macro_expander import MacroExpander
from uasset_read.constants import PKG_Cooked


# === Mock 工具 ===

@dataclass
class FakePinType:
    pin_category: str = ""
    pin_subcategory: str = ""
    is_reference: bool = False
    container_type: int = 0


@dataclass
class FakePin:
    pin_id: str = ""
    pin_name: str = ""
    direction: int = 0
    pin_type: Optional[FakePinType] = None
    linked_to_raw: List[dict] = field(default_factory=list)
    default_value: Optional[str] = None
    persistent_guid: Optional[str] = None


@dataclass
class FakeNode:
    node_guid: str = ""
    class_name: str = "K2Node_CallFunction"
    pins: List[FakePin] = field(default_factory=list)
    node_data: Optional[dict] = None
    node_pos_x: int = 0
    node_pos_y: int = 0
    node_comment: str = ""
    _export_object_name: Optional[str] = None


@dataclass
class FakeGraph:
    graph_name: str = "TestGraph"
    graph_class: str = "EdGraph"
    nodes: List[FakeNode] = field(default_factory=list)
    graph_guid: str = ""
    schema: Optional[str] = None


def make_exec_pin(pin_id, name="exec", direction=0):
    return FakePin(pin_id=pin_id, pin_name=name, direction=direction,
                   pin_type=FakePinType(pin_category="exec"))


# === 4 个关键用例 ===

class TestEdgeDirection:
    """边方向正确性（output -> input）。"""

    def test_output_to_input_edge_direction(self):
        """output pin -> input pin 应产出正确的 from/to 方向。"""
        node_a = FakeNode(
            node_guid="guid-a",
            pins=[FakePin(
                pin_id="PIN-A-OUT", pin_name="then", direction=1,
                pin_type=FakePinType(pin_category="exec"),
            )],
        )
        node_b = FakeNode(
            node_guid="guid-b",
            pins=[FakePin(
                pin_id="PIN-B-IN", pin_name="exec", direction=0,
                pin_type=FakePinType(pin_category="exec"),
            )],
        )
        node_a.pins[0].linked_to_raw = [{"pin_id": "PIN-B-IN"}]
        node_b.pins[0].linked_to_raw = [{"pin_id": "PIN-A-OUT"}]

        graph = FakeGraph(nodes=[node_a, node_b])
        edges = list(_iter_normalized_edges(graph))

        assert len(edges) >= 1
        edge = edges[0]
        assert edge["from_node_guid"] == "guid-a"
        assert edge["from_pin"] == "then"
        assert edge["to_node_guid"] == "guid-b"
        assert edge["to_pin"] == "exec"


class TestKnotChainResolution:
    """Knot 链穿透解析。"""

    def test_simple_knot_chain(self):
        """从目标 pin 穿透 Knot 链应到达非 Knot 终端节点。"""
        source_pin_id = "SOURCEPIN"
        knot_input_id = "KNOTIN"
        knot_output_id = "KNOTOUT"
        target_pin_id = "TARGETPIN"

        source_node = FakeNode(node_guid="src", pins=[
            FakePin(pin_id=source_pin_id, pin_name="ReturnValue", direction=1),
        ])
        knot_node = FakeNode(
            node_guid="knot", class_name="K2Node_Knot",
            pins=[
                FakePin(pin_id=knot_input_id, pin_name="InputPin", direction=0,
                        linked_to_raw=[{"pin_id": source_pin_id}]),
                FakePin(pin_id=knot_output_id, pin_name="OutputPin", direction=1),
            ],
        )
        target_node = FakeNode(node_guid="tgt", pins=[
            FakePin(pin_id=target_pin_id, pin_name="Value", direction=0,
                    linked_to_raw=[{"pin_id": knot_output_id}]),
        ])

        pin_lookup = {
            source_pin_id: ("src", "ReturnValue"),
            knot_input_id: ("knot", "InputPin"),
            knot_output_id: ("knot", "OutputPin"),
            target_pin_id: ("tgt", "Value"),
        }
        node_lookup = {
            "src": source_node,
            "knot": knot_node,
            "tgt": target_node,
        }

        terminal_guid, success = _resolve_knot_chain(
            target_pin_id, pin_lookup, node_lookup
        )
        assert success is True
        assert terminal_guid == target_pin_id


class TestCycleDetection:
    """执行流循环检测。"""

    def test_guid_node_cycle_detected(self):
        """有 GUID 节点自环应 cycle_detected 终止。"""
        pin_in = FakePin(
            pin_id="AA", pin_name="exec",
            direction=0, pin_type=FakePinType(pin_category="exec"),
        )
        pin_out = FakePin(
            pin_id="BB", pin_name="then",
            direction=1, pin_type=FakePinType(pin_category="exec"),
            linked_to_raw=["AA"],
        )
        node = FakeNode(
            node_guid="guid-self",
            class_name="K2Node_CallFunction",
            pins=[pin_out, pin_in],
        )
        pin_lookup = {"aa": ("guid-self", "exec")}
        node_lookup = {"guid-self": node}

        flow = _trace_execution_from_event(
            node, pin_lookup, node_lookup, node_name_lookup={"guid-self": "Self"},
            asset_context={},
        )
        assert any(f.get("cycle_detected") for f in flow), \
            f"Expected cycle_detected in flow: {flow}"


class TestCustomEventNaming:
    """CustomEvent 事件名提取。"""

    def test_custom_event_uses_actual_name(self):
        """CustomEvent 应提取实际事件名。"""
        class FakeNodeData:
            def __init__(self, custom_event_name=None):
                self.custom_event_name = custom_event_name

        class FakeCEPin:
            def __init__(self, name, direction, pin_category="exec"):
                self.pin_name = name
                self.direction = direction
                self.pin_type = type("PT", (), {"pin_category": pin_category})()
                self.linked_to_raw = []
                self.pin_id = f"pid_{name}"

        class FakeCENode:
            def __init__(self, guid, class_name, pins=None, node_data=None):
                self.node_guid = guid
                self.class_name = class_name
                self.pins = pins or []
                self.node_data = node_data

        node_data = FakeNodeData(custom_event_name="OnPlayerDeath")
        node = FakeCENode("guid_1", "K2Node_CustomEvent", node_data=node_data)

        name = _get_start_event_name(node)
        assert name == "CustomEvent.OnPlayerDeath", \
            f"期望 'CustomEvent.OnPlayerDeath'，得到 '{name}'"


class TestScriptSerialUnknownCtrlBits:
    """script_serial 未知 SerializationControlExtensions 位容错。"""

    def test_unknown_ctrl_bits_returns_early(self):
        """ctrl byte 含未知高位时应立即返回，不触发偏移错位级联。"""
        from uasset_read.serializers.graph_node import _read_node_script_serial

        # 构造 mock archive：ctrl = 0x05（bit0 + bit2，bit2 为未知位）
        mock_archive = MagicMock()
        mock_archive.read_u8.return_value = 0x05
        mock_archive.tell.return_value = 100

        mock_summary = MagicMock()
        mock_summary.file_version_ue5 = 1011  # 触发 SerializationControlExtensions 分支

        mock_export = MagicMock()
        mock_export.has_script_serialization = True
        mock_export.serial_offset = 0
        mock_export.script_serialization_start_offset = 100
        mock_export.script_serialization_end_offset = 200
        mock_export.script_serialization_size = 100

        result = _read_node_script_serial(
            archive=mock_archive,
            name_map=[],
            summary=mock_summary,
            node_export=mock_export,
            import_map=[],
            export_map=[],
            linker=None,
            node_name="TestNode",
        )

        # read_u8 只调用一次（读 ctrl byte），不应继续读取后续数据
        assert mock_archive.read_u8.call_count == 1
        # 返回默认值元组（11 个元素）
        assert len(result) == 11
        assert result[0] is None   # function_reference
        assert result[1] is None   # event_reference
        assert result[8] == ""     # node_guid

    def test_known_ctrl_bits_normal_parse(self):
        """ctrl byte 仅含已知位（0x00-0x03）时应正常继续解析。"""
        from uasset_read.serializers.graph_node import _read_node_script_serial

        # ctrl = 0x00：无任何标志位，tell() 始终返回 script_end 使 while 循环不进入
        mock_archive = MagicMock()
        mock_archive.read_u8.return_value = 0x00
        mock_archive.tell.return_value = 200  # >= script_end, while 循环不执行

        mock_summary = MagicMock()
        mock_summary.file_version_ue5 = 1011

        mock_export = MagicMock()
        mock_export.has_script_serialization = True
        mock_export.serial_offset = 0
        mock_export.script_serialization_start_offset = 100
        mock_export.script_serialization_end_offset = 200
        mock_export.script_serialization_size = 100

        result = _read_node_script_serial(
            archive=mock_archive,
            name_map=[],
            summary=mock_summary,
            node_export=mock_export,
            import_map=[],
            export_map=[],
            linker=None,
            node_name="TestNode",
        )

        # read_u8 调用一次（ctrl byte），然后 while 循环因 tell() >= script_end 退出
        assert mock_archive.read_u8.call_count == 1
        assert len(result) == 11

    def test_ctrl_with_extra_byte_returns_early(self):
        """ctrl=0x06（bit1 + 未知 bit2）应读取 extra byte 后立即返回。"""
        from uasset_read.serializers.graph_node import _read_node_script_serial

        # 第一次 read_u8 返回 ctrl=0x06，第二次返回 extra byte
        mock_archive = MagicMock()
        mock_archive.read_u8.side_effect = [0x06, 0x00]
        mock_archive.tell.return_value = 100

        mock_summary = MagicMock()
        mock_summary.file_version_ue5 = 1011

        mock_export = MagicMock()
        mock_export.has_script_serialization = True
        mock_export.serial_offset = 0
        mock_export.script_serialization_start_offset = 100
        mock_export.script_serialization_end_offset = 200
        mock_export.script_serialization_size = 100

        result = _read_node_script_serial(
            archive=mock_archive,
            name_map=[],
            summary=mock_summary,
            node_export=mock_export,
            import_map=[],
            export_map=[],
            linker=None,
            node_name="TestNode",
        )

        # read_u8 调用两次：ctrl byte + extra byte（bit1 标志），然后因未知位返回
        assert mock_archive.read_u8.call_count == 2
        assert len(result) == 11
        assert result[0] is None  # function_reference 未解析
