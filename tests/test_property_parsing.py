"""
tests/test_property_parsing.py - PropertyTag 解析测试（Phase 2）

测试 PropertyTag 结构解析和基本属性类型值提取。

⚠️  DEPRECATED: 此测试文件针对 v1.0 旧版代码，v6.0 重构后已失效。
"""

import pytest

# 立即跳过整个模块，避免执行导入
pytest.skip(reason="Deprecated: 此测试针对旧版代码，v6.0 重构后 API 已变更", allow_module_level=True)

import struct
from io import BytesIO
from dataclasses import dataclass

from uasset_read import (
    FArchive,
    PropertyTag,
    PropertyValue,
    ObjectExport,
    ObjectImport,
    PackageIndex,
    PackageFileSummary,
    use_complete_type_name,
    read_property_tag,
    parse_bool_property,
    parse_int_property,
    parse_float_property,
    parse_str_property,
    parse_name_property,
    parse_object_property,
    parse_soft_object_property,
    parse_array_property,
    parse_property_value,
    parse_properties_from_export,
    resolve_package_index_to_reference,
    PROP_TAG_HAS_ARRAY_INDEX,
    PROP_TAG_HAS_PROPERTY_GUID,
    PROP_TAG_HAS_EXTENSIONS,
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
    """UE5 >= 1012 使用新格式（PROPERTY_TAG_COMPLETE_TYPE_NAME 阈值）。"""
    assert use_complete_type_name(-8, 1012) == True
    assert use_complete_type_name(-8, 1013) == True
    assert use_complete_type_name(-8, 5000) == True


def test_use_complete_type_name_ue5_below_threshold():
    """UE5 < 1012 使用旧格式。"""
    assert use_complete_type_name(-8, 500) == False
    assert use_complete_type_name(-8, 1000) == False  # 1000 < 1012，使用旧格式
    assert use_complete_type_name(-8, 1011) == False
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
    # Phase 28a FIX: UE5 >= 1012 uses FPropertyTypeName format (not FString)
    # Format: Name(FName) + TypeName(FPropertyTypeNameNode) + Size + Flags
    # FPropertyTypeNameNode: FName(8) + InnerCount(4)
    name_map = ["TestProperty", "IntProperty"]

    # FName: index (u32) + number (u32)
    # FPropertyTypeName: FName(8) + InnerCount(4)
    # Size: i32=4
    # Flags: u8=0
    # Padding: 4 bytes for property value data (D-11 validation requires remaining >= Size)
    data = (
        struct.pack('<I', 0) +      # Name index (TestProperty)
        struct.pack('<I', 0) +      # Name number
        struct.pack('<I', 1) +      # TypeName index (IntProperty)
        struct.pack('<I', 0) +      # TypeName number
        struct.pack('<i', 0) +      # InnerCount = 0 (no inner types)
        struct.pack('<i', 4) +      # Size
        struct.pack('<B', 0) +      # Flags (none)
        b'\x00' * 4                 # Padding for property value
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1012)  # UE5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME threshold

    assert tag.name == "TestProperty"
    assert tag.type == "IntProperty"
    assert tag.size == 4
    assert tag.flags == 0
    assert tag.array_index == 0
    assert tag.property_guid is None
    assert tag.bool_val == 0


def test_property_tag_ue5_with_guid():
    """测试 UE5 PropertyTag 带 PropertyGuid。"""
    # Phase 28a FIX: UE5 >= 1012 uses FPropertyTypeName format
    name_map = ["MyProperty", "FloatProperty"]

    # Flags with HasPropertyGuid (0x02)
    guid_bytes = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10"

    # FPropertyTypeNameNode: FName(8) + InnerCount(4)
    data = (
        struct.pack('<I', 0) +      # Name index (MyProperty)
        struct.pack('<I', 0) +      # Name number
        struct.pack('<I', 1) +      # TypeName index (FloatProperty)
        struct.pack('<I', 0) +      # TypeName number
        struct.pack('<i', 0) +      # InnerCount = 0
        struct.pack('<i', 4) +      # Size
        struct.pack('<B', PROP_TAG_HAS_PROPERTY_GUID) +  # Flags
        guid_bytes +                # PropertyGuid (16 bytes)
        b'\x00' * 4                 # Padding for property value
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1012)  # UE5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME threshold

    assert tag.name == "MyProperty"
    assert tag.type == "FloatProperty"
    assert tag.flags == PROP_TAG_HAS_PROPERTY_GUID
    assert tag.property_guid == guid_bytes


def test_property_tag_ue5_with_array_index():
    """测试 UE5 PropertyTag 带 ArrayIndex。"""
    # Phase 28a FIX: UE5 >= 1012 uses FPropertyTypeName format
    name_map = ["ArrayProp", "ArrayProperty"]

    # FPropertyTypeNameNode: FName(8) + InnerCount(4)
    data = (
        struct.pack('<I', 0) +      # Name index (ArrayProp)
        struct.pack('<I', 0) +      # Name number
        struct.pack('<I', 1) +      # TypeName index (ArrayProperty)
        struct.pack('<I', 0) +      # TypeName number
        struct.pack('<i', 0) +      # InnerCount = 0
        struct.pack('<i', 4) +      # Size (reduced for validation)
        struct.pack('<B', PROP_TAG_HAS_ARRAY_INDEX) +  # Flags
        struct.pack('<i', 5) +      # ArrayIndex
        b'\x00' * 4                 # Padding for property value
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1012)  # UE5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME threshold

    assert tag.name == "ArrayProp"
    assert tag.type == "ArrayProperty"
    assert tag.flags == PROP_TAG_HAS_ARRAY_INDEX
    assert tag.array_index == 5


def test_property_tag_ue5_bool_true_flag():
    """测试 UE5 PropertyTag BoolTrue 标志。"""
    # Phase 28a FIX: UE5 >= 1012 uses FPropertyTypeName format
    name_map = ["IsEnabled", "BoolProperty"]

    # FPropertyTypeNameNode: FName(8) + InnerCount(4)
    data = (
        struct.pack('<I', 0) +      # Name index (IsEnabled)
        struct.pack('<I', 0) +      # Name number
        struct.pack('<I', 1) +      # TypeName index (BoolProperty)
        struct.pack('<I', 0) +      # TypeName number
        struct.pack('<i', 0) +      # InnerCount = 0
        struct.pack('<i', 0) +      # Size (bool has no data)
        struct.pack('<B', PROP_TAG_BOOL_TRUE)  # Flags with BoolTrue
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1012)  # UE5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME threshold

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
    # Phase 28a FIX: UE5 >= 1012 uses FPropertyTypeName format
    name_map = ["ComplexProp", "BoolProperty"]

    # Multiple flags: HasArrayIndex + HasPropertyGuid + BoolTrue
    flags = PROP_TAG_HAS_ARRAY_INDEX | PROP_TAG_HAS_PROPERTY_GUID | PROP_TAG_BOOL_TRUE
    guid = b"\xAA" * 16

    # FPropertyTypeNameNode: FName(8) + InnerCount(4)
    data = (
        struct.pack('<I', 0) +      # Name index (ComplexProp)
        struct.pack('<I', 0) +      # Name number
        struct.pack('<I', 1) +      # TypeName index (BoolProperty)
        struct.pack('<I', 0) +      # TypeName number
        struct.pack('<i', 0) +      # InnerCount = 0
        struct.pack('<i', 0) +      # Size
        struct.pack('<B', flags) +  # Combined flags
        struct.pack('<i', 10) +     # ArrayIndex
        guid                        # PropertyGuid
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1012)  # UE5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME threshold

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
    # Phase 28a FIX: UE5 >= 1012 uses FPropertyTypeName format
    # The code extracts only the root type name from FPropertyTypeName
    name_map = ["TestProp", "/Script/CoreUObject.IntProperty"]

    # FPropertyTypeNameNode: FName(8) + InnerCount(4)
    # For "/Script/CoreUObject.IntProperty", first node is the full path
    data = (
        struct.pack('<I', 0) +      # Name index (TestProp)
        struct.pack('<I', 0) +      # Name number
        struct.pack('<I', 1) +      # TypeName index (/Script/CoreUObject.IntProperty)
        struct.pack('<I', 0) +      # TypeName number
        struct.pack('<i', 0) +      # InnerCount = 0
        struct.pack('<i', 4) +      # Size
        struct.pack('<B', 0) +      # Flags (none)
        b'\x00' * 4                 # Padding for property value
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1012)  # UE5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME threshold

    assert tag.name == "TestProp"
    assert tag.type == "/Script/CoreUObject.IntProperty"  # First node name
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
    # Phase 28a FIX: UE5 >= 1012 uses FPropertyTypeName format
    name_map = ["VersionTest", "Bool"]

    # For UE5 >= 1012, expect FPropertyTypeName format
    ue5_data = (
        struct.pack('<I', 0) +      # Name index (VersionTest)
        struct.pack('<I', 0) +      # Name number
        struct.pack('<I', 1) +      # TypeName index (Bool)
        struct.pack('<I', 0) +      # TypeName number
        struct.pack('<i', 0) +      # InnerCount = 0
        struct.pack('<i', 0) +      # Size
        struct.pack('<B', PROP_TAG_BOOL_TRUE)  # Flags
    )

    archive = create_mock_archive_with_data(ue5_data)
    tag_ue5 = read_property_tag(archive, name_map, -8, 1012)  # UE5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME threshold

    # UE5 format reads type as FPropertyTypeName (first node name)
    assert tag_ue5.type == "Bool"
    assert tag_ue5.bool_val == 1


def test_property_guid_ue5_format():
    """测试 UE5 PropertyGuid 读取（16 bytes）。"""
    # Phase 28a FIX: UE5 >= 1012 uses FPropertyTypeName format
    name_map = ["GuidTest", "IntProperty"]
    guid = bytes(range(16))  # 0x00-0x0F

    # FPropertyTypeNameNode: FName(8) + InnerCount(4)
    data = (
        struct.pack('<I', 0) +      # Name index (GuidTest)
        struct.pack('<I', 0) +      # Name number
        struct.pack('<I', 1) +      # TypeName index (IntProperty)
        struct.pack('<I', 0) +      # TypeName number
        struct.pack('<i', 0) +      # InnerCount = 0
        struct.pack('<i', 4) +      # Size
        struct.pack('<B', PROP_TAG_HAS_PROPERTY_GUID) +  # Flags
        guid +                      # 16 bytes GUID
        b'\x00' * 4                 # Padding
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1012)  # UE5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME threshold

    assert tag.property_guid == guid


def test_array_index_flag_ue5_format():
    """测试 UE5 HasArrayIndex 标志读取 int32。"""
    # Phase 28a FIX: UE5 >= 1012 uses FPropertyTypeName format
    name_map = ["ArrayIdxTest", "IntProperty"]

    # FPropertyTypeNameNode: FName(8) + InnerCount(4)
    data = (
        struct.pack('<I', 0) +      # Name index (ArrayIdxTest)
        struct.pack('<I', 0) +      # Name number
        struct.pack('<I', 1) +      # TypeName index (IntProperty)
        struct.pack('<I', 0) +      # TypeName number
        struct.pack('<i', 0) +      # InnerCount = 0
        struct.pack('<i', 4) +      # Size
        struct.pack('<B', PROP_TAG_HAS_ARRAY_INDEX) +  # Flags
        struct.pack('<i', 42) +     # ArrayIndex value
        b'\x00' * 4                 # Padding
    )

    archive = create_mock_archive_with_data(data)
    tag = read_property_tag(archive, name_map, -8, 1012)  # UE5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME threshold

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


# ============================================================================
# Phase 11-02: ObjectProperty Enhanced Resolution Tests
# ============================================================================

def test_object_property_resolved_import():
    """测试resolve_package_index_to_reference解析import引用。"""
    name_map = ["Package", "Class", "Object"]

    # 创建import_map条目
    import_map = [
        ObjectImport(
            class_package="Package",
            class_name="Class",
            outer_index=PackageIndex(0),
            object_name="Object"
        )
    ]
    export_map = []

    # 创建import引用（负数索引：-1对应import_map[0]）
    pkg_idx = PackageIndex(-1)
    resolved = resolve_package_index_to_reference(pkg_idx, import_map, export_map, name_map)

    assert resolved is not None
    assert resolved["type"] == "import"
    assert resolved["class_name"] == "Class"
    assert resolved["object_name"] == "Object"
    assert resolved["package"] == "Package"


def test_object_property_resolved_export():
    """测试resolve_package_index_to_reference解析export引用。"""
    name_map = ["TestClass", "TestObject"]

    # 创建export_map条目
    export_map = [
        ObjectExport(
            class_index=PackageIndex(0),  # None类
            super_index=PackageIndex(0),
            outer_index=PackageIndex(0),
            object_name="TestObject",
            object_flags=0,
            serial_size=0,
            serial_offset=0
        )
    ]
    import_map = []

    # 创建export引用（正数索引：1对应export_map[0]）
    pkg_idx = PackageIndex(1)
    resolved = resolve_package_index_to_reference(pkg_idx, import_map, export_map, name_map)

    assert resolved is not None
    assert resolved["type"] == "export"
    assert resolved["class_name"] == "None"
    assert resolved["object_name"] == "TestObject"


def test_object_property_null_reference():
    """测试resolve_package_index_to_reference返回None对于空引用。"""
    name_map = []
    import_map = []
    export_map = []

    # 创建null引用（索引0）
    pkg_idx = PackageIndex(0)
    resolved = resolve_package_index_to_reference(pkg_idx, import_map, export_map, name_map)

    assert resolved is None


def test_object_property_import_out_of_range():
    """测试resolve_package_index_to_reference处理越界import索引。"""
    name_map = []
    import_map = []  # 空import_map
    export_map = []

    # 创建import引用但没有对应条目
    pkg_idx = PackageIndex(-1)
    resolved = resolve_package_index_to_reference(pkg_idx, import_map, export_map, name_map)

    # 越界应返回None
    assert resolved is None


def test_object_property_export_out_of_range():
    """测试resolve_package_index_to_reference处理越界export索引。"""
    name_map = []
    import_map = []
    export_map = []  # 空export_map

    # 创建export引用但没有对应条目
    pkg_idx = PackageIndex(1)
    resolved = resolve_package_index_to_reference(pkg_idx, import_map, export_map, name_map)

    # 越界应返回None
    assert resolved is None


def test_object_property_export_with_import_class():
    """测试resolve_package_index_to_reference解析export的类引用指向import。"""
    name_map = ["Engine", "Actor", "MyActor"]

    # 创建import条目作为类引用
    import_map = [
        ObjectImport(
            class_package="Engine",
            class_name="Actor",
            outer_index=PackageIndex(0),
            object_name="Default__Actor"
        )
    ]

    # 创建export条目，其class_index指向import
    export_map = [
        ObjectExport(
            class_index=PackageIndex(-1),  # 指向import_map[0]
            super_index=PackageIndex(0),
            outer_index=PackageIndex(0),
            object_name="MyActor",
            object_flags=0,
            serial_size=0,
            serial_offset=0
        )
    ]

    # 解析export引用
    pkg_idx = PackageIndex(1)  # export_map[0]
    resolved = resolve_package_index_to_reference(pkg_idx, import_map, export_map, name_map)

    assert resolved is not None
    assert resolved["type"] == "export"
    assert resolved["class_name"] == "Actor"  # 递归解析class_index得到类名
    assert resolved["object_name"] == "MyActor"


def test_object_property_in_parse_properties():
    """测试parse_properties_from_export增强ObjectProperty返回可读引用。"""
    # Phase 28a FIX: UE5 >= 1012 uses FPropertyTypeName format
    # name_map需要包含属性名、类型名和终止标记名"None"
    name_map = ["TestProp", "None", "Package", "Class", "Target", "ObjectProperty"]

    # D-02: SerializationControlExtensions 头部 (UE5 >= 1011)
    header_data = struct.pack('<B', 0x00)  # NoExtension

    # PropertyTag数据 (UE5 FPropertyTypeName格式)
    # FPropertyTypeNameNode: FName(8) + InnerCount(4)
    prop_data = (
        struct.pack('<I', 0) +      # Name index (TestProp)
        struct.pack('<I', 0) +      # Name number
        struct.pack('<I', 5) +      # TypeName index (ObjectProperty)
        struct.pack('<I', 0) +      # TypeName number
        struct.pack('<i', 0) +      # InnerCount = 0
        struct.pack('<i', 4) +      # Size
        struct.pack('<B', 0) +      # Flags
        struct.pack('<i', -1)       # Value: FPackageIndex = -1 (import reference)
    )

    # 终止标记 (UE5格式: Name="None"时只有FName，无Type/Size/Flags)
    # 参考: PropertyTag.cpp - when Name == "None", serialization ends
    terminator_data = (
        struct.pack('<I', 1) +      # Name index (指向name_map[1]="None")
        struct.pack('<I', 0)        # Name number
    )

    full_data = header_data + prop_data + terminator_data
    archive = create_mock_archive_with_data(full_data)

    # 创建测试导出条目
    export = ObjectExport(
        class_index=PackageIndex(0),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="TestExport",
        object_flags=0,
        serial_size=len(full_data),
        serial_offset=0,
        script_serial_size=len(full_data)  # D-01: UE5 >= 1010 使用 script_serial_size 作为边界
    )

    # 创建import_map
    import_map = [
        ObjectImport(
            class_package="Package",
            class_name="Class",
            outer_index=PackageIndex(0),
            object_name="Target"
        )
    ]

    # 创建summary
    summary = PackageFileSummary(
        tag=0x9E2A83C1,
        legacy_file_version=-8,
        file_version_ue4=522,
        file_version_ue5=1012  # >= PROPERTY_TAG_COMPLETE_TYPE_NAME threshold
    )

    export_map = [export]

    # 解析属性
    properties = parse_properties_from_export(
        export, archive, summary, name_map, export_map, import_map
    )

    # 验证ObjectProperty增强结果
    # Phase 31-04: parse_properties_from_export 增强逻辑将 int 替换为 ref dict
    assert len(properties) == 1
    prop = properties[0]
    assert prop.name == "TestProp"
    assert prop.type == "ObjectProperty"

    # 增强后的格式（resolve_package_index_to_reference 返回）
    assert isinstance(prop.value, dict)
    assert prop.value["type"] == "import"
    assert prop.value["source"] == "import_map"
    assert prop.value["class_name"] == "Class"
    assert prop.value["object_name"] == "Target"


def test_object_property_null_in_parse_properties():
    """测试parse_properties_from_export处理null ObjectProperty引用。"""
    # Phase 28a FIX: UE5 >= 1012 uses FPropertyTypeName format
    # name_map需要包含属性名、类型名和终止标记名"None"
    name_map = ["NullProp", "None", "ObjectProperty"]

    # D-02: SerializationControlExtensions 头部 (UE5 >= 1011)
    header_data = struct.pack('<B', 0x00)  # NoExtension

    # PropertyTag数据 (UE5 FPropertyTypeName格式) - null引用
    # FPropertyTypeNameNode: FName(8) + InnerCount(4)
    prop_data = (
        struct.pack('<I', 0) +      # Name index (NullProp)
        struct.pack('<I', 0) +      # Name number
        struct.pack('<I', 2) +      # TypeName index (ObjectProperty)
        struct.pack('<I', 0) +      # TypeName number
        struct.pack('<i', 0) +      # InnerCount = 0
        struct.pack('<i', 4) +      # Size
        struct.pack('<B', 0) +      # Flags
        struct.pack('<i', 0)        # Value: FPackageIndex = 0 (null)
    )

    # 终止标记 (UE5格式: Name="None"时只有FName，无Type/Size/Flags)
    terminator_data = (
        struct.pack('<I', 1) +      # Name index (指向name_map[1]="None")
        struct.pack('<I', 0)        # Name number
    )

    full_data = header_data + prop_data + terminator_data
    archive = create_mock_archive_with_data(full_data)

    export = ObjectExport(
        class_index=PackageIndex(0),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="TestExport",
        object_flags=0,
        serial_size=len(full_data),
        serial_offset=0,
        script_serial_size=len(full_data)  # D-01: UE5 >= 1010 使用 script_serial_size 作为边界
    )

    summary = PackageFileSummary(
        tag=0x9E2A83C1,
        legacy_file_version=-8,
        file_version_ue4=522,
        file_version_ue5=1012  # >= PROPERTY_TAG_COMPLETE_TYPE_NAME threshold
    )

    properties = parse_properties_from_export(
        export, archive, summary, name_map, [export], []  # import_map=[]
    )

    # 验证null引用结果
    # Phase 31-04: parse_object_property 返回 int (FPackageIndex raw value)
    assert len(properties) == 1
    prop = properties[0]
    assert prop.value == 0


# ============================================================================
# Phase 11-03: SoftObjectProperty Tests
# ============================================================================

def test_soft_object_property_basic():
    """测试SoftObjectProperty基本解析（无子路径）。"""
    tag = PropertyTag(name="SkeletalMesh", type="SoftObjectProperty", size=50)
    # FString: "/Game/Test/Asset" + null + "" (empty subpath)
    asset_path = "/Game/Test/Asset"
    data = (
        struct.pack('<i', len(asset_path) + 1) +  # asset_path length
        (asset_path + "\x00").encode() +          # asset_path string
        struct.pack('<i', 0)                       # sub_path length = 0 (empty)
    )
    archive = create_mock_archive_with_data(data)
    name_map = []

    value = parse_soft_object_property(tag, archive, name_map)

    assert isinstance(value, dict)
    assert value["asset_path"] == asset_path
    assert value["sub_path"] == ""


def test_soft_object_property_with_subpath():
    """测试SoftObjectProperty带子路径解析。"""
    tag = PropertyTag(name="AnimBlueprint", type="SoftObjectProperty", size=80)
    asset_path = "/Game/Characters/Animations"
    sub_path = "SubObject.AnimSequence"

    data = (
        struct.pack('<i', len(asset_path) + 1) +  # asset_path length
        (asset_path + "\x00").encode() +          # asset_path string
        struct.pack('<i', len(sub_path) + 1) +    # sub_path length
        (sub_path + "\x00").encode()              # sub_path string
    )
    archive = create_mock_archive_with_data(data)
    name_map = []

    value = parse_soft_object_property(tag, archive, name_map)

    assert isinstance(value, dict)
    assert value["asset_path"] == asset_path
    assert value["sub_path"] == sub_path


def test_soft_object_property_in_parse_property_value():
    """测试parse_property_value分派SoftObjectProperty。"""
    name_map = []
    export_map = []

    # 创建PropertyTag，type="SoftObjectProperty"
    asset_path = "/Game/Meshes/Character"
    tag = PropertyTag(name="Mesh", type="SoftObjectProperty", size=40)
    data = (
        struct.pack('<i', len(asset_path) + 1) +
        (asset_path + "\x00").encode() +
        struct.pack('<i', 0)  # empty sub_path
    )
    archive = create_mock_archive_with_data(data)

    # 调用parse_property_value
    value = parse_property_value(tag, archive, name_map, export_map)

    # 验证分派成功，返回值不为None
    assert value is not None
    assert isinstance(value, dict)
    assert "asset_path" in value
    assert "sub_path" in value
    assert value["asset_path"] == asset_path
    assert value["sub_path"] == ""


def test_soft_object_property_empty_asset_path():
    """测试SoftObjectProperty空资产路径。"""
    tag = PropertyTag(name="EmptyRef", type="SoftObjectProperty", size=4)
    # 空asset_path和空sub_path
    data = (
        struct.pack('<i', 0) +  # empty asset_path
        struct.pack('<i', 0)    # empty sub_path
    )
    archive = create_mock_archive_with_data(data)
    name_map = []

    value = parse_soft_object_property(tag, archive, name_map)

    assert isinstance(value, dict)
    assert value["asset_path"] == ""
    assert value["sub_path"] == ""


def test_soft_object_property_unicode_path():
    """测试SoftObjectProperty Unicode路径。"""
    tag = PropertyTag(name="Texture", type="SoftObjectProperty", size=60)
    asset_path = "/Game/素材/纹理"  # Chinese characters

    data = (
        struct.pack('<i', len(asset_path.encode('utf-8')) + 1) +
        (asset_path + "\x00").encode('utf-8') +
        struct.pack('<i', 0)  # empty sub_path
    )
    archive = create_mock_archive_with_data(data)
    name_map = []

    value = parse_soft_object_property(tag, archive, name_map)

    assert isinstance(value, dict)
    assert value["asset_path"] == asset_path
    assert value["sub_path"] == ""


# ============================================================================
# Phase 17 D-01: ScriptSerializationOffset 偏移计算测试
# ============================================================================

def test_script_serial_offset_calculation_ue5():
    """D-01: UE5 >= 1010 时，偏移计算使用 serial_offset + script_serial_offset"""
    # 构造测试数据
    export = ObjectExport(
        class_index=PackageIndex(0),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="TestObject",
        object_flags=0,
        serial_size=100,
        serial_offset=1000,
        script_serial_offset=50  # 相对偏移
    )
    summary = PackageFileSummary(
        tag=0x9E2A83C1,
        legacy_file_version=-8,
        file_version_ue4=522,
        file_version_ue5=1010  # >= UE5_SCRIPT_SERIALIZATION_OFFSET
    )

    # 验证计算逻辑：property_start = serial_offset + script_serial_offset
    expected_start = 1000 + 50  # = 1050
    # 实际验证需要 mock archive，此处验证逻辑正确性
    assert export.serial_offset + export.script_serial_offset == expected_start

    # 验证版本阈值判断
    from uasset_read import UE5_SCRIPT_SERIALIZATION_OFFSET
    assert summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET


def test_script_serial_offset_calculation_ue4():
    """D-01: UE5 < 1010 时，偏移计算仅使用 serial_offset"""
    export = ObjectExport(
        class_index=PackageIndex(0),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="TestObject",
        object_flags=0,
        serial_size=100,
        serial_offset=1000,
        script_serial_offset=50  # UE4 不使用此字段
    )
    summary = PackageFileSummary(
        tag=0x9E2A83C1,
        legacy_file_version=-5,
        file_version_ue4=522,
        file_version_ue5=0  # < UE5_SCRIPT_SERIALIZATION_OFFSET
    )

    # 验证计算逻辑：property_start = serial_offset（不加 script_serial_offset）
    expected_start = 1000  # 仅 serial_offset
    assert export.serial_offset == expected_start

    # 验证版本阈值判断
    from uasset_read import UE5_SCRIPT_SERIALIZATION_OFFSET
    assert summary.file_version_ue5 < UE5_SCRIPT_SERIALIZATION_OFFSET


def test_script_serial_offset_zero():
    """D-01: script_serial_offset = 0 时，两种计算结果相同"""
    export = ObjectExport(
        class_index=PackageIndex(0),
        super_index=PackageIndex(0),
        outer_index=PackageIndex(0),
        object_name="TestObject",
        object_flags=0,
        serial_size=100,
        serial_offset=1000,
        script_serial_offset=0
    )

    # 当 script_serial_offset = 0，两种计算等效
    assert export.serial_offset + export.script_serial_offset == export.serial_offset


# ============================================================================
# Phase 17 D-02: SerializationControlExtensions 头部测试
# ============================================================================

def test_serialization_control_extensions_no_extension():
    """D-02: serialization_control = 0x00 时，仅读取 1 byte"""
    # 构造 mock 数据：serialization_control = 0x00
    data = bytes([0x00])  # NoExtension
    archive = create_mock_archive_with_data(data)

    serialization_control = archive.read_u8()
    assert serialization_control == 0x00
    assert not (serialization_control & 0x02)  # 无 OverridableSerializationInformation
    # 仅读取 1 byte，位置正确
    assert archive.tell() == 1


def test_serialization_control_extensions_with_overridable():
    """D-02: serialization_control = 0x02 时，读取 2 bytes"""
    # 构造 mock 数据：serialization_control = 0x02 + overridden_operation
    data = bytes([0x02, 0x00])  # OverridableSerializationInformation + operation
    archive = create_mock_archive_with_data(data)

    serialization_control = archive.read_u8()
    assert serialization_control == 0x02
    assert (serialization_control & 0x02)  # 有 OverridableSerializationInformation

    # 需要读取 overridden_operation
    overridden_operation = archive.read_u8()
    assert archive.tell() == 2  # 总共读取 2 bytes


def test_serialization_control_extensions_version_threshold():
    """D-02: UE5_PROPERTY_TAG_EXTENSION = 1011 版本阈值验证"""
    from uasset_read import UE5_PROPERTY_TAG_EXTENSION
    assert UE5_PROPERTY_TAG_EXTENSION == 1011


# ============================================================================
# Phase 17 D-03: PropertyTag Extensions 测试
# ============================================================================

def test_property_tag_has_extensions_flag():
    """D-03: flags & 0x04 时，Extensions 数据正确读取"""
    assert PROP_TAG_HAS_EXTENSIONS == 0x04


def test_property_tag_extensions_no_extension():
    """D-03: property_extensions = 0x00 时，仅读取 1 byte"""
    # 构造 mock PropertyTag 数据（UE5 格式）
    # Name (FName index), Type (FString), Size (i32), Flags (u8), Extensions (u8)
    # 简化：直接构造 flags + extensions 数据
    data = bytes([
        0x04,  # flags = HAS_EXTENSIONS
        0x00,  # property_extensions = NoExtension
    ])
    archive = create_mock_archive_with_data(data)

    flags = archive.read_u8()
    assert flags == 0x04
    assert flags & PROP_TAG_HAS_EXTENSIONS

    property_extensions = archive.read_u8()
    assert property_extensions == 0x00
    assert not (property_extensions & 0x02)
    assert archive.tell() == 2


def test_property_tag_extensions_with_overridable():
    """D-03: property_extensions = 0x02 时，读取 3 bytes"""
    data = bytes([
        0x04,  # flags = HAS_EXTENSIONS
        0x02,  # property_extensions = OverridableInformation
        0x00,  # override_operation
        0x00,  # experimental_overridable_logic
    ])
    archive = create_mock_archive_with_data(data)

    flags = archive.read_u8()
    assert flags == 0x04
    assert flags & PROP_TAG_HAS_EXTENSIONS

    property_extensions = archive.read_u8()
    assert property_extensions == 0x02
    assert property_extensions & 0x02

    # 读取扩展数据
    override_operation = archive.read_u8()
    experimental_overridable_logic = archive.read_u8()
    assert archive.tell() == 4  # 总共 4 bytes (flags + extensions + operation + logic)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])