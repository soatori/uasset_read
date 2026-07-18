"""parsers 恢复与边界测试 — 合并自 test_property_parser_recovery / test_parser_diagnostics / test_property_bounds。

覆盖范围：
- PropertyTag 偏移恢复机制（#341）
- ArrayProperty tag.size < 4 处理（#345）
- 属性类型日志级别降级（#340）
- TopLevelAssetPath 结构体
- ParseError 携带 ErrorContext 信息
- MapProperty StructProperty key 支持
- validate_size 记录诊断 / strict 模式
- read_property_tag size_exceeded 标志
- parse_properties_from_export size_exceeded 处理
- get_max_reasonable 动态阈值
"""
from __future__ import annotations

import logging
import struct
import tempfile
import os
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from uasset_read.archive import FArchive, ByteArchive
from uasset_read.constants import (
    PROPERTY_TAG_COMPLETE_TYPE_NAME,
    get_max_reasonable,
    MAX_REASONABLE_CAP,
    UE5_LARGE_PROPERTY_MAX_REASONABLE,
)
from uasset_read.exceptions import ParseError, ErrorContext
from uasset_read.models.properties import PropertyTag, PropertyValue, StructValue, MapValue
from uasset_read.models.fallback import PropertyFallback, FallbackReason
from uasset_read.parsers.property_parser import (
    _try_recover_property_tag,
    parse_properties_from_export,
    _MAX_RECOVERY_SCAN,
)
from uasset_read.parsers.property_types import (
    _EXPECTED_STRUCT_SIZES,
    _TAGGED_FALLBACK_STRUCTS,
    parse_array_property,
    parse_struct_property,
    parse_map_property,
)
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex
from uasset_read.serializers.property_tags import read_property_tag


# legacy 版本号（UE5 < 1012），使用简单 FName 类型格式
_LEGACY_UE5 = 0


# ============================================================================
# 辅助工厂
# ============================================================================

def _make_archive(data: bytes, tolerant: bool = False, file_version_ue5: int = PROPERTY_TAG_COMPLETE_TYPE_NAME) -> FArchive:
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


def _make_mock_archive_for_recovery(data: bytes, pos: int = 0, *, file_version_ue5: int = PROPERTY_TAG_COMPLETE_TYPE_NAME):
    """创建 mock FArchive 用于 PropertyTag 恢复测试。"""
    archive = MagicMock()
    archive._data = data
    archive._pos = pos
    archive._file_size = len(data)
    archive._file_version_ue5 = file_version_ue5

    def tell():
        return archive._pos

    def seek(p):
        archive._pos = p

    def read(n):
        start = archive._pos
        archive._pos += n
        return data[start:start + n]

    archive.tell = tell
    archive.seek = seek
    archive.read = read
    return archive


# ============================================================================
# PropertyTag 偏移恢复机制测试 (#341)
# ============================================================================


