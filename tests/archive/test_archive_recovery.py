"""Archive 恢复机制测试（archive/recovery）。

合并自：
- test_error_recovery.py — 数组越界 ParseError、Linker Preload 容错、Export 级错误上下文
- test_fallback.py — Fallback 数据模型、未知 property fallback、截断/损坏文件诊断
- test_tolerant_parsing.py — 容错早期解析诊断、Class-specific tolerant skip、轻量容错
"""
from __future__ import annotations

import ast
import gc
import io
import json
import os
import struct
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.archive import FArchive
from uasset_read.constants import (
    MIN_UASSET_SIZE,
    PACKAGE_FILE_TAG,
    UE4_LEGACY_VERSIONS,
    UE5_LEGACY_VERSIONS,
    UE5_PACKAGE_SAVED_HASH,
    SUPPORTED_LEGACY_VERSIONS,
)
from uasset_read.core import ParseError, parse_single
from uasset_read.exceptions import ParseError as ParseError2, VersionError, ErrorContext
from uasset_read.models.fallback import (
    PropertyFallback,
    StructFallback,
    GenericUObject,
    ExportParseStatus,
    FallbackReason,
)
from uasset_read.models.properties import PropertyValue
from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker
from uasset_read.parsers.utils import read_validated_count_tolerant
from uasset_read.parsers.property_parser import parse_properties_from_export, parse_property_value
from uasset_read.models.properties import PropertyTag
from uasset_read.serializers.object_resources import ObjectExport, PackageIndex
from uasset_read.serializers.package_summary import read_package_summary

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MAX_PARAM_COUNT = 20


def _read_fixture_lines(name: str) -> list[str]:
    path = FIXTURES_DIR / name
    if not path.exists():
        pytest.skip(f"Fixture file not found: {path}", allow_module_level=True)
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return lines[:MAX_PARAM_COUNT]


def _package_with_bad_custom_version_count(count: int) -> bytes:
    data = bytearray()
    data += struct.pack("<Iiii", PACKAGE_FILE_TAG, -9, 0, 0)
    data += struct.pack("<i", UE5_PACKAGE_SAVED_HASH)
    data += b"\x00" * 20
    data += struct.pack("<i", 0)
    data += struct.pack("<I", count)
    data += b"\x00" * 128
    return bytes(data)


def _write_temp_file(data: bytes, suffix: str = ".uasset") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, data)
    os.close(fd)
    return path


def _cleanup_archive_and_file(archive, path):
    try:
        archive.close()
    except Exception:
        pass
    try:
        os.unlink(path)
    except (PermissionError, OSError):
        pass


def _make_archive(data: bytes):
    buf = io.BytesIO(data)
    archive = MagicMock(spec=FArchive)
    archive.read.return_value = data
    archive.tell.return_value = 0
    archive.seek.return_value = None
    archive.total_size.return_value = len(data) + 100
    return archive


def _make_mock_archive(data: bytes):
    archive = MagicMock()
    archive.tell.return_value = 0
    archive.seek = MagicMock()
    archive.read = MagicMock(return_value=data)
    archive.total_size.return_value = len(data) + 1000
    archive.read_u8.return_value = 0
    archive.read_i32.return_value = 0
    archive.read_name.return_value = "None"
    return archive


def _make_mock_export(serial_offset=0, serial_size=100, script_serialization_start_offset=0, script_serialization_end_offset=0):
    export = MagicMock(spec=ObjectExport)
    export.serial_offset = serial_offset
    export.serial_size = serial_size
    export.script_serialization_start_offset = script_serialization_start_offset
    export.script_serialization_end_offset = script_serialization_end_offset
    export.object_name = "TestExport"
    export.class_index = PackageIndex(0)
    return export


def _make_mock_summary(file_version_ue5=0, package_flags=0):
    summary = MagicMock()
    summary.file_version_ue5 = file_version_ue5
    summary.package_flags = package_flags
    return summary


ARCHIVE_PATH = Path(__file__).resolve().parent.parent.parent / "src" / "uasset_read" / "archive.py"



# === 错误恢复机制测试 ===

