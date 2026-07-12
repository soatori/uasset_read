"""IoStore 头部资源限制测试。"""
import io
import pytest

from uasset_read.iostore.reader import IoStoreReader
from uasset_read.exceptions import ParseError


def test_toc_entry_count_too_large():
    """toc_entry_count 超过上限应拒绝。"""
    # 构造一个极小的 utoc 文件，头部声明 10M 条目
    # 我们只测试 _load_chunk_ids 的限制，不需要完整文件
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._utoc_file = io.BytesIO(b"\x00" * 100)
    reader._header = type("FakeHeader", (), {
        "toc_entry_count": 10_000_000,
        "version": 8,
    })()
    reader._chunk_ids = []

    with pytest.raises(ParseError, match="上限"):
        reader._load_chunk_ids()


def test_compression_block_count_too_large():
    """压缩块数量超过上限应拒绝。"""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._utoc_file = io.BytesIO(b"\x00" * 100)
    reader._header = type("FakeHeader", (), {
        "toc_compressed_block_entry_count": 10_000_000,
        "version": 8,
    })()
    reader._compression_blocks = []

    with pytest.raises(ParseError, match="上限"):
        reader._load_compression_blocks()


def test_compression_method_buffer_too_large():
    """压缩方法名缓冲区超过上限应拒绝。"""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._utoc_file = io.BytesIO(b"\x00" * 100)
    reader._header = type("FakeHeader", (), {
        "compression_method_name_count": 100_000,
        "compression_method_name_length": 1000,
        "compression_block_size": 65536,
        "version": 8,
    })()
    reader._compression_methods = ["None"]

    with pytest.raises(ParseError, match="上限"):
        reader._load_compression_methods()


def test_directory_index_size_too_large():
    """目录索引大小超过上限应拒绝。"""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._utoc_file = io.BytesIO(b"\x00" * 100)
    reader._header = type("FakeHeader", (), {
        "version": 8,
        "is_indexed": True,
        "directory_index_size": 500 * 1024 * 1024,  # 500MB
    })()
    reader._read_options = 0xFF  # ReadDirectoryIndex
    reader._directory_index_buffer = None

    with pytest.raises(ParseError, match="上限"):
        reader._load_directory_index()


def test_partition_count_too_large():
    """分区数超过上限应拒绝。"""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._header = type("FakeHeader", (), {
        "partition_count": 10_000,
        "version": 8,
    })()
    reader._ucas_files = []
    reader.utoc_path = "dummy/path.utoc"

    with pytest.raises(ParseError, match="上限"):
        reader._open_container_files()
