from __future__ import annotations

import io
from io import BytesIO
from pathlib import Path
import struct
import zlib

import pytest

from uasset_read.exceptions import ParseError
from uasset_read.iostore.reader import IoStoreReader
from uasset_read.iostore.structures import FIoStoreTocCompressedBlockEntry, FIoStoreTocHeader
import uasset_read.pak.crypto as pak_crypto
import uasset_read.pak.reader as pak_reader_module
from uasset_read.pak.constants import PakFileVersion
from uasset_read.pak.decompress import decompress_entry
from uasset_read.pak.reader import PakFileReader
from uasset_read.pak.structures import FPakCompressedBlock, FPakEntry, FPakInfo
from uasset_read.raw import parse_audio_metadata, parse_ini_file, parse_json_descriptor, parse_raw_file


def test_decompress_entry_reads_uncompressed_plain_bytes():
    entry = FPakEntry(offset=2, uncompressed_size=5, is_compressed=False)

    assert decompress_entry(BytesIO(b"xxhello trailing"), entry) == b"hello"


def test_decompress_entry_rejects_uncompressed_encrypted_without_key():
    entry = FPakEntry(
        offset=0,
        uncompressed_size=5,
        is_encrypted=True,
        is_compressed=False,
    )

    with pytest.raises(ParseError, match="requires AES key"):
        decompress_entry(BytesIO(b"ciphertext"), entry)


def test_decompress_entry_decrypts_uncompressed_encrypted_bytes(monkeypatch):
    calls = []

    def fake_decrypt(data: bytes, key: bytes) -> bytes:
        calls.append((data, key))
        return b"hello decrypted"

    monkeypatch.setattr(pak_crypto, "decrypt_aes_ecb", fake_decrypt)
    entry = FPakEntry(
        offset=0,
        uncompressed_size=5,
        is_encrypted=True,
        is_compressed=False,
    )

    result = decompress_entry(BytesIO(b"ciphertext000000"), entry, encryption_key=b"k" * 16)

    assert result == b"hello"
    assert calls == [(b"ciphertext000000", b"k" * 16)]


def test_decompress_entry_wraps_missing_crypto_as_parse_error(monkeypatch):
    def missing_crypto(data: bytes, key: bytes) -> bytes:
        raise ImportError("cryptography is missing")

    monkeypatch.setattr(pak_crypto, "decrypt_aes_ecb", missing_crypto)
    entry = FPakEntry(
        offset=0,
        uncompressed_size=5,
        is_encrypted=True,
        is_compressed=False,
    )

    with pytest.raises(ParseError, match="cryptography"):
        decompress_entry(BytesIO(b"ciphertext000000"), entry, encryption_key=b"k" * 16)


def test_decompress_entry_rejects_compressed_encrypted_without_key():
    entry = FPakEntry(
        is_encrypted=True,
        is_compressed=True,
        compression_block_size=5,
        compression_blocks=[FPakCompressedBlock(0, 5)],
    )

    with pytest.raises(ParseError, match="requires AES key"):
        decompress_entry(BytesIO(b"ciphertext"), entry, compression_method="None")


def test_reader_maps_compression_method_index_from_one(monkeypatch):
    seen = {}

    def fake_decompress(stream, entry, compression_method, encryption_key):
        seen["method"] = compression_method
        return b"payload"

    monkeypatch.setattr(pak_reader_module, "decompress_entry", fake_decompress)
    reader = PakFileReader("unused.pak")
    reader._file = BytesIO(b"payload")
    reader._file_size = 7
    reader._info = FPakInfo(compression_methods=["LZ4"])
    reader._entries = {
        "Game/A.uasset": FPakEntry(
            offset=0,
            uncompressed_size=7,
            compression_method_index=1,
            is_compressed=True,
        )
    }

    assert reader.extract("Game/A.uasset") == b"payload"
    assert seen["method"] == "LZ4"


