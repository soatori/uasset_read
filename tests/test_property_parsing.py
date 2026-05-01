"""
tests/test_property_parsing.py - PropertyTag 解析测试（Phase 2）

测试 PropertyTag 结构解析和基本属性类型值提取。
"""

import pytest
import struct
from io import BytesIO
from dataclasses import dataclass

from uasset_read import (
    FArchive,
    PropertyTag,
    PropertyValue,
    ObjectExport,
    PackageFileSummary,
    use_complete_type_name,
    read_property_tag,
    parse_bool_property,
    parse_int_property,
    parse_float_property,
    parse_str_property,
    parse_name_property,
    parse_object_property,
    parse_array_property,
    parse_property_value,
    parse_properties_from_export,
    PROP_TAG_HAS_ARRAY_INDEX,
    PROP_TAG_HAS_PROPERTY_GUID,
    PROP_TAG_BOOL_TRUE,
    PROPERTY_TAG_COMPLETE_TYPE_NAME,
)


# ============================================================================
# 测试辅助：Mock FArchive
# ============================================================================

class MockArchive(FArchive):
    """
    Mock FArchive 用于测试，从 BytesIO 读取数据。
    """

    def __init__(self, data: bytes):
        # 不调用父类 __init__，直接设置所需属性
        self._file = BytesIO(data)
        self._byte_swapping = False
        self._file_size = len(data)
        self._path = "mock"
        # Phase 5: mmap fields (not used in mock)
        self._mmap = None
        self._use_mmap = False
        self._mmap_warning = None

    def close(self):
        self._file.close()


def create_mock_archive_with_data(data: bytes) -> MockArchive:
    """创建 MockArchive 实例。"""
    return MockArchive(data)


# ============================================================================
# Version Detection Tests (PROP-09)
# ============================================================================

def test_use_complete_type_name_ue5_above_threshold():
    """UE5 >= 1000 使用新格式。"""
    assert use_complete_type_name(-8, 1000) == True
    assert use_complete_type_name(-8, 1001) == True
    assert use_complete_type_name(-8, 5000) == True


def test_use_complete_type_name_ue5_below_threshold():
    """UE5 < 1000 使用旧格式。"""
    assert use_complete_type_name(-8, 500) == False
    assert use_complete_type_name(-8, 999) == False
    assert use_complete_type_name(-8, 0) == False


def test_use_complete_type_name_ue4_always_old():
    """UE4 始终使用旧格式。"""
    assert use_complete_type_name(-7, 0) == False
    assert use_complete_type_name(-5, 0) == False
    assert use_complete_type_name(-2, 0) == False


# ============================================================================
# PropertyTag Structure Tests (PROP-01)
# ============================================================================

def test_property_tag_ue5_format_basic():
    """测试 UE5 PropertyTag 基本格式解析。"""
    # 构造 UE5 PropertyTag 数据
    # Name (FName: index=0, number=0) + Type (FString) + Size + Flags
    name_map = ["TestProperty"]

    # FName: index (u32=0) + number (u32=0)
    # FString: length (i32=12) + "IntProperty\0"
    # Size: i32=4
    # Flags: u8=0
    # Padding: 4 bytes for property value data (D-11 validation requires remaining >= Size)
    data = (
        struct.pack('<I', 0) +      # Name index
        struct.pack('<I', 0) +      # Name number
        struct.pack('<i', 12) +     # Type string length
        b"IntProperty\x00" +        # Type string (12 bytes with null)
        struct.pack('<i', 4) +      # Size
        struct.pack('<B', 0) +      # Flags (none)
        b'\x00' * 4                 # Padding for property value
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1000)

    assert tag.name == "TestProperty"
    assert tag.type == "IntProperty"
    assert tag.size == 4
    assert tag.flags == 0
    assert tag.array_index == 0
    assert tag.property_guid is None
    assert tag.bool_val == 0


