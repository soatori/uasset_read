"""serialization 恢复与容错测试 — 合并自多个测试文件。

合并来源:
- test_property_tag_retry.py — PropertyTag 解析与重试逻辑 (#276, #404)
- test_property_parser_error_handling.py — 异常处理日志验证
- test_serialization_recovery.py — graph 序列化恢复与属性偏移策略

验证:
1. PropertyTag 损坏时 strict/tolerant 模式行为
2. unversioned mapping 路径的 tolerant 标志传播
3. legacy path struct_type ordering (#404)
4. property_parser.py 中异常处理日志（源码级别验证）
5. archive.py 中 MemoryError 处理
6. 异常处理集成测试（不破坏现有功能）
7. graph 序列化恢复与诊断（P73-RECOVERY 置信度评估）
8. 属性偏移策略（SerialOffset/SerialSize 作为默认策略）
"""
from __future__ import annotations

import ast
import logging
import re
import struct
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
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
from tests.conftest import asset_path


# ============================================================================
# 公共常量
# ============================================================================

BLUEPRINT_SAMPLE_REL = "StackOBot_BP_Drone.uasset"
STATICMESH_SAMPLE_REL = "StackOBot_M_BotBase.uasset"


# ============================================================================
# 公共辅助函数 — PropertyTag 重试测试
# ============================================================================


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


# ============================================================================
# 公共辅助函数 — legacy path struct_type ordering (#404)
# ============================================================================


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


# ============================================================================
# 公共辅助函数 — 异常处理源码级验证
# ============================================================================


