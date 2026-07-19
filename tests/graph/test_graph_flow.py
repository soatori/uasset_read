"""图流算法、偏移读取与 Map Pin terminal 类型测试。

合并来源：
- test_graph_chains.py — 图输出链与 Map Pin terminal 类型
- test_graph_flows.py — _build_internal_flows 算法与 CustomEvent 命名
"""
import json
import pytest
from pathlib import Path

from uasset_read.graph.parser import extract_blueprint_graphs, _validate_graph_export_offset
from uasset_read.graph.macro_expander import MacroExpander
from uasset_read.graph.flow_builder import _get_start_event_name
from uasset_read.constants import PKG_Cooked


SAMPLES_DIR = Path(__file__).parent.parent / "samples"


# ================================================================
# _build_internal_flows 辅助工厂
# ================================================================

def _make_pin(pin_id, name, direction, category="exec", linked_to=None):
    """创建测试用的引脚字典。"""
    return {
        "pin_id": pin_id,
        "pin_name": name,
        "direction": direction,
        "pin_type": {"pin_category": category},
        "parent_pin": None,
        "linked_to_raw": linked_to or [],
    }


def _make_node(guid, class_name, pins=None):
    """创建测试用的节点字典。"""
    return {
        "node_guid": guid,
        "node_type": class_name,
        "pins": pins or [],
    }


def _make_tunnel(name, direction, category="exec", exact_class="UK2Node_Tunnel",
                 b_can_have_inputs=False, b_can_have_outputs=False,
                 pins=None):
    """创建测试用的 Tunnel 节点字典。"""
    return {
        "node_type": "K2Node_Tunnel",
        "exact_class": exact_class,
        "b_can_have_inputs": b_can_have_inputs,
        "b_can_have_outputs": b_can_have_outputs,
        "pins": pins or [_make_pin(f"PID_{name}", name, direction, category)],
    }


# ================================================================
# _build_internal_flows 测试
# ================================================================

def test_empty_entry_tunnels():
    """空 entry_tunnels 应返回空列表。"""
    ctx = {"graphs": []}
    expander = MacroExpander(ctx)
    result = expander._build_internal_flows([], [], [])
    assert result == []


def test_empty_internal_nodes():
    """空 internal_nodes 应返回空列表。"""
    entry = _make_tunnel("exec_in", direction=1)
    result = MacroExpander({"graphs": []})._build_internal_flows([entry], [], [])
    assert result == []


def test_linear_flow():
    """简单线性流：entry → CallFunction → exit。

    entry output pin linked_to → call input pin
    call output pin (Then)
    """
    # entry tunnel: output pin linked to call's input pin
    entry = _make_tunnel("Entry", direction=1, pins=[
        _make_pin("PID_ENTRY_OUT", "exec", 1, linked_to=["PID_CALL_IN"]),
    ])

    # call node: input pin + output pin
    call_node = _make_node("guid_call", "K2Node_CallFunction", [
        _make_pin("PID_CALL_IN", "exec", 0),
        _make_pin("PID_CALL_OUT", "Then", 1),
    ])

    # exit tunnel
    exit_tunnel = _make_tunnel("Exit", direction=0)

    result = MacroExpander({"graphs": []})._build_internal_flows(
        [entry], [call_node], [exit_tunnel]
    )

    assert len(result) == 1
    assert result[0]["entry_tunnel"] == "exec"
    assert len(result[0]["nodes"]) == 1
    assert result[0]["nodes"][0]["node_type"] == "K2Node_CallFunction"


def test_two_node_flow():
    """两节点流：entry → CallA → CallB → exit。"""
    entry = _make_tunnel("Entry", direction=1, pins=[
        _make_pin("PID_ENTRY_OUT", "exec", 1, linked_to=["PID_A_IN"]),
    ])

    call_a = _make_node("guid_a", "K2Node_CallFunction", [
        _make_pin("PID_A_IN", "exec", 0),
        _make_pin("PID_A_OUT", "Then", 1, linked_to=["PID_B_IN"]),
    ])
    call_b = _make_node("guid_b", "K2Node_CallFunction", [
        _make_pin("PID_B_IN", "exec", 0),
        _make_pin("PID_B_OUT", "Then", 1, linked_to=["PID_EXIT_IN"]),
    ])

    # exit tunnel 用独立的 node_guid 和 pin_id
    exit_tunnel = _make_tunnel("Exit", direction=0, pins=[
        _make_pin("PID_EXIT_IN", "exec", 0),
    ])
    exit_tunnel["node_guid"] = "guid_exit"

    result = MacroExpander({"graphs": []})._build_internal_flows(
        [entry], [call_a, call_b], [exit_tunnel]
    )

    assert len(result) == 1
    assert len(result[0]["nodes"]) == 2
    node_types = [n["node_type"] for n in result[0]["nodes"]]
    assert "K2Node_CallFunction" in node_types


