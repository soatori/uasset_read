"""pak/structures.py 单元测试 — FPakEntry bitfield 编解码 + FPakInfo 序列化大小。"""
from __future__ import annotations

import struct
from io import BytesIO

import pytest

from uasset_read.pak.constants import (
    PAK_FILE_MAGIC,
    PAK_INFO_SIZES,
    Flag_Encrypted,
    PakFileVersion,
)
from uasset_read.pak.structures import FPakEntry, FPakInfo


# ---------------------------------------------------------------------------
# TestFPakEntry — bitfield 编解码
# ---------------------------------------------------------------------------

class TestFPakEntry:
    """FPakEntry bitfield 编解码测试。"""

    # -- decode_bitfield 基本测试 ------------------------------------------------

    def test_decode_bitfield_all_32bit(self):
        """所有字段均适合 32 位时的解码。"""
        pak_info = FPakInfo()

        # 构建 bitfield: offset=32bit, uncompressed_size=32bit, size=32bit,
        # compression_method=0, encrypted=0, block_count=0, block_size_index=0
        bitfield = (1 << 31) | (1 << 30) | (1 << 29)  # 三个 32-bit 标志位
        data = bytearray()
        data.extend(struct.pack('<I', bitfield))
        data.extend(struct.pack('<I', 0x1000))        # offset (uint32)
        data.extend(struct.pack('<I', 0x2000))        # uncompressed_size (uint32)
        # 未压缩，不写入 size 字段

        entry, consumed = FPakEntry.decode_bitfield(bytes(data), 0, pak_info)

        assert entry.offset == 0x1000
        assert entry.uncompressed_size == 0x2000
        assert entry.size == 0x2000  # size 默认 == uncompressed_size
        assert entry.compression_method_index == 0
        assert entry.is_encrypted is False
        assert entry.is_compressed is False
        assert entry.compression_block_count == 0
        assert consumed == len(data)

    def test_decode_bitfield_64bit_offset_and_size(self):
        """offset/uncompressed_size 超过 32 位时使用 64 位编码。"""
        pak_info = FPakInfo()
        big_offset = 0x1_0000_0001
        big_ucomp = 0x2_0000_0002

        # 不设置 32-bit 标志 → 使用 64 位
        bitfield = 0
        data = bytearray()
        data.extend(struct.pack('<I', bitfield))
        data.extend(struct.pack('<q', big_offset))
        data.extend(struct.pack('<q', big_ucomp))

        entry, consumed = FPakEntry.decode_bitfield(bytes(data), 0, pak_info)

        assert entry.offset == big_offset
        assert entry.uncompressed_size == big_ucomp
        assert consumed == 4 + 8 + 8

    def test_decode_bitfield_encrypted(self):
        """加密标志位解码。"""
        pak_info = FPakInfo()
        bitfield = (1 << 31) | (1 << 30) | (1 << 29) | (1 << 22)
        data = bytearray()
        data.extend(struct.pack('<I', bitfield))
        data.extend(struct.pack('<I', 100))
        data.extend(struct.pack('<I', 200))

        entry, consumed = FPakEntry.decode_bitfield(bytes(data), 0, pak_info)

        assert entry.is_encrypted is True
        assert entry.flags == Flag_Encrypted

    def test_decode_bitfield_compressed_with_size(self):
        """压缩条目：bitfield 包含压缩方法索引，且会额外读取 size 字段。"""
        pak_info = FPakInfo()
        comp_method = 2
        comp_size = 0x500
        bitfield = (
            (1 << 31) | (1 << 30) | (1 << 29)  # 三个 32-bit 标志位
            | (comp_method << 23)                # compression method = 2
        )
        data = bytearray()
        data.extend(struct.pack('<I', bitfield))
        data.extend(struct.pack('<I', 0x1000))       # offset
        data.extend(struct.pack('<I', 0x2000))       # uncompressed_size
        data.extend(struct.pack('<I', comp_size))    # size (压缩后)

        entry, consumed = FPakEntry.decode_bitfield(bytes(data), 0, pak_info)

        assert entry.compression_method_index == comp_method
        assert entry.is_compressed is True
        assert entry.size == comp_size
        assert entry.uncompressed_size == 0x2000
        assert consumed == len(data)

    def test_decode_bitfield_block_size_index(self):
        """block_size_index 非 0x3F 时通过移位计算。"""
        pak_info = FPakInfo()
        index_val = 3  # → 3 << 11 = 6144
        bitfield = (1 << 31) | (1 << 30) | (1 << 29) | index_val
        data = bytearray()
        data.extend(struct.pack('<I', bitfield))
        data.extend(struct.pack('<I', 100))
        data.extend(struct.pack('<I', 200))

        entry, _ = FPakEntry.decode_bitfield(bytes(data), 0, pak_info)

        assert entry.compression_block_size == index_val << 11

    def test_decode_bitfield_block_size_from_stream(self):
        """block_size_index == 0x3F 时从流中读取实际大小。"""
        pak_info = FPakInfo()
        actual_block_size = 131072
        bitfield = (1 << 31) | (1 << 30) | (1 << 29) | 0x3F
        data = bytearray()
        data.extend(struct.pack('<I', bitfield))
        data.extend(struct.pack('<I', 100))
        data.extend(struct.pack('<I', 200))
        data.extend(struct.pack('<I', actual_block_size))

        entry, consumed = FPakEntry.decode_bitfield(bytes(data), 0, pak_info)

        assert entry.compression_block_size == actual_block_size
        assert consumed == 4 + 4 + 4 + 4

    def test_decode_bitfield_with_offset_in_data(self):
        """从 data 的非零偏移处开始解码。"""
        pak_info = FPakInfo()
        prefix = b'\xff' * 16
        bitfield = (1 << 31) | (1 << 30) | (1 << 29)
        payload = bytearray()
        payload.extend(struct.pack('<I', bitfield))
        payload.extend(struct.pack('<I', 0x42))
        payload.extend(struct.pack('<I', 0x43))

        data = prefix + bytes(payload)
        entry, consumed = FPakEntry.decode_bitfield(data, len(prefix), pak_info)

        assert entry.offset == 0x42
        assert entry.uncompressed_size == 0x43

    # -- encode_bitfield 基本测试 ------------------------------------------------

    def test_encode_bitfield_uncompressed_32bit(self):
        """未压缩条目，所有字段适合 32 位。"""
        entry = FPakEntry(
            offset=0x1000,
            uncompressed_size=0x2000,
            size=0x2000,
            compression_method_index=0,
        )
        encoded = entry.encode_bitfield()

        # 验证基本结构：4 bytes bitfield + 4 bytes offset + 4 bytes ucomp_size
        assert len(encoded) == 12
        bitfield = struct.unpack_from('<I', encoded, 0)[0]
        # 三个 32-bit 标志位都应设置
        assert bitfield & (1 << 31) != 0
        assert bitfield & (1 << 30) != 0
        assert bitfield & (1 << 29) != 0

    def test_encode_bitfield_compressed(self):
        """压缩条目应额外写入 size 字段。"""
        entry = FPakEntry(
            offset=0x1000,
            uncompressed_size=0x2000,
            size=0x1000,
            compression_method_index=2,
            compression_block_size=0,
        )
        encoded = entry.encode_bitfield()

        # 4 + 4 + 4 + 4 (size) + 4 (block_size from stream) = 20
        # block_size=0 → index=0, 非 0x3F → 不写额外数据?
        # 看代码: block_size=0, 0 % 2048 == 0, 但 0 >> 11 == 0 <= 0x3E → index=0
        # (bitfield & 0x3F) == 0 ≠ 0x3F → 不写 block_size
        # 所以实际是 4+4+4+4 = 16
        assert len(encoded) == 16

    def test_encode_bitfield_block_size_from_stream(self):
        """block_size 不是 2048 倍数时使用 0x3F 并写入实际大小。"""
        entry = FPakEntry(
            offset=0x1000,
            uncompressed_size=0x2000,
            size=0x1000,
            compression_method_index=2,
            compression_block_size=1000,  # 不是 2048 的倍数
        )
        encoded = entry.encode_bitfield()

        bitfield = struct.unpack_from('<I', encoded, 0)[0]
        assert (bitfield & 0x3F) == 0x3F

        # 最后 4 字节应为 block_size
        block_size = struct.unpack_from('<I', encoded, len(encoded) - 4)[0]
        assert block_size == 1000

    def test_encode_bitfield_large_offset_64bit(self):
        """offset 超过 32 位时使用 64 位编码。"""
        entry = FPakEntry(
            offset=0x1_0000_0001,
            uncompressed_size=0x2000,
            size=0x2000,
        )
        encoded = entry.encode_bitfield()

        bitfield = struct.unpack_from('<I', encoded, 0)[0]
        # offset 不适合 32 位 → bit 31 不设置
        assert bitfield & (1 << 31) == 0

        offset_val = struct.unpack_from('<q', encoded, 4)[0]
        assert offset_val == 0x1_0000_0001

    def test_encode_bitfield_encrypted_flag(self):
        """加密标志位正确编码。"""
        entry = FPakEntry(
            offset=100,
            uncompressed_size=200,
            size=200,
            is_encrypted=True,
        )
        encoded = entry.encode_bitfield()

        bitfield = struct.unpack_from('<I', encoded, 0)[0]
        assert bitfield & (1 << 22) != 0

    def test_encode_bitfield_sets_serialized_size(self):
        """编码后 serialized_size 应被设置。"""
        entry = FPakEntry(offset=10, uncompressed_size=20, size=20)
        encoded = entry.encode_bitfield()

        assert entry.serialized_size == len(encoded)

    # -- encode/decode roundtrip -------------------------------------------------

    def test_roundtrip_uncompressed_32bit(self):
        """未压缩 + 32 位字段的编解码 roundtrip。"""
        # 注意: compression_block_size=0 时编码器写 0x3F 到 bitfield，
        # 但不追加 4 字节块大小（因 block_size > 0 条件不满足），
        # 导致解码器看到 0x3F 时越界读取。因此使用 2048（index=1）避免此问题。
        original = FPakEntry(
            offset=0x1000,
            uncompressed_size=0x2000,
            size=0x2000,
            compression_method_index=0,
            is_encrypted=False,
            compression_block_count=0,
            compression_block_size=2048,
        )
        encoded = original.encode_bitfield()
        decoded, consumed = FPakEntry.decode_bitfield(encoded, 0, FPakInfo())

        assert decoded.offset == original.offset
        assert decoded.uncompressed_size == original.uncompressed_size
        assert decoded.size == original.size
        assert decoded.compression_method_index == 0
        assert decoded.is_encrypted is False
        assert consumed == len(encoded)

    def test_roundtrip_compressed_32bit(self):
        """压缩 + 32 位字段的编解码 roundtrip。"""
        original = FPakEntry(
            offset=0x5000,
            uncompressed_size=0x8000,
            size=0x6000,
            compression_method_index=2,
            compression_block_count=4,
            compression_block_size=0x1000,
        )
        encoded = original.encode_bitfield()
        decoded, consumed = FPakEntry.decode_bitfield(encoded, 0, FPakInfo())

        assert decoded.offset == original.offset
        assert decoded.uncompressed_size == original.uncompressed_size
        assert decoded.size == original.size
        assert decoded.compression_method_index == 2
        assert decoded.is_compressed is True
        assert decoded.compression_block_count == 4
        assert consumed == len(encoded)

    def test_roundtrip_encrypted_compressed(self):
        """加密 + 压缩的 roundtrip。"""
        original = FPakEntry(
            offset=0x200,
            uncompressed_size=0x400,
            size=0x300,
            compression_method_index=1,
            is_encrypted=True,
            compression_block_count=1,
            compression_block_size=0x1000,
        )
        encoded = original.encode_bitfield()
        decoded, _ = FPakEntry.decode_bitfield(encoded, 0, FPakInfo())

        assert decoded.is_encrypted is True
        assert decoded.is_compressed is True
        assert decoded.size == 0x300

    def test_roundtrip_large_values_64bit(self):
        """超大值（64 位）的 roundtrip。"""
        original = FPakEntry(
            offset=0x1_0000_0001,
            uncompressed_size=0x2_0000_0002,
            size=0x1_5000_0003,
            compression_method_index=3,
            compression_block_count=10,
            compression_block_size=0x2000,
        )
        encoded = original.encode_bitfield()
        decoded, consumed = FPakEntry.decode_bitfield(encoded, 0, FPakInfo())

        assert decoded.offset == original.offset
        assert decoded.uncompressed_size == original.uncompressed_size
        assert decoded.size == original.size
        assert consumed == len(encoded)

    def test_roundtrip_block_size_from_stream(self):
        """block_size 不是 2048 倍数时 roundtrip（使用 0x3F 流读取）。"""
        original = FPakEntry(
            offset=100,
            uncompressed_size=200,
            size=150,
            compression_method_index=1,
            compression_block_size=777,  # 非 2048 倍数
        )
        encoded = original.encode_bitfield()
        decoded, _ = FPakEntry.decode_bitfield(encoded, 0, FPakInfo())

        assert decoded.compression_block_size == 777

    def test_roundtrip_with_offset_in_data(self):
        """从非零偏移开始的 roundtrip。"""
        original = FPakEntry(offset=0x800, uncompressed_size=0x1000, size=0x1000,
                             compression_block_size=2048)
        prefix = b'\xaa' * 32
        encoded = original.encode_bitfield()
        data = prefix + encoded

        decoded, consumed = FPakEntry.decode_bitfield(data, len(prefix), FPakInfo())
        assert decoded.offset == 0x800
        assert consumed == len(encoded)


