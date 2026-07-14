"""IoStore 安全集成测试 — 覆盖恶意输入场景。"""
import io
import struct
import pytest
from unittest.mock import MagicMock

from uasset_read.iostore.reader import IoStoreReader, MAX_TOC_ENTRIES, MAX_PARTITION_COUNT
from uasset_read.exceptions import ParseError


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