class TestPropertyTagRecovery:
    """#341: PropertyTag 早期损坏恢复测试。"""

    def test_recovery_finds_valid_tag_signature_legacy(self):
        """legacy 格式：恢复函数能找到有效的 PropertyTag。"""
        name_map = ["None", "Property", "TestProp"]
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 10)
        data = b'\x00\x00\x00' + fname + type_fname + size + b'\xff' * 30
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        assert archive.tell() == 3

    def test_recovery_finds_valid_tag_signature_ue53(self):
        """UE5.3+ 格式：恢复函数能找到有效的 PropertyTag。"""
        name_map = ["None", "Property", "TestProp"]
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        inner_count = struct.pack('<i', 0)
        size = struct.pack('<i', 10)
        data = b'\x00\x00\x00' + fname + type_fname + inner_count + size + b'\xff' * 30
        archive = _make_mock_archive_for_recovery(data, pos=0)
        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        assert archive.tell() == 3

    def test_recovery_returns_false_when_no_valid_tag(self):
        data = b'\xff' * 100
        archive = _make_mock_archive_for_recovery(data, pos=0)
        result = _try_recover_property_tag(archive, ["None"], max_scan=32)
        assert result is False

    def test_recovery_respects_property_boundary(self):
        name_map = ["None", "Property", "TestProp", "GoodProp"]
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 10)
        data = b'\xff' * 5 + fname + type_fname + size + b'\xff' * 20
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=50, property_end=35)
        assert result is True
        assert archive.tell() == 5

    def test_recovery_with_real_fname_format(self):
        name_map = ["None", "Property", "TestProp", "TaggedProperty"]
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 10)
        data = b'\x00\x00\x00' + fname + type_fname + size + b'\xff' * 30
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        assert archive.tell() == 3

    def test_recovery_rejects_ascii_payload_as_fname(self):
        name_map = ["None", "Property"]
        ascii_payload = b'Hello World!'
        real_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 5)
        data = b'\xff\xfe' + ascii_payload + real_fname + type_fname + size + b'\xff' * 10
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        assert archive.tell() == 14

    def test_recovery_validates_index_against_name_map(self):
        name_map = ["None", "Property", "TestProp"]
        bad_fname = struct.pack('<I', 999) + struct.pack('<I', 0)
        good_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 5)
        data = b'\xff\x00' + bad_fname + b'\xff\x00' + good_fname + type_fname + size + b'\xff' * 10
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        assert archive.tell() == 12

    def test_recovery_validates_tag_size_after_fname(self):
        name_map = ["None", "Property", "TestProp"]
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 48)
        data = b'\x00\x00\x00' + fname + type_fname + size + b'\x00' * 50
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=64, property_end=200)
        assert result is True
        assert archive.tell() == 3

    def test_recovery_rejects_candidate_when_size_exceeds_boundary(self):
        name_map = ["None", "Property", "TestProp"]
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        huge_size = struct.pack('<i', 500)
        data = b'\x00\x00\x00' + fname + type_fname + huge_size + b'\xff' * 20
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=64, property_end=50)
        assert result is False

    def test_recovery_rejects_negative_tag_size(self):
        name_map = ["None", "Property", "TestProp"]
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        neg_size = struct.pack('<i', -1)
        data = b'\x00\x00\x00' + fname + type_fname + neg_size + b'\xff' * 20
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=64, property_end=200)
        assert result is False

    def test_recovery_rejects_window_end_candidate(self):
        name_map = ["None", "Property", "TestProp"]
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        data = b'\xff' * 55 + fname + b'\xff' * 40
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is False

    def test_recovery_ue53_rejects_inner_count_as_size(self):
        name_map = ["None", "IntProperty", "TestProp"]
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        inner_count = struct.pack('<i', 0)
        actual_size = struct.pack('<i', 500)
        data = b'\xff' * 3 + fname + type_fname + inner_count + actual_size + b'\xff' * 20
        archive = _make_mock_archive_for_recovery(data, pos=0)
        result = _try_recover_property_tag(archive, name_map, max_scan=64, property_end=30)
        assert result is False

    def test_recovery_ue53_with_multi_node_type_tree(self):
        name_map = ["None", "StructProperty", "Vector", "TestProp"]
        fname = struct.pack('<I', 3) + struct.pack('<I', 0)
        node1 = struct.pack('<I', 1) + struct.pack('<I', 0) + struct.pack('<i', 1)
        node2 = struct.pack('<I', 2) + struct.pack('<I', 0) + struct.pack('<i', 0)
        size = struct.pack('<i', 20)
        data = b'\xff' * 3 + fname + node1 + node2 + size + b'\xff' * 30
        archive = _make_mock_archive_for_recovery(data, pos=0)
        result = _try_recover_property_tag(archive, name_map, max_scan=64, property_end=200)
        assert result is True
        assert archive.tell() == 3

    def test_recovery_legacy_rejects_ue53_inner_count_as_type_index(self):
        name_map = ["None", "Property", "TestProp"]
        fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        inner_count = struct.pack('<i', 0)
        data = b'\xff' * 3 + fname + type_fname + inner_count + b'\xff' * 20
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=64, property_end=200)
        assert result is True

    def test_recovery_finds_valid_position(self):
        name_map = ["None", "IntProperty", "TestProp"]
        valid_fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 8)
        data = b'\xff' * 10 + valid_fname + type_fname + size + b'\xff' * 30
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        assert archive.tell() == 10

    def test_recovery_stops_at_max_scan(self):
        name_map = ["None", "IntProperty", "TestProp"]
        valid_fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 8)
        data = b'\xff' * 100 + valid_fname + type_fname + size + b'\xff' * 30
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=50)
        assert result is False
        assert archive.tell() == 0

    def test_recovery_records_distance(self):
        name_map = ["None", "IntProperty", "TestProp"]
        valid_fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 8)
        data = b'\xff' * 20 + valid_fname + type_fname + size + b'\xff' * 30
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=_LEGACY_UE5)
        start = archive.tell()
        result = _try_recover_property_tag(archive, name_map, max_scan=64)
        assert result is True
        assert archive.tell() - start == 20

    def test_fallback_when_no_valid_position(self):
        data = b'\xff' * 100
        archive = _make_mock_archive_for_recovery(data, pos=0)
        result = _try_recover_property_tag(archive, ["None"], max_scan=50)
        assert result is False
        assert archive.tell() == 0

    def test_max_recovery_scan_constant_value(self):
        assert _MAX_RECOVERY_SCAN == 256

    def test_recovery_uses_max_recovery_scan_default(self):
        name_map = ["None", "IntProperty", "TestProp"]
        valid_fname = struct.pack('<I', 2) + struct.pack('<I', 0)
        type_fname = struct.pack('<I', 1) + struct.pack('<I', 0)
        size = struct.pack('<i', 8)
        data = b'\xff' * 200 + valid_fname + type_fname + size + b'\xff' * 30
        archive = _make_mock_archive_for_recovery(data, pos=0, file_version_ue5=_LEGACY_UE5)
        result = _try_recover_property_tag(archive, name_map, max_scan=_MAX_RECOVERY_SCAN)
        assert result is True
        assert archive.tell() == 200


