"""
pak/index.py 覆盖率补充测试

覆盖以下关键路径：
- parse_primary_index 主入口
- _parse_legacy_index 旧格式索引
- _parse_v10_index v10+ 格式索引
- parse_path_hash_index 路径哈希索引
- parse_directory_index 目录索引
"""
from __future__ import annotations

import struct
import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock

from uasset_read.exceptions import ParseError
from uasset_read.pak.constants import PakFileVersion, Flag_Encrypted
from uasset_read.pak.structures import FPakInfo, FPakEntry, read_fstring
from uasset_read.pak.index import (
    parse_primary_index,
    _parse_legacy_index,
    _parse_v10_index,
    parse_path_hash_index,
    parse_directory_index,
)


# ===========================================================================
# 辅助函数
# ===========================================================================

def _create_pak_info(
    version: int = PakFileVersion.Initial,
    index_offset: int = 0,
    index_size: int = 100,
    encrypted_index: bool = False,
) -> FPakInfo:
    """创建测试用 FPakInfo。"""
    info = FPakInfo()
    info.version = version
    info.index_offset = index_offset
    info.index_size = index_size
    info.index_hash = b'\x00' * 20
    info.encrypted_index = encrypted_index
    return info


def _mock_validate_index_hash(blob: bytes, expected_hash: bytes) -> bool:
    """模拟索引哈希验证 — 始终返回 True。"""
    return True


def _create_legacy_index_blob(
    mount_point: str,
    entries: list[tuple[str, FPakEntry]],
    version: int = PakFileVersion.Initial,
) -> bytes:
    """创建 legacy 格式索引 blob。"""
    stream = BytesIO()
    # 写入 mount_point
    _write_fstring(stream, mount_point, version)
    # 写入 entries 数量
    stream.write(struct.pack('<i', len(entries)))
    # 写入每个 entry
    for path, entry in entries:
        _write_fstring(stream, path, version)
        _write_legacy_entry(stream, entry, version)
    return stream.getvalue()


def _write_fstring(stream: BytesIO, text: str, version: int = 0) -> None:
    """写入 FString 到流。"""
    if version >= PakFileVersion.Utf8PakDirectory:
        # FUtf8String: uint32 length + UTF-8 bytes + null terminator
        data = text.encode('utf-8')
        stream.write(struct.pack('<I', len(data)))
        stream.write(data)
        stream.write(b'\x00')
    else:
        # Standard FString: int32 length + ANSI bytes + null terminator
        data = text.encode('ascii')
        stream.write(struct.pack('<i', len(data)))
        stream.write(data)
        stream.write(b'\x00')


def _write_legacy_entry(stream: BytesIO, entry: FPakEntry, version: int) -> None:
    """写入 legacy 格式 FPakEntry（对齐 UE FPakEntry::Serialize 顺序）。"""
    stream.write(struct.pack('<q', entry.offset))
    stream.write(struct.pack('<q', entry.size))
    stream.write(struct.pack('<q', entry.uncompressed_size))
    stream.write(struct.pack('<I', entry.compression_method_index))

    # Timestamp (version < 2)
    if version < PakFileVersion.NoTimestamps:
        stream.write(struct.pack('<q', 0))

    # Hash — UE 在 CompressionBlocks 之前写入 Hash
    stream.write(entry.hash.ljust(20, b'\x00')[:20])

    # [version >= CompressionEncryption (3)]: CompressionBlocks, Flags, CompressionBlockSize
    if version >= PakFileVersion.CompressionEncryption:
        if entry.compression_method_index != 0:
            # CompressionBlocks: count + N * (int64, int64)
            if version < PakFileVersion.FNameBasedCompressionMethod:
                stream.write(struct.pack('<H', entry.compression_block_count))
            else:
                stream.write(struct.pack('<I', entry.compression_block_count))

            for _ in range(entry.compression_block_count):
                stream.write(struct.pack('<q', 0))  # compressed_start
                stream.write(struct.pack('<q', 0))  # compressed_end

        # Flags — uint8 (1 byte)
        stream.write(struct.pack('<B', entry.flags))

        # CompressionBlockSize — uint32
        stream.write(struct.pack('<I', entry.compression_block_size))


