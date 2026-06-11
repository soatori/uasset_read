"""Task 11: IoStore chunk 元数据上限测试"""
import pytest
from unittest.mock import Mock
from uasset_read.iostore.reader import IoStoreReader
from uasset_read.iostore.structures import FIoStoreTocHeader
from uasset_read.exceptions import ParseError


def test_load_chunk_ids_exceeds_limit():
    """测试 _load_chunk_ids 超过 MAX_CHUNK_COUNT 时抛出 ParseError"""
    reader = IoStoreReader("dummy.utoc")
    reader._utoc_file = Mock()
    reader._header = Mock()
    reader._header.toc_entry_count = 6_000_000  # 超过 5_000_000 限制

    with pytest.raises(ParseError, match="chunk count.*exceeds limit"):
        reader._load_chunk_ids()


def test_load_chunk_offsets_exceeds_limit():
    """测试 _load_chunk_offsets 超过 MAX_CHUNK_COUNT 时抛出 ParseError"""
    reader = IoStoreReader("dummy.utoc")
    reader._utoc_file = Mock()
    reader._header = Mock()
    reader._header.toc_entry_count = 6_000_000  # 超过 5_000_000 限制

    with pytest.raises(ParseError, match="chunk count.*exceeds limit"):
        reader._load_chunk_offsets()


def test_load_chunk_ids_within_limit():
    """测试 _load_chunk_ids 在限制内正常工作"""
    reader = IoStoreReader("dummy.utoc")
    reader._utoc_file = Mock()
    reader._header = Mock()
    reader._header.toc_entry_count = 100  # 在限制内

    # Mock 读取数据
    reader._utoc_file.read.return_value = b'\x00' * 12

    # 应该正常执行不抛出异常
    reader._load_chunk_ids()
    assert len(reader._chunk_ids) == 100
