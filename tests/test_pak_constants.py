"""
Tests for pak module constants.

Phase 77 — PAK-01.
"""
import pytest

from uasset_read.pak.constants import (
    PAK_FILE_MAGIC,
    PakFileVersion,
    ECompressionFlags,
    Flag_Encrypted,
    Flag_Deleted,
    MaxNumCompressionMethods,
    PAK_INFO_SIZES,
)


class TestPakFileMagic:
    def test_magic_value(self):
        assert PAK_FILE_MAGIC == 0x5A6F12E1

    def test_magic_is_uint32(self):
        assert 0 <= PAK_FILE_MAGIC <= 0xFFFFFFFF


class TestPakFileVersion:
    def test_version_values(self):
        assert PakFileVersion.Initial == 1
        assert PakFileVersion.NoTimestamps == 2
        assert PakFileVersion.EncryptionKeyGuid == 7
        assert PakFileVersion.FNameBasedCompressionMethod == 8
        assert PakFileVersion.PathHashIndex == 10
        assert PakFileVersion.Frostbite == 11
        assert PakFileVersion.Utf8PakDirectory == 12

    def test_version_range(self):
        """All versions are sequential."""
        versions = list(PakFileVersion)
        values = [v.value for v in versions]
        # Check known values exist (not all consecutive due to v3-6 gaps)
        assert 1 in values
        assert 2 in values
        assert 7 in values
        assert 8 in values
        assert 10 in values
        assert 11 in values
        assert 12 in values


class TestECompressionFlags:
    def test_flag_values(self):
        assert ECompressionFlags.NONE == 0
        assert ECompressionFlags.Zlib == 1
        assert ECompressionFlags.Gzip == 2
        assert ECompressionFlags.LZ4 == 4
        assert ECompressionFlags.Zstd == 8
        assert ECompressionFlags.Oodle == 16

    def test_deprecated_flags(self):
        assert ECompressionFlags.COMPRESS_ZLIB_DEPRECATED == 256
        assert ECompressionFlags.COMPRESS_GZIP_DEPRECATED == 512

    def test_bitwise_operations(self):
        """Flags can be combined."""
        combined = ECompressionFlags.Zlib | ECompressionFlags.LZ4
        assert combined == 5
        assert ECompressionFlags.Zlib in combined


class TestPakEntryFlags:
    def test_flag_encrypted(self):
        assert Flag_Encrypted == 0x01

    def test_flag_deleted(self):
        assert Flag_Deleted == 0x02

    def test_flags_dict(self):
        from uasset_read.pak.constants import PAK_ENTRY_FLAGS
        assert PAK_ENTRY_FLAGS["Flag_Encrypted"] == 0x01
        assert PAK_ENTRY_FLAGS["Flag_Deleted"] == 0x02


class TestOtherConstants:
    def test_max_compression_methods(self):
        assert MaxNumCompressionMethods == 5

    def test_pak_info_sizes(self):
        assert PAK_INFO_SIZES["v1-6"] == 44
        assert PAK_INFO_SIZES["v7"] == 61
        assert PAK_INFO_SIZES["v8"] == 221
        assert PAK_INFO_SIZES["v9"] == 222
        assert PAK_INFO_SIZES["v10+"] == 221

    def test_pak_info_size_correctness(self):
        """Verify sizes match UE engine field layout.

        v1-6: Magic(4) + Version(4) + IndexOffset(8) + IndexSize(8) + IndexHash(20) = 44
        v7: + EncryptionKeyGuid(16) + bEncryptedIndex(1) = 44 + 17 = 61
        v8: + CompressionMethods(32*5=160) = 61 + 160 = 221
        v9: + FrozenIndex(1) = 221 + 1 = 222
        v10+: - FrozenIndex = 222 - 1 = 221
        """
        assert PAK_INFO_SIZES["v1-6"] == 4 + 4 + 8 + 8 + 20
        assert PAK_INFO_SIZES["v7"] == PAK_INFO_SIZES["v1-6"] + 16 + 1
        assert PAK_INFO_SIZES["v8"] == PAK_INFO_SIZES["v7"] + 32 * 5
        assert PAK_INFO_SIZES["v9"] == PAK_INFO_SIZES["v8"] + 1
        assert PAK_INFO_SIZES["v10+"] == PAK_INFO_SIZES["v9"] - 1