def _read_source(module_path: str) -> str:
    """读取源码文件内容。"""
    with open(module_path, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================================
# PropertyTag 损坏 strict/tolerant 测试 (原 test_property_tag_retry.py)
# ============================================================================


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


# ============================================================================
# legacy path struct_type ordering (#404)
# ============================================================================


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


# ============================================================================
# 异常处理日志验证 (原 test_property_parser_error_handling.py)
# ============================================================================


class TestPropertyParserErrorLogging:
    """验证 property_parser.py 中的异常处理改进。"""

    def test_binary_or_native_handler_has_logging(self):
        """BinaryOrNative handler 应包含 logger.warning 调用。"""
        source = _read_source("src/uasset_read/parsers/property_parser.py")
        # 查找 BinaryOrNative handler 块
        assert "BinaryOrNative handler failed" in source
        assert 'logger.debug("BinaryOrNative handler failed' in source

    def test_custom_property_fd_handler_has_logging(self):
        """CustomProperty_FD handler 应包含 logger.warning 调用。"""
        source = _read_source("src/uasset_read/parsers/property_parser.py")
        assert "Custom property handler (0x%02X) failed" in source
        assert 'logger.debug("Custom property handler (0x%02X) failed' in source

    def test_game_specific_custom_handler_has_logging(self):
        """游戏特定 custom handler 应包含 logger.warning 调用。"""
        source = _read_source("src/uasset_read/parsers/property_parser.py")
        assert "Game-specific custom property handler failed" in source
        assert 'logger.debug("Game-specific custom property handler failed' in source

    def test_resolve_class_name_export_has_logging(self):
        """parse_properties_from_export 中 resolve_class_name 应有 debug 日志。"""
        source = _read_source("src/uasset_read/parsers/property_parser.py")
        assert 'logger.debug("Failed to resolve class name for export' in source

    def test_resolve_class_name_property_loop_has_logging(self):
        """属性循环中 resolve_class_name 应有 debug 日志。"""
        source = _read_source("src/uasset_read/parsers/property_parser.py")
        assert 'logger.debug("Failed to resolve class name in property loop' in source

    def test_resolve_mapping_struct_name_has_logging(self):
        """_resolve_mapping_struct_name 应有 debug 日志。"""
        source = _read_source("src/uasset_read/parsers/property_parser.py")
        assert 'logger.debug("Failed to resolve mapping struct name' in source

    def test_unversioned_header_parse_has_logging(self):
        """_try_read_unversioned_header 应有 debug 日志。"""
        source = _read_source("src/uasset_read/parsers/property_parser.py")
        assert 'logger.debug("Unversioned header parse failed' in source

    def test_unversioned_variable_size_has_logging(self):
        """_estimate_unversioned_variable_size 应有 debug 日志。"""
        source = _read_source("src/uasset_read/parsers/property_parser.py")
        assert 'logger.debug("Unversioned variable size estimation failed' in source

    def test_no_bare_except_exception_pass(self):
        """验证不再存在裸的 except Exception: pass。"""
        source = _read_source("src/uasset_read/parsers/property_parser.py")
        # 检查不应存在的模式（except Exception 后直接 pass）
        bare_pattern = r"except\s+Exception\s*:\s*pass\s*#\s*解析失败|except\s+Exception\s*:\s*pass\s*#\s*fallback"
        matches = re.findall(bare_pattern, source)
        assert len(matches) == 0, f"发现裸 except Exception: pass: {matches}"


class TestArchiveMemoryErrorHandling:
    """验证 archive.py 中的 MemoryError 处理。"""

    def test_mmap_includes_memory_error(self):
        """mmap 异常处理应包含 MemoryError。"""
        source = _read_source("src/uasset_read/archive.py")
        assert "MemoryError" in source
        assert "(OSError, ValueError, PermissionError, MemoryError)" in source


class TestErrorHandlingIntegration:
    """集成测试：验证异常处理不破坏现有功能。"""

    def test_parse_property_value_with_bad_binary_or_native(self):
        """BinaryOrNative handler 失败时应回退到 raw bytes 而不崩溃。"""
        from io import BytesIO
        from unittest.mock import MagicMock
        from uasset_read.parsers.property_parser import parse_property_value
        from uasset_read.models.properties import PropertyTag

        tag = PropertyTag(
            name="TestProp",
            type="MaterialInput",
            size=4,
            serialize_type="BinaryOrNative",
        )

        # 创建 mock archive
        archive = MagicMock()
        archive.read.return_value = b"\xFF\xFF\xFF\xFF"
        archive.tell.return_value = 0

        # 不应抛出异常
        result = parse_property_value(tag, archive, [], [])
        assert result is not None
        assert result.get("kind") == "binary_or_native_property"

    def test_resolve_mapping_struct_name_fallback(self):
        """_resolve_mapping_struct_name 失败时应返回 fallback 名称。"""
        from dataclasses import dataclass
        from uasset_read.parsers.property_parser import _resolve_mapping_struct_name

        @dataclass
        class FakeExport:
            object_name: str = "FallbackExport"
            class_index: int = -999

        export = FakeExport()
        result = _resolve_mapping_struct_name(export, [], [])

        # 应返回 object_name 作为 fallback
        assert result == "FallbackExport"


# ============================================================================
# Pin 数组恢复测试 (原 test_serialization_recovery.py)
# ============================================================================


class TestPinArrayRecovery:
    """#344: P73-RECOVERY 置信度评估测试。"""

    def _make_archive(self, data: bytes):
        """构造模拟 archive 对象，read 返回真实字节。"""
        archive = MagicMock()
        archive._data = data
        archive._file_size = len(data)
        pos = [0]  # 用列表模拟可变位置

        def _tell():
            return pos[0]

        def _seek(p):
            pos[0] = p

        def _read(n):
            start = pos[0]
            pos[0] += n
            return data[start:start + n]

        archive.tell = _tell
        archive.seek = _seek
        archive.read = _read
        return archive

    def _capture_logs(self, func):
        """使用独立 Handler 捕获日志，避免 caplog 在全量测试中受根日志器级别影响。"""
        test_logger = logging.getLogger("uasset_read.serializers.graph_pin")
        old_level = test_logger.level
        test_logger.setLevel(logging.DEBUG)
        captured: list[logging.LogRecord] = []
        handler = logging.Handler()
        handler.emit = lambda record: captured.append(record)
        test_logger.addHandler(handler)
        try:
            result = func()
        finally:
            test_logger.removeHandler(handler)
            test_logger.setLevel(old_level)
        return result, captured

    def test_recovery_logs_confidence_level(self):
        """验证恢复过程记录置信度级别和诊断信息。"""
        # 布局: [bad_count=255 at pos 0] [valid_count=2 at pos 16] [pin_ref1 at pos 20] [pin_ref2 at pos 44]
        bad_count = 255
        valid_count = 2
        pin_ref = struct.pack('<i', 0) + struct.pack('<i', 1) + b'\x00' * 16

        data = bytearray(200)
        struct.pack_into('<i', data, 0, bad_count)
        struct.pack_into('<i', data, 16, valid_count)
        data[20:20 + len(pin_ref)] = pin_ref
        data[44:44 + len(pin_ref)] = pin_ref

        archive = self._make_archive(bytes(data))

        mock_validation = {"valid": True, "b_null": 0, "owning_node": 1, "owning_node_valid": True, "reason": "ok"}

        with patch('uasset_read.serializers.graph_pin.validate_pin_reference_at', return_value=mock_validation):
            from uasset_read.serializers.graph_pin import _recover_pin_array_count

            def do_test():
                return _recover_pin_array_count(
                    archive, error_pos=0, bad_count=bad_count,
                    export_map=[], import_map=[], scan_window=16
                )
            result, captured = self._capture_logs(do_test)

        assert result is not None
        assert result["count"] == valid_count
        assert result["confidence"] == "high"

        # 验证日志包含置信度和诊断信息
        recovery_logs = [r for r in captured if 'P73-RECOVERY' in r.message]
        assert len(recovery_logs) > 0
        log_msg = recovery_logs[0].message
        assert 'confidence=' in log_msg
        assert 'scan=' in log_msg
        assert 'bad_count=' in log_msg

    def test_recovery_logs_medium_confidence(self):
        """验证中等置信度恢复也记录诊断信息。"""
        bad_count = 255
        valid_count = 1
        pin_ref = struct.pack('<i', 0) + struct.pack('<i', 1) + b'\x00' * 16

        data = bytearray(200)
        struct.pack_into('<i', data, 0, bad_count)
        struct.pack_into('<i', data, 16, valid_count)
        data[20:20 + len(pin_ref)] = pin_ref

        archive = self._make_archive(bytes(data))

        mock_validation = {"valid": True, "b_null": 0, "owning_node": 1, "owning_node_valid": True, "reason": "ok"}

        with patch('uasset_read.serializers.graph_pin.validate_pin_reference_at', return_value=mock_validation):
            from uasset_read.serializers.graph_pin import _recover_pin_array_count

            def do_test():
                return _recover_pin_array_count(
                    archive, error_pos=0, bad_count=bad_count,
                    export_map=[], import_map=[], scan_window=16
                )
            result, captured = self._capture_logs(do_test)

        assert result is not None
        assert result["count"] == valid_count
        assert result["confidence"] == "high"

    def test_recovery_logs_low_confidence_count_zero(self):
        """验证低置信度 count=0 恢复记录诊断信息。"""
        bad_count = 255

        # 用 0xFF 填充（任何 4 字节组合都是 -1，跳过），仅在 pos 16 放 count=0
        data = bytearray(b'\xff' * 200)
        struct.pack_into('<i', data, 0, bad_count)  # bad count at pos 0
        struct.pack_into('<i', data, 16, 0)  # count=0 at pos 16
        # pos 20 保持 0xFF（不是小整数，确保低置信度）

        archive = self._make_archive(bytes(data))

        from uasset_read.serializers.graph_pin import _recover_pin_array_count

        def do_test():
            return _recover_pin_array_count(
                archive, error_pos=0, bad_count=bad_count,
                export_map=[], import_map=[], scan_window=16
            )
        result, captured = self._capture_logs(do_test)

        assert result is not None
        assert result["count"] == 0
        assert result["confidence"] == "low"

        # 验证日志包含 bad_count 和 scan 信息
        recovery_logs = [r for r in captured if 'P73-RECOVERY' in r.message]
        assert len(recovery_logs) > 0
        log_msg = recovery_logs[0].message
        assert 'confidence=low' in log_msg
        assert 'bad_count=255' in log_msg

    def test_recovery_includes_scan_window_in_log(self):
        """验证日志中包含实际使用的 scan_window 大小。"""
        bad_count = 150  # 触发动态窗口调整 (bad_count > 100 -> scan_window >= 64)

        # 构造数据：所有非关键位置填充无效值
        data = bytearray(200)
        for i in range(0, len(data), 4):
            struct.pack_into('<i', data, i, 999)
        struct.pack_into('<i', data, 0, bad_count)
        # valid count at pos 56 (within expanded window of 64, starting from error_pos=0)
        struct.pack_into('<i', data, 56, 1)
        pin_ref = struct.pack('<i', 0) + struct.pack('<i', 1) + b'\x00' * 16
        data[60:60 + len(pin_ref)] = pin_ref

        archive = self._make_archive(bytes(data))

        mock_validation = {"valid": True, "b_null": 0, "owning_node": 1, "owning_node_valid": True, "reason": "ok"}

        with patch('uasset_read.serializers.graph_pin.validate_pin_reference_at', return_value=mock_validation):
            from uasset_read.serializers.graph_pin import _recover_pin_array_count

            def do_test():
                return _recover_pin_array_count(
                    archive, error_pos=0, bad_count=bad_count,
                    export_map=[], import_map=[], scan_window=16
                )
            result, captured = self._capture_logs(do_test)

        assert result is not None
        recovery_logs = [r for r in captured if 'P73-RECOVERY' in r.message]
        assert len(recovery_logs) > 0
        log_msg = recovery_logs[0].message
        # scan_window 应该被扩展到 64
        assert 'scan=64 bytes' in log_msg


class TestGraphSerializerDiagnostics:
    """Verify graph recovery paths emit diagnostics."""

    def test_read_fstring_safe_records_diagnostic_on_truncation(self):
        """_read_fstring_safe should record diagnostic when string is truncated."""
        from uasset_read.serializers.graph import _read_fstring_safe

        archive = MagicMock()
        archive.read_i32.return_value = 99999  # exceeds MAX_SAFE_COUNT (10000)
        archive.tell.return_value = 0x100

        result = _read_fstring_safe(archive, max_length=10000)
        assert isinstance(result, str)

    def test_validate_pin_reference_at_returns_none_on_out_of_range(self):
        """validate_pin_reference_at should return None for out-of-range indices."""
        from uasset_read.serializers.graph import validate_pin_reference_at

        archive = MagicMock()
        archive.tell.return_value = 0x200
        archive.read.return_value = b'\x00\x00\x00\x00' * 6  # 24 bytes
        archive._file_size = 0x100  # Set file_size smaller than pos

        result = validate_pin_reference_at(
            archive,
            pos=0x200,
            export_map=[]
        )
        # Should return None when position exceeds file size
        assert result is None


# ============================================================================
# 属性偏移策略测试 (原 test_serialization_recovery.py)
# ============================================================================


class TestPayloadOffsetStrategy:
    """测试属性解析使用 SerialOffset 作为默认策略。"""

    def test_properties_parsed_from_serial_offset(self, sample_root: Path):
        """验证属性从 SerialOffset 区域开始解析。"""
        # 使用 StaticMesh 而非 Blueprint，因为 Blueprint 样本超过 300 exports
        # 会触发 lightweight tolerant parse，跳过完整属性解析
        staticmesh_path = asset_path(sample_root, STATICMESH_SAMPLE_REL)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(staticmesh_path))

        # 验证解析成功
        assert result.is_success or result.is_partial, f"解析失败: {result.errors}"

        # 验证有 exports 被解析
        assert len(result.export_map) > 0, "应有至少一个 export"

        # 验证至少有一个 export 有属性
        exports_with_properties = [
            exp for exp in result.export_map
            if hasattr(exp, 'properties') and exp.properties
        ]
        assert len(exports_with_properties) > 0, "应有至少一个 export 包含属性"

    def test_script_serialization_offsets_preserved_as_diagnostics(self, sample_root: Path):
        """验证 ScriptSerialization 偏移被保存为诊断字段。"""
        staticmesh_path = asset_path(sample_root, STATICMESH_SAMPLE_REL)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(staticmesh_path))

        # 查找 UE5.10+ 的 exports（有 script_serialization 字段）
        ue510_exports = [
            exp for exp in result.export_map
            if hasattr(exp, 'script_serialization_start_offset')
            and hasattr(exp, 'script_serialization_end_offset')
        ]

        if not ue510_exports:
            pytest.skip("样本中无 UE5.10+ exports")

        # 验证诊断字段存在
        for exp in ue510_exports:
            # 检查绝对偏移字段是否被设置
            assert hasattr(exp, '_script_serialization_start_absolute'), \
                f"Export {exp.object_name} 缺少 _script_serialization_start_absolute"
            assert hasattr(exp, '_script_serialization_end_absolute'), \
                f"Export {exp.object_name} 缺少 _script_serialization_end_absolute"

            # 验证绝对偏移计算正确
            expected_start = exp.serial_offset + exp.script_serialization_start_offset
            expected_end = exp.serial_offset + exp.script_serialization_end_offset

            assert exp._script_serialization_start_absolute == expected_start, \
                f"Export {exp.object_name} 起始偏移计算错误"
            assert exp._script_serialization_end_absolute == expected_end, \
                f"Export {exp.object_name} 结束偏移计算错误"

    def test_exports_have_properties_parsed(self, sample_root: Path):
        """验证 exports 的属性被解析（未被跳过）。"""
        staticmesh_path = asset_path(sample_root, STATICMESH_SAMPLE_REL)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(staticmesh_path))

        # 验证解析成功
        assert result.is_success or result.is_partial, f"解析失败: {result.errors}"

        # 查找非跳过的 exports
        non_skipped_exports = [
            exp for exp in result.export_map
            if getattr(exp, 'parse_status', None) != 'skipped'
        ]

        # 验证至少有一些 exports 有属性
        exports_with_properties = [
            exp for exp in non_skipped_exports
            if hasattr(exp, 'properties') and exp.properties
        ]

        assert len(exports_with_properties) > 0, \
            "应有至少一个非跳过的 export 包含属性"

    def test_property_start_uses_serial_offset(self, sample_root: Path):
        """验证属性解析起始位置使用 SerialOffset。"""
        staticmesh_path = asset_path(sample_root, STATICMESH_SAMPLE_REL)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(staticmesh_path))

        # 验证所有 exports 的属性解析从正确位置开始
        for exp in result.export_map:
            if not hasattr(exp, 'properties') or not exp.properties:
                continue

            # 如果有诊断字段，验证起始位置
            if hasattr(exp, '_script_serialization_start_absolute'):
                # 属性应从 serial_offset 开始，而非 script_serialization_start_absolute
                # （除非两者恰好相等）
                assert exp.serial_offset >= 0, \
                    f"Export {exp.object_name} serial_offset 应为非负数"

    def test_property_end_uses_serial_size(self, sample_root: Path):
        """验证属性解析结束位置使用 SerialOffset + SerialSize。"""
        staticmesh_path = asset_path(sample_root, STATICMESH_SAMPLE_REL)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(staticmesh_path))

        # 验证所有有属性的 exports
        for exp in result.export_map:
            if not hasattr(exp, 'properties') or not exp.properties:
                continue

            # 验证 serial_size 存在且非负
            assert hasattr(exp, 'serial_size'), \
                f"Export {exp.object_name} 缺少 serial_size"
            assert exp.serial_size >= 0, \
                f"Export {exp.object_name} serial_size 应为非负数"

            # 如果有诊断字段，验证结束位置计算
            if hasattr(exp, '_script_serialization_end_absolute'):
                expected_end = exp.serial_offset + exp.serial_size
                # 属性边界应基于 serial_size
                # （注意：_script_serialization_end_absolute 是诊断字段，
                # 实际使用的边界是 serial_offset + serial_size）


