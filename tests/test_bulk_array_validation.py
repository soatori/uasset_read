"""BulkArray 大小校验测试 — 验证 read_bulk_array 方法的防御性编程。"""
from __future__ import annotations

import pytest

from uasset_read.archive import ByteArchive
from uasset_read.exceptions import ParseError


class TestBulkArraySizeValidation:
    """read_bulk_array 大小校验测试。"""

    def test_bulk_array_valid(self):
        """正常 BulkArray 读取 — 大小匹配。"""
        data = b'\x00' * 20
        archive = ByteArchive(data)
        result = archive.read_bulk_array(element_size=4, element_count=5)
        assert len(result) == 20
        assert result == b'\x00' * 20

    def test_bulk_array_size_mismatch(self):
        """BulkArray 大小不匹配异常 — 文件数据不足。"""
        data = b'\x00' * 10
        archive = ByteArchive(data)
        with pytest.raises(ParseError) as exc_info:
            archive.read_bulk_array(element_size=4, element_count=5)
        assert "size mismatch" in str(exc_info.value).lower() or \
               "Cannot read" in str(exc_info.value)

    def test_bulk_array_zero_elements(self):
        """零元素 BulkArray — 返回空字节。"""
        data = b'\x00' * 10
        archive = ByteArchive(data)
        result = archive.read_bulk_array(element_size=4, element_count=0)
        assert len(result) == 0
        assert result == b''

    def test_bulk_array_single_element(self):
        """单元素 BulkArray。"""
        data = b'\xAB\xCD\xEF\x01'
        archive = ByteArchive(data)
        result = archive.read_bulk_array(element_size=4, element_count=1)
        assert len(result) == 4
        assert result == data

    def test_bulk_array_negative_element_size(self):
        """负数 element_size 抛出 ParseError。"""
        data = b'\x00' * 10
        archive = ByteArchive(data)
        with pytest.raises(ParseError) as exc_info:
            archive.read_bulk_array(element_size=-1, element_count=5)
        assert "element_size" in str(exc_info.value).lower()

    def test_bulk_array_negative_element_count(self):
        """负数 element_count 抛出 ParseError。"""
        data = b'\x00' * 10
        archive = ByteArchive(data)
        with pytest.raises(ParseError) as exc_info:
            archive.read_bulk_array(element_size=4, element_count=-1)
        assert "element_count" in str(exc_info.value).lower()

    def test_bulk_array_advances_position(self):
        """读取后文件位置正确推进。"""
        data = b'\x00' * 30
        archive = ByteArchive(data)
        assert archive.tell() == 0
        archive.read_bulk_array(element_size=4, element_count=5)
        assert archive.tell() == 20

    def test_bulk_array_with_element_size_one(self):
        """element_size=1 时等价于 read(count)。"""
        data = bytes(range(10))
        archive = ByteArchive(data)
        result = archive.read_bulk_array(element_size=1, element_count=10)
        assert result == data
