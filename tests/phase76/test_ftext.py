"""FText history_type 2-10 解析测试。"""
import struct
import pytest
from pathlib import Path

from uasset_read.archive import FArchive
from uasset_read.parsers.property_types import parse_text_property
from uasset_read.models.properties import PropertyTag, TextValue


def _make_archive(tmp_path: Path, data: bytes) -> FArchive:
    """创建测试用 FArchive（写入临时文件）。"""
    path = tmp_path / "test.bin"
    path.write_bytes(data)
    return FArchive(str(path), tolerant=True)


def _make_tag(size: int) -> PropertyTag:
    """创建测试用 PropertyTag。"""
    tag = PropertyTag.__new__(PropertyTag)
    tag.size = size
    tag.array_index = 0
    return tag


def _pack_fstring(s: str) -> bytes:
    """打包 FString（UE 格式：UTF-8 + null 终止符，长度包含 null）。"""
    if not s:
        return struct.pack('<i', 0)
    encoded = s.encode('utf-8') + b'\x00'
    return struct.pack('<i', len(encoded)) + encoded


def _build_ftext(history_type: int, namespace: str, key: str, source_string: str, extra: bytes = b'') -> bytes:
    """构建 FText 二进制数据。"""
    flags = struct.pack('<i', 0)  # FText flags
    ht = struct.pack('<B', history_type)
    base = _pack_fstring(namespace) + _pack_fstring(key) + _pack_fstring(source_string)
    return flags + ht + base + extra


class TestFTextBase:
    """history_type == 0 (Base) 测试。"""

    def test_base_simple(self, tmp_path):
        data = _build_ftext(0, "NS", "Key", "Hello")
        archive = _make_archive(tmp_path, data)
        tag = _make_tag(len(data))
        result = parse_text_property(tag, archive)
        assert isinstance(result, TextValue)
        assert result.namespace == "NS"
        assert result.key == "Key"
        assert result.source_string == "Hello"


class TestFTextNamedFormat:
    """history_type == 1 (NamedFormat) 测试。"""

    def test_named_format_no_args(self, tmp_path):
        flags = struct.pack('<i', 0)
        ht = struct.pack('<B', 1)
        ns = _pack_fstring("NS")
        key = _pack_fstring("Key")
        args = struct.pack('<i', 0)  # 0 args
        data = flags + ht + ns + key + args
        archive = _make_archive(tmp_path, data)
        tag = _make_tag(len(data))
        result = parse_text_property(tag, archive)
        assert result.namespace == "NS"
        assert result.key == "Key"
        assert result.source_string == ""


class TestFTextOrderedFormat:
    """history_type == 2 (OrderedFormat) 测试。"""

    def test_ordered_format_no_args(self, tmp_path):
        extra = struct.pack('<i', 0)  # 0 args
        data = _build_ftext(2, "NS", "Key", "Source", extra)
        archive = _make_archive(tmp_path, data)
        tag = _make_tag(len(data))
        result = parse_text_property(tag, archive)
        assert result.namespace == "NS"
        assert result.key == "Key"
        assert result.source_string == "Source"

    def test_ordered_format_with_args(self, tmp_path):
        # args: count=1, key="arg0", value="val0"
        args = struct.pack('<i', 1) + _pack_fstring("arg0") + _pack_fstring("val0")
        data = _build_ftext(2, "NS", "Key", "Source", args)
        archive = _make_archive(tmp_path, data)
        tag = _make_tag(len(data))
        result = parse_text_property(tag, archive)
        assert result.namespace == "NS"
        assert result.key == "Key"


class TestFTextArgumentFormat:
    """history_type == 3 (ArgumentFormat) 测试。"""

    def test_argument_format_no_args(self, tmp_path):
        extra = struct.pack('<i', 0)
        data = _build_ftext(3, "NS", "Key", "Source", extra)
        archive = _make_archive(tmp_path, data)
        tag = _make_tag(len(data))
        result = parse_text_property(tag, archive)
        assert result.namespace == "NS"
        assert result.key == "Key"
        assert result.source_string == "Source"


class TestFTextNumberFormats:
    """history_type 4-6 (AsNumber/AsPercent/AsCurrency) 测试。"""

    def test_as_number(self, tmp_path):
        extra = _pack_fstring("123.45")
        data = _build_ftext(4, "NS", "Key", "Source", extra)
        archive = _make_archive(tmp_path, data)
        tag = _make_tag(len(data))
        result = parse_text_property(tag, archive)
        assert result.namespace == "NS"
        assert result.key == "Key"
        assert result.source_string == "Source"

    def test_as_percent(self, tmp_path):
        extra = _pack_fstring("0.75")
        data = _build_ftext(5, "NS", "Key", "Source", extra)
        archive = _make_archive(tmp_path, data)
        tag = _make_tag(len(data))
        result = parse_text_property(tag, archive)
        assert result.namespace == "NS"

    def test_as_currency(self, tmp_path):
        extra = _pack_fstring("USD") + _pack_fstring("99.99")
        data = _build_ftext(6, "NS", "Key", "Source", extra)
        archive = _make_archive(tmp_path, data)
        tag = _make_tag(len(data))
        result = parse_text_property(tag, archive)
        assert result.namespace == "NS"
        assert result.key == "Key"


class TestFTextDateFormats:
    """history_type 7-9 (DateString/TimeString/DateTimeString) 测试。"""

    def test_date_string(self, tmp_path):
        extra = _pack_fstring("2026-05-28")
        data = _build_ftext(7, "NS", "Key", "Source", extra)
        archive = _make_archive(tmp_path, data)
        tag = _make_tag(len(data))
        result = parse_text_property(tag, archive)
        assert result.namespace == "NS"
        assert result.source_string == "Source"

    def test_time_string(self, tmp_path):
        extra = _pack_fstring("14:30:00")
        data = _build_ftext(8, "NS", "Key", "Source", extra)
        archive = _make_archive(tmp_path, data)
        tag = _make_tag(len(data))
        result = parse_text_property(tag, archive)
        assert result.key == "Key"

    def test_datetime_string(self, tmp_path):
        extra = _pack_fstring("2026-05-28T14:30:00")
        data = _build_ftext(9, "NS", "Key", "Source", extra)
        archive = _make_archive(tmp_path, data)
        tag = _make_tag(len(data))
        result = parse_text_property(tag, archive)
        assert result.source_string == "Source"


class TestFTextTransform:
    """history_type == 10 (Transform) 测试。"""

    def test_transform(self, tmp_path):
        extra = _pack_fstring("ToLower")
        data = _build_ftext(10, "NS", "Key", "Source", extra)
        archive = _make_archive(tmp_path, data)
        tag = _make_tag(len(data))
        result = parse_text_property(tag, archive)
        assert result.namespace == "NS"
        assert result.key == "Key"
        assert result.source_string == "Source"


class TestFTextUnknownType:
    """未知 history_type 的降级处理。"""

    def test_unknown_type_skips(self, tmp_path):
        # history_type = 255, 10 bytes of garbage after
        flags = struct.pack('<i', 0)
        ht = struct.pack('<B', 255)
        garbage = b'\xff' * 10
        data = flags + ht + garbage
        archive = _make_archive(tmp_path, data)
        tag = _make_tag(len(data))
        result = parse_text_property(tag, archive)
        assert isinstance(result, TextValue)
        assert result.namespace == ""
        assert result.key == ""
        assert result.source_string == ""
