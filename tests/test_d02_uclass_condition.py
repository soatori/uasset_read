"""tests/test_d02_uclass_condition.py — D-02 SerializationControlExtensions UClass 条件测试。

Issue #55: 验证 D-02 字节仅在 UClass 派生类 export 中被读取。
UE 源码 Class.cpp:1624-1628: const bool bIsUClass = IsA<UClass>();
非 UClass 的 UStruct（Function、EdGraph 等）不应消费 D-02 字节。
"""
import struct
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.constants import UE5_PROPERTY_TAG_EXTENSION
from uasset_read.parsers.property_parser import parse_properties_from_export
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex


def _make_export(object_name="TestExport", serial_offset=0, serial_size=100):
    """构造 mock ObjectExport。"""
    export = MagicMock(spec=ObjectExport)
    export.object_name = object_name
    export.serial_offset = serial_offset
    export.serial_size = serial_size
    export.script_serialization_start_offset = 0
    export.script_serialization_end_offset = 0
    export.class_index = PackageIndex(0)
    export.has_script_serialization = False
    return export


def _make_summary(file_version_ue5=None):
    """构造 mock PackageFileSummary。"""
    summary = MagicMock()
    summary.file_version_ue5 = file_version_ue5 if file_version_ue5 is not None else UE5_PROPERTY_TAG_EXTENSION
    summary.package_flags = 0
    summary.legacy_file_version = -7
    return summary


def _make_archive_with_data(data: bytes, start_pos: int = 0):
    """构造 mock FArchive。"""
    archive = MagicMock()
    archive.tell.return_value = start_pos
    archive.seek = MagicMock()
    byte_values = list(data) if data else [0]
    archive.read_u8 = MagicMock(side_effect=byte_values)
    archive.read_i32 = MagicMock(return_value=0)
    archive.read_name = MagicMock(return_value="None")
    archive.total_size.return_value = len(data) + 10000
    return archive


# resolve_class_name 在 property_parser.py 中通过函数内 import 使用，
# 需要 patch 到实际定义模块
_RESOLVE_PATCH = "uasset_read.serializers.object_resources.resolve_class_name"


