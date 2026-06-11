"""验证 FEdGraphPinType 数据模型与 UE 源码一致。"""
import pytest
from uasset_read.models.core import FEdGraphPinType, FEdGraphTerminalType, FSimpleMemberReference


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


class TestFSimpleMemberReference:
    """验证 FSimpleMemberReference（成员引用）。"""

    def test_member_reference_creation(self):
        """FSimpleMemberReference 可正确创建。"""
        ref = FSimpleMemberReference(
            member_parent_class=5,
            member_name="MyMember",
            member_guid="00000000-0000-0000-0000-000000000000",
        )
        assert ref.member_name == "MyMember"
        assert ref.member_parent_class == 5

    def test_pin_type_with_member_reference(self):
        """FEdGraphPinType 可包含 pin_subcategory_member_reference。"""
        pin_type = FEdGraphPinType(
            pin_category="float",
            pin_subcategory_member_reference=FSimpleMemberReference(
                member_name="StructMember",
            ),
        )
        assert pin_type.pin_subcategory_member_reference is not None
        assert pin_type.pin_subcategory_member_reference.member_name == "StructMember"

    def test_pin_type_default_member_reference_is_none(self):
        """FEdGraphPinType.pin_subcategory_member_reference 默认为 None。"""
        pin_type = FEdGraphPinType()
        assert pin_type.pin_subcategory_member_reference is None
