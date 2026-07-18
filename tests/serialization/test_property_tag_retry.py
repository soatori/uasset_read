"""PropertyTag 解析与重试逻辑测试。

合并来源:
- test_property_tag_retry.py — 重试逻辑验证 (#276)
- test_property_tag_legacy_struct_type.py — legacy path struct_type ordering (#404)
"""
from __future__ import annotations

import struct
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.archive import FArchive
from uasset_read.exceptions import ParseError
from uasset_read.models.properties import PropertyTag, PropertyValue
from uasset_read.parsers.property_parser import (
    parse_properties_from_export,
    _parse_unversioned_properties_from_mapping,
)
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex
from uasset_read.serializers.property_tags import read_property_tag


def _make_archive(data: bytes, tolerant: bool = False, file_version_ue5: int = 1000) -> FArchive:
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
    archive._file_version_ue5 = file_version_ue5
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
        # 应包含 fallback 条目
        assert len(result) >= 1
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
        assert len(result) >= 1

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


# ---------------------------------------------------------------------------
# legacy path struct_type ordering (#404) — 原 test_property_tag_legacy_struct_type.py
# ---------------------------------------------------------------------------


def _build_legacy_struct_property_tag(
    name_index: int = 0,
    type_index: int = 0,
    size: int = 100,
    struct_name: str = "TestStruct",
    name_map: list[str] | None = None,
) -> bytes:
    """构建 legacy path (file_version_ue5 < 1012) 的 StructProperty tag 二进制数据。

    Legacy 格式:
    - Name: FName (index=4 bytes + number=4 bytes)
    - Type: FName (index=4 bytes + number=4 bytes)
    - Size: int32
    - ArrayIndex: int32 (旧格式始终存在)
    - Type.number == 0 时的类型特定字段:
      - StructProperty: StructName (FName) + StructGuid (FGuid, 16 bytes)
    - HasPropertyGuid: uint8
    - (可选) PropertyGuid: 16 bytes
    """
    if name_map is None:
        name_map = ["TestProp", "StructProperty", struct_name]

    # Name: FName (index, number)
    name_bytes = struct.pack("<II", name_index, 0)
    # Type: FName (index, number) — StructProperty
    type_bytes = struct.pack("<II", type_index, 0)  # number=0 触发类型特定字段
    # Size
    size_bytes = struct.pack("<i", size)
    # ArrayIndex (旧格式始终存在)
    array_index_bytes = struct.pack("<i", 0)
    # StructName: FName (index, number)
    struct_name_index = 2  # name_map[2] = struct_name
    struct_name_bytes = struct.pack("<II", struct_name_index, 0)
    # StructGuid: FGuid (16 bytes)
    struct_guid_bytes = b"\x00" * 16
    # HasPropertyGuid: uint8 (0 = no)
    has_guid_bytes = b"\x00"

    return (
        name_bytes
        + type_bytes
        + size_bytes
        + array_index_bytes
        + struct_name_bytes
        + struct_guid_bytes
        + has_guid_bytes
    )


def _build_legacy_struct_property_tag_large_size(
    name_map: list[str] | None = None,
    size: int = 500 * 1024 * 1024,  # 500MB — 超过默认阈值
) -> tuple[bytes, list[str]]:
    """构建带有大 size 的 legacy StructProperty tag，用于测试动态阈值。

    Returns:
        (binary_data, name_map)
    """
    if name_map is None:
        name_map = ["MyProp", "StructProperty", "LargeStruct"]
    return _build_legacy_struct_property_tag(
        name_index=0,
        type_index=1,  # StructProperty
        size=size,
        struct_name="LargeStruct",
        name_map=name_map,
    ), name_map


