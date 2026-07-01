"""pak 模块缺陷测试（依赖 Task 2）。"""
import io
import struct
import pytest

from uasset_read.pak.constants import (
    PAK_FILE_MAGIC,
    PAK_FILE_MAGICS,
    PakFileVersion,
    PAK_INFO_SIZES,
    Flag_Encrypted,
    Flag_Deleted,
)
from uasset_read.pak.structures import (
    FPakEntry,
    FPakInfo,
    FPakCompressedBlock,
    FPakDirectoryEntry,
    read_fstring,
    decode_encoded_pak_entry,
)
from uasset_read.exceptions import ParseError


class TestPakQuality:
    """pak 模块质量验证。"""

    def test_pak_imports(self):
        """pak 模块可正常导入。"""
        from uasset_read.pak import structures
        assert structures is not None

    def test_pak_entry_roundtrip(self):
        """FPakEntry 序列化/反序列化往返一致性。"""
        entry = FPakEntry()
        entry.offset = 0x1000
        entry.size = 0x800
        entry.uncompressed_size = 0x1000
        entry.compression_method_index = 0
        entry.compression_block_size = 65536
        entry.hash = b'\x00' * 20
        # 验证基本属性
        assert entry.offset == 0x1000
        assert entry.size == 0x800


class TestEncodeBitfieldRoundtrip:
    """encode_bitfield → decode_bitfield 往返一致性。"""

    def test_roundtrip_uncompressed_block_size_zero(self):
        """未压缩 + block_size=0 的 roundtrip（关键缺陷场景）。

        当 compression_block_size=0 且 compression_method_index=0 时，
        编码器应正确处理 bitfield 和后续字段，使解码器能正确还原。
        """
        original = FPakEntry(
            offset=0x1000,
            uncompressed_size=0x2000,
            size=0x2000,
            compression_method_index=0,
            is_encrypted=False,
            compression_block_count=0,
            compression_block_size=0,
        )
        encoded = original.encode_bitfield()

        # 解码不应出错
        decoded, consumed = FPakEntry.decode_bitfield(encoded, 0, FPakInfo())

        assert decoded.offset == original.offset
        assert decoded.uncompressed_size == original.uncompressed_size
        assert decoded.compression_method_index == 0

    def test_roundtrip_compressed_block_size_zero_raises(self):
        """压缩 + block_size=0 应抛出 ValueError。

        当 compression_block_size=0 且 compression_method_index > 0 时，
        编码器应拒绝编解码不对称的状态。
        """
        original = FPakEntry(
            offset=0x1000,
            uncompressed_size=0x2000,
            size=0x1000,
            compression_method_index=2,
            is_encrypted=False,
            compression_block_count=0,
            compression_block_size=0,
        )
        with pytest.raises(ValueError, match="compression_block_size must be > 0"):
            original.encode_bitfield()

    def test_encode_bitfield_block_size_zero_no_stream_read(self):
        """block_size=0 时，编码后数据不应包含 block_size 流字段。

        验证编码器不会写入 0x3F 到 bitfield 同时省略 block_size 数据。
        """
        entry = FPakEntry(
            offset=0x1000,
            uncompressed_size=0x2000,
            size=0x2000,
            compression_method_index=0,
            compression_block_size=0,
        )
        encoded = entry.encode_bitfield()

        # 检查 bitfield 低 6 位不应是 0x3F（否则解码器会尝试读流数据）
        bitfield = struct.unpack_from('<I', encoded, 0)[0]
        block_size_index = bitfield & 0x3F
        assert block_size_index != 0x3F, (
            f"bitfield 低 6 位为 0x3F 但 block_size=0 时不应写入流数据"
        )

    def test_roundtrip_compressed_with_blocks(self):
        """压缩 + 有压缩块时的 roundtrip。"""
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
        assert consumed == len(encoded)