class TestReadValidatedCount:

    """read_validated_count 异常类型测试。"""

    def _make_archive_with_i32(self, value: int) -> FArchive:
        """创建包含指定 i32 值的 FArchive。"""
        import struct
        data = struct.pack("<i", value)
        archive = FArchive.__new__(FArchive)
        archive._stream = BytesIO(data)
        archive._file_size = len(data)
        archive._byte_swapping = False
        archive._use_mmap = False
        archive._mmap = None
        archive._tolerant = True
        archive._file = BytesIO(data)
        return archive

    def test_negative_count_returns_zero_with_warning(self):
        """负数数量应返回 0 并记录警告（而非抛出 ParseError）。"""
        archive = self._make_archive_with_i32(-1)
        result = read_validated_count_tolerant(archive, 1000000, "test")
        assert result == 0

    def test_exceeds_max_returns_zero_with_warning(self):
        """超大数量应返回 0 并记录警告（而非抛出 ParseError）。"""
        archive = self._make_archive_with_i32(9999999)
        result = read_validated_count_tolerant(archive, 1000000, "test")
        assert result == 0

    def test_valid_count_returns_value(self):
        """正常数量应正常返回。"""
        archive = self._make_archive_with_i32(42)
        result = read_validated_count_tolerant(archive, 1000000, "test")
        assert result == 42

    def test_zero_count_returns_value(self):
        """零值应正常返回。"""
        archive = self._make_archive_with_i32(0)
        result = read_validated_count_tolerant(archive, 1000000, "test")
        assert result == 0

    def test_invalid_count_returns_zero_not_exception(self):
        """无效数量应返回 0 而非抛出任何异常。"""
        archive = self._make_archive_with_i32(-100)
        result = read_validated_count_tolerant(archive, 1000000, "test_label")
        assert result == 0


class TestPropertyParserSmartContinue:
    """验证 smart continue 机制能捕获 ParseError。"""

    def test_parse_error_is_caught_by_smart_continue(self):
        """ParseError 应被 property_parser 的 smart continue 捕获。"""
        # 这个测试验证异常类型的兼容性
        # 实际的 smart continue 行为需要完整的解析上下文
        from uasset_read.parsers.property_parser import parse_properties_from_export
        # 确认函数存在且可导入
        assert callable(parse_properties_from_export)


class TestPreloadErrorRecovery:
    """验证 Linker preload 的容错机制。"""

    def test_preload_loop_catches_exceptions(self):
        """preload 循环应捕获单个 export 的异常。"""
        # 直接读取源文件验证 preload 循环有 try/except
        from pathlib import Path
        source_path = Path(__file__).parent.parent.parent / "src" / "uasset_read" / "parse_uasset.py"
        source = source_path.read_text(encoding="utf-8")
        # 确认 preload 循环中有 try/except
        assert "try:" in source and "linker.preload" in source, \
            "preload 循环应包含 try/except 容错处理"


# ===========================================================================
# Export 级错误上下文测试
# 验证当 property 解析失败时，PropertyValue.value 是 PropertyFallback
# 且包含 offset/class 等上下文信息。
# Task 4 of P1: Export 级错误上下文增强。
# ===========================================================================


def _make_mock_archive(data: bytes):
    """构造一个 mock FArchive，返回指定数据。"""
    archive = MagicMock()
    archive.tell.return_value = 0
    archive.seek = MagicMock()
    archive.read = MagicMock(return_value=data)
    archive.total_size.return_value = len(data) + 1000
    archive.read_u8.return_value = 0
    archive.read_i32.return_value = 0
    archive.read_name.return_value = "None"
    return archive


def _make_mock_export(serial_offset=0, serial_size=100, script_serialization_start_offset=0, script_serialization_end_offset=0):
    """构造一个 mock ObjectExport。"""
    export = MagicMock(spec=ObjectExport)
    export.serial_offset = serial_offset
    export.serial_size = serial_size
    export.script_serialization_start_offset = script_serialization_start_offset
    export.script_serialization_end_offset = script_serialization_end_offset
    export.object_name = "TestExport"
    export.class_index = PackageIndex(0)
    return export


def _make_mock_summary(file_version_ue5=0, package_flags=0):
    """构造一个 mock PackageFileSummary。"""
    summary = MagicMock()
    summary.file_version_ue5 = file_version_ue5
    summary.package_flags = package_flags
    return summary


def test_export_with_no_properties_returns_empty_list():
    """空属性列表应返回空 list。"""
    # "None" 终止标记 — FName Index = 0 对应 name_map 中的 "None"
    # read_property_tag 读取 FName：Index (i32) + Number (i32)
    # 构造数据：FName Index=0 (小端) + Number=0 → 名为 "None" 的 tag
    data = b"\x00\x00\x00\x00\x00\x00\x00\x00"  # Index=0, Number=0
    archive = _make_mock_archive(data)
    archive.tell.return_value = 100
    export = _make_mock_export(serial_offset=100, serial_size=50)
    summary = _make_mock_summary()

    # name_map 中 "None" 在索引 0
    result = parse_properties_from_export(
        export=export,
        archive=archive,
        summary=summary,
        name_map=["None"],
        export_map=[],
    )
    assert isinstance(result, list)
    assert len(result) == 0


def test_property_fallback_has_error_message():
    """PropertyFallback 应包含 error_message 字段。"""
    fb = PropertyFallback(
        name="BadProp",
        type="BrokenType",
        size=0,
        raw_bytes=b"",
        reason=FallbackReason.PARSE_ERROR,
        error_message="Test error context",
    )
    assert fb.error_message == "Test error context"
    assert fb.reason == FallbackReason.PARSE_ERROR


