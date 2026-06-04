"""tests/test_unknown_property_fallback.py — 未知 property 结构化 fallback 测试"""
import io
from unittest.mock import MagicMock

from uasset_read.parsers.property_parser import parse_property_value
from uasset_read.models.properties import PropertyTag
from uasset_read.models.fallback import PropertyFallback, FallbackReason


def _make_archive(data: bytes):
    """创建 mock FArchive"""
    from uasset_read.archive import FArchive
    buf = io.BytesIO(data)
    archive = MagicMock(spec=FArchive)
    archive.read.return_value = data
    archive.tell.return_value = 0
    archive.seek.return_value = None
    archive.total_size.return_value = len(data) + 100
    return archive


def test_unknown_property_returns_fallback_not_none():
    """未知类型应返回 PropertyFallback 而非 None"""
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


def test_unknown_property_preserves_array_index():
    """Fallback 应保留 array_index"""
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


def test_unknown_property_reads_raw_bytes():
    """Fallback 应读取原始字节"""
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


def test_unknown_property_to_dict():
    """PropertyFallback.to_dict 应输出 JSON 兼容 dict"""
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


def test_skipped_property_still_returns_dict():
    """Skipped property 应保持现有 dict 格式（不受影响）"""
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


def test_binary_or_native_still_returns_dict():
    """BinaryOrNative property 应保持现有 dict 格式（不受影响）"""
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