class TestDecompressEntrySafety:
    """decompress_entry 安全检查。"""

    def test_compressed_entry_empty_blocks_raises(self):
        """压缩条目无压缩块时应报错而非静默返回空数据。"""
        from uasset_read.pak.decompress import decompress_entry

        entry = FPakEntry(
            offset=0x1000,
            uncompressed_size=0x2000,
            size=0x1000,
            compression_method_index=2,
            is_compressed=True,
            compression_block_count=2,  # 声明有 2 个块
            compression_block_size=0x1000,
            compression_blocks=[],  # 但实际为空
        )

        fake_stream = io.BytesIO(b'\x00' * 0x10000)

        with pytest.raises(ParseError, match="缺少 compression_blocks"):
            decompress_entry(fake_stream, entry, compression_method="Zlib")

    def test_uncompressed_entry_empty_blocks_ok(self):
        """未压缩条目无压缩块时应正常读取数据。"""
        from uasset_read.pak.decompress import decompress_entry

        data = b'\xAB' * 0x100
        entry = FPakEntry(
            offset=0,
            uncompressed_size=0x100,
            size=0x100,
            compression_method_index=0,
            is_compressed=False,
            compression_block_count=0,
            compression_blocks=[],
        )

        fake_stream = io.BytesIO(data)
        result = decompress_entry(fake_stream, entry, compression_method="None")

        assert result == data

    def test_compressed_entry_encrypted_no_key_raises(self):
        """加密压缩条目无密钥时应报错。"""
        from uasset_read.pak.decompress import decompress_entry

        entry = FPakEntry(
            offset=0,
            uncompressed_size=0x100,
            size=0x100,
            is_encrypted=True,
            is_compressed=False,
        )

        fake_stream = io.BytesIO(b'\x00' * 0x100)
        with pytest.raises(ParseError, match="AES key"):
            decompress_entry(fake_stream, entry)


class TestReadFstringEdgeCases:
    """read_fstring 边界条件测试。"""

    def test_empty_string(self):
        """空字符串（length=0）。"""
        data = struct.pack('<i', 0)
        result = read_fstring(io.BytesIO(data))
        assert result == ""

    def test_normal_ascii(self):
        """正常 ASCII 字符串。"""
        text = "Hello"
        encoded = text.encode('ascii')
        data = struct.pack('<i', len(encoded)) + encoded + b'\x00'
        result = read_fstring(io.BytesIO(data))
        assert result == "Hello"

    def test_utf16_string(self):
        """UTF-16 编码的字符串（length < 0）。"""
        text = "ABC"
        utf16_data = text.encode('utf-16-le')
        length = -(len(text))  # 负数表示 UTF-16
        data = struct.pack('<i', length) + utf16_data + b'\x00\x00'
        result = read_fstring(io.BytesIO(data))
        assert result == "ABC"

    def test_truncated_read_raises(self):
        """截断的流应引发 ParseError。"""
        data = struct.pack('<i', 5)  # 声明 5 字节但流中没有数据
        with pytest.raises(ParseError, match="truncated"):
            read_fstring(io.BytesIO(data))

    def test_utf16_truncated_read_raises(self):
        """UTF-16 截断的流应引发 ParseError。"""
        length = -3  # 3 个 UTF-16 字符 = 6 字节
        data = struct.pack('<i', length) + b'\x00' * 2  # 只给 2 字节
        with pytest.raises(ParseError, match="truncated"):
            read_fstring(io.BytesIO(data))


class TestFPakInfoSerializedSizeConsistency:
    """FPakInfo 序列化大小一致性验证。"""

    def test_all_version_sizes_are_positive(self):
        """所有版本的序列化大小应为正数。"""
        for v in range(1, 13):
            size = FPakInfo._serialized_size(v)
            assert size > 0, f"版本 {v} 序列化大小为 {size}"

    def test_v9_larger_than_v8(self):
        """v9 应比 v8 大 1 字节（FrozenIndex）。"""
        assert FPakInfo._serialized_size(9) == FPakInfo._serialized_size(8) + 1

    def test_v10_plus_equals_v8(self):
        """v10+ 应与 v8 相同大小（FrozenIndex 移除）。"""
        assert FPakInfo._serialized_size(10) == FPakInfo._serialized_size(8)

    def test_pak_info_sizes_constant_sum_v1_6(self):
        """v1-6 常量验证（含 bEncryptedIndex）。"""
        assert PAK_INFO_SIZES["v1-6"] == 1 + 4 + 4 + 8 + 8 + 20  # 45

    def test_pak_info_sizes_constant_sum_v7(self):
        """v7 常量验证（EncryptionKeyGuid 已包含在 v1-6 base 中）。"""
        assert PAK_INFO_SIZES["v7"] == PAK_INFO_SIZES["v1-6"] + 16  # 61

    def test_pak_info_sizes_constant_sum_v8(self):
        """v8 常量验证。"""
        assert PAK_INFO_SIZES["v8"] == PAK_INFO_SIZES["v7"] + 32 * 5  # 221

    def test_pak_info_sizes_constant_sum_v9(self):
        """v9 常量验证。"""
        assert PAK_INFO_SIZES["v9"] == PAK_INFO_SIZES["v8"] + 1  # 222