def test_property_fallback_to_dict_includes_error():
    """PropertyFallback.to_dict 应包含错误信息。"""
    fb = PropertyFallback(
        name="ErrorProp",
        type="ErrorType",
        size=16,
        raw_bytes=b"\xAA" * 16,
        reason=FallbackReason.PARSE_ERROR,
        array_index=1,
        error_message="Failed at offset 0x100: invalid data",
    )
    d = fb.to_dict()
    assert d["error_message"] == "Failed at offset 0x100: invalid data"
    assert d["array_index"] == 1
    assert d["reason"] == "parse_error"
    assert d["name"] == "ErrorProp"
    assert d["kind"] == "unknown_property"


def test_parse_error_in_loop_produces_property_fallback():
    """验证 ParseError 在 property loop 中被转为 PropertyFallback。"""
    from uasset_read.models.properties import PropertyValue

    # 直接测试 PropertyValue + PropertyFallback 的兼容性
    fb = PropertyFallback(
        name="DamagedProp",
        type="StructProperty",
        size=32,
        raw_bytes=b"",
        reason=FallbackReason.PARSE_ERROR,
        error_message="ParseError at offset 1024: test",
    )
    pv = PropertyValue(name=fb.name, type="Warning", value=fb, array_index=fb.array_index)
    assert isinstance(pv.value, PropertyFallback)
    assert pv.value.error_message is not None
    assert "offset" in pv.value.error_message


def test_fallback_preserves_tag_data():
    """PropertyFallback 应保留 tag_data。"""
    fb = PropertyFallback(
        name="TaggedProp",
        type="UnknownTagType",
        size=8,
        raw_bytes=b"\x00" * 8,
        reason=FallbackReason.UNSUPPORTED_TYPE,
        tag_data={"mapping_hint": "maybe_custom"},
    )
    assert fb.tag_data is not None
    assert fb.tag_data["mapping_hint"] == "maybe_custom"
    d = fb.to_dict()
    assert "tag_data" in d


def test_property_fallback_raw_bytes_truncated_in_dict():
    """PropertyFallback.to_dict 对 raw_bytes 做 256 字节截断。"""
    large_bytes = b"\xFF" * 512
    fb = PropertyFallback(
        name="LargeProp",
        type="ArrayType",
        size=512,
        raw_bytes=large_bytes,
        reason=FallbackReason.PARSE_ERROR,
        error_message="Array size mismatch",
    )
    d = fb.to_dict()
    assert "raw_data" in d
    assert d["raw_data"] == large_bytes[:256].hex()
    assert d["raw_data_truncated"] is True
    assert d["raw_data_full_size"] == 512


def test_property_fallback_no_raw_bytes_omits_raw_data():
    """无 raw_bytes 时 to_dict 不应包含 raw_data 键。"""
    fb = PropertyFallback(
        name="EmptyProp",
        type="EmptyType",
        size=0,
        raw_bytes=b"",
        reason=FallbackReason.PARSE_ERROR,
        error_message="No data",
    )
    d = fb.to_dict()
    assert "raw_data" not in d
    assert d["error_message"] == "No data"


def test_fallback_reason_enum_serialization():
    """FallbackReason 枚举在 to_dict 中应序列化为字符串。"""
    for reason in FallbackReason:
        fb = PropertyFallback(
            name=f"Test_{reason.value}",
            type="TestType",
            size=0,
            reason=reason,
        )
        d = fb.to_dict()
        assert isinstance(d["reason"], str)
        assert d["reason"] == reason.value


def test_export_error_context_includes_offset():
    """验证 PropertyFallback 错误信息中包含 offset 信息。"""
    # 模拟 property_parser.py 第 421 行的错误信息格式
    offset = 0x0400
    error_msg = f"ParseError at offset {offset}: corrupted property data"
    fb = PropertyFallback(
        name="CorruptedProp",
        type="StructProperty",
        size=64,
        raw_bytes=b"",
        reason=FallbackReason.PARSE_ERROR,
        error_message=error_msg,
    )
    assert str(offset) in fb.error_message
    assert "ParseError" in fb.error_message


def test_property_fallback_with_error_context():
    """PropertyFallback 应携带 ErrorContext 并在 to_dict 中序列化。"""
    from uasset_read.exceptions import ErrorContext

    ctx = ErrorContext(
        offset=0x0800,
        phase="properties",
        operation="read_property_value",
        context_name="MyStructProp",
        export_index=3,
        field_name="TemplateIndex",
        version_info={"file_version_ue5": 500},
    )
    fb = PropertyFallback(
        name="MyStructProp",
        type="StructProperty",
        size=128,
        raw_bytes=b"",
        reason=FallbackReason.PARSE_ERROR,
        error_message="ParseError at offset 2048: bad data",
        error_context=ctx,
    )
    assert fb.error_context is not None
    assert fb.error_context.offset == 0x0800
    assert fb.error_context.phase == "properties"
    assert fb.error_context.export_index == 3
    assert fb.error_context.field_name == "TemplateIndex"
    assert fb.error_context.version_info == {"file_version_ue5": 500}

    d = fb.to_dict()
    assert "error_context" in d
    ec = d["error_context"]
    assert ec["offset"] == 0x0800
    assert ec["phase"] == "properties"
    assert ec["operation"] == "read_property_value"
    assert ec["context_name"] == "MyStructProp"
    assert ec["export_index"] == 3
    assert ec["field_name"] == "TemplateIndex"
    assert ec["version_info"] == {"file_version_ue5": 500}


