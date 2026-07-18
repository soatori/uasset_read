"""图输出链与 Map Pin terminal 类型测试。

合并来源：
- test_graph_output_chain.py — ParseResult.graphs → ExportIR.graphs 输出链及 graph/parser 基本接口
- test_map_pin_terminal.py — Map Pin terminal 类型反序列化
"""
import json
import pytest
from pathlib import Path

from uasset_read.graph.parser import extract_blueprint_graphs
from uasset_read.constants import PKG_Cooked

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


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