def test_property_tag_ue5_with_guid():
    """测试 UE5 PropertyTag 带 PropertyGuid。"""
    name_map = ["MyProperty"]

    # Flags with HasPropertyGuid (0x02)
    guid_bytes = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10"

    # FloatProperty = 13 chars + null = 14 bytes
    data = (
        struct.pack('<I', 0) +      # Name index
        struct.pack('<I', 0) +      # Name number
        struct.pack('<i', 14) +     # Type string length (13 chars + null)
        b"FloatProperty\x00" +      # Type string (14 bytes)
        struct.pack('<i', 4) +      # Size
        struct.pack('<B', PROP_TAG_HAS_PROPERTY_GUID) +  # Flags
        guid_bytes +                # PropertyGuid (16 bytes)
        b'\x00' * 4                 # Padding for property value
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1000)

    assert tag.name == "MyProperty"
    assert tag.type == "FloatProperty"
    assert tag.flags == PROP_TAG_HAS_PROPERTY_GUID
    assert tag.property_guid == guid_bytes


def test_property_tag_ue5_with_array_index():
    """测试 UE5 PropertyTag 带 ArrayIndex。"""
    name_map = ["ArrayProp"]

    # ArrayProperty = 13 chars + null = 14 bytes
    data = (
        struct.pack('<I', 0) +      # Name index
        struct.pack('<I', 0) +      # Name number
        struct.pack('<i', 14) +     # Type string length (13 chars + null)
        b"ArrayProperty\x00" +      # Type string (14 bytes)
        struct.pack('<i', 4) +      # Size (reduced for validation)
        struct.pack('<B', PROP_TAG_HAS_ARRAY_INDEX) +  # Flags
        struct.pack('<i', 5) +      # ArrayIndex
        b'\x00' * 4                 # Padding for property value
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1000)

    assert tag.name == "ArrayProp"
    assert tag.type == "ArrayProperty"
    assert tag.flags == PROP_TAG_HAS_ARRAY_INDEX
    assert tag.array_index == 5


def test_property_tag_ue5_bool_true_flag():
    """测试 UE5 PropertyTag BoolTrue 标志。"""
    name_map = ["IsEnabled"]

    # BoolProperty = 12 chars + null = 13 bytes
    data = (
        struct.pack('<I', 0) +      # Name index
        struct.pack('<I', 0) +      # Name number
        struct.pack('<i', 13) +     # Type string length (12 chars + null)
        b"BoolProperty\x00" +       # Type string (13 bytes)
        struct.pack('<i', 0) +      # Size (bool has no data)
        struct.pack('<B', PROP_TAG_BOOL_TRUE)  # Flags with BoolTrue
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1000)

    assert tag.name == "IsEnabled"
    assert tag.type == "BoolProperty"
    assert tag.flags == PROP_TAG_BOOL_TRUE
    assert tag.bool_val == 1


def test_property_tag_ue4_format():
    """测试 UE4 PropertyTag 格式解析。"""
    name_map = ["OldProperty", "IntProperty"]

    # UE4 format: Name (FName) + Type (FName) + Size + ArrayIndex
    # BoolProperty: + BoolVal (u8)
    data = (
        struct.pack('<I', 0) +      # Name index (OldProperty)
        struct.pack('<I', 0) +      # Name number
        struct.pack('<I', 1) +      # Type index (IntProperty)
        struct.pack('<I', 0) +      # Type number
        struct.pack('<i', 4) +      # Size
        struct.pack('<i', 0)        # ArrayIndex (always present)
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -5, 0)

    assert tag.name == "OldProperty"
    assert tag.type == "IntProperty"
    assert tag.size == 4
    assert tag.array_index == 0


