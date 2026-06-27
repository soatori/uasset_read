"""PackageArchive.read() 边界保护回归测试"""
from __future__ import annotations

import io
import pytest

from uasset_read.package import PackageArchive, ByteArchive
from uasset_read.exceptions import ParseError


def _make_archive(data: bytes) -> PackageArchive:
    """用 ByteArchive 构造一个最小 PackageArchive。"""
    main = ByteArchive("test.uasset", data, tolerant=False)
    return PackageArchive(main, tolerant=False)


def test_read_negative_size_raises():
    """read(-1) 应抛 ParseError 且 tell() 不变。"""
    archive = _make_archive(b"\x00\x01\x02\x03\x04")
    pos_before = archive.tell()
    with pytest.raises(ParseError, match="negative size"):
        archive.read(-1)
    assert archive.tell() == pos_before


def test_read_zero_returns_empty():
    """read(0) 应返回空 bytes，不移动 tell()。"""
    archive = _make_archive(b"\x00\x01\x02")
    result = archive.read(0)
    assert result == b""
    assert archive.tell() == 0


def test_read_normal_returns_data():
    """正常 read 应返回正确数据并推进 tell()。"""
    archive = _make_archive(b"\x00\x01\x02\x03\x04")
    result = archive.read(3)
    assert result == b"\x00\x01\x02"
    assert archive.tell() == 3


def test_read_beyond_eof_raises():
    """read(超过剩余) 应抛 ParseError。"""
    archive = _make_archive(b"\x00\x01")
    with pytest.raises(ParseError, match="Cannot read"):
        archive.read(10)