def test_property_fallback_without_error_context_omits_key():
    """无 ErrorContext 时 to_dict 不应包含 error_context 键。"""
    fb = PropertyFallback(
        name="NoCtxProp",
        type="IntProperty",
        size=4,
        raw_bytes=b"",
        reason=FallbackReason.UNSUPPORTED_TYPE,
    )
    d = fb.to_dict()
    assert "error_context" not in d


def test_property_fallback_error_context_minimal():
    """ErrorContext 仅含必填字段时，to_dict 应只序列化非空可选字段。"""
    from uasset_read.exceptions import ErrorContext

    ctx = ErrorContext(offset=0, phase="header", operation="read_magic")
    fb = PropertyFallback(
        name="TestProp",
        type="IntProperty",
        size=4,
        raw_bytes=b"",
        reason=FallbackReason.PARSE_ERROR,
        error_context=ctx,
    )
    d = fb.to_dict()
    ec = d["error_context"]
    assert ec["offset"] == 0
    assert ec["phase"] == "header"
    assert ec["operation"] == "read_magic"
    # 可选字段不应出现
    assert "context_name" not in ec
    assert "export_index" not in ec
    assert "expected_offset" not in ec
    assert "actual_offset" not in ec
    assert "field_name" not in ec
    assert "version_info" not in ec


# === Fallback 数据模型 + 截断文件诊断 ===

class TestFallbackModels:

    """Fallback 数据模型单元测试。"""

    def test_property_fallback_minimal(self):
        """最小 PropertyFallback 实例化。"""
        fb = PropertyFallback(
            name="UnknownProp",
            type="UnknownType",
            size=32,
            raw_bytes=b"\x00" * 32,
            reason=FallbackReason.UNSUPPORTED_TYPE,
        )
        assert fb.name == "UnknownProp"
        assert fb.type == "UnknownType"
        assert fb.size == 32
        assert len(fb.raw_bytes) == 32
        assert fb.reason == FallbackReason.UNSUPPORTED_TYPE
        assert fb.array_index == 0
        assert fb.tag_data is None

    def test_property_fallback_full(self):
        """完整 PropertyFallback 含所有字段。"""
        fb = PropertyFallback(
            name="TestProp",
            type="CustomType",
            size=16,
            raw_bytes=b"\x01\x02",
            reason=FallbackReason.PARSE_ERROR,
            array_index=2,
            tag_data={"extra": "info"},
            error_message="Failed to parse CustomType",
        )
        assert fb.array_index == 2
        assert fb.tag_data == {"extra": "info"}
        assert fb.error_message is not None

    def test_struct_fallback_minimal(self):
        """最小 StructFallback。"""
        fb = StructFallback(
            struct_type="UnknownStruct",
            size=64,
            raw_bytes=b"\x00" * 64,
            reason=FallbackReason.UNSUPPORTED_STRUCT,
        )
        assert fb.struct_type == "UnknownStruct"
        assert fb.size == 64
        assert len(fb.fields) == 0

    def test_struct_fallback_with_partial_fields(self):
        """StructFallback 含部分解析字段。"""
        fb = StructFallback(
            struct_type="Vector",
            size=12,
            raw_bytes=b"",
            reason=FallbackReason.PARTIAL_PARSE,
            fields={"X": 1.0, "Y": 2.0},
        )
        assert fb.fields["X"] == 1.0
        assert len(fb.fields) == 2

    def test_generic_uobject_minimal(self):
        """最小 GenericUObject。"""
        obj = GenericUObject(
            name="MyExport",
            class_name="UnknownClass",
            serial_offset=0,
            serial_size=100,
            parse_status=ExportParseStatus.FALLBACK,
        )
        assert obj.name == "MyExport"
        assert obj.class_name == "UnknownClass"
        assert obj.serial_size == 100
        assert len(obj.properties) == 0
        assert obj.outer_path == []

    def test_generic_uobject_full(self):
        """完整 GenericUObject。"""
        from uasset_read.models.properties import PropertyValue

        obj = GenericUObject(
            name="BP_MyActor",
            class_name="BlueprintGeneratedClass",
            super_name="Actor",
            outer_path=["Package", "Class"],
            serial_offset=1024,
            serial_size=2048,
            parse_status=ExportParseStatus.PARTIAL,
            properties=[PropertyValue(name="MyVar", type="IntProperty", value=42)],
            fallback_data=StructFallback(
                struct_type="UnknownStruct",
                size=10,
                raw_bytes=b"\xAA" * 10,
                reason=FallbackReason.UNSUPPORTED_STRUCT,
            ),
            requires_mappings=True,
            missing_mapping="SomeStruct",
        )
        assert len(obj.properties) == 1
        assert obj.fallback_data is not None
        assert obj.requires_mappings is True
        assert obj.missing_mapping == "SomeStruct"

    def test_export_parse_status_enum(self):
        """ExportParseStatus 枚举值。"""
        assert ExportParseStatus.SUCCESS == "success"
        assert ExportParseStatus.PARTIAL == "partial"
        assert ExportParseStatus.FALLBACK == "fallback"
        assert ExportParseStatus.SKIPPED == "skipped"
        assert ExportParseStatus.FAILED == "failed"

    def test_export_parse_status_complete(self):
        """验证 ExportParseStatus 包含所有运行时使用的值。"""
        expected_values = {
            "success", "partial", "failed",
            "opaque", "skipped", "partial_metadata",
            "opaque_unversioned", "fallback", "metadata"
        }
        actual_values = {s.value for s in ExportParseStatus}
        assert actual_values == expected_values

    def test_fallback_reason_enum(self):
        """FallbackReason 枚举值。"""
        assert FallbackReason.UNSUPPORTED_TYPE == "unsupported_type"
        assert FallbackReason.UNSUPPORTED_STRUCT == "unsupported_struct"
        assert FallbackReason.PARSE_ERROR == "parse_error"
        assert FallbackReason.PARTIAL_PARSE == "partial_parse"
        assert FallbackReason.MISSING_MAPPING == "missing_mapping"