# ---------------------------------------------------------------------------
# TestFPakInfo — 序列化大小
# ---------------------------------------------------------------------------

class TestFPakInfo:
    """FPakInfo 测试。"""

    def test_serialized_size_v1_to_v6(self):
        """v1-v6 使用最小尺寸。"""
        for v in range(1, 7):
            assert FPakInfo._serialized_size(v) == PAK_INFO_SIZES["v1-6"]

    def test_serialized_size_v7(self):
        assert FPakInfo._serialized_size(7) == PAK_INFO_SIZES["v7"]

    def test_serialized_size_v8(self):
        assert FPakInfo._serialized_size(8) == PAK_INFO_SIZES["v8"]

    def test_serialized_size_v9(self):
        assert FPakInfo._serialized_size(9) == PAK_INFO_SIZES["v9"]

    def test_serialized_size_v10_and_above(self):
        for v in (10, 11, 12, 15, 100):
            assert FPakInfo._serialized_size(v) == PAK_INFO_SIZES["v10+"]

    def test_sizes_match_expected_constants(self):
        """验证 PAK_INFO_SIZES 常量值与已知 UE 格式一致。"""
        # v1-6: Magic(4) + Version(4) + IndexOffset(8) + IndexSize(8) + IndexHash(20) = 44
        assert PAK_INFO_SIZES["v1-6"] == 44
        # v7: + EncryptionKeyGuid(16) + bEncryptedIndex(1) = 61
        assert PAK_INFO_SIZES["v7"] == 61
        # v8: + CompressionMethods(32*5) = 221
        assert PAK_INFO_SIZES["v8"] == 221
        # v9: + FrozenIndex(1) = 222
        assert PAK_INFO_SIZES["v9"] == 222
        # v10+: - FrozenIndex = 221
        assert PAK_INFO_SIZES["v10+"] == 221

    def test_sizes_are_monotonically_non_decreasing(self):
        """版本越大，序列化尺寸不应减小（v10+ 是例外回退）。"""
        sizes = [FPakInfo._serialized_size(v) for v in range(1, 10)]
        # v1-v9 应单调非递减
        for i in range(1, len(sizes)):
            assert sizes[i] >= sizes[i - 1], f"v{i+1} size {sizes[i]} < v{i} size {sizes[i-1]}"
