"""
Tests for pak module structures (FPakInfo, FPakEntry, etc.).

Phase 77 — PAK-01.
"""
import struct
import io
import pytest

from uasset_read.exceptions import ParseError
from uasset_read.pak.constants import (
    PAK_FILE_MAGIC,
    PakFileVersion,
    PAK_INFO_SIZES,
    Flag_Encrypted,
)
from uasset_read.pak.structures import (
    FPakCompressedBlock,
    FPakEntry,
    FPakInfo,
    FPakDirectoryEntry,
    read_fstring,
)


class TestFPakCompressedBlock:
    def test_construction(self):
        block = FPakCompressedBlock(compressed_start=100, compressed_end=200)
        assert block.compressed_start == 100
        assert block.compressed_end == 200


class TestReadFString:
    def test_empty_string(self):
        stream = io.BytesIO(struct.pack('<i', 0))
        assert read_fstring(stream) == ""

    def test_ansi_string(self):
        """Read an ANSI string: length=4, "test" + null terminator."""
        data = struct.pack('<i', 4) + b"test\x00"
        stream = io.BytesIO(data)
        result = read_fstring(stream)
        assert result == "test"

    def test_utf16_string(self):
        """Read a UTF-16 string: length=-2 (negative means UTF-16, 2 chars)."""
        text = "测试"
        utf16_bytes = text.encode('utf-16-le')
        data = struct.pack('<i', -len(text)) + utf16_bytes + b"\x00\x00"
        stream = io.BytesIO(data)
        result = read_fstring(stream)
        assert result == text

    def test_string_strips_trailing_null(self):
        """Trailing null should be stripped by rstrip."""
        data = struct.pack('<i', 5) + b"test\x00"
        stream = io.BytesIO(data)
        result = read_fstring(stream)
        assert result == "test"


