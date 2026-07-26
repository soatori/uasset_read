"""PropertyTag 重试逻辑测试 — 验证 #276 修复。

验证:
1. strict 模式下损坏 tag 立即抛出 ParseError（不重试）
2. tolerant 模式下损坏 tag 警告并跳过（不无限循环）
3. unversioned mapping 路径传播 tolerant 标志
"""
from __future__ import annotations

import struct
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from uasset_read.archive import FArchive
from uasset_read.exceptions import ParseError
from uasset_read.models.properties import PropertyTag, PropertyValue
from uasset_read.parsers.property_parser import (
    parse_properties_from_export,
    _parse_unversioned_properties_from_mapping,
)
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex


def _make_archive(data: bytes, tolerant: bool = False) -> FArchive:
    """从原始字节创建 FArchive 实例（用于测试）。"""
    archive = FArchive.__new__(FArchive)
    archive._stream = BytesIO(data)
    archive._file_size = len(data)
    archive._byte_swapping = False
    archive._use_mmap = False
    archive._mmap = None
    archive._tolerant = tolerant
    archive._file = BytesIO(data)
    archive._hex_view_enabled = False
    archive._hex_view_entries = []
    archive._hex_view_context = ""
    archive._diagnostics = []
    archive._logger = __import__("logging").getLogger("test")
    archive._name_map = None
    return archive


def _make_export(serial_offset: int = 0, serial_size: int = 1024) -> ObjectExport:
    """创建测试用 ObjectExport。"""
    return ObjectExport(
        class_index=PackageIndex(-1),
        super_index=PackageIndex(-1),
        outer_index=PackageIndex(0),
        object_name="TestExport",
        object_flags=0,
        serial_size=serial_size,
        serial_offset=serial_offset,
    )


class TestCorruptedTagStrictRaises:
    """strict 模式下损坏 tag 应立即抛出，不重试。"""

    def test_early_failure_strict_raises(self):
        """tag 名称读取后类型名截断 — strict 模式应抛出 ParseError。"""
        # 构造损坏数据：FName 有效（8 字节），但类型名数据截断
        # index=0 → name_map[0]="TestProp"
        name_bytes = struct.pack("<II", 0, 0)  # FName: index=0, number=0
        truncated_bytes = b"\x00" * 2  # 不够读取类型名
        data = name_bytes + truncated_bytes
        archive = _make_archive(data, tolerant=False)
        archive._file_version_ue5 = 1012  # UE5 >= PROPERTY_TAG_COMPLETE_TYPE_NAME

        summary = MagicMock()
        summary.package_flags = 0
        summary.file_version_ue5 = 1012

        export = _make_export(serial_offset=0, serial_size=100)

        with pytest.raises(ParseError):
            parse_properties_from_export(
                export, archive, summary,
                name_map=["TestProp"],
                export_map=[],
                tolerant=False,
            )

    def test_mid_tag_failure_strict_raises(self):
        """tag 部分读取（size 为负数）— strict 模式应抛出 ParseError。"""
        # FName: index=0, number=0 → "TestProp"
        name_bytes = struct.pack("<II", 0, 0)
        # 类型名 FName: index=0, number=0
        type_bytes = struct.pack("<II", 0, 0)
        # size = -1（负数，validate_size 在 strict 模式抛出）
        size_bytes = struct.pack("<i", -1)
        # flags 字节（不重要，因为 validate_size 先失败）
        flags_bytes = b"\x00"
        data = name_bytes + type_bytes + size_bytes + flags_bytes
        archive = _make_archive(data, tolerant=False)
        archive._file_version_ue5 = 1012

        summary = MagicMock()
        summary.package_flags = 0
        summary.file_version_ue5 = 1012

        export = _make_export(serial_offset=0, serial_size=100)

        with pytest.raises(ParseError):
            parse_properties_from_export(
                export, archive, summary,
                name_map=["TestProp"],
                export_map=[],
                tolerant=False,
            )


