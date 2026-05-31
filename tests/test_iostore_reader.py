"""IoStore Reader 测试"""
import struct
import pytest
from io import BytesIO


def test_iostore_reader_creation():
    """测试 IoStoreReader 创建"""
    from uasset_read.iostore.reader import IoStoreReader

    reader = IoStoreReader("test.utoc", "test.ucas")
    assert reader.utoc_path == "test.utoc"
    assert reader.ucas_path == "test.ucas"
    assert reader.info is None


def test_iostore_reader_creation_defaults():
    """测试 IoStoreReader 默认参数"""
    from uasset_read.iostore.reader import IoStoreReader

    reader = IoStoreReader("game.utoc")
    assert reader.utoc_path == "game.utoc"
    assert reader.ucas_path == "game.ucas"  # 自动推导


def test_iostore_reader_context_manager():
    """测试上下文管理器接口存在"""
    from uasset_read.iostore.reader import IoStoreReader

    assert hasattr(IoStoreReader, '__enter__')
    assert hasattr(IoStoreReader, '__exit__')


def test_iostore_reader_extract_not_implemented():
    """测试 extract 方法对无效文件抛出异常"""
    from uasset_read.iostore.reader import IoStoreReader

    reader = IoStoreReader("test.utoc", "test.ucas")
    # 文件不存在时，extract 应该抛出异常（KeyError = chunk 未找到）
    with pytest.raises((FileNotFoundError, RuntimeError, ValueError, KeyError)):
        reader.extract(b'\x00' * 12)


def test_iostore_reader_properties_before_open():
    """测试 open 前的属性状态"""
    from uasset_read.iostore.reader import IoStoreReader

    reader = IoStoreReader("test.utoc", "test.ucas")
    assert reader.info is None
    assert reader.header is None
    assert reader.mount_point == ""
    assert reader.is_encrypted is False
    assert reader.is_compressed is False
    assert reader.chunk_count == 0
    assert reader.list_files() == []


def test_iostore_reader_does_chunk_exist_before_open():
    """测试 open 前 does_chunk_exist"""
    from uasset_read.iostore.reader import IoStoreReader
    from uasset_read.iostore.structures import FIoChunkId

    reader = IoStoreReader("test.utoc", "test.ucas")
    chunk_id = FIoChunkId(b'\x00' * 12)
    assert reader.does_chunk_exist(chunk_id) is False


def test_iostore_reader_try_resolve_before_open():
    """测试 open 前 try_resolve"""
    from uasset_read.iostore.reader import IoStoreReader
    from uasset_read.iostore.structures import FIoChunkId

    reader = IoStoreReader("test.utoc", "test.ucas")
    chunk_id = FIoChunkId(b'\x00' * 12)
    assert reader.try_resolve(chunk_id) is None


def test_iostore_reader_extract_invalid_chunk_id():
    """测试 extract 方法对无效长度 ChunkId 抛出 ValueError"""
    from uasset_read.iostore.reader import IoStoreReader

    reader = IoStoreReader("test.utoc", "test.ucas")
    with pytest.raises(ValueError, match="ChunkId 必须为 12 字节"):
        reader.extract(b'\x00' * 8)  # 太短


def test_iostore_reader_hash_with_seed():
    """测试 _hash_with_seed 哈希函数"""
    from uasset_read.iostore.reader import IoStoreReader
    from uasset_read.iostore.structures import FIoChunkId

    reader = IoStoreReader("test.utoc", "test.ucas")
    chunk_id = FIoChunkId(b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c')

    # 相同输入应产生相同哈希
    h1 = reader._hash_with_seed(chunk_id, 0)
    h2 = reader._hash_with_seed(chunk_id, 0)
    assert h1 == h2

    # 不同 seed 应产生不同哈希
    h3 = reader._hash_with_seed(chunk_id, 1)
    assert h1 != h3


def test_iostore_structures_import():
    """测试所有结构可以从 iostore 模块导入"""
    from uasset_read.iostore import (
        FIoChunkId,
        FIoOffsetAndSize,
        FIoOffsetAndLength,
        FIoStoreTocHeader,
        FIoStoreTocCompressedBlockEntry,
        FIoStoreTocEntryMeta,
        EIoStoreTocVersion,
        EIoContainerFlags,
        EIoChunkType,
        IoStoreReader,
    )

    # 基本创建验证
    assert EIoStoreTocVersion.Latest == 8
    assert EIoContainerFlags.Encrypted == 2
    assert EIoChunkType.ExportBundleData == 1


def test_fio_offset_and_length_from_bytes():
    """测试 FIoOffsetAndLength 10 字节解码"""
    from uasset_read.iostore.structures import FIoOffsetAndLength

    # 构造 10 字节数据：offset=0x0102030405, length=0x060708090A
    data = bytes([
        0x01, 0x02, 0x03, 0x04, 0x05,  # offset (big-endian)
        0x06, 0x07, 0x08, 0x09, 0x0A,  # length (big-endian)
    ])
    result = FIoOffsetAndLength.from_bytes(data)
    assert result.offset == 0x0102030405
    assert result.length == 0x060708090A


def test_fio_store_toc_compressed_block_entry_from_stream():
    """测试压缩块条目解析"""
    from uasset_read.iostore.structures import FIoStoreTocCompressedBlockEntry

    # 构造 12 字节数据
    # Offset=0x100 (bytes 0-4: 0x00, 0x01, 0x00, 0x00, 0x00)
    # CompressedSize=0x200 (bytes 5-7: 0x00, 0x02, 0x00)
    # UncompressedSize=0x300 (bytes 8-10: 0x00, 0x03, 0x00)
    # CompressionMethodIndex=1 (byte 11: 0x01)
    data = bytes([
        0x00, 0x01, 0x00, 0x00, 0x00,  # offset
        0x00, 0x02, 0x00,              # compressed_size
        0x00, 0x03, 0x00,              # uncompressed_size
        0x01,                           # compression_method_index
    ])
    stream = BytesIO(data)
    result = FIoStoreTocCompressedBlockEntry.from_stream(stream)
    assert result.offset == 0x100
    assert result.compressed_size == 0x200
    assert result.uncompressed_size == 0x300
    assert result.compression_method_index == 1


def test_fio_chunk_id_properties():
    """测试 FIoChunkId 属性"""
    from uasset_read.iostore.structures import FIoChunkId

    # 构造 12 字节 ChunkId
    data = bytes([
        0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,  # id (8 bytes)
        0x00, 0x01,                                        # chunk_index (2 bytes)
        0x02,                                              # chunk_group (1 byte)
        0x03,                                              # chunk_type (1 byte)
    ])
    chunk_id = FIoChunkId(bytes=data)
    assert chunk_id.id == 0x0807060504030201  # little-endian
    assert chunk_id.chunk_index == 1
    assert chunk_id.chunk_group == 2
    assert chunk_id.chunk_type == 3