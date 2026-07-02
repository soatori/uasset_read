"""
FPakEntry legacy 序列化布局与 UE 源码对齐测试。

UE FPakEntry::Serialize (IPlatformFilePak.h:521-570) 序列化顺序：
1. Offset (int64)
2. Size (int64)
3. UncompressedSize (int64)
4. CompressionMethodIndex (int32)
5. Timestamp (int64) — version <= 1 only
6. Hash (20 bytes) — 始终存在
7. [version >= 3] CompressionBlocks (if compressed), Flags (uint8), CompressionBlockSize (uint32)

Python deserialize_legacy 必须严格按此顺序反序列化。
"""
from __future__ import annotations

import struct
import pytest
from io import BytesIO

from uasset_read.pak.constants import PakFileVersion, Flag_Encrypted
from uasset_read.pak.structures import FPakEntry, FPakCompressedBlock


# ===========================================================================
# UE 格式序列化辅助（参照 UE 源码，非 Python 代码）
# ===========================================================================

def _ue_serialize_legacy_entry(
    entry: FPakEntry,
    version: int,
    *,
    extra_hash: bytes | None = None,
) -> bytes:
    """按 UE FPakEntry::Serialize 精确序列化。

    字段顺序严格对照 UE IPlatformFilePak.h:521-570。
    """
    buf = BytesIO()
    buf.write(struct.pack('<q', entry.offset))
    buf.write(struct.pack('<q', entry.size))
    buf.write(struct.pack('<q', entry.uncompressed_size))
    buf.write(struct.pack('<I', entry.compression_method_index))

    # Timestamp (version <= 1 only, 即 version < 2)
    if version < PakFileVersion.NoTimestamps:
        buf.write(struct.pack('<q', 0))

    # Hash — UE 在 CompressionBlocks 之前写入 Hash
    h = extra_hash if extra_hash is not None else entry.hash
    buf.write(h.ljust(20, b'\x00')[:20])

    # [version >= CompressionEncryption (3)]:
    if version >= PakFileVersion.CompressionEncryption:
        if entry.compression_method_index != 0:
            # CompressionBlocks: count + N * (int64 + int64)
            # count: uint16 (v<8) or uint32 (v>=8)
            if version < PakFileVersion.FNameBasedCompressionMethod:
                buf.write(struct.pack('<H', entry.compression_block_count))
            else:
                buf.write(struct.pack('<I', entry.compression_block_count))
            for blk in entry.compression_blocks:
                buf.write(struct.pack('<q', blk.compressed_start))
                buf.write(struct.pack('<q', blk.compressed_end))
        # Flags — uint8 (1 byte)
        buf.write(struct.pack('<B', entry.flags))
        # CompressionBlockSize — uint32
        buf.write(struct.pack('<I', entry.compression_block_size))

    return buf.getvalue()


# ===========================================================================
# 测试: Hash 在 CompressionBlocks 之前
# ===========================================================================

class TestHashBeforeCompressionBlocks:
    """Hash 必须在 CompressionBlocks 之前读取（与 UE 一致）。"""

    def test_v8_compressed_hash_position(self):
        """v8 压缩条目: Hash 位于 CompressionMethodIndex 之后、CompressionBlocks 之前。"""
        entry = FPakEntry(
            offset=0x100,
            size=0x80,
            uncompressed_size=0x100,
            compression_method_index=1,
            compression_block_count=1,
            compression_block_size=4096,
            hash=b'\xAA' * 20,
        )
        entry.compression_blocks = [
            FPakCompressedBlock(compressed_start=0, compressed_end=0x80),
        ]

        raw = _ue_serialize_legacy_entry(entry, version=8)
        decoded = FPakEntry.deserialize_legacy(BytesIO(raw), version=8)

        # Hash 必须被正确读取（不是被 CompressionBlocks 的数据覆盖）
        assert decoded.hash == b'\xAA' * 20, (
            f"Hash 位置错误: 期望 {b'\\xAA' * 20!r}, 实际 {decoded.hash!r}"
        )
        assert decoded.compression_block_count == 1
        assert decoded.compression_blocks[0].compressed_start == 0
        assert decoded.compression_blocks[0].compressed_end == 0x80

    def test_v3_compressed_hash_position(self):
        """v3 压缩条目: Hash 位于 CompressionMethodIndex 之后。"""
        entry = FPakEntry(
            offset=0x200,
            size=0x100,
            uncompressed_size=0x200,
            compression_method_index=2,
            compression_block_count=1,
            compression_block_size=65536,
            hash=b'\xBB' * 20,
        )
        entry.compression_blocks = [
            FPakCompressedBlock(compressed_start=0, compressed_end=0x100),
        ]

        raw = _ue_serialize_legacy_entry(entry, version=3)
        decoded = FPakEntry.deserialize_legacy(BytesIO(raw), version=3)

        assert decoded.hash == b'\xbb' * 20
        assert decoded.compression_block_count == 1

    def test_v8_uncompressed_hash_preserved(self):
        """v8 未压缩条目: Hash 正确保留。"""
        entry = FPakEntry(
            offset=0x50,
            size=0x30,
            uncompressed_size=0x30,
            compression_method_index=0,
            hash=b'\xCC' * 20,
        )

        raw = _ue_serialize_legacy_entry(entry, version=8)
        decoded = FPakEntry.deserialize_legacy(BytesIO(raw), version=8)

        assert decoded.hash == b'\xCC' * 20
        assert decoded.offset == 0x50


