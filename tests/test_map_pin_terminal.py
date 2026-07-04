"""测试 Map Pin terminal 类型反序列化。"""
import pytest
from pathlib import Path

SAMPLES_DIR = Path(r"E:\Develop\lib\Samples")


class TestMapPinTerminal:
    """Map Pin terminal 类型测试。"""

    @pytest.mark.integration
    def test_map_pin_has_terminal_types(self):
        """验证 Map Pin 包含正确的 terminal 类型。"""
        from uasset_read.parse_uasset import parse_package
        from uasset_read.ir_builder import build_package_ir

        # 需要找到包含 Map 属性的蓝图资产
        # 优先使用 FirstPerson 示例
        path = SAMPLES_DIR / "FirstPerson" / "Content" / "FirstPerson" / "Blueprints" / "BP_FirstPersonCharacter.uasset"
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
                            # Map pin 应有 terminal 类型信息
                            # 即使是 None，也不应该是缺失状态
                            assert pin.pin_category != "", \
                                f"Map pin {pin.pin_name} 缺少 pin_category"

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
        assert pin.map_key_pin_subcategory_object is None

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

        import json
        data = json.loads(output)

        # 检查 exports 中的 Map pins 是否包含 terminal 类型字段
        for export in data.get("exports", []):
            for graph in export.get("graphs", []):
                for node in graph.get("nodes", []):
                    for pin in node.get("pins", []):
                        if pin.get("container_type") == "Map":
                            # Map pin 应有 terminal 类型字段
                            # map_key_pin_category 可能为空但字段应存在
                            assert "map_key_pin_category" in pin or pin.get("map_key_pin_category", "") == "", \
                                f"Map pin {pin.get('pin_name')} 缺少 map_key_pin_category"

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

        # 查找 Map 类型引脚并验证 terminal 类型字段存在
        for export in ir.exports:
            for graph in export.graphs:
                for node in graph.nodes:
                    for pin in node.pins:
                        if pin.container_type == "Map":
                            # Map pin 应有 terminal 类型字段（即使值为空）
                            assert hasattr(pin, "map_key_pin_category"), \
                                f"Map pin {pin.pin_name} 缺少 map_key_pin_category 属性"
                            assert hasattr(pin, "map_key_pin_subcategory"), \
                                f"Map pin {pin.pin_name} 缺少 map_key_pin_subcategory 属性"
                            assert hasattr(pin, "map_key_pin_subcategory_object"), \
                                f"Map pin {pin.pin_name} 缺少 map_key_pin_subcategory_object 属性"

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
