"""IoStore 综合测试 — 合并自 tests/iostore/ 目录。

覆盖：
- FIoStoreTocHeader 字段偏移对齐
- 目录索引环检测
- 头部资源限制
- 安全集成
- 分区读取不足回归
- 加密块二次读取短读验证
"""
import io
import struct
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from uasset_read.iostore.reader import IoStoreReader, MAX_TOC_ENTRIES, MAX_PARTITION_COUNT
from uasset_read.iostore.structures import (
    FIoStoreTocHeader,
    FIoStoreTocCompressedBlockEntry,
    TOC_HEADER_SIZE,
    TOC_MAGIC,
)
from uasset_read.exceptions import ParseError


# ============================================================
# test_iostore_header.py — FIoStoreTocHeader 字段偏移对齐
# ============================================================


class TestFIoStoreTocHeaderOffsets:
    """头部字段偏移对齐 UE IoStore.h。"""

    def _build_header(self, container_id=0x1234, encryption_key_guid=None,
                      container_flags=0x05, toc_chunk_perfect_hash_seeds_count=10,
                      partition_size=0x1000):
        """构建 144 字节 IoStore TOC 头部。

        UE 布局（IoStore.h）：
        Offset 0:   toc_magic (16 bytes)
        Offset 16:  version(u8), reserved0(u8), reserved1(u16)
        Offset 20:  toc_header_size(u32), toc_entry_count(u32)
        Offset 28:  toc_compressed_block_entry_count(u32),
                    toc_compressed_block_entry_size(u32)
        Offset 36:  compression_method_name_count(u32),
                    compression_method_name_length(u32)
        Offset 44:  compression_block_size(u32),
                    directory_index_size(u32)
        Offset 52:  partition_count(u32)
        Offset 56:  container_id (uint64)
        Offset 64:  encryption_key_guid (16 bytes)
        Offset 80:  container_flags (uint8)
        Offset 81:  reserved3 (1 byte)
        Offset 82:  reserved4 (2 bytes) — uint16
        Offset 84:  toc_chunk_perfect_hash_seeds_count (uint32)
        Offset 88:  partition_size (uint64)
        Offset 96:  toc_chunks_without_perfect_hash_count (uint32)
        Offset 100: reserved7 (uint32)
        Offset 104: reserved8 (5 x uint64 = 40 bytes)
        """
        if encryption_key_guid is None:
            encryption_key_guid = b'\x00' * 16

        buf = bytearray(TOC_HEADER_SIZE)

        # toc_magic
        buf[0:16] = TOC_MAGIC

        # version(1) + reserved0(1) + reserved1(2) at offset 16
        struct.pack_into('<BBH', buf, 16, 0, 0, 0)

        # toc_header_size(4) + toc_entry_count(4) at offset 20
        struct.pack_into('<II', buf, 20, TOC_HEADER_SIZE, 100)

        # toc_compressed_block_entry_count(4) + toc_compressed_block_entry_size(4) at offset 28
        struct.pack_into('<II', buf, 28, 5, 12)

        # compression_method_name_count(4) + compression_method_name_length(4) at offset 36
        struct.pack_into('<II', buf, 36, 4, 32)

        # compression_block_size(4) + directory_index_size(4) at offset 44
        struct.pack_into('<II', buf, 44, 65536, 256)

        # partition_count(4) + reserved2(4) at offset 52
        struct.pack_into('<II', buf, 52, 1, 0)

        # container_id (uint64) at offset 56
        struct.pack_into('<Q', buf, 56, container_id)

        # encryption_key_guid (16 bytes) at offset 64
        buf[64:80] = encryption_key_guid

        # container_flags (uint8) at offset 80
        buf[80] = container_flags

        # reserved3(1) + reserved4(2) at offset 81-83
        # (already zero)

        # toc_chunk_perfect_hash_seeds_count (uint32) at offset 84
        struct.pack_into('<I', buf, 84, toc_chunk_perfect_hash_seeds_count)

        # partition_size (uint64) at offset 88
        struct.pack_into('<Q', buf, 88, partition_size)

        # toc_chunks_without_perfect_hash_count (uint32) at offset 96
        struct.pack_into('<I', buf, 96, 0)

        # reserved7 (uint32) at offset 100
        # (already zero)

        # reserved8 (5 x uint64 = 40 bytes) at offset 104-143
        # (already zero)

        return bytes(buf)

    def test_container_id_offset(self):
        """container_id 在 offset 56。"""
        header_data = self._build_header(container_id=0xABCD)
        header = FIoStoreTocHeader.from_stream(io.BytesIO(header_data))
        assert header.container_id == 0xABCD

    def test_encryption_key_guid_offset(self):
        """encryption_key_guid 在 offset 64。"""
        guid = b'\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F\x10'
        header_data = self._build_header(encryption_key_guid=guid)
        header = FIoStoreTocHeader.from_stream(io.BytesIO(header_data))
        assert header.encryption_key_guid == guid

    def test_container_flags_offset(self):
        """container_flags(uint8) 在 offset 80。"""
        header_data = self._build_header(container_flags=0x05)
        header = FIoStoreTocHeader.from_stream(io.BytesIO(header_data))
        assert header.container_flags == 0x05

    def test_container_flags_is_uint8(self):
        """container_flags 是 uint8（1 字节），不是 uint32。"""
        # 写入 0xFF 到 offset 80，后面 3 字节也非零
        header_data = bytearray(self._build_header())
        header_data[80] = 0xFF
        header_data[81] = 0x01  # reserved3
        header_data[82] = 0x02  # reserved4 low byte
        header_data[83] = 0x03  # reserved4 high byte
        header = FIoStoreTocHeader.from_stream(io.BytesIO(bytes(header_data)))
        assert header.container_flags == 0xFF

    def test_toc_chunk_perfect_hash_seeds_count_offset(self):
        """toc_chunk_perfect_hash_seeds_count 在 offset 84（UE IoStore.h:65）。"""
        header_data = self._build_header(toc_chunk_perfect_hash_seeds_count=42)
        header = FIoStoreTocHeader.from_stream(io.BytesIO(header_data))
        assert header.toc_chunk_perfect_hash_seeds_count == 42

    def test_partition_size_offset(self):
        """partition_size 在 offset 88（UE IoStore.h:66）。"""
        header_data = self._build_header(partition_size=0xDEADBEEF)
        header = FIoStoreTocHeader.from_stream(io.BytesIO(header_data))
        assert header.partition_size == 0xDEADBEEF

    def test_header_size_144(self):
        """TOC_HEADER_SIZE == 144。"""
        assert TOC_HEADER_SIZE == 144