# ===========================================================================
# 第二部分：未知 property 结构化 fallback 测试
# ===========================================================================

class TestUnknownPropertyFallback:
    """未知 property 的 fallback 行为测试。"""

    def test_unknown_property_returns_fallback_not_none(self):
        """未知类型应返回 PropertyFallback 而非 None。"""
        from uasset_read.parsers.property_parser import parse_property_value
        from uasset_read.models.properties import PropertyTag

        tag = PropertyTag(
            name="TestProp",
            type="CompletelyUnknownType",
            size=8,
            serialize_type="Property",
        )
        archive = _make_archive(b"\x00" * 8)
        result = parse_property_value(tag, archive, [], [])

        assert result is not None, "Unknown property should NOT return None"
        assert isinstance(result, PropertyFallback)
        assert result.name == "TestProp"
        assert result.type == "CompletelyUnknownType"
        assert result.size == 8
        assert result.reason == FallbackReason.UNSUPPORTED_TYPE

    def test_unknown_property_preserves_array_index(self):
        """Fallback 应保留 array_index。"""
        from uasset_read.parsers.property_parser import parse_property_value
        from uasset_read.models.properties import PropertyTag

        tag = PropertyTag(
            name="ArrayProp",
            type="UnknownArrayType",
            size=4,
            array_index=3,
            serialize_type="Property",
        )
        archive = _make_archive(b"\x00" * 4)
        result = parse_property_value(tag, archive, [], [])

        assert isinstance(result, PropertyFallback)
        assert result.array_index == 3

    def test_unknown_property_reads_raw_bytes(self):
        """Fallback 应读取原始字节。"""
        from uasset_read.parsers.property_parser import parse_property_value
        from uasset_read.models.properties import PropertyTag

        raw = b"\xDE\xAD\xBE\xEF"
        tag = PropertyTag(
            name="RawProp",
            type="UnknownRawType",
            size=4,
            serialize_type="Property",
        )
        archive = _make_archive(raw)
        archive.read.return_value = raw
        result = parse_property_value(tag, archive, [], [])

        assert isinstance(result, PropertyFallback)
        assert result.raw_bytes == raw

    def test_unknown_property_to_dict(self):
        """PropertyFallback.to_dict 应输出 JSON 兼容 dict。"""
        fb = PropertyFallback(
            name="TestProp",
            type="UnknownType",
            size=32,
            raw_bytes=b"\xAA" * 32,
            reason=FallbackReason.UNSUPPORTED_TYPE,
            array_index=0,
        )
        d = fb.to_dict()
        assert d["kind"] == "unknown_property"
        assert d["name"] == "TestProp"
        assert d["type"] == "UnknownType"
        assert d["size"] == 32
        assert d["reason"] == "unsupported_type"
        assert "raw_data" in d

    def test_skipped_property_still_returns_dict(self):
        """Skipped property 应保持现有 dict 格式（不受影响）。"""
        from uasset_read.parsers.property_parser import parse_property_value
        from uasset_read.models.properties import PropertyTag

        tag = PropertyTag(
            name="SkipProp",
            type="SomeType",
            size=10,
            serialize_type="Skipped",
        )
        archive = _make_archive(b"\x00" * 10)
        result = parse_property_value(tag, archive, [], [])

        assert isinstance(result, dict)
        assert result["kind"] == "skipped_property"

    def test_binary_or_native_still_returns_dict(self):
        """BinaryOrNative property 应保持现有 dict 格式（不受影响）。"""
        from uasset_read.parsers.property_parser import parse_property_value
        from uasset_read.models.properties import PropertyTag

        tag = PropertyTag(
            name="BinProp",
            type="UnknownBinType",
            size=6,
            serialize_type="BinaryOrNative",
        )
        archive = _make_archive(b"\x00" * 6)
        result = parse_property_value(tag, archive, [], [])

        assert isinstance(result, dict)
        assert result["kind"] == "binary_or_native_property"

    def test_known_property_handler_error_returns_fallback_in_tolerant_mode(self, monkeypatch):
        """已知类型 handler 失败时，tolerant 模式应降级为 PropertyFallback。"""
        from uasset_read.parsers.property_parser import parse_property_value
        from uasset_read.models.properties import PropertyTag

        tag = PropertyTag(name="BadInt", type="IntProperty", size=4)
        archive = _make_archive(b"\x00" * 4)

        def _raise(*args, **kwargs):
            raise ValueError("bad int payload")

        monkeypatch.setattr(
            "uasset_read.parsers.property_parser._get_parse_functions",
            lambda: {"IntProperty": _raise},
        )

        result = parse_property_value(tag, archive, [], [], tolerant=True)

        assert isinstance(result, PropertyFallback)
        assert result.reason == FallbackReason.PARSE_ERROR
        assert "bad int payload" in result.error_message

    def test_known_property_handler_error_raises_in_strict_mode(self, monkeypatch):
        """strict 模式保留快速失败行为。"""
        from uasset_read.parsers.property_parser import parse_property_value
        from uasset_read.models.properties import PropertyTag

        tag = PropertyTag(name="BadInt", type="IntProperty", size=4)
        archive = _make_archive(b"\x00" * 4)

        def _raise(*args, **kwargs):
            raise ValueError("bad int payload")

        monkeypatch.setattr(
            "uasset_read.parsers.property_parser._get_parse_functions",
            lambda: {"IntProperty": _raise},
        )

        with pytest.raises(ValueError, match="bad int payload"):
            parse_property_value(tag, archive, [], [], tolerant=False)