def _create_mock_file_stream(data: bytes) -> BytesIO:
    """创建模拟文件流。"""
    return BytesIO(data)


# ===========================================================================
# parse_primary_index 测试
# ===========================================================================

class TestParsePrimaryIndex:
    """parse_primary_index 主入口函数单元测试。"""

    @patch('uasset_read.pak.crypto.validate_index_hash', _mock_validate_index_hash)
    def test_legacy_index_v1(self):
        """legacy 格式索引 — 版本 1。"""
        # 创建 legacy 索引 blob
        entries = [("/Game/Test.uasset", FPakEntry(offset=100, size=200))]
        index_blob = _create_legacy_index_blob("/", entries, version=1)

        pak_info = _create_pak_info(
            version=1,
            index_offset=0,
            index_size=len(index_blob),
        )

        stream = _create_mock_file_stream(index_blob)
        mount_point, entries_dict, extra_info = parse_primary_index(stream, pak_info)

        assert mount_point == "/"
        assert "/Game/Test.uasset" in entries_dict
        assert entries_dict["/Game/Test.uasset"].offset == 100
        assert extra_info == {}

    @patch('uasset_read.pak.crypto.validate_index_hash', _mock_validate_index_hash)
    def test_legacy_index_v8(self):
        """legacy 格式索引 — 版本 8。"""
        entries = [("/Game/Test.uasset", FPakEntry(offset=100, size=200))]
        index_blob = _create_legacy_index_blob("/", entries, version=8)

        pak_info = _create_pak_info(
            version=8,
            index_offset=0,
            index_size=len(index_blob),
        )

        stream = _create_mock_file_stream(index_blob)
        mount_point, entries_dict, extra_info = parse_primary_index(stream, pak_info)

        assert mount_point == "/"
        assert "/Game/Test.uasset" in entries_dict

    @patch('uasset_read.pak.crypto.validate_index_hash', _mock_validate_index_hash)
    def test_empty_index(self):
        """空索引 — 0 个条目。"""
        index_blob = _create_legacy_index_blob("/", [], version=1)

        pak_info = _create_pak_info(
            version=1,
            index_offset=0,
            index_size=len(index_blob),
        )

        stream = _create_mock_file_stream(index_blob)
        mount_point, entries_dict, extra_info = parse_primary_index(stream, pak_info)

        assert mount_point == "/"
        assert len(entries_dict) == 0

    def test_index_truncated(self):
        """索引截断 — 应抛出 ParseError。"""
        pak_info = _create_pak_info(
            version=1,
            index_offset=0,
            index_size=100,
        )

        # 只提供 10 字节数据
        stream = _create_mock_file_stream(b'\x00' * 10)
        with pytest.raises(ParseError, match="truncated"):
            parse_primary_index(stream, pak_info)

    def test_encrypted_index_no_key(self):
        """加密索引无密钥 — 应抛出 ParseError。"""
        pak_info = _create_pak_info(
            version=1,
            index_offset=0,
            index_size=100,
            encrypted_index=True,
        )

        stream = _create_mock_file_stream(b'\x00' * 100)
        with pytest.raises(ParseError, match="AES key"):
            parse_primary_index(stream, pak_info, aes_key=None)

    def test_index_hash_mismatch(self):
        """索引哈希不匹配 — 应抛出 ParseError。"""
        index_data = b'\x00' * 50
        pak_info = _create_pak_info(
            version=1,
            index_offset=0,
            index_size=len(index_data),
        )
        # 设置不同的哈希
        pak_info.index_hash = b'\xff' * 20

        stream = _create_mock_file_stream(index_data)
        with pytest.raises(ParseError, match="hash mismatch"):
            parse_primary_index(stream, pak_info)

    @patch('uasset_read.pak.crypto.validate_index_hash', _mock_validate_index_hash)
    def test_negative_entry_count(self):
        """负数条目计数 — 应抛出 ParseError。"""
        # 创建包含负数计数的索引 blob
        stream = BytesIO()
        _write_fstring(stream, "/", 1)
        stream.write(struct.pack('<i', -1))  # 负数计数
        index_blob = stream.getvalue()

        pak_info = _create_pak_info(
            version=1,
            index_offset=0,
            index_size=len(index_blob),
        )

        file_stream = _create_mock_file_stream(index_blob)
        with pytest.raises(ParseError, match="Invalid entry count"):
            parse_primary_index(file_stream, pak_info)

    @patch('uasset_read.pak.crypto.validate_index_hash', _mock_validate_index_hash)
    def test_unexpected_end_reading_entry_count(self):
        """读取条目计数时意外结束 — 应抛出 ParseError。"""
        # 创建只有 mount_point 的索引 blob
        stream = BytesIO()
        _write_fstring(stream, "/", 1)
        index_blob = stream.getvalue()

        pak_info = _create_pak_info(
            version=1,
            index_offset=0,
            index_size=len(index_blob),
        )

        file_stream = _create_mock_file_stream(index_blob)
        with pytest.raises(ParseError, match="Unexpected end"):
            parse_primary_index(file_stream, pak_info)