# ===========================================================================
# 测试: Flags 字段 (uint8, version >= 3)
# ===========================================================================

class TestFlagsField:
    """Flags 字段: uint8, 在 version >= CompressionEncryption (3) 时存在。"""

    def test_v8_encrypted_flag(self):
        """v8 加密条目: Flags 包含 Flag_Encrypted。"""
        entry = FPakEntry(
            offset=0x100,
            size=0x80,
            uncompressed_size=0x100,
            compression_method_index=1,
            flags=Flag_Encrypted,
            compression_block_count=1,
            compression_block_size=4096,
        )
        entry.compression_blocks = [
            FPakCompressedBlock(compressed_start=0, compressed_end=0x80),
        ]

        raw = _ue_serialize_legacy_entry(entry, version=8)
        decoded = FPakEntry.deserialize_legacy(BytesIO(raw), version=8)

        assert decoded.flags == Flag_Encrypted, (
            f"Flags 读取错误: 期望 {Flag_Encrypted}, 实际 {decoded.flags}"
        )

    def test_v3_encrypted_flag(self):
        """v3 加密条目: Flags 在 version >= 3 时被读取。"""
        entry = FPakEntry(
            offset=0x100,
            size=0x80,
            uncompressed_size=0x100,
            compression_method_index=1,
            flags=Flag_Encrypted,
            compression_block_count=1,
            compression_block_size=4096,
        )
        entry.compression_blocks = [
            FPakCompressedBlock(compressed_start=0, compressed_end=0x80),
        ]

        raw = _ue_serialize_legacy_entry(entry, version=3)
        decoded = FPakEntry.deserialize_legacy(BytesIO(raw), version=3)

        assert decoded.flags == Flag_Encrypted

    def test_v8_zero_flags(self):
        """v8 无标志: Flags 为 0。"""
        entry = FPakEntry(
            offset=0x100,
            size=0x80,
            uncompressed_size=0x100,
            compression_method_index=1,
            flags=0,
            compression_block_count=1,
            compression_block_size=4096,
        )
        entry.compression_blocks = [
            FPakCompressedBlock(compressed_start=0, compressed_end=0x80),
        ]

        raw = _ue_serialize_legacy_entry(entry, version=8)
        decoded = FPakEntry.deserialize_legacy(BytesIO(raw), version=8)

        assert decoded.flags == 0

    def test_v2_no_flags_field(self):
        """v2 不存在 Flags 字段。"""
        entry = FPakEntry(
            offset=0x100,
            size=0x80,
            uncompressed_size=0x100,
            compression_method_index=1,
            flags=0,
        )

        raw = _ue_serialize_legacy_entry(entry, version=2)
        # v2 没有 CompressionEncryption, 也没有 Flags
        # 反序列化不应读取 Flags
        decoded = FPakEntry.deserialize_legacy(BytesIO(raw), version=2)
        assert decoded.offset == 0x100


# ===========================================================================
# 测试: CompressionBlockSize (uint32, version >= 3)
# ===========================================================================

class TestCompressionBlockSizeField:
    """CompressionBlockSize: uint32, 在 version >= 3 时存在于 Flags 之后。"""

    def test_v8_compression_block_size(self):
        """v8: CompressionBlockSize 在 Flags 之后被正确读取。"""
        entry = FPakEntry(
            offset=0x100,
            size=0x80,
            uncompressed_size=0x100,
            compression_method_index=1,
            compression_block_size=65536,
            compression_block_count=1,
        )
        entry.compression_blocks = [
            FPakCompressedBlock(compressed_start=0, compressed_end=0x80),
        ]

        raw = _ue_serialize_legacy_entry(entry, version=8)
        decoded = FPakEntry.deserialize_legacy(BytesIO(raw), version=8)

        assert decoded.compression_block_size == 65536, (
            f"CompressionBlockSize 错误: 期望 65536, 实际 {decoded.compression_block_size}"
        )

    def test_v3_compression_block_size(self):
        """v3: CompressionBlockSize 在 Flags 之后被正确读取。"""
        entry = FPakEntry(
            offset=0x100,
            size=0x80,
            uncompressed_size=0x100,
            compression_method_index=2,
            compression_block_size=32768,
            compression_block_count=1,
        )
        entry.compression_blocks = [
            FPakCompressedBlock(compressed_start=0, compressed_end=0x80),
        ]

        raw = _ue_serialize_legacy_entry(entry, version=3)
        decoded = FPakEntry.deserialize_legacy(BytesIO(raw), version=3)

        assert decoded.compression_block_size == 32768