# ============================================================================
# ArrayProperty tag.size < 4 测试 (#345)
# ============================================================================


class TrackingArchive:
    """记录 read_i32 调用次数。"""
    def __init__(self):
        self.pos = 0
        self.read_count = 0
    def tell(self):
        return self.pos
    def read_i32(self):
        self.read_count += 1
        self.pos += 4
        return 0
    def read_fstring(self):
        return ""
    def read_byte(self):
        return 0


def test_small_tag_size_skips_count_read():
    """tag.size < 4 不应读取 count。"""
    for size in (0, 1, 3):
        a = TrackingArchive()
        tag = PropertyTag(name="A", type="ArrayProperty", size=size)
        result = parse_array_property(tag, a, [], [])
        assert result == [], f"size={size}: 应返回空数组"
        assert a.read_count == 0, f"size={size}: 不应调用 read_i32 (count)"


# ============================================================================
# 属性类型日志级别测试 (#340)
# ============================================================================


class TestTransformWarningDowngrade:
    """#340: Transform size 警告应降级为 debug。"""

    def test_unknown_transform_variant_logs_debug_not_warning(self):
        tag = MagicMock()
        tag.name = "TestTransform"
        tag.type = "StructProperty"
        tag.struct_type = "Transform"
        tag.size = 48
        tag.array_index = 0

        archive = MagicMock()
        archive.read_f32 = MagicMock(return_value=0.0)
        archive.read_f64 = MagicMock(return_value=0.0)
        archive.read_bytes = MagicMock(return_value=b'\x00' * 48)
        archive.tell = MagicMock(return_value=0)
        archive.total_size = MagicMock(return_value=1000)
        archive._tolerant = True

        test_logger = logging.getLogger("uasset_read.parsers.property_types")
        old_level = test_logger.level
        test_logger.setLevel(logging.DEBUG)
        captured: list[logging.LogRecord] = []
        handler = logging.Handler()
        handler.emit = lambda record: captured.append(record)
        test_logger.addHandler(handler)
        try:
            try:
                parse_struct_property(tag, archive, [], [])
            except Exception:
                pass
        finally:
            test_logger.removeHandler(handler)
            test_logger.setLevel(old_level)

        debug_msgs = [r for r in captured if r.levelno == logging.DEBUG]
        warning_msgs = [r for r in captured if r.levelno == logging.WARNING and 'Transform' in r.message]
        assert len(debug_msgs) > 0, "Expected debug logs but got none"
        assert len(warning_msgs) == 0, f"Expected no warnings but got: {warning_msgs}"

    def test_unknown_non_lwc_struct_variant_logs_debug_not_warning(self):
        tag = MagicMock()
        tag.name = "TestStruct"
        tag.type = "StructProperty"
        tag.struct_type = "Vector"
        tag.size = 99
        tag.array_index = 0

        archive = MagicMock()
        archive.read_f32 = MagicMock(return_value=0.0)
        archive.read_f64 = MagicMock(return_value=0.0)
        archive.read_bytes = MagicMock(return_value=b'\x00' * 99)
        archive.tell = MagicMock(return_value=0)
        archive.total_size = MagicMock(return_value=1000)

        test_logger = logging.getLogger("uasset_read.parsers.property_types")
        old_level = test_logger.level
        test_logger.setLevel(logging.DEBUG)
        captured: list[logging.LogRecord] = []
        handler = logging.Handler()
        handler.emit = lambda record: captured.append(record)
        test_logger.addHandler(handler)
        try:
            try:
                parse_struct_property(tag, archive, [], [])
            except Exception:
                pass
        finally:
            test_logger.removeHandler(handler)
            test_logger.setLevel(old_level)

        debug_msgs = [r for r in captured if r.levelno == logging.DEBUG]
        warning_msgs = [r for r in captured if r.levelno == logging.WARNING and 'Vector' in r.message]
        assert len(debug_msgs) > 0 and len(warning_msgs) == 0

    def test_standard_transform_size_no_warning(self, caplog):
        tag = MagicMock()
        tag.name = "TestTransform"
        tag.type = "StructProperty"
        tag.struct_type = "Transform"
        tag.size = 40
        tag.array_index = 0

        archive = MagicMock()
        archive.read_f32 = MagicMock(return_value=0.0)
        archive.read_f64 = MagicMock(return_value=0.0)
        archive.read_bytes = MagicMock(return_value=b'\x00' * 40)
        archive.tell = MagicMock(return_value=0)
        archive.total_size = MagicMock(return_value=1000)

        with caplog.at_level(logging.DEBUG):
            try:
                parse_struct_property(tag, archive, [], [])
            except Exception:
                pass

        size_mismatch_msgs = [r for r in caplog.records if 'tag.size' in r.message and 'Transform' in r.message]
        assert len(size_mismatch_msgs) == 0