def test_reader_resolves_paths_like_package_provider(monkeypatch):
    def fake_decompress(stream, entry, compression_method, encryption_key):
        return b"payload"

    monkeypatch.setattr(pak_reader_module, "decompress_entry", fake_decompress)
    reader = PakFileReader("unused.pak")
    reader._file = BytesIO(b"payload")
    reader._file_size = 7
    reader._info = FPakInfo(compression_methods=[])
    reader._entries = {
        "Game/Folder/A.uasset": FPakEntry(offset=0, uncompressed_size=7),
    }

    assert reader.get_entry("folder/a") is reader._entries["Game/Folder/A.uasset"]
    assert reader.extract("/game/folder/a.uasset") == b"payload"
    assert reader.extract("A") == b"payload"
    assert reader.extract("Missing") is None


def test_reader_rejects_traversal_path_before_exact_match():
    reader = PakFileReader("unused.pak")
    reader._entries = {
        "../evil.uasset": FPakEntry(offset=0, uncompressed_size=7),
    }

    assert reader.get_entry("../evil.uasset") is None
    assert reader.extract("../evil.uasset") is None


def test_reader_rejects_out_of_range_compression_method_index():
    reader = PakFileReader("unused.pak")
    reader._file = BytesIO(b"payload")
    reader._file_size = 7
    reader._info = FPakInfo(compression_methods=["Zlib"])
    reader._entries = {
        "Game/A.uasset": FPakEntry(
            offset=0,
            uncompressed_size=7,
            compression_method_index=2,
            is_compressed=True,
        )
    }

    with pytest.raises(ParseError, match="out of range"):
        reader.extract("Game/A.uasset")


def test_decompress_entry_reads_compressed_block_and_bad_method():
    payload = b"pak compressed payload"
    compressed = zlib.compress(payload)
    entry = FPakEntry(
        offset=0,
        uncompressed_size=len(payload),
        is_compressed=True,
        compression_block_size=len(payload),
        compression_blocks=[FPakCompressedBlock(0, len(compressed))],
    )

    assert decompress_entry(BytesIO(compressed), entry, compression_method="zlib") == payload

    with pytest.raises(ValueError, match="Unknown compression method"):
        decompress_entry(BytesIO(compressed), entry, compression_method="NoSuchMethod")


def _legacy_entry_bytes(version: int, timestamp: bool) -> bytes:
    """构建 legacy FPakEntry 字节流（对齐 UE FPakEntry::Serialize 格式）。"""
    parts = [
        struct.pack("<q", 10),     # Offset
        struct.pack("<q", 5),      # Size
        struct.pack("<q", 5),      # UncompressedSize
        struct.pack("<I", 0),      # CompressionMethodIndex
    ]
    if timestamp:
        parts.append(struct.pack("<q", 123456))  # Timestamp (v<2 only)
    # Hash — UE 在 CompressionBlocks 之前写入 Hash
    parts.append(b"h" * 20)
    # [v>=3]: CompressionBlockCount, Flags, CompressionBlockSize
    if version >= PakFileVersion.CompressionEncryption:
        count_fmt = "<H" if version < PakFileVersion.FNameBasedCompressionMethod else "<I"
        parts.extend([
            struct.pack(count_fmt, 0),  # CompressionBlockCount (0 blocks)
            struct.pack("<B", 0),       # Flags (uint8)
            struct.pack("<I", 65536),   # CompressionBlockSize
        ])
    return b"".join(parts)


def test_legacy_v1_entry_consumes_timestamp():
    stream = BytesIO(_legacy_entry_bytes(PakFileVersion.Initial, timestamp=True))

    entry = FPakEntry.deserialize_legacy(stream, PakFileVersion.Initial)

    assert entry.compression_block_count == 0
    # version 1 (< 3): CompressionBlockSize 不存在于流中，保持默认值 0
    assert entry.compression_block_size == 0
    assert stream.tell() == len(stream.getvalue())


def test_legacy_v2_entry_does_not_consume_timestamp():
    stream = BytesIO(_legacy_entry_bytes(PakFileVersion.NoTimestamps, timestamp=False))

    entry = FPakEntry.deserialize_legacy(stream, PakFileVersion.NoTimestamps)

    assert entry.compression_block_count == 0
    # version 2 (< 3): CompressionBlockSize 不存在于流中，保持默认值 0
    assert entry.compression_block_size == 0
    assert stream.tell() == len(stream.getvalue())


