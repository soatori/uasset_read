"""StructProperty Transform 解析测试 — 修正大小常量和读取逻辑 (#329)"""

import struct
import pytest
from unittest.mock import MagicMock
from uasset_read.parsers.property_parser import parse_properties_from_export
from uasset_read.serializers.object_resources import ObjectExport
from uasset_read.serializers.package_summary import PackageFileSummary
from uasset_read.constants import UE5_PROPERTY_TAG_EXTENSION
import uasset_read.parsers.property_parser as pp


def test_transform_size_f32():
    """FTransform3f 大小应为 40 字节。"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # 当前值为 48，应为 40
    assert _EXPECTED_STRUCT_SIZES.get("Transform") == 40


def test_transform_size_lwc():
    """Transform LWC 映射应为 (40, 80)。"""
    from uasset_read.parsers.property_types import _LWC_TYPE_MAP
    # 当前值为 (48, 48)，应为 (40, 80)
    assert _LWC_TYPE_MAP.get("Transform") == (40, 80)


def test_transform3f_size():
    """Transform3f 紧凑格式大小应为 40 字节。"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Transform3f") == 40


def test_transform_read_f32():
    """FTransform3f 应正确读取 40 字节。"""
    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.property_types import _try_fast_path_struct

    # 构造 40 字节的 FTransform3f 数据
    # Rotation: 4 * float (16 bytes)
    # Translation: 3 * float (12 bytes)
    # Scale3D: 3 * float (12 bytes)
    data = struct.pack('<10f',
        0.0, 0.0, 0.0, 1.0,  # Rotation (x, y, z, w)
        100.0, 200.0, 300.0,  # Translation (x, y, z)
        1.0, 1.0, 1.0         # Scale3D (x, y, z)
    )
    archive = ByteArchive(data)

    # 创建 mock PropertyTag
    tag = MagicMock()
    tag.size = 40
    tag.struct_type = "Transform"

    result = _try_fast_path_struct("Transform", tag, archive, name_map=[])

    assert result is not None
    assert result.struct_type == "Transform"
    assert result.fields["Translation"]["X"] == 100.0
    assert result.fields["Translation"]["Y"] == 200.0
    assert result.fields["Translation"]["Z"] == 300.0
    assert result.fields["Rotation"]["W"] == 1.0
    assert result.fields["Scale3D"]["X"] == 1.0
    assert result.fields["Scale3D"]["Y"] == 1.0
    assert result.fields["Scale3D"]["Z"] == 1.0


def test_transform_read_f64():
    """FTransform3d 应正确读取 80 字节。"""
    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.property_types import _try_fast_path_struct

    # 构造 80 字节的 FTransform3d 数据
    # Rotation: 4 * double (32 bytes)
    # Translation: 3 * double (24 bytes)
    # Scale3D: 3 * double (24 bytes)
    data = struct.pack('<10d',
        0.0, 0.0, 0.0, 1.0,  # Rotation (x, y, z, w)
        100.0, 200.0, 300.0,  # Translation (x, y, z)
        1.0, 1.0, 1.0         # Scale3D (x, y, z)
    )
    archive = ByteArchive(data)

    # 创建 mock PropertyTag
    tag = MagicMock()
    tag.size = 80
    tag.struct_type = "Transform"

    result = _try_fast_path_struct("Transform", tag, archive, name_map=[])

    assert result is not None
    assert result.struct_type == "Transform"
    assert result.fields["Translation"]["X"] == 100.0
    assert result.fields["Translation"]["Y"] == 200.0
    assert result.fields["Translation"]["Z"] == 300.0
    assert result.fields["Rotation"]["W"] == 1.0
    assert result.fields["Scale3D"]["X"] == 1.0
    assert result.fields["Scale3D"]["Y"] == 1.0
    assert result.fields["Scale3D"]["Z"] == 1.0


def test_transform_read_unexpected_size():
    """非标准大小的 Transform 在 tolerant 模式下应跳过并返回警告。"""
    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.property_types import _try_fast_path_struct

    # 构造 52 字节的数据（非标准大小）
    data = struct.pack('<10f',
        1.0, 2.0, 3.0, 4.0,   # Rotation
        10.0, 20.0, 30.0,     # Translation
        100.0, 200.0, 300.0   # Scale3D
    )
    archive = ByteArchive(data, tolerant=True)  # 设置为 tolerant 模式

    # 创建 mock PropertyTag
    tag = MagicMock()
    tag.size = 52
    tag.struct_type = "Transform"

    # tolerant 模式：返回带 _warning 的 StructValue
    result = _try_fast_path_struct("Transform", tag, archive, name_map=[])
    assert result is not None
    assert result.struct_type == "Transform"
    assert "_warning" in result.fields
    assert "52" in result.fields["_warning"]