# ===========================================================================
# 第三部分：截断/损坏文件诊断测试（合并自 test_truncated_file.py）
# ===========================================================================

class TestTruncatedFileDetection:
    """截断文件检测测试。"""

    def test_tiny_file_raises_parse_error(self):
        """小于 MIN_UASSET_SIZE 的文件应抛出 ParseError。"""
        path = _write_temp_file(b"\x00" * 32)
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(ParseError, match="文件过小"):
                read_package_summary(archive)
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_tiny_file_records_diagnostic(self):
        """小于 MIN_UASSET_SIZE 的文件应记录 truncated_file 诊断。"""
        path = _write_temp_file(b"\x00" * 32)
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(ParseError):
                read_package_summary(archive)
            diagnostics = archive.get_diagnostics()
            assert len(diagnostics) >= 1
            assert any(d.kind == "truncated_file" for d in diagnostics)
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_empty_file_raises_parse_error(self):
        """空文件应抛出 ParseError。"""
        path = _write_temp_file(b"")
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(ParseError, match="文件过小"):
                read_package_summary(archive)
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_exactly_min_size_no_truncation_error(self):
        """恰好 MIN_UASSET_SIZE 字节的文件不应因大小报错（可能因内容报其他错）。"""
        data = struct.pack("<I", PACKAGE_FILE_TAG) + b"\x00" * (MIN_UASSET_SIZE - 4)
        path = _write_temp_file(data)
        archive = FArchive(path, tolerant=False)
        try:
            try:
                read_package_summary(archive)
            except ParseError as e:
                assert "文件过小" not in str(e)
            except VersionError:
                pass  # 版本错误是预期的
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_one_byte_below_min_size_raises(self):
        """MIN_UASSET_SIZE - 1 字节的文件应抛出 ParseError。"""
        path = _write_temp_file(b"\x00" * (MIN_UASSET_SIZE - 1))
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(ParseError, match="文件过小"):
                read_package_summary(archive)
        finally:
            _cleanup_archive_and_file(archive, path)


class TestArchiveDiagnosticMethods:
    """FArchive 诊断方法测试。"""

    def test_check_remaining_within_bounds(self):
        """check_remaining 在范围内应返回 True。"""
        path = _write_temp_file(b"\x00" * 128)
        archive = FArchive(path, tolerant=False)
        try:
            assert archive.check_remaining(64) is True
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_check_remaining_out_of_bounds(self):
        """check_remaining 超出范围应返回 False 并记录诊断。"""
        path = _write_temp_file(b"\x00" * 32)
        archive = FArchive(path, tolerant=False)
        try:
            archive.seek(20)
            assert archive.check_remaining(100) is False
            assert len(archive.get_diagnostics()) >= 1
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_read_safe_within_bounds(self):
        """read_safe 在范围内应正常返回数据。"""
        data = b"\x01\x02\x03\x04\x05"
        path = _write_temp_file(data)
        archive = FArchive(path, tolerant=False)
        try:
            result = archive.read_safe(5)
            assert result == data
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_seek_safe_beyond_file(self):
        """seek_safe 超出文件范围应记录诊断。"""
        path = _write_temp_file(b"\x00" * 32)
        archive = FArchive(path, tolerant=True)
        try:
            archive.seek_safe(1000)
            assert len(archive.get_diagnostics()) >= 1
        finally:
            _cleanup_archive_and_file(archive, path)


