"""验证 FEdGraphPinType 数据模型与 UE 源码一致。"""
import pytest
from io import BytesIO
from unittest.mock import MagicMock
from uasset_read.models.core import FEdGraphPinType, FEdGraphTerminalType, FSimpleMemberReference


def _make_archive(data: bytes):
    """创建 mock FArchive。

    模拟 FArchive 的读取方法，用于测试序列化器。
    """
    buf = BytesIO(data)
    archive = MagicMock()

    # 基础读取方法
    archive.read = lambda n: buf.read(n)
    archive.read_bytes = lambda n: buf.read(n)
    archive.tell = lambda: buf.tell()
    archive.seek = lambda pos: buf.seek(pos)

    # 整数读取（小端序）
    archive.read_u8 = lambda: int.from_bytes(buf.read(1), 'little')
    archive.read_i8 = lambda: int.from_bytes(buf.read(1), 'little', signed=True)
    archive.read_i32 = lambda: int.from_bytes(buf.read(4), 'little', signed=True)
    archive.read_u32 = lambda: int.from_bytes(buf.read(4), 'little')

    # Bool 读取（UE 标准 4 字节）
    archive.read_bool = lambda: int.from_bytes(buf.read(4), 'little') != 0

    # Bool 读取（UE5 紧凑 1 字节）
    archive.read_bool_1byte = lambda: int.from_bytes(buf.read(1), 'little') != 0

    # FName 读取（索引 + 实例号，共 8 字节）
    def read_name(name_map=None):
        index = int.from_bytes(buf.read(4), 'little')
        number = int.from_bytes(buf.read(4), 'little')  # noqa: F841
        if name_map and 0 <= index < len(name_map):
            return name_map[index]
        return "None"
    archive.read_name = read_name

    # FString 读取
    def read_fstring():
        length = int.from_bytes(buf.read(4), 'little', signed=True)
        if length <= 0:
            return ""
        data = buf.read(length)
        return data.decode('utf-8', errors='replace').rstrip('\x00')
    archive.read_fstring = read_fstring

    # 文件大小（用于边界检查）
    archive._file_size = len(data)

    # validate_size（property_tags 使用）
    archive.validate_size = lambda size, name, tolerant=False: None

    return archive


def _make_summary(**custom_versions):
    """创建 mock PackageFileSummary。

    Args:
        **custom_versions: CustomVersion GUID -> 版本号映射
        ue4_version: 特殊参数，设置 file_version_ue4
    """
    summary = MagicMock()
    summary.file_version_ue4 = custom_versions.pop('ue4_version', 500)

    def get_custom_version(guid, default=0):
        return custom_versions.get(guid, default)

    summary.get_custom_version = get_custom_version
    return summary


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


class TestFEdGraphPinTypeFieldRemoval:
    """验证 FEdGraphPinType 错误字段已移除。"""

    def test_is_map_key_removed(self):
        """is_map_key 字段已移除。"""
        pin_type = FEdGraphPinType()
        assert not hasattr(pin_type, 'is_map_key')

    def test_is_map_value_removed(self):
        """is_map_value 字段已移除。"""
        pin_type = FEdGraphPinType()
        assert not hasattr(pin_type, 'is_map_value')

    def test_map_expressed_via_pin_value_type(self):
        """Map 类型通过 pin_value_type 表达。"""
        pin_type = FEdGraphPinType(
            pin_category="map",
            container_type=3,  # Map
            pin_value_type=FEdGraphTerminalType(pin_category="int"),
        )
        assert pin_type.container_type == 3
        assert pin_type.pin_value_type.pin_category == "int"


class TestBlueprintVariableFTextCategory:
    """验证 BlueprintVariable.Category 使用 FText 读取。"""

    def test_category_is_ftext(self):
        """Category 字段应使用 read_ftext() 读取。"""
        from uasset_read.blueprint._ftext import read_ftext

        # 验证 read_ftext() 可正确读取 Category
        data = (
            b'\x00\x00\x00\x00'  # flags
            b'\x00'              # history_type = 0 (Base)
            b'\x00\x00\x00\x00'  # namespace
            b'\x00\x00\x00\x00'  # key
            b'\x08\x00\x00\x00Default\x00'  # source_string = "Default"
        )
        archive = _make_archive(data)
        summary = _make_summary(ue4_version=500)

        result = read_ftext(archive, summary)
        assert result == "Default"