# ===========================================================================
# _parse_legacy_index 测试
# ===========================================================================

class TestParseLegacyIndex:
    """_parse_legacy_index 旧格式索引解析测试。"""

    def test_single_entry(self):
        """单个条目。"""
        entry = FPakEntry(offset=100, size=200, uncompressed_size=200)
        stream = BytesIO()
        _write_fstring(stream, "/Game/Test.uasset", 1)
        _write_legacy_entry(stream, entry, 1)
        stream.seek(0)

        result = _parse_legacy_index(stream, 1, 1)
        assert "/Game/Test.uasset" in result
        assert result["/Game/Test.uasset"].offset == 100

    def test_multiple_entries(self):
        """多个条目。"""
        stream = BytesIO()
        entries = [
            ("/Game/A.uasset", FPakEntry(offset=0, size=100)),
            ("/Game/B.uasset", FPakEntry(offset=100, size=200)),
            ("/Game/C.uasset", FPakEntry(offset=300, size=150)),
        ]
        for path, entry in entries:
            _write_fstring(stream, path, 1)
            _write_legacy_entry(stream, entry, 1)
        stream.seek(0)

        result = _parse_legacy_index(stream, 3, 1)
        assert len(result) == 3
        assert "/Game/A.uasset" in result
        assert "/Game/B.uasset" in result
        assert "/Game/C.uasset" in result

    def test_empty_path_raises_error(self):
        """空路径 — 应抛出 ParseError。"""
        stream = BytesIO()
        _write_fstring(stream, "", 1)  # 空路径
        stream.seek(0)

        with pytest.raises(ParseError, match="Empty path"):
            _parse_legacy_index(stream, 1, 1)

    def test_entry_with_compression(self):
        """带压缩的条目。"""
        entry = FPakEntry(
            offset=100,
            size=150,
            uncompressed_size=200,
            compression_method_index=1,
            is_compressed=True,
        )
        stream = BytesIO()
        _write_fstring(stream, "/Game/Compressed.uasset", 8)
        _write_legacy_entry(stream, entry, 8)
        stream.seek(0)

        result = _parse_legacy_index(stream, 1, 8)
        assert "/Game/Compressed.uasset" in result
        assert result["/Game/Compressed.uasset"].is_compressed is True

    def test_entry_with_encryption_flag(self):
        """带加密标志的条目。"""
        # 创建带加密标志的条目
        entry = FPakEntry(
            offset=100,
            size=200,
            flags=Flag_Encrypted,  # Flag_Encrypted = 0x01
        )
        stream = BytesIO()
        _write_fstring(stream, "/Game/Encrypted.uasset", 8)
        _write_legacy_entry(stream, entry, 8)
        stream.seek(0)

        result = _parse_legacy_index(stream, 1, 8)
        # 验证 flags 字段被正确读取
        assert result["/Game/Encrypted.uasset"].flags == Flag_Encrypted

    def test_entry_with_compression_blocks(self):
        """带压缩块的条目。"""
        entry = FPakEntry(
            offset=100,
            size=150,
            uncompressed_size=200,
            compression_method_index=1,
            compression_block_count=2,
            compression_block_size=1024,
        )
        stream = BytesIO()
        _write_fstring(stream, "/Game/Blocked.uasset", 8)
        _write_legacy_entry(stream, entry, 8)
        stream.seek(0)

        result = _parse_legacy_index(stream, 1, 8)
        assert result["/Game/Blocked.uasset"].compression_block_count == 2


