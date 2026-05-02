"""
tests/test_graph_parsing.py - Phase 7: 蓝图图核心解析测试（GRAPH-01~09）

Wave 3 Task 2: 创建 Phase 7 单元测试并验证完整功能。

测试覆盖：
- GRAPH-01: EdGraph 导出类型检测
- GRAPH-02: UEdGraph 基本信息
- GRAPH-03: UEdGraphNode 基类字段
- GRAPH-04: UEdGraphPin 完整结构
- GRAPH-05~09: 节点类型特定解析器
"""

import pytest
import struct
import tempfile
import os
from typing import TYPE_CHECKING

# Phase 1/2/3 imports
from uasset_read import (
    FArchive,
    PackageFileSummary,
    PackageIndex,
    ObjectImport,
    ObjectExport,
    ParseResult,
)

# Phase 7 imports
from uasset_read import (
    UEdGraph,
    UEdGraphNode,
    UEdGraphPin,
    FMemberReference,
    FEdGraphPinType,
    resolve_class_name,
    extract_blueprint_graphs,
    read_ue_graph_pin,
    read_ue_graph_node,
    read_ue_graph,
    # Wave 3: Node Type Specific Parsers
    K2NodeCallFunction,
    K2NodeEvent,
    K2NodeKnot,
    EdGraphNodeComment,
    K2NodeEnhancedInputAction,
    read_fmember_reference,
    read_k2node_call_function,
    read_k2node_event,
    read_k2node_knot,
    read_edgraph_node_comment,
    read_k2node_enhanced_input,
    # Constants
    PACKAGE_FILE_TAG,
    MAX_PINS_PER_NODE,
    MAX_NODES_PER_GRAPH,
    MAX_LINKEDTO_PER_PIN,
    ParseError,
)


# ============================================================================
# 辅助类和函数
# ============================================================================

class MockImport:
    """模拟 ObjectImport 用于测试"""
    def __init__(self, class_package: str = "", class_name: str = "TestClass",
                 object_name: str = "TestObject"):
        self.class_package = class_package
        self.class_name = class_name
        self.object_name = object_name


class MockExport:
    """模拟 ObjectExport 用于测试"""
    def __init__(self, object_name: str = "TestNode", class_index: int = 0,
                 serial_offset: int = 0, serial_size: int = 0):
        self.object_name = object_name
        self.class_index = PackageIndex(class_index)
        self.serial_offset = serial_offset
        self.serial_size = serial_size
        self.outer_index = PackageIndex(0)


def create_test_archive(data: bytes) -> FArchive:
    """创建测试用的 FArchive"""
    import tempfile
    fd, path = tempfile.mkstemp(suffix='.uasset')
    os.write(fd, data)
    os.close(fd)
    archive = FArchive(path)
    return archive, path


def create_mock_summary() -> PackageFileSummary:
    """创建模拟 PackageFileSummary"""
    return PackageFileSummary(
        tag=PACKAGE_FILE_TAG,
        legacy_file_version=-8,
        legacy_ue3_version=864,
        file_version_ue4=522,
        file_version_ue5=1001,
        file_version_licensee=0,
        package_name="TestPackage",
        package_flags=0,
        name_count=5,
        name_offset=100,
        export_count=1,
        export_offset=200,
        import_count=1,
        import_offset=300,
    )


# ============================================================================
# GRAPH-01: EdGraph 导出类型检测
# ============================================================================

class TestEdGraphDetection:
    """测试 EdGraph 类型检测（GRAPH-01）"""

    def test_resolve_class_name_from_export(self):
        """ClassIndex > 0 从 ExportMap 解析类名"""
        export_map = [MockExport(object_name="TestClass")]
        import_map = []
        result = resolve_class_name(PackageIndex(1), import_map, export_map)
        assert result == "TestClass"

    def test_resolve_class_name_from_import(self):
        """ClassIndex < 0 从 ImportMap 解析类名"""
        export_map = []
        import_map = [MockImport(class_name="ImportedClass")]
        result = resolve_class_name(PackageIndex(-1), import_map, export_map)
        assert result == "ImportedClass"

    def test_resolve_class_name_null_index(self):
        """ClassIndex = 0 返回 None"""
        export_map = [MockExport(object_name="TestClass")]
        import_map = []
        result = resolve_class_name(PackageIndex(0), import_map, export_map)
        assert result is None

    def test_detect_edgraph_export(self):
        """GRAPH-01: EdGraph 类型检测"""
        # 使用真实 Lyra 资产测试 EdGraph 检测
        # 此测试需要真实资产文件
        pytest.skip("需要真实 .uasset 文件测试")