# ===========================================================================
# 原始文件解析器测试
# ===========================================================================

def test_parse_uplugin_descriptor(tmp_path: Path):
    path = tmp_path / "Example.uplugin"
    path.write_text('{"FileVersion": 3, "FriendlyName": "Example"}', encoding="utf-8")

    result = parse_json_descriptor(str(path))

    assert result.is_success
    assert result.file_type == "uplugin"
    assert result.metadata["FriendlyName"] == "Example"


def test_parse_ini_file(tmp_path: Path):
    path = tmp_path / "DefaultGame.ini"
    path.write_text("[/Script/Game]\nName=Demo\n", encoding="utf-8")

    result = parse_ini_file(str(path))

    assert result.is_success
    assert result.metadata["/Script/Game"]["Name"] == "Demo"


def test_parse_audio_metadata_reads_size_and_magic(tmp_path: Path):
    path = tmp_path / "Sound.bnk"
    path.write_bytes(b"BKHD\x00\x00\x00\x00\x7b\x00\x00\x00")

    result = parse_audio_metadata(str(path))

    assert result.is_success
    assert result.metadata["codec"] == "wwise-bank"
    assert result.metadata["soundbank_id"] == 123


def test_parse_raw_file_rejects_unknown_type(tmp_path: Path):
    path = tmp_path / "unknown.txt"
    path.write_text("x", encoding="utf-8")

    result = parse_raw_file(str(path))

    assert not result.is_success
    assert result.file_type == "unknown"


# ===========================================================================
# IoStore Reader 分区读取回归测试
# ===========================================================================

def _make_reader_with_short_partition(data: bytes, length: int) -> IoStoreReader:
    """构造一个 UCAS 分区数据不足的 IoStoreReader。"""
    reader = IoStoreReader.__new__(IoStoreReader)
    # 模拟一个只有 data 长度的分区流
    reader._ucas_files = [io.BytesIO(data)]
    reader._header = FIoStoreTocHeader.__new__(FIoStoreTocHeader)
    reader._header.partition_size = 0  # 不限分区大小
    reader._header.container_flags = 0  # 无加密
    return reader


def _make_reader_with_compressed_block(
    block_data: bytes, uncompressed_size: int, method_index: int = 1
) -> IoStoreReader:
    """构造一个压缩块数据不足的 IoStoreReader。"""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._ucas_files = [io.BytesIO(block_data)]
    reader._header = FIoStoreTocHeader.__new__(FIoStoreTocHeader)
    reader._header.container_flags = 0
    reader._header.partition_size = len(block_data) + 100  # 确保块在第一个分区内
    reader._compression_blocks = [
        FIoStoreTocCompressedBlockEntry(
            offset=0,
            compressed_size=len(block_data) + 50,  # 声称比实际数据大
            uncompressed_size=uncompressed_size,
            compression_method_index=method_index,
        )
    ]
    reader._compression_methods = ["None", "Zlib"]
    reader._compression_block_size = 64 * 1024 * 1024  # 64MB
    return reader


def test_uncompressed_partition_short_read_raises():
    """分区读取不足时应抛 ParseError 而非静默返回短数据。"""
    reader = _make_reader_with_short_partition(b"ab", length=10)
    with pytest.raises(ParseError, match="分区读取不足"):
        reader._read_uncompressed_partitions(
            partition_index=0, partition_offset=0, length=10
        )


def test_uncompressed_partition_normal_read():
    """正常分区读取应返回完整数据。"""
    data = b"hello world"
    reader = _make_reader_with_short_partition(data, length=len(data))
    result = reader._read_uncompressed_partitions(
        partition_index=0, partition_offset=0, length=len(data)
    )
    assert result == data