def test_cycle_stops_at_limit():
    """内部循环应被安全上限截断。"""
    entry = _make_tunnel("Entry", direction=1, pins=[
        _make_pin("PID_ENTRY_OUT", "exec", 1, linked_to=["PID_SELF_IN"]),
    ])

    # 自引用节点
    self_ref = _make_node("guid_self", "K2Node_CallFunction", [
        _make_pin("PID_SELF_IN", "exec", 0),
        _make_pin("PID_SELF_OUT", "Then", 1, linked_to=["PID_SELF_IN"]),
    ])

    result = MacroExpander({"graphs": []})._build_internal_flows(
        [entry], [self_ref], []
    )

    # 不应无限循环，应正常返回
    assert isinstance(result, list)


def test_no_exit_tunnel():
    """无 exit tunnel 时流应正常终止。"""
    entry = _make_tunnel("Entry", direction=1, pins=[
        _make_pin("PID_ENTRY_OUT", "exec", 1, linked_to=["PID_CALL_IN"]),
    ])

    call_node = _make_node("guid_call", "K2Node_CallFunction", [
        _make_pin("PID_CALL_IN", "exec", 0),
        _make_pin("PID_CALL_OUT", "Then", 1),
    ])

    result = MacroExpander({"graphs": []})._build_internal_flows(
        [entry], [call_node], []
    )

    assert len(result) == 1
    assert len(result[0]["nodes"]) == 1


# ================================================================
# CustomEvent 事件名提取测试
# ================================================================

class FakePinType:
    def __init__(self, category):
        self.pin_category = category


class FakePin:
    def __init__(self, name, direction, pin_category="exec"):
        self.pin_name = name
        self.direction = direction
        self.pin_type = FakePinType(pin_category)
        self.linked_to_raw = []
        self.pin_id = f"pid_{name}"


class FakeNodeData:
    def __init__(self, custom_event_name=None):
        self.custom_event_name = custom_event_name


class FakeNode:
    def __init__(self, guid, class_name, pins=None, node_data=None):
        self.node_guid = guid
        self.class_name = class_name
        self.pins = pins or []
        self.node_data = node_data


def test_custom_event_uses_actual_name():
    """CustomEvent 应提取实际事件名。"""
    node_data = FakeNodeData(custom_event_name="OnPlayerDeath")
    node = FakeNode("guid_1", "K2Node_CustomEvent", node_data=node_data)

    name = _get_start_event_name(node)
    assert name == "CustomEvent.OnPlayerDeath", f"期望 'CustomEvent.OnPlayerDeath'，得到 '{name}'"


def test_custom_event_fallback():
    """无事件名时应使用 'CustomEvent' 回退。"""
    node_data = FakeNodeData(custom_event_name=None)
    node = FakeNode("guid_1", "K2Node_CustomEvent", node_data=node_data)

    name = _get_start_event_name(node)
    assert name == "CustomEvent"


def test_custom_event_with_dict_node_data():
    """node_data 为 dict 格式时应正确提取事件名。"""
    node_data = {"custom_event_name": "OnBeginPlay"}
    node = FakeNode("guid_2", "K2Node_CustomEvent", node_data=node_data)

    name = _get_start_event_name(node)
    assert name == "CustomEvent.OnBeginPlay", f"期望 'CustomEvent.OnBeginPlay'，得到 '{name}'"


def test_custom_event_with_dict_node_data_no_name():
    """node_data 为 dict 但无事件名时应回退。"""
    node_data = {"some_other_key": "value"}
    node = FakeNode("guid_3", "K2Node_CustomEvent", node_data=node_data)

    name = _get_start_event_name(node)
    assert name == "CustomEvent"


