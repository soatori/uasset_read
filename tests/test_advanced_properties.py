"""
tests/test_advanced_properties.py - 高级属性类型测试（Phase 9）

测试六种高级属性类型解析：
- StructProperty（ADVP-01）
- MapProperty（ADVP-02）
- SetProperty（ADVP-03）
- EnumProperty（ADVP-04）
- TextProperty（ADVP-05）
- DelegateProperty（ADVP-06）
"""

import pytest
import struct
from io import BytesIO
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from uasset_read import (
    FArchive,
    PropertyTag,
    ObjectExport,
    PackageFileSummary,
    ParseError,
    # Wave 1 数据类
    AdvancedPropertyValue,
    StructValue,
    MapValue,
    SetValue,
    EnumValue,
    TextValue,
    DelegateValue,
    # Wave 2 解析函数
    parse_struct_property,
    parse_map_property,
    parse_set_property,
    parse_enum_property,
    parse_text_property,
    parse_delegate_property,
    # 辅助函数
    _extract_struct_type_from_tag,
    _extract_map_types_from_tag,
    _extract_set_type_from_tag,
    _extract_enum_type_from_tag,
    # 常量
    MAX_PROPERTY_COUNT,
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


def create_mock_summary(
    legacy_version: int = -8,
    ue5_version: int = 1000,
    ue4_version: int = 0
) -> PackageFileSummary:
    """创建 Mock PackageFileSummary。"""
    return PackageFileSummary(
        tag=0x9E2A83C1,  # 魔术标签
        legacy_file_version=legacy_version,
        file_version_ue4=ue4_version,
        file_version_ue5=ue5_version,
        name_count=0,
        name_offset=0,
        export_count=0,
        export_offset=0,
        import_count=0,
        import_offset=0,
    )


# ============================================================================
# StructProperty 测试（ADVP-01）
# ============================================================================

def test_extract_struct_type_from_tag_ue5():
    """测试从 UE5 PropertyTag 提取结构体类型名。"""
    # UE5 格式: "StructProperty(/Script/CoreUObject.Vector)"
    tag = PropertyTag(
        name="Location",
        type="StructProperty(/Script/CoreUObject.Vector)",
        size=0
    )

    struct_type = _extract_struct_type_from_tag(tag)
    assert struct_type == "Vector"


def test_extract_struct_type_from_tag_ue5_with_path():
    """测试从 UE5 PropertyTag 提取结构体类型名（带完整路径）。"""
    # UE5 格式: "StructProperty(/Script/Game.MyCustomStruct)"
    tag = PropertyTag(
        name="CustomData",
        type="StructProperty(/Script/Game.MyCustomStruct)",
        size=0
    )

    struct_type = _extract_struct_type_from_tag(tag)
    assert struct_type == "MyCustomStruct"


def test_extract_struct_type_from_tag_ue4():
    """测试从 UE4 PropertyTag 提取结构体类型名（无括号）。"""
    # UE4 格式: 简化处理，返回 UnknownStruct
    tag = PropertyTag(
        name="OldData",
        type="StructProperty",
        size=0
    )

    struct_type = _extract_struct_type_from_tag(tag)
    assert struct_type == "UnknownStruct"


def test_struct_property_depth_limit():
    """测试 StructProperty 递归深度限制（D-01 MAX_DEPTH=5）。"""
    name_map = ["None"]
    tag = PropertyTag(name="Nested", type="StructProperty(Unknown)", size=0)
    archive = create_mock_archive_with_data(b"")
    summary = create_mock_summary()
    export_map = []

    # Depth > 5 应抛出 ParseError
    with pytest.raises(ParseError):
        parse_struct_property(tag, archive, name_map, export_map, summary, depth=6)


def test_struct_property_depth_at_limit():
    """测试 StructProperty 递归深度等于限制（depth=5 应成功）。"""
    name_map = ["None"]
    tag = PropertyTag(name="AtLimit", type="StructProperty(Unknown)", size=0)

    # 仅 None 标记（UE5 格式）
    # FName: index (u32) + number (u32)
    # "None" 在 name_map 中索引为 0
    data = (
        struct.pack('<I', 0) +  # Name index ("None")
        struct.pack('<I', 0) +  # Name number
        struct.pack('<i', 5) +  # Type string length ("None\0")
        b"None\x00" +           # Type string
        struct.pack('<i', 0) +  # Size
        struct.pack('<B', 0)    # Flags
    )

    archive = create_mock_archive_with_data(data)
    summary = create_mock_summary()
    export_map = []

    # Depth = 5 应成功（在限制边界）
    result = parse_struct_property(tag, archive, name_map, export_map, summary, depth=5)
    assert isinstance(result, StructValue)
    assert result.property_type == "StructProperty"


def test_struct_property_empty():
    """测试空 StructProperty（仅 None 标记）。"""
    name_map = ["None"]
    tag = PropertyTag(name="EmptyStruct", type="StructProperty", size=0)

    # 仅 None 标记（UE5 格式）
    data = (
        struct.pack('<I', 0) +  # Name index ("None")
        struct.pack('<I', 0) +  # Name number
        struct.pack('<i', 5) +  # Type string length ("None\0")
        b"None\x00" +           # Type string
        struct.pack('<i', 0) +  # Size
        struct.pack('<B', 0)    # Flags
    )

    archive = create_mock_archive_with_data(data)
    summary = create_mock_summary()
    export_map = []

    result = parse_struct_property(tag, archive, name_map, export_map, summary, depth=0)

    assert isinstance(result, StructValue)
    assert result.property_type == "StructProperty"
    # UE4 格式（无括号）返回 "UnknownStruct"
    assert result.struct_type == "UnknownStruct"
    assert result.fields == {}


# ============================================================================
# MapProperty 测试（ADVP-02）
# ============================================================================

def test_extract_map_types_from_tag_ue5():
    """测试从 UE5 PropertyTag 提取 Map Key/Value 类型。"""
    # UE5 格式: "MapProperty(IntProperty,StrProperty)"
    tag = PropertyTag(
        name="IntToStrMap",
        type="MapProperty(IntProperty,StrProperty)",
        size=0
    )

    key_type, value_type = _extract_map_types_from_tag(tag)
    assert key_type == "IntProperty"
    assert value_type == "StrProperty"


def test_extract_map_types_from_tag_ue5_with_spaces():
    """测试从 UE5 PropertyTag 提取 Map Key/Value 类型（带空格）。"""
    # UE5 格式: "MapProperty(IntProperty, StrProperty)"（逗号后有空格）
    tag = PropertyTag(
        name="MapWithSpaces",
        type="MapProperty(IntProperty, StrProperty)",
        size=0
    )

    key_type, value_type = _extract_map_types_from_tag(tag)
    assert key_type == "IntProperty"
    assert value_type == "StrProperty"


def test_extract_map_types_from_tag_ue4():
    """测试从 UE4 PropertyTag 提取 Map Key/Value 类型（默认值）。"""
    # UE4 格式: 简化处理，返回默认类型
    tag = PropertyTag(
        name="OldMap",
        type="MapProperty",
        size=0
    )

    key_type, value_type = _extract_map_types_from_tag(tag)
    assert key_type == "IntProperty"
    assert value_type == "IntProperty"


def test_map_property_empty():
    """测试空 MapProperty（NumEntries=0）。"""
    name_map = []
    tag = PropertyTag(name="EmptyMap", type="MapProperty(IntProperty,IntProperty)", size=0)

    data = struct.pack('<i', 0)  # NumEntries=0

    archive = create_mock_archive_with_data(data)
    summary = create_mock_summary()
    export_map = []

    result = parse_map_property(tag, archive, name_map, export_map, summary)

    assert isinstance(result, MapValue)
    assert result.property_type == "MapProperty"
    assert len(result.entries) == 0


# ============================================================================
# SetProperty 测试（ADVP-03）
# ============================================================================

def test_extract_set_type_from_tag_ue5():
    """测试从 UE5 PropertyTag 提取 Set 元素类型。"""
    # UE5 格式: "SetProperty(IntProperty)"
    tag = PropertyTag(
        name="IntSet",
        type="SetProperty(IntProperty)",
        size=0
    )

    element_type = _extract_set_type_from_tag(tag)
    assert element_type == "IntProperty"


def test_extract_set_type_from_tag_ue5_with_class():
    """测试从 UE5 PropertyTag 提取 Set 元素类型（带完整类名）。"""
    # UE5 格式: "SetProperty(/Script/CoreUObject.ObjectProperty)"
    tag = PropertyTag(
        name="ObjectSet",
        type="SetProperty(/Script/CoreUObject.ObjectProperty)",
        size=0
    )

    element_type = _extract_set_type_from_tag(tag)
    assert element_type == "/Script/CoreUObject.ObjectProperty"


def test_extract_set_type_from_tag_ue4():
    """测试从 UE4 PropertyTag 提取 Set 元素类型（默认值）。"""
    # UE4 格式: 简化处理，返回默认类型
    tag = PropertyTag(
        name="OldSet",
        type="SetProperty",
        size=0
    )

    element_type = _extract_set_type_from_tag(tag)
    assert element_type == "IntProperty"


def test_set_property_empty():
    """测试空 SetProperty（NumElements=0）。"""
    name_map = []
    tag = PropertyTag(name="EmptySet", type="SetProperty(IntProperty)", size=0)

    data = struct.pack('<i', 0)  # NumElements=0

    archive = create_mock_archive_with_data(data)
    summary = create_mock_summary()
    export_map = []

    result = parse_set_property(tag, archive, name_map, export_map, summary)

    assert isinstance(result, SetValue)
    assert result.property_type == "SetProperty"
    assert len(result.elements) == 0


# ============================================================================
# EnumProperty 测试（ADVP-04）
# ============================================================================

def test_extract_enum_type_from_tag_ue5():
    """测试从 UE5 PropertyTag 提取枚举类型名。"""
    # UE5 格式: "EnumProperty(/Script/Game.EWalletState)"
    tag = PropertyTag(
        name="WalletState",
        type="EnumProperty(/Script/Game.EWalletState)",
        size=0
    )

    enum_type = _extract_enum_type_from_tag(tag)
    assert enum_type == "EWalletState"


def test_extract_enum_type_from_tag_ue5_simple():
    """测试从 UE5 PropertyTag 提取枚举类型名（无路径前缀）。"""
    # UE5 格式: "EnumProperty(SimpleEnum)"
    tag = PropertyTag(
        name="SimpleState",
        type="EnumProperty(SimpleEnum)",
        size=0
    )

    enum_type = _extract_enum_type_from_tag(tag)
    assert enum_type == "SimpleEnum"


def test_extract_enum_type_from_tag_ue4():
    """测试从 UE4 PropertyTag 提取枚举类型名（默认值）。"""
    # UE4 格式: 简化处理，返回 UnknownEnum
    tag = PropertyTag(
        name="OldEnum",
        type="EnumProperty",
        size=0
    )

    enum_type = _extract_enum_type_from_tag(tag)
    assert enum_type == "UnknownEnum"


def test_enum_property_basic():
    """测试 EnumProperty 基本解析。"""
    name_map = ["Active", "Inactive"]

    tag = PropertyTag(
        name="WalletState",
        type="EnumProperty(/Script/Game.EWalletState)",
        size=0
    )

    # 构造 Mock 数据：FName EnumValueName
    # FName: index (u32) + number (u32)
    # "Active" 在 name_map 中索引为 0
    data = (
        struct.pack('<I', 0) +  # FName index (Active)
        struct.pack('<I', 0)    # FName number
    )

    archive = create_mock_archive_with_data(data)
    summary = create_mock_summary()

    result = parse_enum_property(tag, archive, name_map, summary)

    assert isinstance(result, EnumValue)
    assert result.property_type == "EnumProperty"
    assert result.enum_type == "EWalletState"
    assert result.value_name == "EWalletState::Active"  # D-04 格式


# ============================================================================
# TextProperty 测试（ADVP-05）
# ============================================================================

def test_text_property_basic():
    """测试 TextProperty 完整结构解析（D-05）。"""
    tag = PropertyTag(name="DisplayText", type="TextProperty", size=0)

    # 构造 Mock 数据：FText 四字段
    # Flags + Namespace + Key + SourceString
    # FString 格式: length (i32) + data + null terminator
    data = (
        struct.pack('<i', 0) +  # Flags
        struct.pack('<i', 7) + b"GameUI\x00" +  # Namespace (length=7, 包含 null)
        struct.pack('<i', 12) + b"WelcomeText\x00" +  # Key (length=12)
        struct.pack('<i', 17) + b"Welcome to Game!\x00"  # SourceString (length=17)
    )

    archive = create_mock_archive_with_data(data)

    result = parse_text_property(tag, archive)

    assert isinstance(result, TextValue)
    assert result.property_type == "TextProperty"
    assert result.namespace == "GameUI"
    assert result.key == "WelcomeText"
    assert result.source_string == "Welcome to Game!"


def test_text_property_empty():
    """测试 TextProperty 空字段处理。"""
    tag = PropertyTag(name="EmptyText", type="TextProperty", size=0)

    # 空字段
    data = (
        struct.pack('<i', 0) +  # Flags
        struct.pack('<i', 0) +  # Namespace (empty)
        struct.pack('<i', 0) +  # Key (empty)
        struct.pack('<i', 0)    # SourceString (empty)
    )

    archive = create_mock_archive_with_data(data)

    result = parse_text_property(tag, archive)

    assert isinstance(result, TextValue)
    assert result.property_type == "TextProperty"
    assert result.namespace == ""
    assert result.key == ""
    assert result.source_string == ""


def test_text_property_with_flags():
    """测试 TextProperty 带 Flags。"""
    tag = PropertyTag(name="LocalizedText", type="TextProperty", size=0)

    # Flags = 1（表示本地化文本）
    # FString: length (i32) + data (length bytes, not including null)
    # According to FArchive.read_fstring: reads length, then reads length bytes (excluding null)
    data = (
        struct.pack('<i', 1) +  # Flags
        struct.pack('<i', 6) + b"UIText" +  # Namespace (length=6, data=UIText)
        struct.pack('<i', 7) + b"Label_1" +  # Key (length=7, data=Label_1)
        struct.pack('<i', 10) + b"Option One"  # SourceString (length=10, data=Option One)
    )

    archive = create_mock_archive_with_data(data)

    result = parse_text_property(tag, archive)

    assert isinstance(result, TextValue)
    assert result.property_type == "TextProperty"
    assert result.namespace == "UIText"
    assert result.key == "Label_1"
    assert result.source_string == "Option One"


# ============================================================================
# DelegateProperty 测试（ADVP-06）
# ============================================================================

def test_delegate_property_basic():
    """测试 DelegateProperty 原始引用解析（D-06）。"""
    name_map = ["OnClicked"]

    tag = PropertyTag(name="ButtonDelegate", type="DelegateProperty", size=0)

    # 构造 Mock 数据：FScriptDelegate
    # ObjectRef (FPackageIndex = int32) + FunctionName (FName)
    # FName: index (u32) + number (u32)
    data = (
        struct.pack('<i', 5) +  # ObjectRef (export reference)
        struct.pack('<I', 0) + struct.pack('<I', 0)  # FunctionName (OnClicked)
    )

    archive = create_mock_archive_with_data(data)

    result = parse_delegate_property(tag, archive, name_map)

    assert isinstance(result, DelegateValue)
    assert result.property_type == "DelegateProperty"
    assert result.object_ref == 5  # D-06b 原始值，不解析
    assert result.function_name == "OnClicked"


def test_delegate_property_import_reference():
    """测试 DelegateProperty 导入引用（负数 ObjectRef）。"""
    name_map = ["OnEvent"]

    tag = PropertyTag(name="EventDelegate", type="DelegateProperty", size=0)

    # FScriptDelegate with import reference (negative ObjectRef)
    data = (
        struct.pack('<i', -3) +  # ObjectRef (import reference)
        struct.pack('<I', 0) + struct.pack('<I', 0)  # FunctionName (OnEvent)
    )

    archive = create_mock_archive_with_data(data)

    result = parse_delegate_property(tag, archive, name_map)

    assert isinstance(result, DelegateValue)
    assert result.property_type == "DelegateProperty"
    assert result.object_ref == -3  # Import reference
    assert result.function_name == "OnEvent"


def test_delegate_property_null_reference():
    """测试 DelegateProperty 空引用（ObjectRef=0）。"""
    name_map = ["None"]

    tag = PropertyTag(name="NullDelegate", type="DelegateProperty", size=0)

    # FScriptDelegate with null reference
    data = (
        struct.pack('<i', 0) +  # ObjectRef = 0 (null)
        struct.pack('<I', 0) + struct.pack('<I', 0)  # FunctionName (None)
    )

    archive = create_mock_archive_with_data(data)

    result = parse_delegate_property(tag, archive, name_map)

    assert isinstance(result, DelegateValue)
    assert result.property_type == "DelegateProperty"
    assert result.object_ref == 0  # Null reference
    assert result.function_name == "None"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])