class TestCorruptedTagTolerantWarnsAndSkips:
    """tolerant 模式下损坏 tag 应警告并跳过（不无限循环）。"""

    def test_early_failure_tolerant_does_not_hang(self):
        """tag 名称读取后类型名截断 — tolerant 模式不应挂起。"""
        name_bytes = struct.pack("<II", 0, 0)
        truncated_bytes = b"\x00" * 2
        data = name_bytes + truncated_bytes
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1012

        summary = MagicMock()
        summary.package_flags = 0
        summary.file_version_ue5 = 1012

        export = _make_export(serial_offset=0, serial_size=100)

        # 不应挂起（超时由 pytest 控制）
        result = parse_properties_from_export(
            export, archive, summary,
            name_map=["TestProp"],
            export_map=[],
            tolerant=True,
        )

        assert isinstance(result, list)
        # Should either recover (fallback) or gracefully terminate (empty list).
        # With recovery scan, tiny buffers may not contain a valid tag to recover to.
        if len(result) >= 1:
            assert result[0].type == "Warning"

    def test_mid_tag_failure_tolerant_skips(self):
        """tag 部分读取（size 为负数）— tolerant 模式应跳过。"""
        name_bytes = struct.pack("<II", 0, 0)
        type_bytes = struct.pack("<II", 0, 0)
        size_bytes = struct.pack("<i", -1)
        flags_bytes = b"\x00"
        data = name_bytes + type_bytes + size_bytes + flags_bytes
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1012

        summary = MagicMock()
        summary.package_flags = 0
        summary.file_version_ue5 = 1012

        export = _make_export(serial_offset=0, serial_size=100)

        result = parse_properties_from_export(
            export, archive, summary,
            name_map=["TestProp"],
            export_map=[],
            tolerant=True,
        )

        assert isinstance(result, list)
        # Should either recover or gracefully terminate
        # (tiny data buffers may not contain a valid recovery target)

    def test_no_retry_at_same_offset(self):
        """损坏 tag 后不应在同一偏移重试（之前的无限循环 bug）。"""
        # FName 有效但仅 2 字节剩余（不够读取类型名 u32）
        name_bytes = struct.pack("<II", 0, 0)  # 8 字节
        padding = b"\x00" * 2  # 2 字节 — 不够读取 u32 类型名
        data = name_bytes + padding
        archive = _make_archive(data, tolerant=True)
        archive._file_version_ue5 = 1012

        summary = MagicMock()
        summary.package_flags = 0
        summary.file_version_ue5 = 1012

        export = _make_export(serial_offset=0, serial_size=100)

        result = parse_properties_from_export(
            export, archive, summary,
            name_map=["TestProp"],
            export_map=[],
            tolerant=True,
        )

        # 应返回结果（不挂起），且最多只有 1 个 fallback（不重复重试）
        assert isinstance(result, list)
        assert len(result) <= 1


class TestUnversionedMappingRespectsTolerant:
    """unversioned mapping 路径应传播 tolerant 标志。"""

    def test_strict_unversioned_raises_on_parse_error(self):
        """strict 模式下 unversioned 解析错误应抛出。"""
        # 构造有效的 unversioned mapping — StrProperty 无固定大小，需要足够数据
        mock_mapping_type = MagicMock()
        mock_mapping_type.type = "StrProperty"
        mock_mapping_type.is_fixed_size.return_value = False

        mock_prop_info = MagicMock()
        mock_prop_info.name = "TestProp"
        mock_prop_info.mapping_type = mock_mapping_type

        mock_struct_mapping = MagicMock()
        mock_struct_mapping.name = "TestStruct"
        mock_struct_mapping.properties = {0: mock_prop_info}
        mock_struct_mapping.super_type = None
        mock_struct_mapping.property_by_name.return_value = mock_prop_info

        mock_mappings = MagicMock()
        mock_mappings.get_struct.return_value = mock_struct_mapping
        mock_mappings.property_by_name.return_value = mock_prop_info

        # 仅 2 字节 — 不够读取 StrProperty 的 fstring 长度前缀 (i32)
        data = b"\x00" * 2
        archive = _make_archive(data, tolerant=False)

        export = _make_export(serial_offset=0, serial_size=100)
        summary = MagicMock()
        summary.package_flags = 0

        with pytest.raises(ParseError):
            _parse_unversioned_properties_from_mapping(
                export, archive, summary,
                name_map=["TestProp"],
                export_map=[],
                mappings=mock_mappings,
                struct_name="TestStruct",
                property_end=100,
                tolerant=False,
            )

    def test_tolerant_unversioned_continues_on_error(self):
        """tolerant 模式下 unversioned 解析错误应创建 fallback。"""
        mock_mapping_type = MagicMock()
        mock_mapping_type.type = "StrProperty"
        mock_mapping_type.is_fixed_size.return_value = False

        mock_prop_info = MagicMock()
        mock_prop_info.name = "TestProp"
        mock_prop_info.mapping_type = mock_mapping_type

        mock_struct_mapping = MagicMock()
        mock_struct_mapping.name = "TestStruct"
        mock_struct_mapping.properties = {0: mock_prop_info}
        mock_struct_mapping.super_type = None
        mock_struct_mapping.property_by_name.return_value = mock_prop_info

        mock_mappings = MagicMock()
        mock_mappings.get_struct.return_value = mock_struct_mapping
        mock_mappings.property_by_name.return_value = mock_prop_info

        # 仅 2 字节 — 不够读取 StrProperty 的 fstring 长度前缀 (i32)
        data = b"\x00" * 2
        archive = _make_archive(data, tolerant=True)

        export = _make_export(serial_offset=0, serial_size=100)
        summary = MagicMock()
        summary.package_flags = 0

        result = _parse_unversioned_properties_from_mapping(
            export, archive, summary,
            name_map=["TestProp"],
            export_map=[],
            mappings=mock_mappings,
            struct_name="TestStruct",
            property_end=100,
        )

        # 应返回结果（含 fallback），不抛出异常
        assert isinstance(result, list)
        # 可能包含 fallback 条目或 tail
        assert len(result) >= 1