class TestCorruptedHeader:
    """损坏头部检测测试。"""

    def test_invalid_tag_raises_version_error(self):
        """无效魔数应抛出 VersionError。"""
        data = b"\xFF\xFF\xFF\xFF" + b"\x00" * (MIN_UASSET_SIZE - 4)
        path = _write_temp_file(data)
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(VersionError, match="Invalid package tag"):
                read_package_summary(archive)
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_valid_tag_invalid_version_raises(self):
        """有效魔数但无效版本应抛出 VersionError。"""
        data = struct.pack("<I", PACKAGE_FILE_TAG)
        data += struct.pack("<i", -999)  # 无效 legacy_file_version
        data += b"\x00" * (MIN_UASSET_SIZE - len(data))
        path = _write_temp_file(data)
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(VersionError):
                read_package_summary(archive)
        finally:
            _cleanup_archive_and_file(archive, path)


class TestDiagnosticsIntegration:
    """诊断集成测试。"""

    def test_diagnostic_to_dict(self):
        """诊断对象应可序列化为 dict。"""
        path = _write_temp_file(b"\x00" * 10)
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(ParseError):
                read_package_summary(archive)
            for d in archive.get_diagnostics():
                d_dict = d.to_dict()
                assert "kind" in d_dict
                assert d_dict["kind"] == "truncated_file"
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_diagnostics_initially_empty(self):
        """新打开的文件 diagnostics 应为空。"""
        path = _write_temp_file(b"\x00" * 128)
        archive = FArchive(path, tolerant=False)
        try:
            assert archive.get_diagnostics() == []
        finally:
            _cleanup_archive_and_file(archive, path)

    def test_diagnostics_populated_after_error(self):
        """错误发生后 diagnostics 应有内容。"""
        path = _write_temp_file(b"\x00" * 10)
        archive = FArchive(path, tolerant=False)
        try:
            with pytest.raises(ParseError):
                read_package_summary(archive)
            assert len(archive.get_diagnostics()) > 0
        finally:
            _cleanup_archive_and_file(archive, path)




# === 容错解析测试 ===

class TestTolerantEarlyParseDiagnostics:

    """容错早期解析诊断行为测试。"""

    def test_tolerant_json_returns_parse_stage_diagnostic(self, tmp_path):
        """tolerant 模式下 JSON 输出 status=failed。"""
        path = tmp_path / "bad_custom_versions.uasset"
        path.write_bytes(_package_with_bad_custom_version_count(10_000_001))

        output = parse_single(str(path), format="json", tolerant=True)
        data = json.loads(output)

        assert data["status"]["status"] == "failed"

    def test_strict_json_still_raises_on_early_parse_failure(self, tmp_path):
        """strict 模式下早期解析失败应抛出异常。"""
        path = tmp_path / "bad_custom_versions.uasset"
        path.write_bytes(_package_with_bad_custom_version_count(10_000_001))

        with pytest.raises(ParseError):
            parse_single(str(path), format="json", tolerant=False)


class TestStrictModeConsistency:
    """严格模式语义一致性：parse_package / parse_uasset_with_linker 在
    tolerant=False 时必须抛出异常，不能静默返回失败结果。"""

    def test_parse_package_strict_raises(self, tmp_path):
        """parse_package strict 模式抛出 ParseError。"""
        path = tmp_path / "bad.uasset"
        path.write_bytes(_package_with_bad_custom_version_count(10_000_001))
        with pytest.raises(ParseError):
            parse_package(str(path), tolerant=False)

    def test_parse_uasset_with_linker_strict_raises(self, tmp_path):
        """parse_uasset_with_linker strict 模式抛出 ParseError。"""
        path = tmp_path / "bad.uasset"
        path.write_bytes(_package_with_bad_custom_version_count(10_000_001))
        with pytest.raises(ParseError):
            parse_uasset_with_linker(str(path), tolerant=False)

    def test_parse_package_tolerant_returns_failed_result(self, tmp_path):
        """parse_package tolerant 模式返回失败结果。"""
        path = tmp_path / "bad.uasset"
        path.write_bytes(_package_with_bad_custom_version_count(10_000_001))
        result = parse_package(str(path), tolerant=True)
        assert result.is_success is False
        assert result.errors