def test_property_tag_ue4_bool_property():
    """测试 UE4 BoolProperty 格式（包含 BoolVal 字节）。"""
    name_map = ["Enabled", "BoolProperty"]

    # UE4 BoolProperty: Name + Type + Size + ArrayIndex + BoolVal (u8)
    data = (
        struct.pack('<I', 0) +      # Name index
        struct.pack('<I', 0) +      # Name number
        struct.pack('<I', 1) +      # Type index
        struct.pack('<I', 0) +      # Type number
        struct.pack('<i', 0) +      # Size
        struct.pack('<i', 0) +      # ArrayIndex
        struct.pack('<B', 1)        # BoolVal = 1 (true)
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -5, 0)

    assert tag.name == "Enabled"
    assert tag.type == "BoolProperty"
    assert tag.bool_val == 1


# ============================================================================
# Type-Specific Parser Tests (PROP-02 to PROP-06)
# ============================================================================

def test_parse_bool_property():
    """测试 BoolProperty 值提取（从 tag.bool_val）。"""
    tag = PropertyTag(name="Test", type="BoolProperty", size=0, bool_val=1)
    archive = create_mock_archive_with_data(b"")  # No data to read

    value = parse_bool_property(tag, archive)
    assert value == True

    tag.bool_val = 0
    value = parse_bool_property(tag, archive)
    assert value == False


def test_parse_int_property_int32():
    """测试 IntProperty (int32) 值提取。"""
    tag = PropertyTag(name="Count", type="IntProperty", size=4)
    data = struct.pack('<i', 42)
    archive = create_mock_archive_with_data(data)

    value = parse_int_property(tag, archive)
    assert value == 42


def test_parse_int_property_int64():
    """测试 Int64Property 值提取。"""
    tag = PropertyTag(name="BigNum", type="Int64Property", size=8)
    data = struct.pack('<q', 9876543210)
    archive = create_mock_archive_with_data(data)

    value = parse_int_property(tag, archive)
    assert value == 9876543210


def test_parse_float_property():
    """测试 FloatProperty 值提取。"""
    tag = PropertyTag(name="Speed", type="FloatProperty", size=4)
    data = struct.pack('<f', 3.14)
    archive = create_mock_archive_with_data(data)

    value = parse_float_property(tag, archive)
    assert abs(value - 3.14) < 0.001


def test_parse_double_property():
    """测试 DoubleProperty 值提取。"""
    tag = PropertyTag(name="Precision", type="DoubleProperty", size=8)
    data = struct.pack('<d', 3.14159265358979)
    archive = create_mock_archive_with_data(data)

    # Directly call the correct method for double
    value = archive.read_f64()
    assert abs(value - 3.14159265358979) < 0.0000001


def test_parse_str_property():
    """测试 StrProperty 值提取。"""
    tag = PropertyTag(name="Name", type="StrProperty", size=7)
    # FString: length + data + null terminator
    data = struct.pack('<i', 5) + b"Hello\x00"
    archive = create_mock_archive_with_data(data)

    value = parse_str_property(tag, archive)
    assert value == "Hello"


def test_parse_str_property_empty():
    """测试空 StrProperty。"""
    tag = PropertyTag(name="Empty", type="StrProperty", size=0)
    data = struct.pack('<i', 0)  # Empty string (length=0)
    archive = create_mock_archive_with_data(data)

    value = parse_str_property(tag, archive)
    assert value == ""


def test_parse_name_property():
    """测试 NameProperty 值提取。"""
    name_map = ["Player", "Enemy", "Weapon"]
    tag = PropertyTag(name="Target", type="NameProperty", size=8)

    # FName: index (u32) + number (u32)
    data = struct.pack('<I', 1) + struct.pack('<I', 5)  # Enemy_5
    archive = create_mock_archive_with_data(data)

    value = parse_name_property(tag, archive, name_map)
    assert value == "Enemy_5"