class TestD02UclassCondition:
    """D-02 SerializationControlExtensions 仅在 UClass 派生类中读取。"""

    def test_uclass_derived_reads_d02(self):
        """UClass 派生类（BlueprintGeneratedClass）应读取 D-02 字节。"""
        none_fname = struct.pack("<ii", 0, 0)  # FName Index=0, Number=0 → "None"
        data = bytes([0x00]) + none_fname  # D-02 = 0x00 (NoExtension)
        archive = _make_archive_with_data(data)
        export = _make_export()
        summary = _make_summary()

        with patch(_RESOLVE_PATCH, return_value="BlueprintGeneratedClass"):
            parse_properties_from_export(
                export=export, archive=archive, summary=summary,
                name_map=["None"], export_map=[], import_map=[MagicMock()],
            )

        # 应调用 read_u8 读取 D-02 字节
        archive.read_u8.assert_called()

    def test_non_uclass_skips_d02(self):
        """非 UClass 类（Function）不应读取 D-02 字节。"""
        none_fname = struct.pack("<ii", 0, 0)
        data = none_fname  # 仅 "None" 终止标记（不含 D-02 字节）
        archive = _make_archive_with_data(data)
        export = _make_export()
        summary = _make_summary()

        with patch(_RESOLVE_PATCH, return_value="Function"):
            parse_properties_from_export(
                export=export, archive=archive, summary=summary,
                name_map=["None"], export_map=[], import_map=[MagicMock()],
            )

        archive.read_u8.assert_not_called()

    def test_unknown_class_skips_d02(self):
        """类名未知（resolve 返回 None）时不应读取 D-02 字节（降级处理）。"""
        none_fname = struct.pack("<ii", 0, 0)
        data = none_fname
        archive = _make_archive_with_data(data)
        export = _make_export()
        summary = _make_summary()

        with patch(_RESOLVE_PATCH, return_value=None):
            parse_properties_from_export(
                export=export, archive=archive, summary=summary,
                name_map=["None"], export_map=[], import_map=[MagicMock()],
            )

        archive.read_u8.assert_not_called()

    def test_uclass_with_overridable_reads_both_bytes(self):
        """UClass 派生类且 D-02=0x02 时应读取两个字节（control + operation）。"""
        none_fname = struct.pack("<ii", 0, 0)
        data = bytes([0x02, 0x01]) + none_fname  # D-02=0x02, OverriddenOperation=0x01
        archive = _make_archive_with_data(data)
        export = _make_export()
        summary = _make_summary()

        with patch(_RESOLVE_PATCH, return_value="Class"):
            parse_properties_from_export(
                export=export, archive=archive, summary=summary,
                name_map=["None"], export_map=[], import_map=[MagicMock()],
            )

        # read_u8 应调用 2 次：D-02 字节 + OverriddenOperation
        assert archive.read_u8.call_count == 2

    def test_no_import_map_skips_d02(self):
        """import_map 为 None 时 class_name 无法解析，不应读取 D-02 字节。"""
        none_fname = struct.pack("<ii", 0, 0)
        data = none_fname
        archive = _make_archive_with_data(data)
        export = _make_export()
        summary = _make_summary()

        parse_properties_from_export(
            export=export, archive=archive, summary=summary,
            name_map=["None"], export_map=[], import_map=None,
        )

        archive.read_u8.assert_not_called()

    def test_old_ue_version_skips_d02(self):
        """UE5 < 1011 版本不应读取 D-02 字节。"""
        none_fname = struct.pack("<ii", 0, 0)
        data = bytes([0x00]) + none_fname
        archive = _make_archive_with_data(data)
        export = _make_export()
        summary = _make_summary(file_version_ue5=1010)  # < 1011

        with patch(_RESOLVE_PATCH, return_value="BlueprintGeneratedClass"):
            parse_properties_from_export(
                export=export, archive=archive, summary=summary,
                name_map=["None"], export_map=[], import_map=[MagicMock()],
            )

        archive.read_u8.assert_not_called()

    def test_widget_bpgc_reads_d02(self):
        """WidgetBlueprintGeneratedClass 是 UClass 派生类，应读取 D-02。"""
        none_fname = struct.pack("<ii", 0, 0)
        data = bytes([0x00]) + none_fname
        archive = _make_archive_with_data(data)
        export = _make_export()
        summary = _make_summary()

        with patch(_RESOLVE_PATCH, return_value="WidgetBlueprintGeneratedClass"):
            parse_properties_from_export(
                export=export, archive=archive, summary=summary,
                name_map=["None"], export_map=[], import_map=[MagicMock()],
            )

        archive.read_u8.assert_called()

    def test_edgraph_skips_d02(self):
        """EdGraph 是 UStruct 子类，不应读取 D-02。"""
        none_fname = struct.pack("<ii", 0, 0)
        data = none_fname
        archive = _make_archive_with_data(data)
        export = _make_export()
        summary = _make_summary()

        with patch(_RESOLVE_PATCH, return_value="EdGraph"):
            parse_properties_from_export(
                export=export, archive=archive, summary=summary,
                name_map=["None"], export_map=[], import_map=[MagicMock()],
            )

        archive.read_u8.assert_not_called()

    def test_user_defined_struct_skips_d02(self):
        """UserDefinedStruct 是 UStruct 子类，不应读取 D-02。"""
        none_fname = struct.pack("<ii", 0, 0)
        data = none_fname
        archive = _make_archive_with_data(data)
        export = _make_export()
        summary = _make_summary()

        with patch(_RESOLVE_PATCH, return_value="UserDefinedStruct"):
            parse_properties_from_export(
                export=export, archive=archive, summary=summary,
                name_map=["None"], export_map=[], import_map=[MagicMock()],
            )

        archive.read_u8.assert_not_called()

    def test_uclass_d02_transforms_stored(self):
        """UClass 派生类的 D-02 数据应存储到 export.transforms 中。"""
        none_fname = struct.pack("<ii", 0, 0)
        data = bytes([0x00]) + none_fname
        archive = _make_archive_with_data(data)
        export = _make_export()
        summary = _make_summary()

        with patch(_RESOLVE_PATCH, return_value="BlueprintGeneratedClass"):
            parse_properties_from_export(
                export=export, archive=archive, summary=summary,
                name_map=["None"], export_map=[], import_map=[MagicMock()],
            )

        assert hasattr(export, "transforms")
        assert "serialization_control" in export.transforms
        ctrl = export.transforms["serialization_control"]
        assert ctrl["value"] == 0x00
        assert ctrl["overridden_operation"] is None
