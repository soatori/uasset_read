"""FIoStoreTocHeader 字段偏移对齐测试。"""
import io
import struct
import pytest
from uasset_read.iostore.structures import FIoStoreTocHeader, TOC_HEADER_SIZE, TOC_MAGIC


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
        Offset 52:  partition_count(u32), reserved2(u32)
        Offset 56:  container_id (uint64)
        Offset 64:  encryption_key_guid (16 bytes)
        Offset 80:  container_flags (uint8)
        Offset 81:  reserved3 (1 byte)
        Offset 82:  reserved4 (2 bytes) — uint16
        Offset 84:  reserved5 (4 bytes) — uint32
        Offset 88:  toc_chunk_perfect_hash_seeds_count (uint32)
        Offset 92:  reserved6 (4 bytes) — uint32
        Offset 96:  partition_size (uint64)
        Offset 104: toc_chunks_without_perfect_hash_count (uint32)
        Offset 108: reserved7 (uint32)
        Offset 112: reserved8 (32 bytes)
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

        # reserved3(1) + reserved4(2) + reserved5(4) at offset 81-87
        # (already zero)

        # toc_chunk_perfect_hash_seeds_count (uint32) at offset 88
        struct.pack_into('<I', buf, 88, toc_chunk_perfect_hash_seeds_count)

        # reserved6(4) at offset 92
        # (already zero)

        # partition_size (uint64) at offset 96
        struct.pack_into('<Q', buf, 96, partition_size)

        # toc_chunks_without_perfect_hash_count (uint32) at offset 104
        struct.pack_into('<I', buf, 104, 0)

        # reserved7 (uint32) at offset 108
        # (already zero)

        # reserved8 (32 bytes) at offset 112-143
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
        """toc_chunk_perfect_hash_seeds_count 在 offset 88（非 92）。"""
        header_data = self._build_header(toc_chunk_perfect_hash_seeds_count=42)
        header = FIoStoreTocHeader.from_stream(io.BytesIO(header_data))
        assert header.toc_chunk_perfect_hash_seeds_count == 42

    def test_partition_size_offset(self):
        """partition_size 在 offset 96。"""
        header_data = self._build_header(partition_size=0xDEADBEEF)
        header = FIoStoreTocHeader.from_stream(io.BytesIO(header_data))
        assert header.partition_size == 0xDEADBEEF

    def test_header_size_144(self):
        """TOC_HEADER_SIZE == 144。"""
        assert TOC_HEADER_SIZE == 144