# ===========================================================================
# 测试: 完整往返 (roundtrip)
# ===========================================================================

class TestLegacyRoundtrip:
    """UE 格式序列化 → Python 反序列化 完整往返。"""

    def test_roundtrip_v8_compressed_with_flags(self):
        """v8 压缩+加密条目: 完整往返验证。"""
        entry = FPakEntry(
            offset=0x1000,
            size=0x800,
            uncompressed_size=0x1000,
            compression_method_index=2,
            flags=Flag_Encrypted,
            compression_block_count=2,
            compression_block_size=65536,
            hash=b'\xDD' * 20,
        )
        entry.compression_blocks = [
            FPakCompressedBlock(compressed_start=0, compressed_end=0x400),
            FPakCompressedBlock(compressed_start=0x400, compressed_end=0x800),
        ]

        raw = _ue_serialize_legacy_entry(entry, version=8)
        decoded = FPakEntry.deserialize_legacy(BytesIO(raw), version=8)

        assert decoded.offset == 0x1000
        assert decoded.size == 0x800
        assert decoded.uncompressed_size == 0x1000
        assert decoded.compression_method_index == 2
        assert decoded.hash == b'\xDD' * 20
        assert decoded.compression_block_count == 2
        assert decoded.compression_block_size == 65536
        assert decoded.flags == Flag_Encrypted
        assert decoded.compression_blocks[0].compressed_start == 0
        assert decoded.compression_blocks[0].compressed_end == 0x400
        assert decoded.compression_blocks[1].compressed_start == 0x400
        assert decoded.compression_blocks[1].compressed_end == 0x800

    def test_roundtrip_v3_compressed(self):
        """v3 压缩条目: 完整往返验证。"""
        entry = FPakEntry(
            offset=0x500,
            size=0x300,
            uncompressed_size=0x500,
            compression_method_index=1,
            compression_block_count=1,
            compression_block_size=4096,
            hash=b'\xEE' * 20,
        )
        entry.compression_blocks = [
            FPakCompressedBlock(compressed_start=0, compressed_end=0x300),
        ]

        raw = _ue_serialize_legacy_entry(entry, version=3)
        decoded = FPakEntry.deserialize_legacy(BytesIO(raw), version=3)

        assert decoded.offset == 0x500
        assert decoded.size == 0x300
        assert decoded.uncompressed_size == 0x500
        assert decoded.compression_method_index == 1
        assert decoded.hash == b'\xEE' * 20
        assert decoded.compression_block_size == 4096
        assert decoded.compression_blocks[0].compressed_end == 0x300

    def test_roundtrip_v1_simple(self):
        """v1 简单条目: 无 compression blocks/flags/block_size。"""
        entry = FPakEntry(
            offset=0x100,
            size=0x50,
            uncompressed_size=0x50,
            compression_method_index=0,
            hash=b'\xFF' * 20,
        )

        raw = _ue_serialize_legacy_entry(entry, version=1)
        decoded = FPakEntry.deserialize_legacy(BytesIO(raw), version=1)

        assert decoded.offset == 0x100
        assert decoded.size == 0x50
        assert decoded.uncompressed_size == 0x50
        assert decoded.hash == b'\xFF' * 20

    def test_roundtrip_v8_uncompressed_with_flags(self):
        """v8 未压缩但有 flags 的条目: CompressionBlocks 不写入。"""
        entry = FPakEntry(
            offset=0x200,
            size=0x100,
            uncompressed_size=0x100,
            compression_method_index=0,
            flags=Flag_Encrypted,
            hash=b'\x11' * 20,
        )

        raw = _ue_serialize_legacy_entry(entry, version=8)
        decoded = FPakEntry.deserialize_legacy(BytesIO(raw), version=8)

        assert decoded.offset == 0x200
        assert decoded.flags == Flag_Encrypted
        assert decoded.hash == b'\x11' * 20
        # 未压缩时 Size == UncompressedSize
        assert decoded.size == 0x100


# ===========================================================================
# 测试: C-5 decode_encoded_pak_entry 位域布局
# ===========================================================================

class TestDecodeEncodedPakEntry:
    """C-5: decode_encoded_pak_entry 已删除（死代码），验证其不再存在。"""

    def test_function_removed(self):
        """decode_encoded_pak_entry 已从 structures.py 中移除。"""
        from uasset_read.pak import structures
        assert not hasattr(structures, 'decode_encoded_pak_entry'), (
            "decode_encoded_pak_entry 应已删除（C-5 死代码）"
        )