def test_transform_read_unexpected_size_strict():
    """非标准大小的 Transform 在 strict 模式下应抛出 ParseError。"""
    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.property_types import _try_fast_path_struct
    from uasset_read.exceptions import ParseError

    # 构造 52 字节的数据（非标准大小）
    data = struct.pack('<10f',
        1.0, 2.0, 3.0, 4.0,   # Rotation
        10.0, 20.0, 30.0,     # Translation
        100.0, 200.0, 300.0   # Scale3D
    )
    archive = ByteArchive(data)
    archive._tolerant = False  # 设置为 strict 模式

    tag = MagicMock()
    tag.size = 52
    tag.struct_type = "Transform"

    with pytest.raises(ParseError, match="unexpected size 52"):
        _try_fast_path_struct("Transform", tag, archive, name_map=[])


def test_transform_serialization_order():
    """验证 Transform 序列化顺序：Rotation → Translation → Scale3D。"""
    from uasset_read.archive import ByteArchive
    from uasset_read.parsers.property_types import _try_fast_path_struct

    # 使用明确可区分的值来验证顺序
    # Rotation: (1.0, 2.0, 3.0, 4.0) = 16 bytes
    # Translation: (10.0, 20.0, 30.0) = 12 bytes
    # Scale3D: (100.0, 200.0, 300.0) = 12 bytes
    data = struct.pack('<10f',
        1.0, 2.0, 3.0, 4.0,   # Rotation
        10.0, 20.0, 30.0,     # Translation
        100.0, 200.0, 300.0   # Scale3D
    )
    archive = ByteArchive(data)

    tag = MagicMock()
    tag.size = 40
    tag.struct_type = "Transform"

    result = _try_fast_path_struct("Transform", tag, archive, name_map=[])

    assert result.fields["Rotation"]["X"] == 1.0
    assert result.fields["Rotation"]["W"] == 4.0
    assert result.fields["Translation"]["X"] == 10.0
    assert result.fields["Translation"]["Z"] == 30.0
    assert result.fields["Scale3D"]["X"] == 100.0
    assert result.fields["Scale3D"]["Z"] == 300.0


# --- SerializationControlExtensions 未知位处理测试 (#339) ---


def _make_archive(control_byte: int, tell_first: int = 0, tell_loop: int = 200):
    """构造模拟 archive，控制 SerializationControlExtensions 和属性循环。"""
    archive = MagicMock()
    archive.read_u8.return_value = control_byte
    # tell() 第一次返回 tell_first（control_offset），后续返回 tell_loop（>= property_end 触发 break）
    archive.tell.side_effect = [tell_first] + [tell_loop] * 20
    archive._file_size = tell_loop
    archive._tolerant = True
    return archive


def _make_export(transforms=None):
    """构造模拟 export。"""
    export = MagicMock()
    export.serial_offset = 0
    export.serial_size = 100
    export.object_name = "TestExport"
    export.transforms = transforms if transforms is not None else {}
    return export


def _make_summary():
    """构造模拟 summary。"""
    summary = MagicMock()
    summary.file_version_ue5 = UE5_PROPERTY_TAG_EXTENSION
    summary.package_flags = 0
    return summary


def test_serialization_control_unknown_bits():
    """SerializationControlExtensions 未知位应被记录但不影响解析。"""
    # 0xB8 = 10111000 (bits 0x08, 0x10, 0x20, 0x80)
    control_byte = 0xB8

    archive = _make_archive(control_byte)
    summary = _make_summary()
    export = _make_export()

    # 应该不抛异常
    _result = parse_properties_from_export(
        export, archive, summary, [], [], tolerant=True
    )

    # 验证 serialization_control 被记录
    assert "serialization_control" in export.transforms
    assert export.transforms["serialization_control"]["value"] == control_byte


def test_serialization_control_diagnostic_recorded():
    """未知位应在 archive 上记录诊断信息。"""
    control_byte = 0x04  # 单个未知位

    archive = _make_archive(control_byte, tell_first=42)
    summary = _make_summary()
    export = _make_export()

    parse_properties_from_export(
        export, archive, summary, [], [], tolerant=True
    )

    # 验证 _record_diagnostic 被调用（包含未知位信息）
    archive._record_diagnostic.assert_called_once()
    call_kwargs = archive._record_diagnostic.call_args[1]
    assert call_kwargs["module"] == "property_parser"
    assert call_kwargs["field"] == "serialization_control"
    assert "0x04" in call_kwargs["error"]