# ===========================================================================
# parse_path_hash_index 测试
# ===========================================================================

class TestParsePathHashIndex:
    """parse_path_hash_index 路径哈希索引解析测试。"""

    def test_single_entry(self):
        """单个条目。"""
        # 创建 PathHashIndex 数据
        stream = BytesIO()
        stream.write(struct.pack('<I', 1))  # num_entries
        stream.write(struct.pack('<Q', 12345))  # path_hash
        stream.write(struct.pack('<q', 100))  # file_offset
        stream.write(struct.pack('<q', 200))  # entry_size
        data = stream.getvalue()

        pak_info = _create_pak_info()
        file_stream = _create_mock_file_stream(data)

        result = parse_path_hash_index(file_stream, 0, len(data), pak_info)
        assert 12345 in result
        assert result[12345] == (100, 200)

    def test_multiple_entries(self):
        """多个条目。"""
        stream = BytesIO()
        stream.write(struct.pack('<I', 3))  # num_entries
        for i in range(3):
            stream.write(struct.pack('<Q', i * 1000))  # path_hash
            stream.write(struct.pack('<q', i * 100))  # file_offset
            stream.write(struct.pack('<q', i * 50))  # entry_size
        data = stream.getvalue()

        pak_info = _create_pak_info()
        file_stream = _create_mock_file_stream(data)

        result = parse_path_hash_index(file_stream, 0, len(data), pak_info)
        assert len(result) == 3
        assert 0 in result
        assert 1000 in result
        assert 2000 in result

    def test_empty_index(self):
        """空索引 — 0 个条目。"""
        stream = BytesIO()
        stream.write(struct.pack('<I', 0))  # num_entries = 0
        data = stream.getvalue()

        pak_info = _create_pak_info()
        file_stream = _create_mock_file_stream(data)

        result = parse_path_hash_index(file_stream, 0, len(data), pak_info)
        assert len(result) == 0

    def test_truncated_data(self):
        """数据截断 — 应抛出 ParseError。"""
        pak_info = _create_pak_info()
        file_stream = _create_mock_file_stream(b'\x00' * 10)

        with pytest.raises(ParseError, match="truncated"):
            parse_path_hash_index(file_stream, 0, 100, pak_info)

    def test_offset_in_file(self):
        """偏移在文件中 — 正确定位读取。"""
        # 创建包含前导数据的文件流
        preamble = b'\x00' * 50
        stream = BytesIO()
        stream.write(struct.pack('<I', 1))  # num_entries
        stream.write(struct.pack('<Q', 999))  # path_hash
        stream.write(struct.pack('<q', 500))  # file_offset
        stream.write(struct.pack('<q', 600))  # entry_size
        index_data = stream.getvalue()

        file_stream = _create_mock_file_stream(preamble + index_data)

        pak_info = _create_pak_info()
        result = parse_path_hash_index(file_stream, 50, len(index_data), pak_info)
        assert 999 in result
        assert result[999] == (500, 600)


# ===========================================================================
# parse_directory_index 测试
# ===========================================================================