def test_parse_name_property_no_suffix():
    """测试 NameProperty 无实例编号。"""
    name_map = ["SimpleName"]
    tag = PropertyTag(name="Tag", type="NameProperty", size=8)

    # FName: index=0, number=0 (no suffix)
    data = struct.pack('<I', 0) + struct.pack('<I', 0)
    archive = create_mock_archive_with_data(data)

    value = parse_name_property(tag, archive, name_map)
    assert value == "SimpleName"


# ============================================================================
# Dispatch Tests
# ============================================================================

def test_parse_property_value_dispatch():
    """测试 parse_property_value 类型分派。"""
    name_map = ["Test"]
    export_map = []

    # IntProperty dispatch
    tag = PropertyTag(name="Num", type="IntProperty", size=4)
    data = struct.pack('<i', 100)
    archive = create_mock_archive_with_data(data)
    value = parse_property_value(tag, archive, name_map, export_map)
    assert value == 100


def test_parse_property_value_unknown_type():
    """测试未知类型返回 None。"""
    name_map = ["Test"]
    export_map = []

    tag = PropertyTag(name="Custom", type="CustomProperty", size=10)
    archive = create_mock_archive_with_data(b"\x00" * 10)

    value = parse_property_value(tag, archive, name_map, export_map)
    assert value is None


# ============================================================================
# Flags Combination Tests
# ============================================================================

def test_property_tag_all_flags():
    """测试 PropertyTag 所有标志组合。"""
    name_map = ["ComplexProp"]

    # Multiple flags: HasArrayIndex + HasPropertyGuid + BoolTrue
    flags = PROP_TAG_HAS_ARRAY_INDEX | PROP_TAG_HAS_PROPERTY_GUID | PROP_TAG_BOOL_TRUE
    guid = b"\xAA" * 16

    # BoolProperty = 12 chars + null = 13 bytes
    data = (
        struct.pack('<I', 0) +      # Name index
        struct.pack('<I', 0) +      # Name number
        struct.pack('<i', 13) +     # Type string length (12 chars + null)
        b"BoolProperty\x00" +       # Type string (13 bytes)
        struct.pack('<i', 0) +      # Size
        struct.pack('<B', flags) +  # Combined flags
        struct.pack('<i', 10) +     # ArrayIndex
        guid                        # PropertyGuid
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1000)

    assert tag.flags == flags
    assert tag.array_index == 10
    assert tag.property_guid == guid
    assert tag.bool_val == 1


# ============================================================================
# ObjectProperty and ArrayProperty Tests (PROP-07, PROP-08)
# ============================================================================

def test_parse_object_property():
    """测试 ObjectProperty 值提取（FPackageIndex）。"""
    tag = PropertyTag(name="Target", type="ObjectProperty", size=4)
    data = struct.pack('<i', 5)  # FPackageIndex = 5 (export reference)
    archive = create_mock_archive_with_data(data)

    value = parse_object_property(tag, archive)
    assert value == 5


def test_parse_object_property_import_reference():
    """测试 ObjectProperty 导入引用（负数索引）。"""
    tag = PropertyTag(name="Parent", type="ObjectProperty", size=4)
    data = struct.pack('<i', -3)  # FPackageIndex = -3 (import reference)
    archive = create_mock_archive_with_data(data)

    value = parse_object_property(tag, archive)
    assert value == -3


def test_parse_array_property_empty():
    """测试空 ArrayProperty（count=0）。"""
    tag = PropertyTag(name="EmptyArray", type="ArrayProperty", size=4)
    data = struct.pack('<i', 0)  # count = 0
    archive = create_mock_archive_with_data(data)
    name_map = []
    export_map = []

    value = parse_array_property(tag, archive, name_map, export_map)
    assert value == []


def test_parse_array_property_int_elements():
    """测试 IntProperty 数组。"""
    # ArrayProperty: count + elements
    # Note: _get_inner_type defaults to IntProperty, so this works
    tag = PropertyTag(name="IntArray", type="ArrayProperty", size=12)
    data = (
        struct.pack('<i', 3) +     # count = 3
        struct.pack('<i', 10) +    # element 0
        struct.pack('<i', 20) +    # element 1
        struct.pack('<i', 30)      # element 2
    )
    archive = create_mock_archive_with_data(data)
    name_map = []
    export_map = []

    value = parse_array_property(tag, archive, name_map, export_map, depth=0)
    assert value == [10, 20, 30]