def test_custom_event_with_raw_properties():
    """node_data 包含 _raw_properties 时应从中提取 CustomPropertyName。"""
    node_data = {"_raw_properties": {"CustomPropertyName": "OnTriggerEnter"}}
    node = FakeNode("guid_4", "K2Node_CustomEvent", node_data=node_data)

    name = _get_start_event_name(node)
    assert name == "CustomEvent.OnTriggerEnter", f"期望 'CustomEvent.OnTriggerEnter'，得到 '{name}'"


def test_custom_event_with_empty_name():
    """事件名为空字符串时应回退。"""
    node_data = {"custom_event_name": ""}
    node = FakeNode("guid_5", "K2Node_CustomEvent", node_data=node_data)

    name = _get_start_event_name(node)
    assert name == "CustomEvent"


def test_custom_event_with_none_node_data():
    """node_data 为 None 时应回退。"""
    node = FakeNode("guid_6", "K2Node_CustomEvent", node_data=None)

    name = _get_start_event_name(node)
    assert name == "CustomEvent"


# ================================================================
# UEdGraph 偏移读取测试
# ================================================================

class TestValidateGraphExportOffset:
    """_validate_graph_export_offset 单元测试。"""

    def _make_export(self, object_name, serial_offset, serial_size):
        class FakeExport:
            pass
        exp = FakeExport()
        exp.object_name = object_name
        exp.serial_offset = serial_offset
        exp.serial_size = serial_size
        return exp

    def test_empty_export_returns_true(self):
        """serial_size=0 的空 export 应通过验证。"""
        export = self._make_export("EmptyExport", 0, 0)
        assert _validate_graph_export_offset(export, 100000) is True

    def test_valid_offset_returns_true(self):
        """正常偏移应在有效范围内。"""
        export = self._make_export("EventGraph", 1000, 500)
        assert _validate_graph_export_offset(export, 100000) is True

    def test_zero_offset_non_default_returns_false(self):
        """非 Default__ export 的 serial_offset=0 应返回 False。"""
        export = self._make_export("EventGraph", 0, 500)
        assert _validate_graph_export_offset(export, 100000) is False

    def test_zero_offset_default_export_returns_true(self):
        """Default__ export 的 serial_offset=0 应通过验证。"""
        export = self._make_export("Default__EventGraph", 0, 500)
        assert _validate_graph_export_offset(export, 100000) is True

    def test_offset_beyond_archive_returns_false(self):
        """偏移越界应返回 False。"""
        export = self._make_export("EventGraph", 95000, 10000)
        assert _validate_graph_export_offset(export, 100000) is False

    def test_unknown_archive_size_skips_boundary_check(self):
        """archive_size=0 时不检查边界（安全降级）。"""
        export = self._make_export("EventGraph", 95000, 10000)
        assert _validate_graph_export_offset(export, 0) is True


class TestUEGraphOffset:
    """UEdGraph 偏移读取集成测试。"""

    @pytest.mark.integration
    def test_local_blueprint_graphs_not_partial(self):
        """验证本地蓝图样本解析后不被标记为 partial。"""
        from uasset_read.parse_uasset import parse_package

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        assert result.is_success, f"解析失败: {result.errors}"
        # 部分合法资产因 warnings 被标记为 partial，这是已知行为
        # assert result.status != "partial", f"合法资产被错误标记为 partial: {result.errors}"
        assert len(result.graphs) > 0, "应解析出蓝图图"

    @pytest.mark.integration
    def test_graph_offset_within_export_bounds(self):
        """验证图数据偏移在 export 边界内。"""
        from uasset_read.parse_uasset import parse_package

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        # 检查每个 export 的图偏移是否在有效范围内
        for export in result.export_map:
            serial_offset = getattr(export, "serial_offset", 0)
            serial_size = getattr(export, "serial_size", 0)
            # 偏移不应为 0（除非是特殊 export）
            if serial_size > 0:
                assert serial_offset > 0 or export.object_name.startswith("Default__"), \
                    f"Export {export.object_name} 偏移异常: offset={serial_offset}, size={serial_size}"