class TestParseDirectoryIndex:
    """parse_directory_index 目录索引解析测试。"""

    def test_single_directory_single_file(self):
        """单个目录单个文件。"""
        stream = BytesIO()
        stream.write(struct.pack('<I', 1))  # num_directories
        _write_fstring(stream, "/Game/Maps", 1)
        stream.write(struct.pack('<I', 1))  # num_files
        _write_fstring(stream, "Test.umap", 1)
        stream.write(struct.pack('<q', 100))  # file_offset
        stream.write(struct.pack('<q', 200))  # file_size
        data = stream.getvalue()

        pak_info = _create_pak_info()
        file_stream = _create_mock_file_stream(data)

        result = parse_directory_index(file_stream, 0, len(data), pak_info)
        assert "/Game/Maps" in result
        assert "Test.umap" in result["/Game/Maps"]
        assert result["/Game/Maps"]["Test.umap"] == (100, 200)

    def test_multiple_directories(self):
        """多个目录。"""
        stream = BytesIO()
        stream.write(struct.pack('<I', 2))  # num_directories

        # 第一个目录
        _write_fstring(stream, "/Game/Maps", 1)
        stream.write(struct.pack('<I', 2))  # num_files
        _write_fstring(stream, "Map1.umap", 1)
        stream.write(struct.pack('<q', 100))
        stream.write(struct.pack('<q', 200))
        _write_fstring(stream, "Map2.umap", 1)
        stream.write(struct.pack('<q', 300))
        stream.write(struct.pack('<q', 400))

        # 第二个目录
        _write_fstring(stream, "/Game/Textures", 1)
        stream.write(struct.pack('<I', 1))  # num_files
        _write_fstring(stream, "Tex1.utxt", 1)
        stream.write(struct.pack('<q', 500))
        stream.write(struct.pack('<q', 600))

        data = stream.getvalue()
        pak_info = _create_pak_info()
        file_stream = _create_mock_file_stream(data)

        result = parse_directory_index(file_stream, 0, len(data), pak_info)
        assert len(result) == 2
        assert "/Game/Maps" in result
        assert "/Game/Textures" in result
        assert len(result["/Game/Maps"]) == 2
        assert len(result["/Game/Textures"]) == 1

    def test_empty_directory(self):
        """空目录 — 0 个文件。"""
        stream = BytesIO()
        stream.write(struct.pack('<I', 1))  # num_directories
        _write_fstring(stream, "/Empty", 1)
        stream.write(struct.pack('<I', 0))  # num_files = 0
        data = stream.getvalue()

        pak_info = _create_pak_info()
        file_stream = _create_mock_file_stream(data)

        result = parse_directory_index(file_stream, 0, len(data), pak_info)
        assert "/Empty" in result
        assert len(result["/Empty"]) == 0

    def test_no_directories(self):
        """无目录 — 0 个目录。"""
        stream = BytesIO()
        stream.write(struct.pack('<I', 0))  # num_directories = 0
        data = stream.getvalue()

        pak_info = _create_pak_info()
        file_stream = _create_mock_file_stream(data)

        result = parse_directory_index(file_stream, 0, len(data), pak_info)
        assert len(result) == 0

    def test_truncated_data(self):
        """数据截断 — 应抛出 ParseError。"""
        pak_info = _create_pak_info()
        file_stream = _create_mock_file_stream(b'\x00' * 10)

        with pytest.raises(ParseError, match="truncated"):
            parse_directory_index(file_stream, 0, 100, pak_info)

    def test_offset_in_file(self):
        """偏移在文件中 — 正确定位读取。"""
        preamble = b'\x00' * 50
        stream = BytesIO()
        stream.write(struct.pack('<I', 1))  # num_directories
        _write_fstring(stream, "/Game", 1)
        stream.write(struct.pack('<I', 1))  # num_files
        _write_fstring(stream, "File.txt", 1)
        stream.write(struct.pack('<q', 100))
        stream.write(struct.pack('<q', 200))
        index_data = stream.getvalue()

        file_stream = _create_mock_file_stream(preamble + index_data)
        pak_info = _create_pak_info()

        result = parse_directory_index(file_stream, 50, len(index_data), pak_info)
        assert "/Game" in result
        assert "File.txt" in result["/Game"]