class TestArrayPropertySmallSize:
    """#345: ArrayProperty tag.size < 4 处理测试。"""

    def test_empty_array_no_warning(self, caplog):
        tag = MagicMock()
        tag.name = "DebugWatch_RigVMModel___Test"
        tag.type = "ArrayProperty"
        tag.size = 0
        tag.array_index = 0
        tag.inner_type = "IntProperty"

        archive = MagicMock()
        archive.read_i32 = MagicMock(return_value=0)
        archive.tell = MagicMock(return_value=0)

        with caplog.at_level(logging.WARNING):
            result = parse_array_property(tag, archive, [], [])
        assert result == []
        size_warnings = [r for r in caplog.records if r.levelno >= logging.WARNING and 'tag.size' in r.message]
        assert len(size_warnings) == 0

    def test_tag_size_1_no_warning(self, caplog):
        tag = MagicMock()
        tag.name = "DebugWatch_RigVMModel___Test[0]"
        tag.type = "ArrayProperty"
        tag.size = 1
        tag.array_index = 0
        tag.inner_type = "IntProperty"

        archive = MagicMock()
        archive.read_i32 = MagicMock(return_value=0)
        archive.tell = MagicMock(return_value=0)

        with caplog.at_level(logging.WARNING):
            result = parse_array_property(tag, archive, [], [])
        assert result == []
        size_warnings = [r for r in caplog.records if r.levelno >= logging.WARNING and 'tag.size' in r.message]
        assert len(size_warnings) == 0


# ============================================================================
# TopLevelAssetPath 结构体测试
# ============================================================================


class TestTopLevelAssetPath:
    def test_expected_size_is_none(self):
        size = _EXPECTED_STRUCT_SIZES.get("TopLevelAssetPath")
        assert size is None

    def test_not_in_tagged_fallback_structs(self):
        assert "TopLevelAssetPath" not in _TAGGED_FALLBACK_STRUCTS


# ============================================================================
# ParseError 上下文诊断测试
# ============================================================================


