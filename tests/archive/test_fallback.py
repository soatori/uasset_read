"""Fallback / 截断文件 / serialize_bits 综合测试 — 合并自以下测试文件：
- test_fallback_models.py / test_unknown_property_fallback.py — Fallback 数据模型与未知 property fallback
- test_truncated_file.py — 截断/损坏文件诊断功能
- test_archive_serialize_bits.py — archive.py 内联 import 和 serialize_bits 修复 (#246)
"""
from __future__ import annotations

import ast
import io
import os
import struct
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from uasset_read.archive import FArchive
from uasset_read.constants import MIN_UASSET_SIZE, PACKAGE_FILE_TAG
from uasset_read.exceptions import ParseError, VersionError
from uasset_read.models.fallback import (
    PropertyFallback,
    StructFallback,
    GenericUObject,
    ExportParseStatus,
    FallbackReason,
)
from uasset_read.serializers.package_summary import read_package_summary


ARCHIVE_PATH = Path(__file__).resolve().parent.parent.parent / "src" / "uasset_read" / "archive.py"


def _write_temp_file(data: bytes, suffix: str = ".uasset") -> str:
    """创建临时文件并返回路径。"""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, data)
    os.close(fd)
    return path


def _cleanup_archive_and_file(archive, path):
    """安全关闭 archive 并删除临时文件。"""
    try:
        archive.close()
    except Exception:
        pass
    try:
        os.unlink(path)
    except (PermissionError, OSError):
        pass


def _make_archive(data: bytes):
    """创建 mock FArchive。"""
    buf = io.BytesIO(data)
    archive = MagicMock(spec=FArchive)
    archive.read.return_value = data
    archive.tell.return_value = 0
    archive.seek.return_value = None
    archive.total_size.return_value = len(data) + 100
    return archive


# ===========================================================================
# 第一部分：Fallback 数据模型测试
# ===========================================================================

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


# ===========================================================================
# 第四部分：archive.py 内联 import 和 serialize_bits 修复测试（合并自 test_archive_serialize_bits.py）
# ===========================================================================