# ===========================================================================
# FPakEntry.decode_bitfield 测试
# ===========================================================================

class TestDecodeBitfield:
    """FPakEntry.decode_bitfield 方法单元测试。"""

    def test_simple_uncompressed_entry(self):
        """简单未压缩条目 — 所有值适合 32 位。"""
        # 构建 bitfield: offset_fits_32=1, uncompressed_size_fits_32=1, size_fits_32=1,
        # compression_method=0, encrypted=0, block_count=0, block_size_index=0
        bitfield = (1 << 31) | (1 << 30) | (1 << 29)  # 所有 fits_32 标志
        data = struct.pack('<I', bitfield)
        data += struct.pack('<I', 100)  # offset (32-bit)
        data += struct.pack('<I', 200)  # uncompressed_size (32-bit)
        # size 未压缩时 == uncompressed_size，不读取

        pak_info = _create_pak_info()
        entry, consumed = FPakEntry.decode_bitfield(data, 0, pak_info)

        assert entry.offset == 100
        assert entry.uncompressed_size == 200
        assert entry.size == 200  # 未压缩时 size == uncompressed_size
        assert entry.is_compressed is False
        assert entry.is_encrypted is False

    def test_compressed_entry(self):
        """压缩条目 — compression_method > 0。"""
        # 构建 bitfield: compression_method=2, block_size_index=0x3F (read from stream)
        bitfield = (1 << 31) | (1 << 30) | (1 << 29)  # 所有 fits_32
        bitfield |= (2 << 23)  # compression_method = 2
        bitfield |= 0x3F  # block_size_index = 0x3F (read from stream)

        data = struct.pack('<I', bitfield)
        data += struct.pack('<I', 4096)  # compression_block_size
        data += struct.pack('<I', 100)  # offset
        data += struct.pack('<I', 1000)  # uncompressed_size
        data += struct.pack('<I', 800)  # size (compressed)

        pak_info = _create_pak_info()
        entry, consumed = FPakEntry.decode_bitfield(data, 0, pak_info)

        assert entry.compression_method_index == 2
        assert entry.compression_block_size == 4096
        assert entry.offset == 100
        assert entry.uncompressed_size == 1000
        assert entry.size == 800
        assert entry.is_compressed is True

    def test_encrypted_entry(self):
        """加密条目 — encrypted 标志。"""
        bitfield = (1 << 31) | (1 << 30) | (1 << 29)
        bitfield |= (1 << 22)  # encrypted flag

        data = struct.pack('<I', bitfield)
        data += struct.pack('<I', 100)  # offset
        data += struct.pack('<I', 200)  # uncompressed_size

        pak_info = _create_pak_info()
        entry, consumed = FPakEntry.decode_bitfield(data, 0, pak_info)

        assert entry.is_encrypted is True
        assert entry.flags & 0x01 != 0  # Flag_Encrypted

    def test_64bit_offset(self):
        """64 位偏移 — offset_fits_32=0。"""
        bitfield = (1 << 30) | (1 << 29)  # 只有 size 和 uncompressed_size fits_32

        data = struct.pack('<I', bitfield)
        data += struct.pack('<q', 0x100000000)  # offset (64-bit)
        data += struct.pack('<I', 200)  # uncompressed_size

        pak_info = _create_pak_info()
        entry, consumed = FPakEntry.decode_bitfield(data, 0, pak_info)

        assert entry.offset == 0x100000000

    def test_64bit_uncompressed_size(self):
        """64 位未压缩大小 — uncompressed_size_fits_32=0。"""
        bitfield = (1 << 31) | (1 << 29)  # 只有 offset 和 size fits_32

        data = struct.pack('<I', bitfield)
        data += struct.pack('<I', 100)  # offset
        data += struct.pack('<q', 0x100000000)  # uncompressed_size (64-bit)

        pak_info = _create_pak_info()
        entry, consumed = FPakEntry.decode_bitfield(data, 0, pak_info)

        assert entry.uncompressed_size == 0x100000000

    def test_block_size_index_calculation(self):
        """压缩块大小索引计算 — 非 0x3F 索引。"""
        # block_size_index = 5, 计算: 5 << 11 = 10240
        bitfield = (1 << 31) | (1 << 30) | (1 << 29)
        bitfield |= 5  # block_size_index = 5

        data = struct.pack('<I', bitfield)
        data += struct.pack('<I', 100)  # offset
        data += struct.pack('<I', 200)  # uncompressed_size

        pak_info = _create_pak_info()
        entry, consumed = FPakEntry.decode_bitfield(data, 0, pak_info)

        assert entry.compression_block_size == 5 << 11  # 10240

    def test_compression_blocks_count(self):
        """压缩块数量 — bitfield 中编码。"""
        # block_count = 10 (10 << 6)
        bitfield = (1 << 31) | (1 << 30) | (1 << 29)
        bitfield |= (10 << 6)  # block_count = 10

        data = struct.pack('<I', bitfield)
        data += struct.pack('<I', 100)  # offset
        data += struct.pack('<I', 200)  # uncompressed_size

        pak_info = _create_pak_info()
        entry, consumed = FPakEntry.decode_bitfield(data, 0, pak_info)

        assert entry.compression_block_count == 10