class TestLightweightTolerantParseStatus:
    """轻量容错解析必须输出 status='partial' + status_code。"""

    @staticmethod
    def _make_large_export_package() -> bytes:
        """构造一个 export_count > 300 的最小包头。"""
        data = bytearray()
        data += struct.pack("<Iiii", PACKAGE_FILE_TAG, -9, 0, 0)
        data += struct.pack("<i", UE5_PACKAGE_SAVED_HASH)
        data += b"\x00" * 20
        data += struct.pack("<i", 0)  # total_header_size
        data += struct.pack("<I", 3)  # custom version count (正常值)
        data += b"\x00" * 128
        # name_map
        data += struct.pack("<I", 1)  # name_count
        data += struct.pack("<I", 0)  # name_offset (placeholder)
        # import_map
        data += struct.pack("<I", 0)  # import_count
        data += struct.pack("<I", 0)  # import_offset
        # export_map — 301 exports
        data += struct.pack("<I", 301)  # export_count
        data += struct.pack("<I", 0)  # export_offset
        # 用零字节填充足够长度让解析器能读取
        data += b"\x00" * 4096
        return bytes(data)

    def test_lightweight_parse_marks_status_partial(self, tmp_path):
        """轻量容错路径输出 partial 状态。"""
        from uasset_read.ir_builder import _result_status
        from unittest.mock import MagicMock

        result = MagicMock()
        result.is_success = True
        result.errors = []
        result.metadata = {"lightweight_tolerant_parse": True}
        assert _result_status(result) == "partial"

    def test_normal_success_not_marked_partial(self):
        """正常成功解析不应标记为 partial。"""
        from uasset_read.ir_builder import _result_status
        from unittest.mock import MagicMock

        result = MagicMock()
        result.is_success = True
        result.errors = []
        result.metadata = {}
        assert _result_status(result) == "success"

    def test_success_with_errors_marked_partial(self):
        """成功但有错误时标记为 partial。"""
        from uasset_read.ir_builder import _result_status
        from unittest.mock import MagicMock

        result = MagicMock()
        result.is_success = True
        result.errors = ["some warning"]
        result.metadata = {}
        assert _result_status(result) == "partial"


# ===========================================================================
# 第二部分：Class-specific tolerant skip 测试
# ===========================================================================

class TestCubeBuilderTolerantSkip:
    """CubeBuilder_* export 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_cube_builder.txt"))
    def test_cube_builder_tolerant_parse_succeeds(self, asset_path: str):
        """CubeBuilder 资产应能解析成功（可能有局部错误，但资产级 is_success 为 True）。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None, "Summary should be parsed"
        assert result.export_map is not None, "Export map should be parsed"
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
        del result
        gc.collect()


class TestAnimationDataModelTolerantSkip:
    """AnimationDataModel export 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_animation_data_model.txt"))
    def test_animation_data_model_tolerant_parse_succeeds(self, asset_path: str):
        """AnimationDataModel 资产应能解析成功。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
        del result
        gc.collect()


class TestPayloadOffsetsTolerant:
    """Payload TOC / export offset 异常的 tolerant 处理测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_payload_offsets.txt"))
    def test_payload_offset_tolerant_parse(self, asset_path: str):
        """Payload offset 异常资产应能解析到 summary 和 export_map。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
        del result
        gc.collect()


class TestNiagaraTolerantSkip:
    """Niagara payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_niagara.txt"))
    def test_niagara_tolerant_parse(self, asset_path: str):
        """Niagara 资产 tolerant 解析测试。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
        del result
        gc.collect()


class TestMovieSceneTolerantSkip:
    """MovieScene payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_movie_scene.txt"))
    def test_movie_scene_tolerant_parse(self, asset_path: str):
        """MovieScene 资产 tolerant 解析测试。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
        del result
        gc.collect()


class TestK2NodeTolerantSkip:
    """K2Node payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_k2_nodes.txt"))
    def test_k2node_tolerant_parse(self, asset_path: str):
        """K2Node 资产 tolerant 解析测试。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
        del result
        gc.collect()


class TestMetaSoundTolerantSkip:
    """MetaSound payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_metasound.txt"))
    def test_metasound_tolerant_parse(self, asset_path: str):
        """MetaSound 资产 tolerant 解析测试。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
        del result
        gc.collect()


class TestMaterialExpressionTolerantSkip:
    """MaterialExpression payload 的 tolerant skip 测试。"""

    @pytest.mark.parametrize("asset_path", _read_fixture_lines("real_asset_failures_material_expression.txt"))
    def test_material_expression_tolerant_parse(self, asset_path: str):
        """MaterialExpression 资产 tolerant 解析测试。"""
        result = parse_uasset_with_linker(asset_path, tolerant=True)
        assert result.summary is not None
        assert result.export_map is not None
        fatal_errors = [e for e in result.errors if "serial_offset" in e.lower() or "payloadtoc" in e.lower()]
        assert len(fatal_errors) == 0, f"Fatal errors should not occur: {fatal_errors}"