class TestParseErrorContext:
    """验证各属性解析器抛出的 ParseError 携带 ErrorContext。"""

    def test_parse_int_property_byteproperty_missing_name_map(self):
        from uasset_read.parsers.property_types import parse_int_property
        tag = MagicMock()
        tag.name = "TestByteProp"
        tag.type = "ByteProperty"
        tag.enum_type = "TestEnum"
        archive = MagicMock()
        archive.tell = MagicMock(return_value=42)
        with pytest.raises(ParseError) as exc_info:
            parse_int_property(tag, archive, name_map=None)
        ctx = exc_info.value.context
        assert ctx is not None
        assert ctx.offset == 42
        assert ctx.phase == "properties"
        assert ctx.operation == "parse_int_property"
        assert ctx.context_name == "TestByteProp"

    def test_parse_array_property_depth_exceeded(self):
        from uasset_read.parsers.property_types import parse_array_property
        tag = MagicMock()
        tag.name = "DeepArray"
        tag.type = "ArrayProperty"
        tag.size = 100
        tag.inner_type = "IntProperty"
        archive = MagicMock()
        archive.tell = MagicMock(return_value=1000)
        with pytest.raises(ParseError) as exc_info:
            parse_array_property(tag, archive, name_map=[], export_map=[], depth=11)
        assert "nesting depth" in str(exc_info.value)
        ctx = exc_info.value.context
        assert ctx is not None
        assert ctx.offset == 1000
        assert ctx.phase == "properties"
        assert ctx.operation == "parse_array_property"
        assert ctx.context_name == "DeepArray"

    def test_parse_struct_property_depth_exceeded(self):
        from uasset_read.parsers.property_types import parse_struct_property
        tag = MagicMock()
        tag.name = "DeepStruct"
        tag.type = "StructProperty"
        tag.struct_type = "Vector"
        tag.size = 12
        tag.array_index = 0
        archive = MagicMock()
        archive.tell = MagicMock(return_value=2000)
        with pytest.raises(ParseError) as exc_info:
            parse_struct_property(tag, archive, name_map=[], export_map=[], depth=6)
        assert "nesting depth" in str(exc_info.value)
        ctx = exc_info.value.context
        assert ctx is not None
        assert ctx.offset == 2000

    def test_try_fast_path_struct_transform_unexpected_size(self):
        from uasset_read.parsers.property_types import _try_fast_path_struct
        tag = MagicMock()
        tag.name = "BadTransform"
        tag.type = "StructProperty"
        tag.struct_type = "Transform"
        tag.size = 48
        archive = MagicMock()
        archive._tolerant = False
        archive.tell = MagicMock(return_value=3000)
        with pytest.raises(ParseError) as exc_info:
            _try_fast_path_struct("Transform", tag, archive, name_map=[])
        assert "unexpected size" in str(exc_info.value)
        ctx = exc_info.value.context
        assert ctx is not None
        assert ctx.offset == 3000

    def test_error_context_dataclass_fields(self):
        ctx = ErrorContext(offset=100, phase="properties", operation="parse_struct_property", context_name="MyProp")
        assert ctx.offset == 100
        assert ctx.phase == "properties"
        assert ctx.operation == "parse_struct_property"
        assert ctx.context_name == "MyProp"
        assert ctx.export_index is None
        assert ctx.expected_offset is None
        assert ctx.actual_offset is None
        assert ctx.field_name == ""

    def test_parse_error_str_includes_context_info(self):
        err = ParseError("test error")
        err.reader_name = "FArchive"
        err.position = 100
        err.length = 1000
        err.export_name = "TestExport"
        s = str(err)
        assert "test error" in s
        assert "FArchive" in s
        assert "TestExport" in s


# ============================================================================
# MapProperty StructProperty key 测试
# ============================================================================


def _make_tag_for_map(
    key_type: str = "StructProperty",
    value_type: str = "IntProperty",
    key_type_struct: str = "TestStruct",
    value_type_struct: str | None = None,
) -> PropertyTag:
    return PropertyTag(
        name="TestMap", type="MapProperty", size=0,
        key_type=key_type, value_type=value_type,
        key_type_struct=key_type_struct, value_type_struct=value_type_struct,
    )


def _write_property_tag(name: str, type_name: str, size: int) -> bytes:
    buf = bytearray()
    name_bytes = name.encode("utf-8")
    buf += struct.pack("<i", len(name_bytes))
    buf += name_bytes
    type_bytes = type_name.encode("utf-8")
    buf += struct.pack("<i", len(type_bytes))
    buf += type_bytes
    buf += struct.pack("<i", size)
    buf += struct.pack("<i", 0)
    buf += struct.pack("<B", 0)
    return bytes(buf)


def _write_none_sentinel() -> bytes:
    return struct.pack("<i", 0)