class TestFPakInfoDeserialize:
    """FPakInfo.deserialize 反序列化测试。"""

    def _build_pak_info_trailer_v1_6(self, version=6, magic=PAK_FILE_MAGIC):
        """构建 v1-6 FPakInfo 尾部（含 bEncryptedIndex）。"""
        buf = io.BytesIO()
        buf.write(struct.pack('<B', 0))       # bEncryptedIndex (1 byte, always present)
        buf.write(struct.pack('<I', magic))
        buf.write(struct.pack('<i', version))
        buf.write(struct.pack('<q', 0x1000))  # index_offset
        buf.write(struct.pack('<q', 0x2000))  # index_size
        buf.write(b'\x00' * 20)              # index_hash
        return buf.getvalue()

    def test_deserialize_v6(self):
        """v6 FPakInfo 反序列化。"""
        data = self._build_pak_info_trailer_v1_6(version=6)
        info = FPakInfo.deserialize(io.BytesIO(data), len(data))
        assert info.version == 6
        assert info.index_offset == 0x1000
        assert info.index_size == 0x2000
        assert info.magic == PAK_FILE_MAGIC

    def test_deserialize_v7(self):
        """v7 FPakInfo 反序列化（含 EncryptionKeyGuid）。"""
        buf = io.BytesIO()
        buf.write(b'\x00' * 16)              # EncryptionKeyGuid
        buf.write(struct.pack('<B', 0))       # bEncryptedIndex
        buf.write(struct.pack('<I', PAK_FILE_MAGIC))
        buf.write(struct.pack('<i', 7))
        buf.write(struct.pack('<q', 0x3000))
        buf.write(struct.pack('<q', 0x4000))
        buf.write(b'\x00' * 20)
        data = buf.getvalue()
        info = FPakInfo.deserialize(io.BytesIO(data), len(data))
        assert info.version == 7
        assert info.index_offset == 0x3000

    def test_deserialize_no_magic_raises(self):
        """无有效魔数应引发 ParseError。"""
        data = b'\x00' * 222
        with pytest.raises(ParseError, match="no valid FPakInfo"):
            FPakInfo.deserialize(io.BytesIO(data), len(data))

    def test_deserialize_file_too_small(self):
        """文件过小时应引发 ParseError。"""
        data = b'\x00' * 10
        with pytest.raises(ParseError, match="no valid FPakInfo"):
            FPakInfo.deserialize(io.BytesIO(data), len(data))


class TestConstantsConsistency:
    """常量一致性验证。"""

    def test_pak_file_magic_is_uint32(self):
        """PAK_FILE_MAGIC 应在 uint32 范围内。"""
        assert 0 <= PAK_FILE_MAGIC <= 0xFFFFFFFF

    def test_all_game_magics_in_pak_file_magics(self):
        """所有游戏特定魔数应在 PAK_FILE_MAGICS 集合中。"""
        from uasset_read.pak.constants import (
            PAK_FILE_MAGIC_OUTLAST_TRIALS,
            PAK_FILE_MAGIC_TORCHLIGHT_INFINITE,
            PAK_FILE_MAGIC_WILD_ASSAULT,
            PAK_FILE_MAGIC_GAMELOOP_UNDAWN,
        )
        assert PAK_FILE_MAGIC_OUTLAST_TRIALS in PAK_FILE_MAGICS
        assert PAK_FILE_MAGIC_TORCHLIGHT_INFINITE in PAK_FILE_MAGICS
        assert PAK_FILE_MAGIC_WILD_ASSAULT in PAK_FILE_MAGICS
        assert PAK_FILE_MAGIC_GAMELOOP_UNDAWN in PAK_FILE_MAGICS

    def test_flag_constants(self):
        """标志常量应为单 bit 值。"""
        assert Flag_Encrypted == 0x01
        assert Flag_Deleted == 0x02
        assert Flag_Encrypted & Flag_Deleted == 0  # 无重叠

    def test_pak_file_version_monotonic(self):
        """版本枚举应单调递增。"""
        versions = [
            PakFileVersion.Initial,
            PakFileVersion.NoTimestamps,
            PakFileVersion.CompressionEncryption,
            PakFileVersion.IndexEncryption,
            PakFileVersion.RelativeChunkOffsets,
            PakFileVersion.DeleteRecords,
            PakFileVersion.EncryptionKeyGuid,
            PakFileVersion.FNameBasedCompressionMethod,
            PakFileVersion.FrozenIndex,
            PakFileVersion.PathHashIndex,
            PakFileVersion.Fnv64BugFix,
            PakFileVersion.Utf8PakDirectory,
        ]
        for i in range(1, len(versions)):
            assert versions[i] > versions[i - 1], (
                f"版本 {versions[i]} <= {versions[i-1]}"
            )