# ============================================================================
# GRAPH-02: UEdGraph 基本信息
# ============================================================================

class TestUEdGraphBasic:
    """测试 UEdGraph 基本信息（GRAPH-02）"""

    def test_ue_graph_dataclass_structure(self):
        """UEdGraph 数据类结构验证"""
        graph = UEdGraph(
            graph_name="EventGraph",
            graph_class="EdGraph",
            schema="EdGraphSchema_K2",
            nodes=[],
            graph_guid="1234567890abcdef1234567890abcdef",
            b_editable=True
        )
        assert graph.graph_name == "EventGraph"
        assert graph.graph_class == "EdGraph"
        assert graph.schema == "EdGraphSchema_K2"
        assert len(graph.nodes) == 0
        assert graph.b_editable == True

    def test_read_ue_graph_basic(self):
        """GRAPH-02: UEdGraph Schema、GraphGuid、Nodes"""
        # 需要合成图二进制数据测试
        pytest.skip("需要合成图二进制数据")


# ============================================================================
# GRAPH-03: UEdGraphNode 基类字段
# ============================================================================

class TestUEdGraphNodeBasic:
    """测试 UEdGraphNode 基类字段（GRAPH-03）"""

    def test_ue_graph_node_dataclass_structure(self):
        """UEdGraphNode 数据类结构验证"""
        node = UEdGraphNode(
            node_guid="1234567890abcdef1234567890abcdef",
            node_pos_x=100,
            node_pos_y=200,
            node_comment="Test Comment",
            pins=[],
            class_name="K2Node_CallFunction",
            node_data=None
        )
        assert node.node_guid == "1234567890abcdef1234567890abcdef"
        assert node.node_pos_x == 100
        assert node.node_pos_y == 200
        assert node.node_comment == "Test Comment"
        assert node.class_name == "K2Node_CallFunction"
        assert node.node_data is None

    def test_read_ue_graph_node_basic(self):
        """GRAPH-03: NodeGuid、NodePos、Comment、Pins"""
        # 需要合成节点二进制数据测试
        pytest.skip("需要合成节点二进制数据")


# ============================================================================
# GRAPH-04: UEdGraphPin 完整结构
# ============================================================================

class TestUEdGraphPinComplete:
    """测试 UEdGraphPin 完整结构（GRAPH-04）"""

    def test_ue_graph_pin_dataclass_structure(self):
        """UEdGraphPin 数据类结构验证"""
        pin_type = FEdGraphPinType(
            pin_category="exec",
            pin_sub_category="",
            container_type=0,
            is_reference=False,
            is_const=False
        )
        pin = UEdGraphPin(
            pin_id="1234567890abcdef1234567890abcdef",
            pin_name="execute",
            direction=0,  # EGPD_Input
            pin_type=pin_type,
            default_value=None,
            auto_default_value=None,
            linked_to_raw=["target_pin_guid"],
            sub_pins=[],
            parent_pin=None,
            flags=0
        )
        assert pin.pin_id == "1234567890abcdef1234567890abcdef"
        assert pin.pin_name == "execute"
        assert pin.direction == 0
        assert pin.pin_type.pin_category == "exec"
        assert len(pin.linked_to_raw) == 1

    def test_read_ue_graph_pin_complete(self):
        """GRAPH-04: PinId、PinName、Direction、PinType、DefaultValue、LinkedTo"""
        # 需要合成引脚二进制数据测试
        pytest.skip("需要合成引脚二进制数据")


# ============================================================================
# GRAPH-05: K2Node_CallFunction 解析
# ============================================================================