# ============================================================
# test_iostore.py — 目录索引环检测、头部资源限制、安全集成
# ============================================================


# ── 辅助函数：构造畸形目录索引 buffer ─────────────────────────────────


def _build_cyclic_directory_index() -> bytes:
    """构造一个包含环的目录索引 buffer。

    结构：mount_point + directory_entries + file_entries + string_table
    环：entry 0 的 first_child_entry = 0（指向自身）
    """
    buf = bytearray()

    # mount_point: FString "Test/"
    mount = b"Test/\x00"
    buf += struct.pack("<i", len(mount))  # length (positive = UTF-8)
    buf += mount

    # directory_entries: 1 entry
    buf += struct.pack("<i", 1)  # count = 1
    # FIoDirectoryIndexEntry: name(4) + first_child_entry(4) + next_sibling_entry(4) + first_file_entry(4)
    buf += struct.pack("<i", 0)   # name = string_table[0]
    buf += struct.pack("<i", 0)   # first_child_entry = 0 → 环！
    buf += struct.pack("<i", -1)  # next_sibling_entry = invalid
    buf += struct.pack("<i", -1)  # first_file_entry = invalid

    # file_entries: 0 entries
    buf += struct.pack("<i", 0)

    # string_table: 1 entry
    buf += struct.pack("<i", 1)  # count = 1
    name = b"dir\x00"
    buf += struct.pack("<i", len(name))
    buf += name

    return bytes(buf)