def _write_int32(value: int) -> bytes:
    return struct.pack("<i", value)


class TestMapPropertyStructKey:
    def test_struct_key_parsed_correctly(self):
        struct_buf = bytearray()
        tag1 = _write_property_tag("CurveName", "StrProperty", 9)
        struct_buf += tag1
        name_bytes = b"TestCurve"
        struct_buf += _write_int32(len(name_bytes))
        struct_buf += name_bytes
        tag2 = _write_property_tag("CurveType", "IntProperty", 4)
        struct_buf += tag2
        struct_buf += _write_int32(1)
        struct_buf += _write_none_sentinel()

        map_buf = bytearray()
        map_buf += _write_int32(0)
        map_buf += _write_int32(1)
        map_buf += bytes(struct_buf)
        map_buf += _write_int32(42)

        archive = ByteArchive(bytes(map_buf))
        tag = _make_tag_for_map()
        result = parse_map_property(tag, archive, name_map=[], export_map=[])
        assert isinstance(result, MapValue)
        assert result.key_type == "StructProperty"
        assert len(result.entries) == 1
        key = result.entries[0]["key"]
        assert isinstance(key, StructValue)
        assert key.struct_type == "TestStruct"
        assert key.parse_status in ("parsed", "opaque")
        if key.parse_status == "parsed":
            assert "CurveName" in key.fields
            assert "CurveType" in key.fields

    def test_struct_key_empty_struct(self):
        struct_buf = _write_none_sentinel()
        map_buf = bytearray()
        map_buf += _write_int32(0)
        map_buf += _write_int32(1)
        map_buf += struct_buf
        map_buf += _write_int32(10)

        archive = ByteArchive(bytes(map_buf))
        tag = _make_tag_for_map()
        result = parse_map_property(tag, archive, name_map=[], export_map=[])
        key = result.entries[0]["key"]
        assert isinstance(key, StructValue)
        assert key.fields == {}

    def test_struct_key_multiple_entries(self):
        def make_struct(curve_name: str, curve_type: int) -> bytes:
            buf = bytearray()
            buf += _write_property_tag("CurveName", "StrProperty", len(curve_name))
            name_bytes = curve_name.encode("utf-8")
            buf += _write_int32(len(name_bytes))
            buf += name_bytes
            buf += _write_property_tag("CurveType", "IntProperty", 4)
            buf += _write_int32(curve_type)
            buf += _write_none_sentinel()
            return bytes(buf)

        map_buf = bytearray()
        map_buf += _write_int32(0)
        map_buf += _write_int32(2)
        map_buf += make_struct("Curve1", 0)
        map_buf += _write_int32(100)
        map_buf += make_struct("Curve2", 1)
        map_buf += _write_int32(200)

        archive = ByteArchive(bytes(map_buf))
        tag = _make_tag_for_map()
        result = parse_map_property(tag, archive, name_map=[], export_map=[])
        assert isinstance(result, MapValue)
        assert result.key_type == "StructProperty"
        assert len(result.entries) >= 1

    def test_struct_key_unknown_struct_type(self):
        struct_buf = _write_none_sentinel()
        map_buf = bytearray()
        map_buf += _write_int32(0)
        map_buf += _write_int32(1)
        map_buf += struct_buf
        map_buf += _write_int32(1)

        archive = ByteArchive(bytes(map_buf))
        tag = _make_tag_for_map(key_type_struct=None)
        result = parse_map_property(tag, archive, name_map=[], export_map=[])
        key = result.entries[0]["key"]
        assert isinstance(key, StructValue)
        assert key.struct_type == "Unknown"


# ============================================================================
# validate_size 记录诊断测试
# ============================================================================