class TestFPakInfo:
    def test_serialized_size(self):
        assert FPakInfo._serialized_size(1) == 44
        assert FPakInfo._serialized_size(6) == 44
        assert FPakInfo._serialized_size(7) == 61
        assert FPakInfo._serialized_size(8) == 221
        assert FPakInfo._serialized_size(9) == 222
        assert FPakInfo._serialized_size(10) == 221
        assert FPakInfo._serialized_size(12) == 221

    def test_deserialize_v8(self):
        """Deserialize a crafted v8 FPakInfo trailer."""
        info_size = PAK_INFO_SIZES["v8"]
        file_size = 1024
        trailer_pos = file_size - info_size

        # Build FPakInfo trailer for v8
        # New fields (v>=7): EncryptionKeyGuid(16) + bEncryptedIndex(1)
        encryption_key_guid = b"\x01" * 16
        b_encrypted_index = struct.pack('<B', 0)

        # Core fields: Magic(4) + Version(4) + IndexOffset(8) + IndexSize(8) + IndexHash(20)
        magic = struct.pack('<I', PAK_FILE_MAGIC)
        version = struct.pack('<i', 8)
        index_offset = struct.pack('<q', 100)
        index_size = struct.pack('<q', 500)
        index_hash = b"\xAB" * 20

        # Compression methods (v>=8): 5 * 32 bytes
        compression_methods = b""
        methods = ["None", "Zlib", "LZ4", "Zstd", "Oodle"]
        for method in methods:
            compression_methods += method.encode('ascii').ljust(32, b'\x00')

        # Assemble trailer
        trailer = encryption_key_guid + b_encrypted_index + magic + version + \
            index_offset + index_size + index_hash + compression_methods

        # Build full file: header data + trailer
        file_data = b"\x00" * trailer_pos + trailer
        assert len(file_data) == file_size

        stream = io.BytesIO(file_data)
        info = FPakInfo.deserialize(stream, file_size)

        assert info.version == 8
        assert info.magic == PAK_FILE_MAGIC
        assert info.index_offset == 100
        assert info.index_size == 500
        assert info.index_hash == b"\xAB" * 20
        assert info.encryption_key_guid == b"\x01" * 16
        assert info.encrypted_index is False
        assert "Zlib" in info.compression_methods
        assert "Zstd" in info.compression_methods

    def test_deserialize_v1(self):
        """Deserialize a minimal v1 FPakInfo (no new fields)."""
        info_size = PAK_INFO_SIZES["v1-6"]
        file_size = 512
        trailer_pos = file_size - info_size

        # Core fields only
        magic = struct.pack('<I', PAK_FILE_MAGIC)
        version = struct.pack('<i', 1)
        index_offset = struct.pack('<q', 50)
        index_size = struct.pack('<q', 200)
        index_hash = b"\xCD" * 20

        trailer = magic + version + index_offset + index_size + index_hash
        file_data = b"\x00" * trailer_pos + trailer

        stream = io.BytesIO(file_data)
        info = FPakInfo.deserialize(stream, file_size)

        assert info.version == 1
        assert info.index_offset == 50
        assert info.index_size == 200
        assert info.compression_methods == []

    def test_deserialize_v10(self):
        """Deserialize a v10 FPakInfo (no FrozenIndex, has compression methods)."""
        info_size = PAK_INFO_SIZES["v10+"]
        file_size = 2048
        trailer_pos = file_size - info_size

        encryption_key_guid = b"\xFF" * 16
        b_encrypted_index = struct.pack('<B', 1)
        magic = struct.pack('<I', PAK_FILE_MAGIC)
        version = struct.pack('<i', 10)
        index_offset = struct.pack('<q', 256)
        index_size = struct.pack('<q', 1024)
        index_hash = b"\xEF" * 20

        compression_methods = b""
        for method in ["None", "Zlib", ""]:
            compression_methods += method.encode('ascii').ljust(32, b'\x00')
        compression_methods = compression_methods.ljust(32 * 5, b'\x00')

        trailer = encryption_key_guid + b_encrypted_index + magic + version + \
            index_offset + index_size + index_hash + compression_methods

        file_data = b"\x00" * trailer_pos + trailer
        stream = io.BytesIO(file_data)
        info = FPakInfo.deserialize(stream, file_size)

        assert info.version == 10
        assert info.encrypted_index is True
        assert info.compression_methods == ["None", "Zlib"]
        assert info.index_is_frozen is False  # v10 has no frozen index

    def test_deserialize_garbage_raises(self):
        """FPakInfo.deserialize should raise ParseError for non-.pak data."""
        file_data = b"\x00" * 256
        stream = io.BytesIO(file_data)

        with pytest.raises(ParseError, match="Unknown .pak format"):
            FPakInfo.deserialize(stream, len(file_data))

    def test_deserialize_too_small_raises(self):
        """File smaller than smallest FPakInfo should raise."""
        file_data = b"\x00" * 10  # Way too small
        stream = io.BytesIO(file_data)

        with pytest.raises(ParseError, match="Unknown .pak format"):
            FPakInfo.deserialize(stream, len(file_data))