class TestLegacyPathStructTypeOrdering:
    """验证 legacy path 中 validate_size 在 struct_type 赋值后调用。"""

    def test_struct_type_available_for_validate_size(self):
        """legacy path 的 StructProperty 应在 validate_size 调用前设置 struct_type。"""
        # 使用 tolerant 模式避免 size 超过 remaining 的异常，专注测试 struct_type 传递
        data, name_map = _build_legacy_struct_property_tag_large_size(size=1000)
        archive = _make_archive(data, file_version_ue5=1000)
        archive._tolerant = True  # 容错模式，size 超限不会抛异常

        # Mock validate_size 来验证调用参数
        with patch.object(archive, 'validate_size', wraps=archive.validate_size) as mock_validate:
            tag = read_property_tag(archive, name_map, tolerant=True)

            # 验证 validate_size 被调用
            assert mock_validate.called
            # 验证 property_type 参数是 struct_type 而非 tag.type
            call_kwargs = mock_validate.call_args
            property_type = call_kwargs.kwargs.get('property_type') or call_kwargs[1].get('property_type')
            # 在修复后，property_type 应该是 "LargeStruct" (struct_type)
            # 在修复前，property_type 会是 "None" 或 tag.type
            assert property_type == "LargeStruct", (
                f"Expected property_type='LargeStruct', got '{property_type}'. "
                "validate_size was called before struct_type was assigned."
            )

    def test_struct_type_set_before_validate_size(self):
        """验证 tag.struct_type 在 validate_size 被调用前已设置。"""
        data, name_map = _build_legacy_struct_property_tag_large_size(size=100)
        archive = _make_archive(data, file_version_ue5=1000)
        archive._tolerant = True  # 容错模式，size 超限不会抛异常

        # 使用 side_effect 来捕获 validate_size 调用时的 tag 状态
        validate_size_called = []
        original_validate_size = archive.validate_size

        def capture_validate_size(*args, **kwargs):
            # 捕获调用时的 archive 位置和参数
            validate_size_called.append({
                'args': args,
                'kwargs': kwargs,
                'pos': archive.tell(),
            })
            return original_validate_size(*args, **kwargs)

        with patch.object(archive, 'validate_size', side_effect=capture_validate_size):
            tag = read_property_tag(archive, name_map, tolerant=True)

            # 验证 tag.struct_type 已设置
            assert tag.struct_type == "LargeStruct", (
                f"Expected tag.struct_type='LargeStruct', got '{tag.struct_type}'"
            )

            # 验证 validate_size 被调用
            assert len(validate_size_called) == 1

    def test_non_struct_property_unchanged(self):
        """非 StructProperty 类型在 legacy path 中行为不变。"""
        name_map = ["BoolProp", "BoolProperty"]
        # BoolProperty: FName (name) + FName (type) + Size + ArrayIndex + BoolVal + HasPropertyGuid
        name_bytes = struct.pack("<II", 0, 0)  # BoolProp
        type_bytes = struct.pack("<II", 1, 0)  # BoolProperty
        size_bytes = struct.pack("<i", 1)
        array_index_bytes = struct.pack("<i", 0)
        bool_val_bytes = b"\x01"  # BoolVal = true
        has_guid_bytes = b"\x00"

        data = (
            name_bytes
            + type_bytes
            + size_bytes
            + array_index_bytes
            + bool_val_bytes
            + has_guid_bytes
        )
        archive = _make_archive(data, file_version_ue5=1000)

        with patch.object(archive, 'validate_size', wraps=archive.validate_size) as mock_validate:
            tag = read_property_tag(archive, name_map, tolerant=False)

            assert tag.type == "BoolProperty"
            assert tag.bool_val == 1
            # 验证 validate_size 被调用，property_type 是 tag.type
            call_kwargs = mock_validate.call_args
            property_type = call_kwargs.kwargs.get('property_type') or call_kwargs[1].get('property_type')
            assert property_type == "BoolProperty"


class TestLegacyPathStructPropertyLargeSize:
    """验证 legacy path 中大 StructProperty 的动态阈值生效。"""

    def test_large_struct_property_with_correct_struct_type(self):
        """大 StructProperty 应使用 struct_type 作为 property_type。"""
        # 构建 500MB size 的 StructProperty
        data, name_map = _build_legacy_struct_property_tag_large_size(
            size=500 * 1024 * 1024  # 500MB
        )
        archive = _make_archive(data, file_version_ue5=1000)

        # Mock validate_size 来验证参数，不实际执行验证
        with patch.object(archive, 'validate_size') as mock_validate:
            tag = read_property_tag(archive, name_map, tolerant=False)

            # 验证 tag 结构正确
            assert tag.type == "StructProperty"
            assert tag.struct_type == "LargeStruct"
            assert tag.size == 500 * 1024 * 1024

            # 验证 validate_size 被调用，且 property_type 是 struct_type
            mock_validate.assert_called_once()
            call_kwargs = mock_validate.call_args
            property_type = call_kwargs.kwargs.get('property_type') or call_kwargs[1].get('property_type')
            assert property_type == "LargeStruct"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
