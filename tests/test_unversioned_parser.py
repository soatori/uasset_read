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
    archive.read_uint16 = MagicMock(side_effect=lambda: int.from_bytes(buf.read(2), 'little'))
    return archive


def test_header_single_keep_fragment():
    """单个 keep 片段 + 终止"""
    # Fragment: keep=3, skip=0, zero=False → raw = (0 << 5) | (3 << 1) | 0 = 6
    # Terminator: keep=0, skip=0, zero=False → raw = 0
    # Validity mask: 0
    data = (0).to_bytes(2, 'little') + (6).to_bytes(2, 'little') + (0).to_bytes(2, 'little')
    archive = _make_archive(data)
    header = read_unversioned_header(archive)
    assert len(header.fragments) == 2  # keep + terminator
    assert header.fragments[0].keep_count == 3
    assert header.fragments[0].skip_count == 0
    assert not header.fragments[0].is_zero


def test_header_skip_keep_sequence():
    """skip=2, keep=1 片段"""
    # skip=2, keep=1, zero=False → raw = (2 << 5) | (1 << 1) | 0 = 66
    # Terminator: 0
    # Validity mask: 0
    data = (0).to_bytes(2, 'little') + (66).to_bytes(2, 'little') + (0).to_bytes(2, 'little')
    archive = _make_archive(data)
    header = read_unversioned_header(archive)
    assert header.fragments[0].skip_count == 2
    assert header.fragments[0].keep_count == 1
    assert not header.fragments[0].is_zero


def test_header_zero_mask():
    """zero flag 设置"""
    # keep=1, zero=True → raw = (0 << 5) | (1 << 1) | 1 = 3
    # Terminator: 0
    data = (0).to_bytes(2, 'little') + (3).to_bytes(2, 'little') + (0).to_bytes(2, 'little')
    archive = _make_archive(data)
    header = read_unversioned_header(archive)
    assert header.fragments[0].is_zero
    assert header.fragments[0].keep_count == 1


def test_parse_with_schema_order():
    """按 schema 顺序解析属性"""
    result = parse_unversioned_properties(
        archive=None,
        header=UnversionedHeader(
            fragments=[UnversionedFragment(keep_count=2)],
            zero_mask=0,
            validity_mask=0,
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
            fragments=[UnversionedFragment(keep_count=1)],
            zero_mask=0,
            validity_mask=0,
        ),
        mapping={},
        schema_order=["UnknownProp"],
    )
    assert result.fidelity == "opaque_missing_mapping"