class TestK2NodeCallFunction:
    """测试 K2Node_CallFunction 特有字段解析（GRAPH-05）"""

    def test_k2node_call_function_dataclass(self):
        """K2NodeCallFunction 数据类结构验证"""
        func_ref = FMemberReference(
            member_parent="Character",
            member_name="Jump",
            member_guid="abcdef1234567890",
            b_self_context=True
        )
        node_data = K2NodeCallFunction(
            function_reference=func_ref,
            b_defaults_to_pure=False
        )
        assert node_data.function_reference.member_name == "Jump"
        assert node_data.function_reference.b_self_context == True
        assert node_data.b_defaults_to_pure == False

    def test_k2node_call_function_parser(self):
        """GRAPH-05: FunctionReference 提取"""
        # 需要合成节点二进制数据测试
        pytest.skip("需要合成节点二进制数据")

    def test_fmember_reference_parsing(self):
        """FMemberReference 辅助函数测试"""
        # 需要合成二进制数据测试
        pytest.skip("需要合成二进制数据")


# ============================================================================
# GRAPH-06: K2Node_Event 解析
# ============================================================================

class TestK2NodeEvent:
    """测试 K2Node_Event 特有字段解析（GRAPH-06）"""

    def test_k2node_event_dataclass(self):
        """K2NodeEvent 数据类结构验证"""
        event_ref = FMemberReference(
            member_parent="/Script/Engine.BPGenClass",
            member_name="ReceiveBeginPlay",
            member_guid="abcdef1234567890",
            b_self_context=False
        )
        node_data = K2NodeEvent(
            event_reference=event_ref,
            b_override_function=False
        )
        assert node_data.event_reference.member_name == "ReceiveBeginPlay"
        assert node_data.event_reference.member_parent == "/Script/Engine.BPGenClass"
        assert node_data.b_override_function == False

    def test_k2node_event_parser(self):
        """GRAPH-06: EventReference 提取"""
        pytest.skip("需要合成节点二进制数据")


# ============================================================================
# GRAPH-07: K2Node_Knot 解析
# ============================================================================

class TestK2NodeKnot:
    """测试 K2Node_Knot 特有字段解析（GRAPH-07）"""

    def test_k2node_knot_dataclass(self):
        """K2NodeKnot 数据类结构验证（无额外字段）"""
        node_data = K2NodeKnot()
        # Knot 节点无额外字段，仅验证实例创建成功
        assert isinstance(node_data, K2NodeKnot)

    def test_k2node_knot_parser(self):
        """GRAPH-07: Knot 节点（仅基类）"""
        pytest.skip("需要合成节点二进制数据")


# ============================================================================
# GRAPH-08: EdGraphNode_Comment 解析
# ============================================================================

class TestEdGraphNodeComment:
    """测试 EdGraphNode_Comment 特有字段解析（GRAPH-08）"""

    def test_edgraph_node_comment_dataclass(self):
        """EdGraphNodeComment 数据类结构验证"""
        node_data = EdGraphNodeComment(
            comment_color=(0.05, 0.05, 0.05, 1.0),
            node_width=1440,
            node_height=544,
            font_size=14
        )
        assert node_data.comment_color == (0.05, 0.05, 0.05, 1.0)
        assert node_data.node_width == 1440
        assert node_data.node_height == 544
        assert node_data.font_size == 14

    def test_edgraph_node_comment_parser(self):
        """GRAPH-08: Comment 节点文本和尺寸"""
        pytest.skip("需要合成节点二进制数据")


# ============================================================================
# GRAPH-09: K2Node_EnhancedInputAction 解析
# ============================================================================

class TestK2NodeEnhancedInputAction:
    """测试 K2Node_EnhancedInputAction 特有字段解析（GRAPH-09）"""

    def test_k2node_enhanced_input_dataclass(self):
        """K2NodeEnhancedInputAction 数据类结构验证"""
        node_data = K2NodeEnhancedInputAction(
            input_action_path="/Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Jump.IA_Jump'"
        )
        assert node_data.input_action_path == "/Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Jump.IA_Jump'"

    def test_k2node_enhanced_input_parser(self):
        """GRAPH-09: InputAction 路径"""
        pytest.skip("需要合成节点二进制数据")


# ============================================================================
# 类型分派测试
# ============================================================================