class TestValidateSizeRecordsDiagnostic:
    def test_tolerant_records_diagnostic_on_size_exceeded(self):
        data = b"\x00" * 4
        archive = _make_archive(data, tolerant=True, file_version_ue5=1012)
        result = archive.validate_size(100, "TestProp", tolerant=True)
        assert result is False
        assert len(archive._diagnostics) >= 1
        diag = archive._diagnostics[-1]
        assert "exceeds remaining" in diag.error
        assert "TestProp" in diag.error

    def test_tolerant_records_diagnostic_on_negative_size(self):
        data = b"\x00" * 4
        archive = _make_archive(data, tolerant=True, file_version_ue5=1012)
        result = archive.validate_size(-1, "TestProp", tolerant=True)
        assert result is False
        assert len(archive._diagnostics) >= 1
        diag = archive._diagnostics[-1]
        assert "negative" in diag.error

    def test_tolerant_records_diagnostic_on_max_reasonable_exceeded(self):
        data = b"\x00" * (1024 * 1024)
        archive = _make_archive(data, tolerant=True, file_version_ue5=0)
        result = archive.validate_size(200 * 1024, "TestProp", tolerant=True)
        assert result is False
        assert len(archive._diagnostics) >= 1
        diag = archive._diagnostics[-1]
        assert "max_reasonable" in diag.error

    def test_valid_size_returns_true(self):
        data = b"\x00" * 1024
        archive = _make_archive(data, tolerant=True, file_version_ue5=0)
        result = archive.validate_size(100, "TestProp", tolerant=True)
        assert result is True
        assert len(archive._diagnostics) == 0


class TestValidateSizeStrictRaises:
    def test_strict_raises_on_size_exceeded(self):
        data = b"\x00" * 4
        archive = _make_archive(data, tolerant=False, file_version_ue5=1012)
        with pytest.raises(ParseError, match="exceeds remaining"):
            archive.validate_size(100, "TestProp", tolerant=False)

    def test_strict_raises_on_negative_size(self):
        data = b"\x00" * 4
        archive = _make_archive(data, tolerant=False, file_version_ue5=1012)
        with pytest.raises(ParseError, match="negative"):
            archive.validate_size(-1, "TestProp", tolerant=False)


# ============================================================================
# read_property_tag size_exceeded 测试
# ============================================================================


class TestReadPropertyTagSizeExceeded:
    def test_tolerant_sets_size_exceeded_flag(self):
        name_bytes = struct.pack("<II", 0, 0)
        type_bytes = struct.pack("<II", 0, 0)
        inner_count = struct.pack("<i", 0)
        size_bytes = struct.pack("<i", 1000)
        data = name_bytes + type_bytes + inner_count + size_bytes
        archive = _make_archive(data, tolerant=True, file_version_ue5=1012)
        tag = read_property_tag(archive, ["TestProp"], tolerant=True)
        assert tag.size_exceeded is True
        assert tag.size == 1000
        assert tag.serialize_type == "Property"

    def test_tolerant_skips_flags_reading(self):
        name_bytes = struct.pack("<II", 0, 0)
        type_bytes = struct.pack("<II", 0, 0)
        inner_count = struct.pack("<i", 0)
        size_bytes = struct.pack("<i", 1000)
        data = name_bytes + type_bytes + inner_count + size_bytes
        archive = _make_archive(data, tolerant=True, file_version_ue5=1012)
        tag = read_property_tag(archive, ["TestProp"], tolerant=True)
        assert archive.tell() == 24

    def test_valid_size_sets_size_exceeded_false(self):
        name_bytes = struct.pack("<II", 0, 0)
        type_bytes = struct.pack("<II", 0, 0)
        inner_count = struct.pack("<i", 0)
        size_bytes = struct.pack("<i", 4)
        flags_bytes = b"\x00"
        value_bytes = b"\x00" * 4
        data = name_bytes + type_bytes + inner_count + size_bytes + flags_bytes + value_bytes
        archive = _make_archive(data, tolerant=True, file_version_ue5=1012)
        tag = read_property_tag(archive, ["TestProp"], tolerant=True)
        assert tag.size_exceeded is False
        assert tag.size == 4


# ============================================================================
# parse_properties_from_export size_exceeded 测试
# ============================================================================


