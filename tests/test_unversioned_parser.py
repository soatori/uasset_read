"""验证 UnversionedProperties 解析模块。"""
import pytest
from io import BytesIO
from uasset_read.parsers.unversioned_parser import (
    read_unversioned_header,
    parse_unversioned_properties,
    UnversionedHeader,
    UnversionedFragment,
    UnversionedPropertyResult,
)


def _make_archive(data: bytes):
    """从字节创建最小 FArchive 替身。"""
    from unittest.mock import MagicMock
    buf = BytesIO(data)
    archive = MagicMock()
    archive.read_u16 = MagicMock(side_effect=lambda: int.from_bytes(buf.read(2), 'little'))
    archive.read_u8 = MagicMock(side_effect=lambda: int.from_bytes(buf.read(1), 'little'))
    archive.read_u32 = MagicMock(side_effect=lambda: int.from_bytes(buf.read(4), 'little'))
    archive.tell = MagicMock(return_value=0)
    return archive


def test_header_single_keep_fragment():
    """单个 keep 片段 + 终止"""
    # Fragment: keep=3, skip=0, zero=False, is_last=True
    # raw = (3 << 9) | 0x0100 = 0x0600 | 0x0100 = 0x0700
    data = (0x0700).to_bytes(2, 'little')  # keep=3, is_last=True
    archive = _make_archive(data)
    header = read_unversioned_header(archive)
    assert len(header.fragments) == 1
    assert header.fragments[0].keep_count == 3
    assert header.fragments[0].skip_count == 0
    assert not header.fragments[0].has_any_zeroes
    assert header.fragments[0].is_last


def test_header_skip_keep_sequence():
    """skip=2, keep=1 片段"""
    # skip=2, keep=1, zero=False, is_last=True
    # raw = (1 << 9) | 0x0100 | (2 << 0) = 0x0200 + 0x0100 + 0x0002 = 0x0302
    data = (0x0302).to_bytes(2, 'little')
    archive = _make_archive(data)
    header = read_unversioned_header(archive)
    assert header.fragments[0].skip_count == 2
    assert header.fragments[0].keep_count == 1
    assert not header.fragments[0].has_any_zeroes
    assert header.fragments[0].is_last


def test_header_zero_mask():
    """zero flag 设置"""
    # keep=1, zero=True (has_any_zeroes), is_last=True
    # raw = (1 << 9) | 0x0100 | 0x0080 = 0x0200 + 0x0100 + 0x0080 = 0x0380
    # zero_mask = 1 (1个零值位)
    data = (0x0380).to_bytes(2, 'little') + (1).to_bytes(1, 'little')
    archive = _make_archive(data)
    header = read_unversioned_header(archive)
    assert header.fragments[0].has_any_zeroes
    assert header.fragments[0].keep_count == 1
    assert header.fragments[0].is_last
    assert header.zero_mask == 1


def test_parse_with_schema_order():
    """按 schema 顺序解析属性"""
    result = parse_unversioned_properties(
        archive=None,
        header=UnversionedHeader(
            fragments=[UnversionedFragment(keep_count=2, is_last=True)],
            zero_mask=0,
            num_zero_bits=0,
        ),
        mapping={"PropA": 4, "PropB": 8},
        schema_order=["PropA", "PropB"],
    )
    assert result.fidelity in ("schema_backed", "partial_size_inferred")


def test_parse_missing_mapping_produces_partial():
    """缺少 mapping 时产生 partial fidelity"""
    result = parse_unversioned_properties(
        archive=None,
        header=UnversionedHeader(
            fragments=[UnversionedFragment(keep_count=1, is_last=True)],
            zero_mask=0,
            num_zero_bits=0,
        ),
        mapping={},
        schema_order=["UnknownProp"],
    )
    assert result.fidelity == "opaque_missing_mapping"