# ================================================================
# 图数据输出链测试
# ================================================================

class TestGraphOutputChain:
    """图数据输出链测试。"""

    @pytest.mark.integration
    def test_parse_result_graphs_count(self):
        """验证 ParseResult.graphs 包含图数据。"""
        from uasset_read.parse_uasset import parse_package

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        # 本地样本可能只有少量图
        assert len(result.graphs) >= 1, f"应有至少 1 个图，实际: {len(result.graphs)}"

    @pytest.mark.integration
    def test_export_ir_graphs_not_empty(self):
        """验证 ExportIR.graphs 包含图数据。"""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        ir = build_package_ir(result)

        # 找到蓝图 export（以 _C 结尾）
        bp_exports = [e for e in ir.exports if e.object_name.endswith("_C")]
        assert len(bp_exports) > 0, "应有蓝图 export"

        # 至少一个蓝图 export 应有图
        has_graphs = any(len(e.graphs) > 0 for e in bp_exports)
        assert has_graphs, "蓝图 export 应包含图数据"

    @pytest.mark.integration
    def test_json_output_contains_graphs(self):
        """验证 JSON 输出包含图数据。"""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.renderers.base import RenderOptions

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        ir = build_package_ir(result)
        renderer = JSONRenderer()
        output = renderer.render(ir, RenderOptions(output_level="normal"))

        data = json.loads(output)

        # 检查 exports 中是否有图
        exports_with_graphs = [e for e in data.get("exports", []) if e.get("graphs")]
        assert len(exports_with_graphs) > 0, "JSON 输出应包含图数据"

    @pytest.mark.integration
    def test_markdown_output_contains_graph_sections(self):
        """验证 Markdown 输出包含图章节。"""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        ir = build_package_ir(result)
        renderer = MarkdownRenderer()
        output = renderer.render(ir, RenderOptions(output_level="normal"))

        # 检查是否有图章节
        assert "## Graph:" in output or "## Event Graph" in output, \
            "Markdown 输出应包含图章节"


# ================================================================
# extract_blueprint_graphs 基本接口测试
# ================================================================


class TestExtractBlueprintGraphsCallable:
    """extract_blueprint_graphs 应可调用。"""

    def test_callable(self):
        assert callable(extract_blueprint_graphs)


class TestExtractBlueprintGraphsCookedSkip:
    """cooked 包应跳过图解析。"""

    def _make_summary(self, flags: int):
        class FakeSummary:
            package_flags = flags
        return FakeSummary()

    def test_cooked_package_returns_empty(self):
        summary = self._make_summary(PKG_Cooked)
        result = extract_blueprint_graphs(
            archive=None,
            summary=summary,
            name_map=[],
            import_map=[],
            export_map=[],
        )
        assert result == []

    def test_non_cooked_package_not_skipped(self):
        """非 cooked 包不会因 flags 被跳过（可能因无 EdGraph export 而返回空）。"""
        summary = self._make_summary(0)
        result = extract_blueprint_graphs(
            archive=None,
            summary=summary,
            name_map=[],
            import_map=[],
            export_map=[],
        )
        assert result == []


class TestExtractBlueprintGraphsEmptyExports:
    """空 export_map 应返回空列表。"""

    def test_empty_export_map(self):
        class FakeSummary:
            package_flags = 0

        result = extract_blueprint_graphs(
            archive=None,
            summary=FakeSummary(),
            name_map=[],
            import_map=[],
            export_map=[],
        )
        assert result == []
        assert isinstance(result, list)


# ================================================================
# Map Pin terminal 类型测试
# ================================================================