def test_compressed_block_short_read_raises():
    """压缩块读取不足时应抛 ParseError 而非静默返回短数据。"""
    # TOC 声称 compressed_size=52，但实际只有 2 字节
    reader = _make_reader_with_compressed_block(b"ab", uncompressed_size=10)
    with pytest.raises(ParseError, match="压缩块.*读取不足"):
        reader._read_data(0, 2)  # 读取 2 字节触发块加载


# ===========================================================================
# Pak 解压缩块校验回归测试
# ===========================================================================

def _make_entry(blocks, uncompressed_size=1024, compression_block_size=65536):
    """构造一个最小 FPakEntry。"""
    entry = FPakEntry.__new__(FPakEntry)
    entry.compression_blocks = blocks
    entry.compression_block_size = compression_block_size
    entry.is_encrypted = False
    entry.is_compressed = True
    entry.uncompressed_size = uncompressed_size
    entry.compression_method_index = 1
    entry.offset = 0
    entry.size = sum(b.compressed_end - b.compressed_start for b in blocks)
    entry.compression_method = "Zlib"
    entry.hash = b"\x00" * 20
    return entry


def test_compressed_end_before_start_raises():
    """compressed_end < compressed_start 应抛 ParseError。"""
    block = FPakCompressedBlock(compressed_start=100, compressed_end=50)
    entry = _make_entry([block])

    stream = BytesIO(b"\x00" * 200)
    with pytest.raises(ParseError, match="compressed_end.*compressed_start"):
        decompress_entry(stream, entry, compression_method="Zlib")


def test_short_read_raises():
    """块读取不足时应抛 ParseError。"""
    block = FPakCompressedBlock(compressed_start=0, compressed_end=100)
    entry = _make_entry([block])

    stream = BytesIO(b"\x00" * 10)  # 只有 10 字节，期望 100
    with pytest.raises(ParseError, match="读取不足"):
        decompress_entry(stream, entry, compression_method="Zlib")


def test_uncompressed_short_read_raises():
    """非压缩 entry 读取不足时应抛 ParseError。"""
    entry = FPakEntry.__new__(FPakEntry)
    entry.is_compressed = False
    entry.is_encrypted = False
    entry.offset = 0
    entry.uncompressed_size = 100
    entry.compression_blocks = []

    stream = BytesIO(b"\x00" * 10)  # 只有 10 字节，期望 100
    with pytest.raises(ParseError, match="非压缩短读"):
        decompress_entry(stream, entry, compression_method="None")


def test_uncompressed_normal_read():
    """非压缩 entry 正常读取应返回完整数据。"""
    entry = FPakEntry.__new__(FPakEntry)
    entry.is_compressed = False
    entry.is_encrypted = False
    entry.offset = 0
    entry.uncompressed_size = 5
    entry.compression_blocks = []

    data = b"hello"
    stream = BytesIO(data)
    result = decompress_entry(stream, entry, compression_method="None")
    assert result == data


def test_uncompressed_encrypted_short_read_at_aligned_size():
    """加密非压缩 entry：读取不足 aligned raw_size 时应抛错。"""
    entry = FPakEntry.__new__(FPakEntry)
    entry.is_compressed = False
    entry.is_encrypted = True
    entry.offset = 0
    entry.uncompressed_size = 13  # 不是 16 的倍数 → aligned 为 16
    entry.compression_blocks = []

    # 只提供 13 字节，不够 16 字节 aligned raw_size
    stream = BytesIO(b"x" * 13)
    dummy_key = b"\x00" * 32
    with pytest.raises(ParseError, match="Pak 非压缩短读"):
        decompress_entry(stream, entry, compression_method="None", encryption_key=dummy_key)


def test_compressed_result_truncated_to_expected_size():
    """压缩结果超过预期大小时应截断到 uncompressed_size。"""
    # 构造一个返回过多数据的压缩块
    original = b"x" * 100
    compressed = zlib.compress(original)

    block = FPakCompressedBlock(compressed_start=0, compressed_end=len(compressed))
    entry = _make_entry([block], uncompressed_size=50, compression_block_size=100)  # 预期 50 字节

    stream = BytesIO(compressed)
    result = decompress_entry(stream, entry, compression_method="Zlib")
    assert len(result) == 50
    assert result == original[:50]