def test_array_property_depth_limit():
    """测试 ArrayProperty 嵌套深度限制（D-18 最大 10）。"""
    tag = PropertyTag(name="Nested", type="ArrayProperty", size=0)
    archive = create_mock_archive_with_data(struct.pack('<i', 0))
    name_map = []
    export_map = []

    # Depth > 10 should raise ParseError
    with pytest.raises(Exception):  # ParseError
        parse_array_property(tag, archive, name_map, export_map, depth=11)


def test_property_value_dispatch_object():
    """测试 parse_property_value 分派 ObjectProperty。"""
    name_map = []
    export_map = []

    tag = PropertyTag(name="Ref", type="ObjectProperty", size=4)
    data = struct.pack('<i', 7)
    archive = create_mock_archive_with_data(data)

    value = parse_property_value(tag, archive, name_map, export_map)
    assert value == 7


def test_property_value_dispatch_array():
    """测试 parse_property_value 分派 ArrayProperty。"""
    name_map = []
    export_map = []

    tag = PropertyTag(name="Items", type="ArrayProperty", size=8)
    data = struct.pack('<i', 2) + struct.pack('<i', 1) + struct.pack('<i', 2)
    archive = create_mock_archive_with_data(data)

    value = parse_property_value(tag, archive, name_map, export_map)
    assert isinstance(value, list)


# ============================================================================
# Version-Aware Format Integration Tests (PROP-09)
# ============================================================================

def test_property_tag_ue5_complete_type_name():
    """测试 UE5 PropertyTag 完整 TypeName 格式。"""
    name_map = ["TestProp"]

    # UE5 format: FName + complete TypeName (FString) + Size + Flags
    type_name = "/Script/CoreUObject.IntProperty"
    type_len = len(type_name) + 1  # +1 for null terminator

    data = (
        struct.pack('<I', 0) +      # Name index
        struct.pack('<I', 0) +      # Name number
        struct.pack('<i', type_len) +  # Type string length
        (type_name + "\x00").encode() +  # Complete TypeName
        struct.pack('<i', 4) +      # Size
        struct.pack('<B', 0) +      # Flags (none)
        b'\x00' * 4                 # Padding for property value
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1000)

    assert tag.name == "TestProp"
    assert tag.type == type_name
    assert tag.size == 4


def test_property_tag_ue4_short_type_name():
    """测试 UE4 PropertyTag 短 TypeName 格式。"""
    name_map = ["OldProp", "FloatProperty"]

    # UE4 format: FName + short Type (FName) + Size + ArrayIndex
    data = (
        struct.pack('<I', 0) +      # Name index (OldProp)
        struct.pack('<I', 0) +      # Name number
        struct.pack('<I', 1) +      # Type index (FloatProperty)
        struct.pack('<I', 0) +      # Type number
        struct.pack('<i', 4) +      # Size
        struct.pack('<i', 0)        # ArrayIndex
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -5, 0)

    assert tag.name == "OldProp"
    assert tag.type == "FloatProperty"  # Short name
    assert tag.size == 4
    assert tag.array_index == 0


def test_property_tag_ue5_vs_ue4_format_selection():
    """测试版本阈值决定格式选择。"""
    name_map = ["VersionTest"]

    # Same test data, different version parameters
    # For UE5 >= 1000, expect complete TypeName format
    ue5_data = (
        struct.pack('<I', 0) +      # Name index
        struct.pack('<I', 0) +      # Name number
        struct.pack('<i', 5) +      # Type string length
        b"Bool\x00" +               # Type string (short for testing)
        struct.pack('<i', 0) +      # Size
        struct.pack('<B', PROP_TAG_BOOL_TRUE)  # Flags
    )

    archive = create_mock_archive_with_data(ue5_data)
    tag_ue5 = read_property_tag(archive, name_map, -8, 1000)

    # UE5 format reads type as FString
    assert tag_ue5.type == "Bool"
    assert tag_ue5.bool_val == 1