class TestNoInlineImports:
    """验证 archive.py 不包含函数体内的内联 import。"""

    @pytest.fixture(autouse=True)
    def _parse_archive(self):
        self._source = ARCHIVE_PATH.read_text(encoding="utf-8")
        self._tree = ast.parse(self._source)

    def _function_body_imports(self, module: ast.Module) -> list[tuple[str, int]]:
        """收集所有函数/方法体内的 import 语句。"""
        results = []
        for node in ast.walk(module):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if isinstance(child, ast.Import):
                        for alias in child.names:
                            results.append((alias.name, child.lineno))
                    elif isinstance(child, ast.ImportFrom):
                        if child.module:
                            results.append((child.module, child.lineno))
        return results

    def test_no_inline_import_struct(self):
        """函数体内不应有 `import struct`。"""
        body_imports = self._function_body_imports(self._tree)
        struct_imports = [(n, l) for n, l in body_imports if n == "struct"]
        assert not struct_imports, (
            f"发现内联 `import struct`（应移至模块顶部）: {struct_imports}"
        )

    def test_no_inline_import_math(self):
        """函数体内不应有 `import math`。"""
        body_imports = self._function_body_imports(self._tree)
        math_imports = [(n, l) for n, l in body_imports if n == "math"]
        assert not math_imports, (
            f"发现内联 `import math`（应移至模块顶部）: {math_imports}"
        )

    def test_no_inline_import_os(self):
        """函数体内不应有 `__import__('os')`。"""
        source = self._source
        assert "__import__('os')" not in source and '__import__("os")' not in source, (
            "发现内联 `__import__('os')`（应改为模块顶部 `import os`）"
        )

    def test_module_level_struct_import(self):
        """模块顶部应有 `import struct`。"""
        module_imports = []
        for node in ast.iter_child_nodes(self._tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_imports.append(alias.name)
        assert "struct" in module_imports, "模块顶部缺少 `import struct`"

    def test_module_level_os_import(self):
        """模块顶部应有 `import os`。"""
        module_imports = []
        for node in ast.iter_child_nodes(self._tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_imports.append(alias.name)
        assert "os" in module_imports, "模块顶部缺少 `import os`"


class TestSerializeBits:
    """验证 serialize_bits 序列化行为与 UE FArchive::SerializeBits 一致。"""

    @pytest.fixture()
    def archive_le(self):
        """创建 LE 模式 ByteArchive。"""
        from uasset_read.archive import ByteArchive
        return ByteArchive(b'\x00' * 256)

    @pytest.fixture()
    def archive_be(self):
        """创建 BE 模式 ByteArchive。"""
        from uasset_read.archive import ByteArchive
        ar = ByteArchive(b'\x00' * 256)
        ar.set_byte_swapping(True)
        return ar

    def test_byte_count_8_bits(self, archive_le):
        """8 bits → 1 byte。"""
        result = archive_le.serialize_bits(0xFF, 8)
        assert len(result) == 1

    def test_byte_count_9_bits(self, archive_le):
        """9 bits → 2 bytes（向上取整）。"""
        result = archive_le.serialize_bits(0x1FF, 9)
        assert len(result) == 2

    def test_byte_count_1_bit(self, archive_le):
        """1 bit → 1 byte。"""
        result = archive_le.serialize_bits(1, 1)
        assert len(result) == 1

    def test_byte_count_16_bits(self, archive_le):
        """16 bits → 2 bytes。"""
        result = archive_le.serialize_bits(0xFFFF, 16)
        assert len(result) == 2

    def test_byte_count_32_bits(self, archive_le):
        """32 bits → 4 bytes。"""
        result = archive_le.serialize_bits(0xFFFFFFFF, 32)
        assert len(result) == 4

    def test_value_correctness_le(self, archive_le):
        """LE 模式：值应以小端序编码。"""
        result = archive_le.serialize_bits(0x0102, 16)
        assert result == b'\x02\x01'

    def test_value_correctness_be(self, archive_be):
        """BE 模式：值应以大端序编码。"""
        result = archive_be.serialize_bits(0x0102, 16)
        assert result == b'\x01\x02'

    def test_value_truncation_non_aligned(self, archive_le):
        """非字节对齐位数：高位应被截断（UE bitmask 行为）。

        UE FArchive::SerializeBits 在加载时执行:
            ((uint8*)V)[LengthBits / 8] &= ((1 << (LengthBits & 7)) - 1)

        对于 3 bits，mask = (1 << 3) - 1 = 0x07。
        值 0xFF 应被截断为 0x07（仅保留低 3 位）。
        """
        result = archive_le.serialize_bits(0xFF, 3)
        # 1 byte, 值应为 0xFF & 0x07 = 0x07
        assert result == b'\x07'

    def test_value_5_bits(self, archive_le):
        """5 bits: mask = 0x1F。"""
        result = archive_le.serialize_bits(0xFF, 5)
        assert result == b'\x1F'

    def test_value_1_bit_true(self, archive_le):
        """1 bit 值为 1。"""
        result = archive_le.serialize_bits(1, 1)
        assert result == b'\x01'

    def test_value_1_bit_zero(self, archive_le):
        """1 bit 值为 0。"""
        result = archive_le.serialize_bits(0, 1)
        assert result == b'\x00'

    def test_value_zero(self, archive_le):
        """全零值。"""
        result = archive_le.serialize_bits(0, 8)
        assert result == b'\x00'

    def test_no_math_dependency(self):
        """serialize_bits 不应依赖 math 模块（用整数除法替代）。"""
        from uasset_read.archive import ByteArchive
        # 确保方法可正常调用（不抛 ImportError）
        ar = ByteArchive(b'\x00' * 16)
        result = ar.serialize_bits(42, 7)
        assert isinstance(result, bytes)
