"""pak 模块编解码对称性测试。"""
import pytest
from uasset_read.pak.structures import FPakEntry
from uasset_read.pak.decompress import decompress_block


class TestBitfieldSymmetry:
    """验证 bitfield 编解码对称。"""

    def test_encode_decode_roundtrip(self):
        """编码后解码应返回原始值。"""
        entry = FPakEntry(
            offset=0x1000,
            uncompressed_size=4096,
            size=2048,
            compression_method_index=1,
            is_encrypted=False,
            compression_block_count=4,
            compression_block_size=4096,
        )
        # 编码
        encoded = entry.encode_bitfield()
        # 解码：构造包含 bitfield 的字节流并创建最小 FPakInfo mock
        from uasset_read.pak.structures import FPakInfo
        pak_info = FPakInfo()
        decoded, consumed = FPakEntry.decode_bitfield(encoded, 0, pak_info)
        # 验证关键字段对称
        assert decoded.offset == entry.offset
        assert decoded.uncompressed_size == entry.uncompressed_size
        assert decoded.size == entry.size
        assert decoded.compression_method_index == entry.compression_method_index
        assert decoded.is_encrypted == entry.is_encrypted
        assert decoded.compression_block_count == entry.compression_block_count
        assert decoded.compression_block_size == entry.compression_block_size

    def test_encode_decode_roundtrip_uncompressed(self):
        """未压缩条目的编解码对称。"""
        entry = FPakEntry(
            offset=0x2000,
            uncompressed_size=512,
            size=512,
            compression_method_index=0,
            is_encrypted=False,
            compression_block_count=0,
            compression_block_size=0,
        )
        encoded = entry.encode_bitfield()
        from uasset_read.pak.structures import FPakInfo
        pak_info = FPakInfo()
        decoded, consumed = FPakEntry.decode_bitfield(encoded, 0, pak_info)
        assert decoded.offset == entry.offset
        assert decoded.uncompressed_size == entry.uncompressed_size
        assert decoded.size == entry.size
        assert decoded.compression_method_index == 0

    def test_block_size_zero_raises(self):
        """block_size=0 且压缩时应抛出异常而非静默编码。"""
        entry = FPakEntry(
            offset=0x1000,
            uncompressed_size=4096,
            size=2048,
            compression_method_index=1,
            is_encrypted=False,
            compression_block_count=1,
            compression_block_size=0,  # 无效：压缩条目 block_size 必须 > 0
        )
        with pytest.raises((ValueError, AssertionError)):
            entry.encode_bitfield()


class TestDecompressValidation:
    """验证 decompress_block 验证逻辑。"""

    def test_no_compression_method_raises(self):
        """无压缩方法 (None) 时应抛异常而非默认 Zlib。"""
        with pytest.raises((ValueError, TypeError, NotImplementedError)):
            decompress_block(b"test", uncompressed_size=4, method=None)

    def test_unknown_method_raises(self):
        """未知压缩方法应抛出 ValueError。"""
        with pytest.raises(ValueError):
            decompress_block(b"test", uncompressed_size=4, method="UnknownCodec")