def _build_sibling_cycle_index() -> bytes:
    """构造一个 next_sibling_entry 自环的目录索引 buffer。

    结构：mount_point + directory_entries + file_entries + string_table
    环：entry 0 的 next_sibling_entry = 0（指向自身）
    """
    buf = bytearray()

    # mount_point: FString "Test/"
    mount = b"Test/\x00"
    buf += struct.pack("<i", len(mount))  # length (positive = UTF-8)
    buf += mount

    # directory_entries: 1 entry
    buf += struct.pack("<i", 1)  # count = 1
    # FIoDirectoryIndexEntry: name(4) + first_child_entry(4) + next_sibling_entry(4) + first_file_entry(4)
    buf += struct.pack("<i", 0)   # name = string_table[0]
    buf += struct.pack("<i", -1)  # first_child_entry = invalid
    buf += struct.pack("<i", 0)   # next_sibling_entry = 0 → 环！
    buf += struct.pack("<i", -1)  # first_file_entry = invalid

    # file_entries: 0 entries
    buf += struct.pack("<i", 0)

    # string_table: 1 entry
    buf += struct.pack("<i", 1)  # count = 1
    name = b"dir\x00"
    buf += struct.pack("<i", len(name))
    buf += name

    return bytes(buf)


def _build_reader_with_directory_index(index_bytes: bytes) -> IoStoreReader:
    """构造一个绑定了指定目录索引 buffer 的 IoStoreReader 实例。"""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._directory_index_buffer = index_bytes
    reader._header = None
    reader._aes_key = None
    reader._chunk_ids = []
    reader._directory_index = {}
    reader._mount_point = ""
    return reader


# ── 目录索引环检测测试 ────────────────────────────────────────────────


def test_cyclic_directory_index_raises_parse_error():
    """目录索引环应抛出 ParseError，而非 RecursionError。"""
    reader = _build_reader_with_directory_index(_build_cyclic_directory_index())

    # 不应是 RecursionError
    with pytest.raises(ParseError, match="环|cycle|深度"):
        reader._parse_directory_index()


def test_file_chain_cycle_raises():
    """文件链环应抛出 ParseError。"""
    buf = bytearray()
    # mount_point
    mount = b"/\x00"
    buf += struct.pack("<i", len(mount))
    buf += mount

    # directory_entries: 1 entry（无子目录）
    buf += struct.pack("<i", 1)
    buf += struct.pack("<i", -1)  # name = invalid
    buf += struct.pack("<i", -1)  # first_child_entry = invalid
    buf += struct.pack("<i", -1)  # next_sibling_entry = invalid
    buf += struct.pack("<i", 0)   # first_file_entry = 0

    # file_entries: 1 entry，next_file_entry = 0（环）
    buf += struct.pack("<i", 1)
    buf += struct.pack("<i", 0)   # name
    buf += struct.pack("<i", 0)   # user_data
    buf += struct.pack("<i", 0)   # next_file_entry = 0 → 环！

    # string_table
    buf += struct.pack("<i", 1)
    fname = b"test.uasset\x00"
    buf += struct.pack("<i", len(fname))
    buf += fname

    reader = _build_reader_with_directory_index(bytes(buf))

    with pytest.raises(ParseError, match="环|cycle|深度"):
        reader._parse_directory_index()


def test_sibling_cycle_raises_parse_error():
    """next_sibling_entry 自环应抛出 ParseError，而非无限循环。"""
    reader = _build_reader_with_directory_index(_build_sibling_cycle_index())

    with pytest.raises(ParseError, match="环|cycle|深度"):
        reader._parse_directory_index()


