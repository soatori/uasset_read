"""验证 FEdGraphPinType 数据模型与 UE 源码一致。"""
import pytest
from uasset_read.models.core import FEdGraphPinType, FEdGraphTerminalType


class TestFEdGraphTerminalType:
    """验证 FEdGraphTerminalType（Map value 类型）。"""

    def test_terminal_type_creation(self):
        """FEdGraphTerminalType 可正确创建。"""
        terminal = FEdGraphTerminalType(
            pin_category="int",
            pin_subcategory="",
            pin_subcategory_object=None,
        )
        assert terminal.pin_category == "int"
        assert terminal.pin_subcategory == ""
        assert terminal.pin_subcategory_object is None

    def test_pin_type_with_value_type(self):
        """FEdGraphPinType 可包含 pin_value_type。"""
        pin_type = FEdGraphPinType(
            pin_category="map",
            pin_value_type=FEdGraphTerminalType(pin_category="int"),
        )
        assert pin_type.pin_value_type is not None
        assert pin_type.pin_value_type.pin_category == "int"

    def test_pin_type_default_value_type_is_none(self):
        """FEdGraphPinType.pin_value_type 默认为 None。"""
        pin_type = FEdGraphPinType()
        assert pin_type.pin_value_type is None
