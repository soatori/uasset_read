"""Fallback 相关测试 — 合并自以下测试文件：
- test_fallback_models.py — Fallback 数据模型（PropertyFallback / StructFallback / GenericUObject）
- test_unknown_property_fallback.py — 未知 property 结构化 fallback
"""
from __future__ import annotations

import io
from unittest.mock import MagicMock

import pytest

from uasset_read.models.fallback import (
    PropertyFallback,
    StructFallback,
    GenericUObject,
    ExportParseStatus,
    FallbackReason,
)


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

def _make_archive(data: bytes):
    """创建 mock FArchive。"""
    from uasset_read.archive import FArchive
    buf = io.BytesIO(data)
    archive = MagicMock(spec=FArchive)
    archive.read.return_value = data
    archive.tell.return_value = 0
    archive.seek.return_value = None
    archive.total_size.return_value = len(data) + 100
    return archive


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