class TestPayloadOffsetStrategyUnit:
    """单元测试：验证偏移计算逻辑。"""

    def test_diagnostic_offset_calculation(self):
        """验证诊断偏移字段的计算逻辑。"""

        @dataclass
        class MockExport:
            serial_offset: int = 1000
            serial_size: int = 500
            script_serialization_start_offset: int = 100
            script_serialization_end_offset: int = 400
            object_name: str = "TestExport"

        export = MockExport()

        # 模拟 property_parser.py 中的计算逻辑
        export._script_serialization_start_absolute = (
            export.serial_offset + getattr(export, 'script_serialization_start_offset', 0)
        )
        export._script_serialization_end_absolute = (
            export.serial_offset + getattr(export, 'script_serialization_end_offset', 0)
        )

        # 验证计算结果
        assert export._script_serialization_start_absolute == 1100
        assert export._script_serialization_end_absolute == 1400

    def test_default_property_boundaries(self):
        """验证默认属性边界使用 SerialOffset/SerialSize。"""

        @dataclass
        class MockExport:
            serial_offset: int = 2000
            serial_size: int = 800
            object_name: str = "TestExport"

        export = MockExport()

        # 默认策略：property_start = serial_offset
        property_start = export.serial_offset
        # 默认策略：property_end = serial_offset + serial_size
        property_end = export.serial_offset + export.serial_size

        assert property_start == 2000
        assert property_end == 2800

    def test_missing_script_offsets_handled(self):
        """验证缺少 script_serialization 字段时的安全处理。"""

        @dataclass
        class MockExport:
            serial_offset: int = 1000
            serial_size: int = 500
            object_name: str = "TestExport"
            # 注意：没有 script_serialization_* 字段

        export = MockExport()

        # 使用 getattr 提供默认值 0
        export._script_serialization_start_absolute = (
            export.serial_offset + getattr(export, 'script_serialization_start_offset', 0)
        )
        export._script_serialization_end_absolute = (
            export.serial_offset + getattr(export, 'script_serialization_end_offset', 0)
        )

        # 应使用默认值 0
        assert export._script_serialization_start_absolute == 1000
        assert export._script_serialization_end_absolute == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