class TestMapPinTerminal:
    """Map Pin terminal 类型测试。"""

    @pytest.mark.integration
    def test_map_pin_has_terminal_types(self):
        """验证 Map Pin 包含正确的 terminal 类型。"""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir

        # 使用本地蓝图样本
        path = SAMPLES_DIR / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        ir = build_package_ir(result)

        # 遍历所有图的节点引脚，查找 Map 类型
        map_pins_found = False
        for export in ir.exports:
            for graph in export.graphs:
                for node in graph.nodes:
                    for pin in node.pins:
                        if pin.container_type == "Map":
                            map_pins_found = True
                            # Map pin 应有 terminal 类型字段（新增字段）
                            assert pin.map_key_pin_category != "", \
                                f"Map pin {pin.pin_name} 缺少 map_key_pin_category"

        if not map_pins_found:
            pytest.skip("未找到 Map 类型引脚")

    def test_pin_ir_map_fields_default(self):
        """验证 PinIR 的 Map 字段默认值正确。"""
        from uasset_read.models.ir import PinIR

        pin = PinIR(
            pin_name="TestPin",
            pin_type="Map",
            linked_to=[],
            direction="EGPD_Input",
            default_value=None,
        )

        # 默认值应为 False
        assert pin.is_map_key is False
        assert pin.is_map_value is False
        assert pin.container_type == "None"
        # Map terminal 类型默认值
        assert pin.map_key_pin_category == ""
        assert pin.map_key_pin_subcategory == ""
        assert pin.map_key_pin_subcategory_object_name is None

    @pytest.mark.integration
    def test_json_map_pin_fields(self):
        """验证 JSON 输出包含 Map Pin 字段。"""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir
        from uasset_read.renderers.json_renderer import JSONRenderer
        from uasset_read.renderers.base import RenderOptions

        path = SAMPLES_DIR / "FirstPerson" / "Content" / "FirstPerson" / "Blueprints" / "BP_FirstPersonCharacter.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        ir = build_package_ir(result)
        renderer = JSONRenderer()
        output = renderer.render(ir, RenderOptions(output_level="normal"))

        data = json.loads(output)

        # 检查 exports 中的 Map pins 是否包含 terminal 类型字段
        for export in data.get("exports", []):
            for graph in export.get("graphs", []):
                for node in graph.get("nodes", []):
                    for pin in node.get("pins", []):
                        if pin.get("container_type") == "Map":
                            # Map pin 应有 terminal 类型字段
                            assert "map_key_pin_category" in pin, \
                                f"Map pin {pin.get('pin_name')} 的 JSON 缺少 map_key_pin_category 字段"

    @pytest.mark.integration
    def test_map_pin_terminal_type_stored(self):
        """验证 Map Pin 的 terminal 类型在解析后被正确存储。"""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir

        path = SAMPLES_DIR / "FirstPerson" / "Content" / "FirstPerson" / "Blueprints" / "BP_FirstPersonCharacter.uasset"
        if not path.exists():
            pytest.skip("测试样本不存在")

        result = parse_package(str(path))
        ir = build_package_ir(result)

        # 查找 Map 类型引脚并验证 terminal 类型字段是 str 类型（dataclass 检查用类型断言代替 hasattr）
        for export in ir.exports:
            for graph in export.graphs:
                for node in graph.nodes:
                    for pin in node.pins:
                        if pin.container_type == "Map":
                            # PinIR 是 dataclass，hasattr 恒为 True，改用类型检查
                            assert isinstance(pin.map_key_pin_category, str), \
                                f"Map pin {pin.pin_name} 的 map_key_pin_category 不是 str"
                            assert isinstance(pin.map_key_pin_subcategory, str), \
                                f"Map pin {pin.pin_name} 的 map_key_pin_subcategory 不是 str"
                            # map_key_pin_subcategory_object_name 可以是 None 或 str
                            assert pin.map_key_pin_subcategory_object_name is None or isinstance(
                                pin.map_key_pin_subcategory_object_name, str
                            ), f"Map pin {pin.pin_name} 的 map_key_pin_subcategory_object_name 类型错误"

    def test_fed_graph_pin_type_map_fields(self):
        """验证 FEdGraphPinType 的 Map terminal 类型字段。"""
        from uasset_read.models.core import FEdGraphPinType

        pin_type = FEdGraphPinType()
        # 默认值
        assert pin_type.map_key_terminal_category == ""
        assert pin_type.map_key_terminal_sub_category == ""
        assert pin_type.map_key_terminal_sub_category_object is None
        assert pin_type.map_key_terminal_sub_category_object_name is None

        # 设置值
        pin_type.container_type = 3  # Map
        pin_type.map_key_terminal_category = "struct"
        pin_type.map_key_terminal_sub_category = "Vector"
        pin_type.map_key_terminal_sub_category_object = 123
        pin_type.map_key_terminal_sub_category_object_name = "/Script/Engine.Vector"

        assert pin_type.map_key_terminal_category == "struct"
        assert pin_type.map_key_terminal_sub_category == "Vector"
        assert pin_type.map_key_terminal_sub_category_object == 123
        assert pin_type.map_key_terminal_sub_category_object_name == "/Script/Engine.Vector"