def test_serialization_control_bit_names_in_diagnostic():
    """多个未知位应有对应的位名诊断。"""
    # 0x08 | 0x10 = 0x18
    control_byte = 0x18

    archive = _make_archive(control_byte, tell_first=10)
    summary = _make_summary()
    export = _make_export()

    parse_properties_from_export(
        export, archive, summary, [], [], tolerant=True
    )

    archive._record_diagnostic.assert_called_once()
    error_msg = archive._record_diagnostic.call_args[1]["error"]
    assert "Unknown_Bit3" in error_msg
    assert "Unknown_Bit4" in error_msg


def test_serialization_control_no_unknown_bits():
    """已知位 0x01|0x02 不应记录诊断。"""
    control_byte = 0x03  # 仅已知位

    archive = _make_archive(control_byte)
    summary = _make_summary()
    export = _make_export()

    parse_properties_from_export(
        export, archive, summary, [], [], tolerant=True
    )

    # 无未知位时不应调用 _record_diagnostic
    archive._record_diagnostic.assert_not_called()

    # transforms 仍应记录
    assert "serialization_control" in export.transforms
    sc = export.transforms["serialization_control"]
    assert sc["value"] == 0x03
    assert sc["unknown_bits"] == 0


def test_serialization_control_transforms_fields():
    """transforms 中应包含 value, overridden_operation, unknown_bits, offset。"""
    control_byte = 0x02  # OverridableSerializationInformation
    overridden_byte = 0x01

    archive = MagicMock()
    archive.read_u8.side_effect = [control_byte, overridden_byte]
    archive.tell.side_effect = [5, 200, 200, 200, 200]
    archive._file_size = 200
    archive._tolerant = True

    summary = _make_summary()
    export = _make_export()

    parse_properties_from_export(
        export, archive, summary, [], [], tolerant=True
    )

    sc = export.transforms["serialization_control"]
    assert sc["value"] == 0x02
    assert sc["overridden_operation"] == 0x01
    assert sc["unknown_bits"] == 0
    assert sc["offset"] == 5


# --- 测试 _TYPE_HANDLER_MAP 缓存机制（parsers/property_parser.py） ---


class TestGetParseFunctionsCache:
    """_get_parse_functions() 模块级缓存行为。"""

    def test_returns_dict_with_all_known_property_types(self):
        """首次调用返回包含所有已知属性类型的映射表。"""
        result = pp._get_parse_functions()
        expected_keys = [
            "BoolProperty", "IntProperty", "Int64Property", "Int16Property",
            "Int8Property", "ByteProperty", "UInt16Property", "UInt32Property",
            "UInt64Property", "FloatProperty", "DoubleProperty", "StrProperty",
            "NameProperty", "ObjectProperty", "SoftObjectProperty", "ArrayProperty",
            "StructProperty", "MapProperty", "SetProperty", "EnumProperty",
            "TextProperty", "DelegateProperty", "Utf8StrProperty",
            "WeakObjectProperty", "LazyObjectProperty", "ClassProperty",
            "SoftClassProperty", "AssetObjectProperty", "AssetClassProperty",
            "MulticastDelegateProperty", "MulticastInlineDelegateProperty",
            "MulticastSparseDelegateProperty", "InterfaceProperty",
            "FieldPathProperty", "OptionalProperty", "VerseStringProperty",
            "VerseClassProperty", "VerseFunctionProperty", "VerseDynamicProperty",
            "VerseCellProperty", "VerseValueProperty", "AnsiStrProperty",
            "GuidProperty",
        ]
        assert isinstance(result, dict)
        for key in expected_keys:
            assert key in result, f"缺少已知属性类型 key: {key}"

    def test_all_values_are_callable(self):
        """映射表中每个 value 都是 callable。"""
        result = pp._get_parse_functions()
        for key, handler in result.items():
            assert callable(handler), f"{key} 的值不可调用: {handler!r}"

    def test_second_call_returns_same_object(self):
        """第二次调用返回同一对象（id 相同），验证缓存生效。"""
        first = pp._get_parse_functions()
        second = pp._get_parse_functions()
        assert first is second
        assert id(first) == id(second)