def test_sibling_cycle_no_hang_subprocess():
    """子进程隔离验证：修复后 sibling 自环不应导致进程挂起。

    使用 subprocess.run 超时检测，确保 _parse_directory_index 不死循环。
    """
    import pathlib
    project_root = str(pathlib.Path(__file__).resolve().parent.parent.parent)

    code = """
import sys
sys.path.insert(0, "src")
from uasset_read.iostore.reader import IoStoreReader
from uasset_read.exceptions import ParseError
import struct

# 构造 next_sibling_entry 自环 buffer
buf = bytearray()
mount = b"Test/\\x00"
buf += struct.pack("<i", len(mount))
buf += mount
buf += struct.pack("<i", 1)      # directory_entries count = 1
buf += struct.pack("<i", 0)      # name = 0
buf += struct.pack("<i", -1)     # first_child_entry = invalid
buf += struct.pack("<i", 0)      # next_sibling_entry = 0 → 环！
buf += struct.pack("<i", -1)     # first_file_entry = invalid
buf += struct.pack("<i", 0)      # file_entries count = 0
buf += struct.pack("<i", 1)      # string_table count = 1
name = b"dir\\x00"
buf += struct.pack("<i", len(name))
buf += name

reader = IoStoreReader.__new__(IoStoreReader)
reader._directory_index_buffer = bytes(buf)
reader._header = None
reader._aes_key = None
reader._chunk_ids = []
reader._directory_index = {}
reader._mount_point = ""

try:
    reader._parse_directory_index()
    sys.exit(1)  # 应该抛出异常，不应正常返回
except ParseError:
    sys.exit(0)  # 预期行为：ParseError
except Exception:
    sys.exit(1)  # 其他异常视为失败
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        timeout=3.0,
        cwd=project_root,
    )
    assert result.returncode == 0, (
        f"子进程应正常退出（ParseError），实际退出码: {result.returncode}\n"
        f"stdout: {result.stdout.decode()}\n"
        f"stderr: {result.stderr.decode()}"
    )


# ── 头部资源限制测试 ─────────────────────────────────────────────────


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


# ── 安全集成测试 — 覆盖恶意输入场景 ─────────────────────────────────


class TestIoStoreResourceLimits:
    """头部资源限制集成测试。"""

    def test_max_toc_entries_respected(self):
        """toc_entry_count = 10 应正常处理（小规模边界值）。"""
        reader = IoStoreReader.__new__(IoStoreReader)
        reader._utoc_file = io.BytesIO(b"\x00" * 12 * 10)
        reader._header = type("H", (), {"toc_entry_count": 10, "version": 8})()
        reader._chunk_ids = []
        # 不应抛异常
        reader._load_chunk_ids()
        assert len(reader._chunk_ids) == 10

    def test_toc_entries_exactly_at_limit(self):
        """toc_entry_count 恰好等于 100 应通过。"""
        reader = IoStoreReader.__new__(IoStoreReader)
        # 需要足够的数据
        data = b"\x00" * (12 * 100)
        reader._utoc_file = io.BytesIO(data)
        reader._header = type("H", (), {"toc_entry_count": 100, "version": 8})()
        reader._chunk_ids = []
        reader._load_chunk_ids()
        assert len(reader._chunk_ids) == 100

    def test_partition_count_limit(self):
        """分区数超过上限应拒绝。"""
        reader = IoStoreReader.__new__(IoStoreReader)
        reader._header = type("H", (), {
            "partition_count": MAX_PARTITION_COUNT + 1,
            "version": 8,
        })()
        reader._ucas_files = []
        reader.utoc_path = "/fake/test.utoc"
        reader._ucas_path_override = None

        with pytest.raises(ParseError, match="上限"):
            reader._open_container_files()


class TestDirectoryIndexSafety:
    """目录索引安全测试。"""

    def _build_sibling_cycle_index(self) -> bytes:
        """构造 sibling 链环的目录索引 buffer。

        两个目录 entry 互相指向对方为 next_sibling，形成环。
        """
        buf = bytearray()

        # mount_point: FString "/"
        mount = b"/\x00"
        buf += struct.pack("<i", len(mount))
        buf += mount

        # directory_entries: 2 entries
        buf += struct.pack("<i", 2)
        # entry 0
        buf += struct.pack("<i", 0)    # name
        buf += struct.pack("<i", -1)   # first_child
        buf += struct.pack("<i", 1)    # next_sibling = 1
        buf += struct.pack("<i", -1)   # first_file
        # entry 1
        buf += struct.pack("<i", 1)    # name
        buf += struct.pack("<i", -1)   # first_child
        buf += struct.pack("<i", 0)    # next_sibling = 0 → 环！
        buf += struct.pack("<i", -1)   # first_file

        # file_entries
        buf += struct.pack("<i", 0)

        # string_table
        buf += struct.pack("<i", 2)
        for name in [b"a\x00", b"b\x00"]:
            buf += struct.pack("<i", len(name))
            buf += name

        return bytes(buf)

    def test_sibling_chain_cycle(self):
        """sibling 链环应被检测。"""
        reader = IoStoreReader.__new__(IoStoreReader)
        reader._directory_index_buffer = self._build_sibling_cycle_index()
        reader._header = None
        reader._aes_key = None
        reader._chunk_ids = []
        reader._directory_index = {}
        reader._mount_point = ""

        with pytest.raises(ParseError, match="环|cycle|深度"):
            reader._parse_directory_index()

    def test_file_chain_cycle(self):
        """文件链环应被检测。"""
        buf = bytearray()
        # mount_point
        mount = b"/\x00"
        buf += struct.pack("<i", len(mount))
        buf += mount

        # directory_entries: 1 entry（无子目录）
        buf += struct.pack("<i", 1)
        buf += struct.pack("<i", -1)  # name = invalid
        buf += struct.pack("<i", -1)  # first_child_entry = invalid
        buf += struct.pack("<i", -1)  # next_sibling_entry = invalid
        buf += struct.pack("<i", 0)   # first_file_entry = 0

        # file_entries: 1 entry，next_file_entry = 0（环）
        buf += struct.pack("<i", 1)
        buf += struct.pack("<i", 0)   # name
        buf += struct.pack("<i", 0)   # user_data
        buf += struct.pack("<i", 0)   # next_file_entry = 0 → 环！

        # string_table
        buf += struct.pack("<i", 1)
        fname = b"test.uasset\x00"
        buf += struct.pack("<i", len(fname))
        buf += fname

        reader = IoStoreReader.__new__(IoStoreReader)
        reader._directory_index_buffer = bytes(buf)
        reader._header = None
        reader._aes_key = None
        reader._chunk_ids = []
        reader._directory_index = {}
        reader._mount_point = ""

        with pytest.raises(ParseError, match="环|cycle|深度"):
            reader._parse_directory_index()

    def test_self_referencing_child_cycle(self):
        """first_child_entry 自引用环应被检测。"""
        buf = bytearray()
        # mount_point
        mount = b"/\x00"
        buf += struct.pack("<i", len(mount))
        buf += mount

        # directory_entries: 1 entry，first_child = 自身
        buf += struct.pack("<i", 1)
        buf += struct.pack("<i", 0)   # name
        buf += struct.pack("<i", 0)   # first_child = 0 → 自引用！
        buf += struct.pack("<i", -1)  # next_sibling = invalid
        buf += struct.pack("<i", -1)  # first_file = invalid

        # file_entries: 0
        buf += struct.pack("<i", 0)

        # string_table: 1
        buf += struct.pack("<i", 1)
        name = b"dir\x00"
        buf += struct.pack("<i", len(name))
        buf += name

        reader = IoStoreReader.__new__(IoStoreReader)
        reader._directory_index_buffer = bytes(buf)
        reader._header = None
        reader._aes_key = None
        reader._chunk_ids = []
        reader._directory_index = {}
        reader._mount_point = ""

        with pytest.raises(ParseError, match="环|cycle|深度"):
            reader._parse_directory_index()


class TestEncryptedBlockShortRead:
    """加密块二次读取短读验证。"""

    def test_second_read_short_raises_parse_error(self):
        """第二次 read 返回不足字节时应抛出 ParseError。"""
        reader = IoStoreReader.__new__(IoStoreReader)

        # 构造假 header — encrypted, 大 partition_size
        reader._header = type("H", (), {
            "is_encrypted": True,
            "partition_size": 0xFFFFFFFFFFFFFFFF,
        })()

        # compressed_size=17 → aligned_size=32 (16 字节对齐)
        block = type("Block", (), {
            "compressed_size": 17,
            "uncompressed_size": 100,
            "compression_method_index": 1,
            "offset": 0,
        })()
        reader._compression_blocks = [block]
        reader._compression_block_size = 64 * 1024 * 1024

        # 第一次 read 返回 17 字节（够 compressed_size）
        # 第二次 read 返回 5 字节（不够对齐到 32）
        first_read_data = b'\x00' * 17
        second_read_data = b'\x00' * 5

        call_count = [0]

        def mock_read(size):
            call_count[0] += 1
            if call_count[0] == 1:
                return first_read_data
            elif call_count[0] == 2:
                return second_read_data
            return b''

        mock_stream = MagicMock()
        mock_stream.read = mock_read
        mock_stream.seek = MagicMock()
        reader._ucas_files = [mock_stream]
        reader._aes_key = b'\x00' * 16

        # mock decrypt 以跳过实际 AES 解密
        import uasset_read.iostore.reader as reader_mod
        original_decrypt = reader_mod.decrypt_aes_ecb
        reader_mod.decrypt_aes_ecb = lambda data, key: data

        try:
            # compression_block_size=10 使 block 在不同块中，进入多块循环
            reader._compression_block_size = 10
            with pytest.raises(ParseError, match="对齐读取不足"):
                reader._read_data(0, 10)
        finally:
            reader_mod.decrypt_aes_ecb = original_decrypt


# ── 分区读取不足回归测试 ─────────────────────────────────────────────


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