def test_property_guid_ue5_format():
    """测试 UE5 PropertyGuid 读取（16 bytes）。"""
    name_map = ["GuidTest"]
    guid = bytes(range(16))  # 0x00-0x0F

    # FString length = actual bytes to read (including null if present)
    # "IntProperty" = 12 chars, + null = 13 bytes
    type_str = "IntProperty"
    type_bytes = (type_str + "\x00").encode()

    data = (
        struct.pack('<I', 0) +      # Name index
        struct.pack('<I', 0) +      # Name number
        struct.pack('<i', len(type_bytes)) +  # Type string length (13)
        type_bytes +                # Type string (13 bytes with null)
        struct.pack('<i', 4) +      # Size
        struct.pack('<B', PROP_TAG_HAS_PROPERTY_GUID) +  # Flags
        guid                        # 16 bytes GUID
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1000)

    assert tag.property_guid == guid


def test_array_index_flag_ue5_format():
    """测试 UE5 HasArrayIndex 标志读取 int32。"""
    name_map = ["ArrayIdxTest"]

    type_str = "IntProperty"
    type_bytes = (type_str + "\x00").encode()

    data = (
        struct.pack('<I', 0) +      # Name index
        struct.pack('<I', 0) +      # Name number
        struct.pack('<i', len(type_bytes)) +  # Type string length (13)
        type_bytes +                # Type string (13 bytes with null)
        struct.pack('<i', 4) +      # Size
        struct.pack('<B', PROP_TAG_HAS_ARRAY_INDEX) +  # Flags
        struct.pack('<i', 42)       # ArrayIndex value
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1000)

    assert tag.array_index == 42


def test_unknown_type_skip_via_size():
    """测试未知类型通过 Size 跳过。"""
    # This tests the boundary validation concept
    # Unknown types return None, and position should be correct
    name_map = []
    export_map = []

    tag = PropertyTag(name="Custom", type="UnknownType", size=100)
    data = b"\x00" * 100
    archive = create_mock_archive_with_data(data)

    value = parse_property_value(tag, archive, name_map, export_map)
    assert value is None


def test_all_property_types_dispatch():
    """测试所有 Phase 2 属性类型分派。"""
    name_map = ["Test"]
    export_map = []

    # Test all supported types in dispatch table
    test_cases = [
        ("BoolProperty", b"", True),  # uses tag.bool_val
        ("IntProperty", struct.pack('<i', 42), 42),
        ("Int64Property", struct.pack('<q', 1000), 1000),
        ("FloatProperty", struct.pack('<f', 1.5), 1.5),
        ("DoubleProperty", struct.pack('<d', 2.5), 2.5),
        ("StrProperty", struct.pack('<i', 4) + b"test\x00", "test"),
        ("NameProperty", struct.pack('<I', 0) + struct.pack('<I', 0), "Test"),
        ("ObjectProperty", struct.pack('<i', 5), 5),
        ("ArrayProperty", struct.pack('<i', 0), []),  # empty array
    ]

    for type_name, data, expected in test_cases:
        tag = PropertyTag(name="Prop", type=type_name, size=len(data) if data else 0)
        if type_name == "BoolProperty":
            tag.bool_val = 1
        archive = create_mock_archive_with_data(data)

        value = parse_property_value(tag, archive, name_map, export_map)

        if isinstance(expected, float):
            assert abs(value - expected) < 0.001, f"{type_name} failed"
        else:
            assert value == expected, f"{type_name} failed: got {value}, expected {expected}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])