class TestParsePropertiesSizeExceeded:
    def test_tolerant_creates_fallback_for_size_exceeded(self):
        serialization_control = b"\x00"
        name_bytes = struct.pack("<II", 0, 0)
        type_bytes = struct.pack("<II", 0, 0)
        inner_count = struct.pack("<i", 0)
        size_bytes = struct.pack("<i", 1000)
        data = serialization_control + name_bytes + type_bytes + inner_count + size_bytes
        archive = _make_archive(data, tolerant=True, file_version_ue5=1012)
        summary = MagicMock()
        summary.package_flags = 0
        summary.file_version_ue5 = 1012
        export = _make_export(serial_offset=0, serial_size=100)
        result = parse_properties_from_export(
            export, archive, summary, name_map=["TestProp"], export_map=[], tolerant=True,
        )
        assert isinstance(result, list)
        assert len(result) >= 1
        prop = result[0]
        assert isinstance(prop, PropertyValue)
        assert prop.name == "TestProp"
        assert isinstance(prop.value, PropertyFallback)
        assert prop.value.reason == FallbackReason.SIZE_EXCEEDED

    def test_strict_raises_on_size_exceeded(self):
        serialization_control = b"\x00"
        name_bytes = struct.pack("<II", 0, 0)
        type_bytes = struct.pack("<II", 0, 0)
        inner_count = struct.pack("<i", 0)
        size_bytes = struct.pack("<i", 1000)
        data = serialization_control + name_bytes + type_bytes + inner_count + size_bytes
        archive = _make_archive(data, tolerant=False, file_version_ue5=1012)
        summary = MagicMock()
        summary.package_flags = 0
        summary.file_version_ue5 = 1012
        export = _make_export(serial_offset=0, serial_size=100)
        with pytest.raises(ParseError, match="exceeds remaining"):
            parse_properties_from_export(
                export, archive, summary, name_map=["TestProp"], export_map=[], tolerant=False,
            )


# ============================================================================
# max_reasonable 动态阈值测试
# ============================================================================


class TestGetMaxReasonable:
    def test_default_property_returns_standard_cap(self):
        assert get_max_reasonable("IntProperty", engine_version=5) == MAX_REASONABLE_CAP

    def test_struct_property_returns_standard_cap(self):
        assert get_max_reasonable("StructProperty", engine_version=5) == MAX_REASONABLE_CAP

    def test_bone_animation_tracks_allows_large_size(self):
        assert get_max_reasonable("BoneAnimationTracks", engine_version=5) == UE5_LARGE_PROPERTY_MAX_REASONABLE

    def test_pose_container_allows_large_size(self):
        assert get_max_reasonable("PoseContainer", engine_version=5) == UE5_LARGE_PROPERTY_MAX_REASONABLE

    def test_array_connection_map_allows_large_size(self):
        assert get_max_reasonable("ArrayConnectionMap", engine_version=5) == UE5_LARGE_PROPERTY_MAX_REASONABLE

    def test_rigvm_allows_large_size(self):
        assert get_max_reasonable("RigVM", engine_version=5) == UE5_LARGE_PROPERTY_MAX_REASONABLE

    def test_ue4_large_type_still_uses_standard_cap(self):
        assert get_max_reasonable("BoneAnimationTracks", engine_version=4) == MAX_REASONABLE_CAP

    def test_ue5_non_large_type_uses_standard_cap(self):
        assert get_max_reasonable("SomeOtherType", engine_version=5) == MAX_REASONABLE_CAP

    def test_engine_version_zero_uses_standard_cap(self):
        assert get_max_reasonable("BoneAnimationTracks", engine_version=0) == MAX_REASONABLE_CAP

    def test_large_property_max_is_500mb(self):
        assert UE5_LARGE_PROPERTY_MAX_REASONABLE == 500 * 1024 * 1024

    def test_standard_cap_is_100mb(self):
        assert MAX_REASONABLE_CAP == 100 * 1024 * 1024


class TestValidateSizeWithPropertyType:
    def test_validate_size_accepts_large_struct(self):
        file_size = 600 * 1024 * 1024
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * min(file_size, 1024))
            temp_path = f.name
        try:
            archive = FArchive(temp_path, tolerant=False)
            archive._file_size = file_size
            archive._file_version_ue5 = 5
            archive.validate_size(
                500 * 1024 * 1024, context="TestProp", tolerant=False, property_type="BoneAnimationTracks",
            )
        finally:
            archive.close()
            os.unlink(temp_path)

    def test_validate_size_rejects_large_normal_property(self):
        file_size = 600 * 1024 * 1024
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * min(file_size, 1024))
            temp_path = f.name
        try:
            archive = FArchive(temp_path, tolerant=False)
            archive._file_size = file_size
            archive._file_version_ue5 = 5
            try:
                archive.validate_size(
                    500 * 1024 * 1024, context="TestProp", tolerant=False, property_type="IntProperty",
                )
                assert False, "应抛出 ParseError"
            except ParseError as e:
                assert "max_reasonable" in str(e)
        finally:
            archive.close()
            os.unlink(temp_path)