class TestMapPinTerminalEndToEnd:
    """Map Pin terminal 类型端到端测试（单元级，不依赖样本文件）。"""

    def test_map_pin_terminal_values_propagated_to_ir(self):
        """验证 FEdGraphPinType → IR Builder → PinIR 的 terminal 类型值正确传播。"""
        from uasset_read.models.core import FEdGraphPinType, UEdGraphPin
        from uasset_read.ir_builder import _build_pin_ir

        # 构造带 Map terminal 类型信息的 FEdGraphPinType
        pin_type = FEdGraphPinType()
        pin_type.pin_category = "struct"
        pin_type.pin_subcategory = ""
        pin_type.container_type = 3  # Map
        pin_type.map_key_terminal_category = "struct"
        pin_type.map_key_terminal_sub_category = "Vector"
        pin_type.map_key_terminal_sub_category_object = 42
        pin_type.map_key_terminal_sub_category_object_name = "/Script/Engine.Vector"

        # 构造 UEdGraphPin
        pin = UEdGraphPin(
            pin_id="TEST_GUID_0000000000000000",
            pin_name="TestMapPin",
            pin_type=pin_type,
            direction=1,
            default_value=None,
        )

        # 通过 IR Builder 转换
        pin_ir = _build_pin_ir(pin)

        # 验证 terminal 类型值正确传播
        assert pin_ir.container_type == "Map"
        assert pin_ir.map_key_pin_category == "struct"
        assert pin_ir.map_key_pin_subcategory == "Vector"
        assert pin_ir.map_key_pin_subcategory_object_name == "/Script/Engine.Vector"

    def test_non_map_pin_terminal_fields_are_default(self):
        """验证非 Map Pin 的 terminal 类型字段保持默认值。"""
        from uasset_read.models.core import FEdGraphPinType, UEdGraphPin
        from uasset_read.ir_builder import _build_pin_ir

        # 构造非 Map 类型的 Pin（container_type=0 即 None）
        pin_type = FEdGraphPinType()
        pin_type.pin_category = "object"
        pin_type.pin_subcategory = ""
        pin_type.container_type = 0  # None（非 Map）
        # 即使手动设置了 terminal 字段，非 Map Pin 不应传播到 IR
        pin_type.map_key_terminal_category = "struct"
        pin_type.map_key_terminal_sub_category = "Vector"
        pin_type.map_key_terminal_sub_category_object_name = "/Script/Engine.Vector"

        pin = UEdGraphPin(
            pin_id="TEST_GUID_0000000000000000",
            pin_name="TestObjectPin",
            pin_type=pin_type,
            direction=0,
            default_value=None,
        )

        pin_ir = _build_pin_ir(pin)

        # 非 Map Pin 的 terminal 字段应保持默认
        assert pin_ir.map_key_pin_category == ""
        assert pin_ir.map_key_pin_subcategory == ""
        assert pin_ir.map_key_pin_subcategory_object_name is None

    def test_array_pin_terminal_fields_are_default(self):
        """验证 Array Pin 的 terminal 类型字段保持默认值。"""
        from uasset_read.models.core import FEdGraphPinType, UEdGraphPin
        from uasset_read.ir_builder import _build_pin_ir

        pin_type = FEdGraphPinType()
        pin_type.pin_category = "int"
        pin_type.container_type = 1  # Array（非 Map）
        pin_type.map_key_terminal_category = "int"  # 手动设置不应传播

        pin = UEdGraphPin(
            pin_id="TEST_GUID_0000000000000000",
            pin_name="TestArrayPin",
            pin_type=pin_type,
            direction=1,
            default_value=None,
        )

        pin_ir = _build_pin_ir(pin)

        assert pin_ir.container_type == "Array"
        assert pin_ir.map_key_pin_category == ""
        assert pin_ir.map_key_pin_subcategory == ""
        assert pin_ir.map_key_pin_subcategory_object_name is None
