"""SerializationControlExtensions 未知位处理测试 (#339)"""
import pytest
from unittest.mock import MagicMock
from uasset_read.parsers.property_parser import parse_properties_from_export
from uasset_read.serializers.object_resources import ObjectExport
from uasset_read.serializers.package_summary import PackageFileSummary
from uasset_read.constants import UE5_PROPERTY_TAG_EXTENSION


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