class TestFPakEntry:
    def test_deserialize_legacy_v1(self):
        """Deserialize a legacy (v<8) FPakEntry with uint16 block count."""
        entry_data = struct.pack('<q', 0)       # offset
        entry_data += struct.pack('<q', 1024)    # uncompressed_size
        entry_data += struct.pack('<q', 512)     # compressed size
        entry_data += struct.pack('<I', 1)       # compression_method_index
        # No timestamp (v>=2)
        entry_data += struct.pack('<H', 2)       # compression_block_count (uint16 for v<8)
        entry_data += struct.pack('<I', 256)     # compression_block_size
        # 2 compression blocks
        entry_data += struct.pack('<q', 100)     # block 0 start
        entry_data += struct.pack('<q', 300)     # block 0 end
        entry_data += struct.pack('<q', 300)     # block 1 start
        entry_data += struct.pack('<q', 512)     # block 1 end
        entry_data += b"\x01" * 20              # hash

        stream = io.BytesIO(entry_data)
        entry = FPakEntry.deserialize_legacy(stream, version=7)

        assert entry.offset == 0
        assert entry.uncompressed_size == 1024
        assert entry.size == 512
        assert entry.compression_method_index == 1
        assert entry.compression_block_count == 2
        assert entry.compression_block_size == 256
        assert len(entry.compression_blocks) == 2
        assert entry.compression_blocks[0].compressed_start == 100
        assert entry.compression_blocks[0].compressed_end == 300
        assert entry.compression_blocks[1].compressed_start == 300
        assert entry.compression_blocks[1].compressed_end == 512
        assert entry.hash == b"\x01" * 20
        assert entry.is_compressed is True

    def test_deserialize_legacy_v8(self):
        """Deserialize a v8+ FPakEntry with uint32 block count."""
        entry_data = struct.pack('<q', 0)       # offset
        entry_data += struct.pack('<q', 4096)    # uncompressed_size
        entry_data += struct.pack('<q', 4096)    # size (uncompressed)
        entry_data += struct.pack('<I', 0)       # compression_method_index (None)
        entry_data += struct.pack('<I', 0)       # compression_block_count (uint32 for v>=8)
        entry_data += struct.pack('<I', 0)       # compression_block_size
        entry_data += b"\x00" * 20              # hash

        stream = io.BytesIO(entry_data)
        entry = FPakEntry.deserialize_legacy(stream, version=8)

        assert entry.offset == 0
        assert entry.compression_block_count == 0
        assert entry.is_compressed is False

    def test_decode_bitfield_basic(self):
        """Decode a basic bitfield entry where all values fit in 32-bit."""
        # Bitfield: offset_fits_32 + uncompressed_size_fits_32 + size_fits_32
        bitfield = (1 << 31) | (1 << 30) | (1 << 29)  # All fit in 32-bit
        bitfield |= (1 << 23)  # compression_method_index = 1
        bitfield |= (1 << 22)  # encrypted
        bitfield |= (100 << 6)  # block_count = 100
        bitfield |= (0x3F)  # block_size_index = 0x3F (read from stream)

        # Actual values (all 32-bit since they fit)
        data = struct.pack('<I', bitfield)
        data += struct.pack('<I', 0x1000)     # offset = 4096
        data += struct.pack('<I', 0x10000)    # uncompressed_size = 65536
        data += struct.pack('<I', 0x8000)     # size = 32768
        data += struct.pack('<I', 1024)       # block_size from stream

        pak_info = FPakInfo(version=10)
        entry, consumed = FPakEntry.decode_bitfield(data, 0, pak_info)

        assert entry.offset == 0x1000
        assert entry.uncompressed_size == 0x10000
        assert entry.size == 0x8000
        assert entry.compression_method_index == 1
        assert entry.is_encrypted is True
        assert entry.compression_block_count == 100
        assert entry.compression_block_size == 1024
        assert consumed > 0

    def test_decode_bitfield_64bit_offset(self):
        """Decode bitfield with offset that needs 64-bit."""
        bitfield = (0 << 31)  # offset does NOT fit in 32-bit
        bitfield |= (1 << 30)  # uncompressed_size fits in 32-bit
        bitfield |= (1 << 29)  # size fits in 32-bit

        data = struct.pack('<I', bitfield)
        data += struct.pack('<q', 0x1_0000_0000)  # offset = 4GB (needs 64-bit)
        data += struct.pack('<I', 0x1000)          # uncompressed_size
        data += struct.pack('<I', 0x800)           # size

        pak_info = FPakInfo(version=10)
        entry, consumed = FPakEntry.decode_bitfield(data, 0, pak_info)

        assert entry.offset == 0x1_0000_0000
        assert entry.uncompressed_size == 0x1000


class TestFPakDirectoryEntry:
    def test_construction(self):
        entry = FPakEntry(offset=0, uncompressed_size=100)
        dir_entry = FPakDirectoryEntry(
            path="Game/Content",
            filename="test.txt",
            entry=entry,
        )
        assert dir_entry.path == "Game/Content"
        assert dir_entry.filename == "test.txt"
        assert dir_entry.entry is entry