class TestGameVersions:
    """游戏版本映射测试。"""

    def test_detect_game_standard_magic(self):
        """标准魔数应返回 UNKNOWN。"""
        from uasset_read.pak.game_versions import detect_game_from_magic
        assert detect_game_from_magic(PAK_FILE_MAGIC) == 0  # EGame.UNKNOWN

    def test_detect_game_custom_magic(self):
        """自定义魔数应返回对应游戏。"""
        from uasset_read.pak.game_versions import (
            detect_game_from_magic,
            MAGIC_TO_GAME_MAP,
            EGame,
        )
        for magic, game in MAGIC_TO_GAME_MAP.items():
            assert detect_game_from_magic(magic) == game

    def test_get_game_info_unknown(self):
        """未知游戏应返回默认信息。"""
        from uasset_read.pak.game_versions import get_game_info, EGame
        name, version = get_game_info(EGame.UNKNOWN)
        assert name == "Unknown"
        assert isinstance(version, int)

    def test_all_games_have_info(self):
        """所有游戏标识都应有对应信息。"""
        from uasset_read.pak.game_versions import get_game_info, EGame
        games = [
            EGame.OUTLAST_TRIALS, EGame.TORCHLIGHT_INFINITE,
            EGame.WILD_ASSAULT, EGame.GAMELOOP_UNDAWN,
            EGame.BLACK_MYTH_WUKONG, EGame.STALKER_2,
            EGame.PUBG, EGame.FORTNITE,
        ]
        for game in games:
            name, version = get_game_info(game)
            assert name != "Unknown", f"游戏 {game} 无名称映射"
            assert isinstance(version, int)


class TestDecodeEncodedPakEntryFunction:
    """decode_encoded_pak_entry 函数测试。"""

    def test_disabled_returns_none(self):
        """禁用时返回 None。"""
        result = decode_encoded_pak_entry(b'\x00' * 4, is_enabled=False)
        assert result is None

    def test_short_data_returns_none(self):
        """数据不足 4 字节时返回 None。"""
        result = decode_encoded_pak_entry(b'\x00' * 3, is_enabled=True)
        assert result is None

    def test_all_fields_decoded(self):
        """验证所有位域字段正确解码。"""
        bf = 0
        bf |= 1 << 31  # offset_fits_32
        bf |= 1 << 30  # uncompressed_size_fits_32
        bf |= 1 << 29  # size_fits_32
        bf |= (2 & 0x3F) << 23  # compression_method = 2
        bf |= 1 << 22  # is_encrypted
        bf |= (3 & 0xFFFF) << 6  # block_count = 3
        bf |= 5 & 0x3F  # block_size_index = 5

        data = struct.pack('<I', bf) + b'\x00' * 16
        result = decode_encoded_pak_entry(data, is_enabled=True)
        assert result is not None
        assert result['offset_fits_32'] is True
        assert result['uncompressed_size_fits_32'] is True
        assert result['size_fits_32'] is True
        assert result['compression_method_index'] == 2
        assert result['is_encrypted'] is True
        assert result['compression_block_count'] == 3
        assert result['block_size_index'] == 5
