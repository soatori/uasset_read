"""FPakEntry 二进制格式对齐测试 — 验证字段顺序和 bitfield 布局。"""
import io
import struct
import pytest
from uasset_read.pak.structures import FPakEntry, decode_encoded_pak_entry


class TestFPakEntryLegacyDeserialization:
    """legacy 格式字段顺序对齐 UE FPakEntry::Serialize。"""

    def _build_legacy_entry(self, version=8):
        """构建一个 legacy FPakEntry 字节流。

        UE 序列化顺序（version >= 2, < 10）：
        Offset(i64) → Size(i64) → UncompressedSize(i64) → CompressionMethodIndex(u32)
        → CompressionBlockCount(u32) → CompressionBlockSize(u32)
        → CompressionBlocks[] → Hash(20bytes)
        """
        buf = io.BytesIO()
        # Offset
        buf.write(struct.pack('<q', 0x1000))
        # Size (压缩后大小)
        buf.write(struct.pack('<q', 0x800))
        # UncompressedSize
        buf.write(struct.pack('<q', 0x1000))
        # CompressionMethodIndex
        buf.write(struct.pack('<I', 1))
        # CompressionBlockCount (v>=8 → uint32)
        buf.write(struct.pack('<I', 0))
        # CompressionBlockSize
        buf.write(struct.pack('<I', 65536))
        # Hash (20 bytes)
        buf.write(b'\x00' * 20)
        # Flags (v>=8)
        buf.write(struct.pack('<I', 0))
        return buf.getvalue()

    def test_legacy_field_order(self):
        """验证 legacy 反序列化读取正确的字段顺序。"""
        data = self._build_legacy_entry(version=8)
        entry = FPakEntry.deserialize_legacy(io.BytesIO(data), version=8)
        assert entry.offset == 0x1000
        assert entry.size == 0x800       # Size（压缩后）
        assert entry.uncompressed_size == 0x1000
        assert entry.compression_method_index == 1
        assert entry.compression_block_size == 65536

    def test_legacy_no_timestamp(self):
        """version >= 2 不读取 Timestamp。"""
        data = self._build_legacy_entry(version=2)
        entry = FPakEntry.deserialize_legacy(io.BytesIO(data), version=2)
        assert entry.offset == 0x1000

    def test_legacy_with_timestamp(self):
        """version < 2 读取 Timestamp (8 bytes)。"""
        buf = io.BytesIO()
        buf.write(struct.pack('<q', 0x1000))   # Offset
        buf.write(struct.pack('<q', 0x1000))   # Size
        buf.write(struct.pack('<q', 0x1000))   # UncompressedSize
        buf.write(struct.pack('<I', 1))        # CompressionMethodIndex
        buf.write(struct.pack('<q', 0))        # Timestamp (v<2)
        buf.write(struct.pack('<I', 0))        # CompressionBlockCount
        buf.write(struct.pack('<I', 65536))    # CompressionBlockSize
        buf.write(b'\x00' * 20)               # Hash
        entry = FPakEntry.deserialize_legacy(io.BytesIO(buf.getvalue()), version=1)
        assert entry.offset == 0x1000


class TestFPakEntryBitfield:
    """v10+ bitfield 编码对齐 UE PakFile.cpp DecodePakEntry。"""

    def _build_bitfield(self, offset_fits_32=True, uncomp_fits_32=True,
                        size_fits_32=True, compression_method=0,
                        is_encrypted=False, block_count=0, block_size_index=0):
        """构建 4 字节 bitfield。

        UE 布局：
        Bit 31: offset_fits_32
        Bit 30: uncompressed_size_fits_32
        Bit 29: size_fits_32
        Bits 23-28: compression_method (6 bits)
        Bit 22: encrypted
        Bits 6-21: compression_block_count (16 bits)
        Bits 0-5: compression_block_size_index (6 bits)
        """
        bf = 0
        if offset_fits_32:
            bf |= 1 << 31
        if uncomp_fits_32:
            bf |= 1 << 30
        if size_fits_32:
            bf |= 1 << 29
        bf |= (compression_method & 0x3F) << 23
        if is_encrypted:
            bf |= 1 << 22
        bf |= (block_count & 0xFFFF) << 6
        bf |= block_size_index & 0x3F
        return struct.pack('<I', bf)

    def _build_pak_info(self):
        """构建最小 FPakInfo 用于测试。"""
        from uasset_read.pak.structures import FPakInfo
        info = FPakInfo()
        info.compression_methods = ["None", "Zlib", "Gzip", "Oodle"]
        return info

    def test_bitfield_all_32bit(self):
        """所有字段都适合 32 位。"""
        pak_info = self._build_pak_info()
        bf = self._build_bitfield(
            offset_fits_32=True, uncomp_fits_32=True, size_fits_32=True,
            compression_method=0, block_size_index=1
        )
        # 后续 4+4+4 = 12 字节数据
        data = bf + struct.pack('<III', 0x1000, 0x2000, 0x2000)
        entry, consumed = FPakEntry.decode_bitfield(data, 0, pak_info)
        assert entry.offset == 0x1000
        assert entry.uncompressed_size == 0x2000
        assert entry.compression_block_size == 1 << 11  # index=1 → 2048

    def test_bitfield_64bit_offset(self):
        """Offset 不适合 32 位。"""
        pak_info = self._build_pak_info()
        bf = self._build_bitfield(
            offset_fits_32=False, uncomp_fits_32=True, size_fits_32=True,
            compression_method=0, block_size_index=0
        )
        data = bf + struct.pack('<q', 0x100000000) + struct.pack('<I', 0x2000)
        entry, consumed = FPakEntry.decode_bitfield(data, 0, pak_info)
        assert entry.offset == 0x100000000

    def test_bitfield_block_size_0x3f_reads_stream(self):
        """block_size_index=0x3F 从流中读取。"""
        pak_info = self._build_pak_info()
        bf = self._build_bitfield(
            offset_fits_32=True, uncomp_fits_32=True, size_fits_32=True,
            compression_method=0, block_size_index=0x3F
        )
        # UE 读取顺序: CompressionBlockSize → Offset → UncompressedSize → Size
        data = bf + struct.pack('<IIII', 131072, 0x1000, 0x2000, 0x2000)
        entry, consumed = FPakEntry.decode_bitfield(data, 0, pak_info)
        assert entry.compression_block_size == 131072
        assert entry.offset == 0x1000


class TestDecodeEncodedPakEntry:
    """decode_encoded_pak_entry 位域布局对齐。"""

    def test_compression_method_from_bits_23_28(self):
        """compression_method 从 bits 23-28 读取（非 bits 0-5）。"""
        # 构建 bitfield: compression_method=3 at bits 23-28
        value = (3 & 0x3F) << 23
        data = struct.pack('<I', value) + b'\x00' * 16
        result = decode_encoded_pak_entry(data, is_enabled=True)
        assert result is not None
        assert result['compression_method_index'] == 3

    def test_encrypted_from_bit_22(self):
        """is_encrypted 从 bit 22 读取。"""
        value = (1 << 22) | ((2 & 0x3F) << 23)
        data = struct.pack('<I', value) + b'\x00' * 16
        result = decode_encoded_pak_entry(data, is_enabled=True)
        assert result is not None
        assert result['is_encrypted'] is True

    def test_disabled_returns_none(self):
        """is_enabled=False 时返回 None。"""
        result = decode_encoded_pak_entry(b'\x00' * 4, is_enabled=False)
        assert result is None