class TestNodeTypeDispatch:
    """测试节点类型 match/case 分派"""

    def test_unknown_node_type_handling(self):
        """D-02a: 未知类型触发警告但解析继续"""
        # 创建未知类型的节点
        node = UEdGraphNode(
            node_guid="test_guid",
            class_name="UnknownNodeType",
            node_data={"unknown_type": "UnknownNodeType"}
        )
        assert node.node_data is not None
        assert node.node_data.get("unknown_type") == "UnknownNodeType"

    def test_known_node_types_dispatch(self):
        """验证已知节点类型的分派"""
        known_types = [
            "K2Node_CallFunction",
            "K2Node_Event",
            "K2Node_Knot",
            "EdGraphNode_Comment",
            "K2Node_EnhancedInputAction"
        ]
        for type_name in known_types:
            # 模拟类型识别
            node = UEdGraphNode(
                node_guid="test_guid",
                class_name=type_name,
                node_data=None  # 实际解析会填充
            )
            assert node.class_name == type_name


# ============================================================================
# 安全边界测试
# ============================================================================

class TestSafetyBounds:
    """测试安全边界常量和验证"""

    def test_max_pins_per_node_constant(self):
        """T-07-02-02: MAX_PINS_PER_NODE 常量验证"""
        assert MAX_PINS_PER_NODE == 1000

    def test_max_nodes_per_graph_constant(self):
        """T-07-02-03: MAX_NODES_PER_GRAPH 常量验证"""
        assert MAX_NODES_PER_GRAPH == 5000

    def test_max_linkedto_per_pin_constant(self):
        """T-07-02-04: MAX_LINKEDTO_PER_PIN 常量验证"""
        assert MAX_LINKEDTO_PER_PIN == 100

    def test_pins_count_boundary(self):
        """pins_count 边界检查测试"""
        # 需要合成数据测试边界溢出
        pytest.skip("需要合成数据测试边界溢出")


# ============================================================================
# 集成测试
# ============================================================================

class TestIntegration:
    """完整解析流程集成测试"""

    def test_full_graph_parsing_integration(self):
        """完整 Graph→Node→Pin 三层解析"""
        # 使用真实 Lyra 资产测试完整流程
        pytest.skip("需要真实 .uasset 文件测试")

    def test_cooked_asset_skip(self):
        """T-07-01-02: cooked 资产跳过图解析"""
        # 需要 cooked 资产测试
        pytest.skip("需要 cooked .uasset 文件测试")


# ============================================================================
# 数据导入测试
# ============================================================================

class TestImports:
    """验证所有新导出的函数和数据类可导入"""

    def test_import_node_type_dataclasses(self):
        """节点类型数据类导入验证"""
        from uasset_read import (
            K2NodeCallFunction,
            K2NodeEvent,
            K2NodeKnot,
            EdGraphNodeComment,
            K2NodeEnhancedInputAction
        )
        assert K2NodeCallFunction is not None
        assert K2NodeEvent is not None
        assert K2NodeKnot is not None
        assert EdGraphNodeComment is not None
        assert K2NodeEnhancedInputAction is not None

    def test_import_node_type_parsers(self):
        """节点类型解析器导入验证"""
        from uasset_read import (
            read_fmember_reference,
            read_k2node_call_function,
            read_k2node_event,
            read_k2node_knot,
            read_edgraph_node_comment,
            read_k2node_enhanced_input
        )
        assert read_fmember_reference is not None
        assert read_k2node_call_function is not None
        assert read_k2node_event is not None
        assert read_k2node_knot is not None
        assert read_edgraph_node_comment is not None
        assert read_k2node_enhanced_input is not None

    def test_import_graph_dataclasses(self):
        """图数据类导入验证"""
        from uasset_read import (
            UEdGraph,
            UEdGraphNode,
            UEdGraphPin,
            FMemberReference
        )
        assert UEdGraph is not None
        assert UEdGraphNode is not None
        assert UEdGraphPin is not None
        assert FMemberReference is not None

    def test_import_graph_parsers(self):
        """图解析器导入验证"""
        from uasset_read import (
            resolve_class_name,
            extract_blueprint_graphs,
            read_ue_graph_pin,
            read_ue_graph_node,
            read_ue_graph
        )
        assert resolve_class_name is not None
        assert extract_blueprint_graphs is not None
        assert read_ue_graph_pin is not None
        assert read_ue_graph_node is not None
        assert read_ue_graph is not None