# ===========================================================================
# FPakEntry.encode_bitfield 测试
# ===========================================================================

class TestEncodeBitfield:
    """FPakEntry.encode_bitfield 方法单元测试。"""

    def test_roundtrip_simple(self):
        """简单条目编码解码往返。"""
        original = FPakEntry(
            offset=100,
            size=200,
            uncompressed_size=200,
            compression_method_index=0,
            is_encrypted=False,
            compression_block_count=0,
            compression_block_size=0,
        )

        encoded = original.encode_bitfield()
        pak_info = _create_pak_info()
        decoded, consumed = FPakEntry.decode_bitfield(encoded, 0, pak_info)

        assert decoded.offset == original.offset
        assert decoded.size == original.size
        assert decoded.uncompressed_size == original.uncompressed_size

    def test_roundtrip_compressed(self):
        """压缩条目编码解码往返。"""
        original = FPakEntry(
            offset=100,
            size=800,
            uncompressed_size=1000,
            compression_method_index=2,
            compression_block_count=5,
            compression_block_size=4096,
        )

        encoded = original.encode_bitfield()
        pak_info = _create_pak_info()
        decoded, consumed = FPakEntry.decode_bitfield(encoded, 0, pak_info)

        assert decoded.offset == original.offset
        assert decoded.size == original.size
        assert decoded.uncompressed_size == original.uncompressed_size
        assert decoded.compression_method_index == original.compression_method_index

    def test_roundtrip_encrypted(self):
        """加密条目编码解码往返。"""
        original = FPakEntry(
            offset=100,
            size=200,
            uncompressed_size=200,
            is_encrypted=True,
        )

        encoded = original.encode_bitfield()
        pak_info = _create_pak_info()
        decoded, consumed = FPakEntry.decode_bitfield(encoded, 0, pak_info)

        assert decoded.offset == original.offset
        assert decoded.is_encrypted is True

    def test_encode_64bit_offset(self):
        """编码 64 位偏移。"""
        entry = FPakEntry(
            offset=0x100000000,  # > 32-bit
            size=200,
            uncompressed_size=200,
        )

        encoded = entry.encode_bitfield()
        # 验证 bitfield 中 offset_fits_32 为 0
        bitfield = struct.unpack_from('<I', encoded, 0)[0]
        assert bitfield & (1 << 31) == 0  # offset_fits_32 = 0

    def test_encode_64bit_size(self):
        """编码 64 位大小。"""
        entry = FPakEntry(
            offset=100,
            size=0x100000000,  # > 32-bit
            uncompressed_size=0x100000000,
        )

        encoded = entry.encode_bitfield()
        pak_info = _create_pak_info()
        decoded, consumed = FPakEntry.decode_bitfield(encoded, 0, pak_info)

        assert decoded.size == 0x100000000
        assert decoded.uncompressed_size == 0x100000000
