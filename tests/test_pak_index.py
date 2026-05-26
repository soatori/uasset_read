"""
Tests for pak module index parsing.

Phase 77 — PAK-04.
"""
import io
import struct
import hashlib
import zlib
import pytest

from uasset_read.exceptions import ParseError
from uasset_read.pak.constants import PAK_FILE_MAGIC, PakFileVersion, PAK_INFO_SIZES
from uasset_read.pak.structures import FPakInfo, FPakEntry, FPakDirectoryEntry
from uasset_read.pak.index import (
    parse_primary_index,
    parse_path_hash_index,
    parse_directory_index,
)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class TestParseLegacyIndex:
    """Test legacy (v<10) index parsing."""

    def _build_legacy_index_blob(self, mount_point: str, entries: list[tuple[str, FPakEntry]], version: int) -> bytes:
        """Build a legacy index blob in memory."""
        buf = io.BytesIO()

        # Mount point (FString)
        mp_bytes = mount_point.encode('ascii')
        buf.write(struct.pack('<i', len(mp_bytes)))
        buf.write(mp_bytes)
        buf.write(b'\x00')

        # Num entries
        buf.write(struct.pack('<i', len(entries)))

        # Entries
        for path, entry in entries:
            # Path (FString)
            path_bytes = path.encode('ascii')
            buf.write(struct.pack('<i', len(path_bytes)))
            buf.write(path_bytes)
            buf.write(b'\x00')

            # FPakEntry (legacy format)
            buf.write(struct.pack('<q', entry.offset))
            buf.write(struct.pack('<q', entry.uncompressed_size))
            buf.write(struct.pack('<q', entry.size))
            buf.write(struct.pack('<I', entry.compression_method_index))
            if version < PakFileVersion.FNameBasedCompressionMethod:
                buf.write(struct.pack('<H', entry.compression_block_count))
            else:
                buf.write(struct.pack('<I', entry.compression_block_count))
            buf.write(struct.pack('<I', entry.compression_block_size))
            # Compression blocks (none for uncompressed)
            buf.write(b'\x00' * 20)  # hash

        return buf.getvalue()

    def test_parse_single_uncompressed_entry(self):
        """Parse a legacy index with one uncompressed entry."""
        mount_point = "../../../"
        entry = FPakEntry(
            offset=0,
            uncompressed_size=44,
            size=44,
            compression_method_index=0,
            compression_block_count=0,
            compression_block_size=0,
        )
        content = b"test file content here padded to 44 bytes!!!"
        assert len(content) == 44

        # Build full pak file: content + index blob + FPakInfo trailer
        index_blob = self._build_legacy_index_blob(mount_point, [("Game/Content/test.txt", entry)], version=8)
        index_hash = hashlib.sha1(index_blob).digest()

        # Build FPakInfo trailer (v8)
        info_size = PAK_INFO_SIZES["v8"]
        index_offset = len(content)

        encryption_key_guid = b"\x00" * 16
        b_encrypted_index = struct.pack('<B', 0)
        magic = struct.pack('<I', PAK_FILE_MAGIC)
        version = struct.pack('<i', 8)
        idx_off = struct.pack('<q', index_offset)
        idx_size = struct.pack('<q', len(index_blob))
        idx_hash = index_hash

        compression_methods = b""
        for method in ["None", "Zlib", "LZ4", "Zstd", "Oodle"]:
            compression_methods += method.encode('ascii').ljust(32, b'\x00')

        trailer = encryption_key_guid + b_encrypted_index + magic + version + \
            idx_off + idx_size + idx_hash + compression_methods

        file_data = content + index_blob + trailer
        assert len(file_data) == index_offset + len(index_blob) + info_size

        stream = io.BytesIO(file_data)
        info = FPakInfo.deserialize(stream, len(file_data))
        assert info.version == 8

        mount_point_out, entries, extra = parse_primary_index(stream, info)
        assert mount_point_out == mount_point
        assert len(entries) == 1
        assert "Game/Content/test.txt" in entries
        assert entries["Game/Content/test.txt"].offset == 0

    def test_parse_multiple_entries(self):
        """Parse a legacy index with multiple entries."""
        mount_point = "../../../"
        entries_in = []
        for i in range(3):
            e = FPakEntry(
                offset=i * 100,
                uncompressed_size=50,
                size=50,
                compression_method_index=0,
                compression_block_count=0,
                compression_block_size=0,
            )
            entries_in.append((f"Game/Content/file_{i}.bin", e))

        index_blob = self._build_legacy_index_blob(mount_point, entries_in, version=8)
        index_hash = hashlib.sha1(index_blob).digest()

        info_size = PAK_INFO_SIZES["v8"]
        index_offset = 300  # fake content area

        encryption_key_guid = b"\x00" * 16
        b_encrypted_index = struct.pack('<B', 0)
        magic = struct.pack('<I', PAK_FILE_MAGIC)
        version = struct.pack('<i', 8)
        idx_off = struct.pack('<q', index_offset)
        idx_size = struct.pack('<q', len(index_blob))
        idx_hash = index_hash

        compression_methods = b""
        for method in ["None", "Zlib", "LZ4", "Zstd", "Oodle"]:
            compression_methods += method.encode('ascii').ljust(32, b'\x00')

        trailer = encryption_key_guid + b_encrypted_index + magic + version + \
            idx_off + idx_size + idx_hash + compression_methods

        file_data = b"\x00" * index_offset + index_blob + trailer

        stream = io.BytesIO(file_data)
        info = FPakInfo.deserialize(stream, len(file_data))

        mount_point_out, entries, extra = parse_primary_index(stream, info)
        assert mount_point_out == mount_point
        assert len(entries) == 3
        assert "Game/Content/file_0.bin" in entries
        assert "Game/Content/file_2.bin" in entries


class TestParseV10Index:
    """Test v10+ index parsing with bitfield-encoded entries."""

    def _build_v10_index_blob(self, mount_point: str, named_entries: dict[str, FPakEntry], pak_info: FPakInfo) -> bytes:
        """Build a v10+ index blob with encoded + non-encoded entries."""
        buf = io.BytesIO()

        # Mount point
        mp_bytes = mount_point.encode('ascii')
        buf.write(struct.pack('<i', len(mp_bytes)))
        buf.write(mp_bytes)
        buf.write(b'\x00')

        # Num entries (total)
        total = len(named_entries)  # simplified: only named entries
        buf.write(struct.pack('<i', total))

        # PathHashSeed
        buf.write(struct.pack('<Q', 12345))

        # bHasPathHashIndex = false
        buf.write(struct.pack('<B', 0))

        # bHasDirectoryIndex = false
        buf.write(struct.pack('<B', 0))

        # EncodedPakEntries: 0
        buf.write(struct.pack('<I', 0))

        # NonEncodedEntries
        buf.write(struct.pack('<I', len(named_entries)))
        for path, entry in named_entries.items():
            # Serialize entry using bitfield encoding
            path_bytes = path.encode('ascii')
            # We need to manually build the bitfield + values
            # For simplicity, set all fits_32 flags
            bitfield = (1 << 31) | (1 << 30) | (1 << 29)  # all fit in 32-bit
            bitfield |= (entry.compression_method_index & 0x3F) << 23
            if entry.is_encrypted:
                bitfield |= (1 << 22)
            bitfield |= (entry.compression_block_count & 0xFFFF) << 6
            bitfield |= 0x3F  # block size index = read from stream

            entry_buf = io.BytesIO()
            entry_buf.write(struct.pack('<I', bitfield))
            entry_buf.write(struct.pack('<I', entry.offset))
            entry_buf.write(struct.pack('<I', entry.uncompressed_size))
            entry_buf.write(struct.pack('<I', entry.size))
            entry_buf.write(struct.pack('<I', entry.compression_block_size))

            entry_data = entry_buf.getvalue()
            serialized_size = len(entry_data)

            buf.write(struct.pack('<i', len(path_bytes)))
            buf.write(path_bytes)
            buf.write(b'\x00')
            buf.write(struct.pack('<I', serialized_size))
            buf.write(entry_data)

        return buf.getvalue()

    def test_parse_v10_named_entries(self):
        """Parse v10+ index with non-encoded (named) entries."""
        mount_point = "../../../"
        named = {
            "Game/Content/test_v10.txt": FPakEntry(
                offset=0,
                uncompressed_size=100,
                size=100,
                compression_method_index=0,
                compression_block_count=0,
                compression_block_size=0,
            ),
        }

        info = FPakInfo(
            version=10,
            index_offset=500,
            index_size=0,  # will be set below
            index_hash=b"",
            compression_methods=["None", "Zlib"],
        )

        index_blob = self._build_v10_index_blob(mount_point, named, info)
        index_hash = hashlib.sha1(index_blob).digest()
        info.index_size = len(index_blob)
        info.index_hash = index_hash

        content = b"\x00" * 500
        file_data = content + index_blob

        stream = io.BytesIO(file_data)
        mount_out, entries, extra = parse_primary_index(stream, info)
        assert mount_out == mount_point
        assert len(entries) == 1
        assert "Game/Content/test_v10.txt" in entries
        entry = entries["Game/Content/test_v10.txt"]
        assert entry.offset == 0
        assert entry.uncompressed_size == 100


class TestParsePathHashIndex:
    """Test PathHashIndex parsing."""

    def test_parse_basic(self):
        """Parse a basic PathHashIndex with 2 entries."""
        entries = {
            0xDEADBEEF1: (100, 50),
            0xDEADBEEF2: (200, 75),
        }

        buf = io.BytesIO()
        buf.write(struct.pack('<I', len(entries)))
        for path_hash, (file_offset, size) in entries.items():
            buf.write(struct.pack('<Q', path_hash))
            buf.write(struct.pack('<q', file_offset))
            buf.write(struct.pack('<q', size))

        data = buf.getvalue()
        file_stream = io.BytesIO(data)
        info = FPakInfo(version=10)

        result = parse_path_hash_index(file_stream, 0, len(data), info)
        assert len(result) == 2
        assert result[0xDEADBEEF1] == (100, 50)
        assert result[0xDEADBEEF2] == (200, 75)


class TestParseDirectoryIndex:
    """Test DirectoryIndex parsing."""

    def test_parse_basic(self):
        """Parse a basic DirectoryIndex."""
        buf = io.BytesIO()
        buf.write(struct.pack('<I', 1))  # 1 directory
        # Directory name
        dir_name = b"Game/Content\x00"
        buf.write(struct.pack('<i', len(dir_name) - 1))
        buf.write(dir_name)
        # Files
        buf.write(struct.pack('<I', 2))  # 2 files
        # File 1
        file1 = b"file1.txt\x00"
        buf.write(struct.pack('<i', len(file1) - 1))
        buf.write(file1)
        buf.write(struct.pack('<q', 100))
        buf.write(struct.pack('<q', 50))
        # File 2
        file2 = b"file2.txt\x00"
        buf.write(struct.pack('<i', len(file2) - 1))
        buf.write(file2)
        buf.write(struct.pack('<q', 200))
        buf.write(struct.pack('<q', 75))

        data = buf.getvalue()
        file_stream = io.BytesIO(data)
        info = FPakInfo(version=10)

        result = parse_directory_index(file_stream, 0, len(data), info)
        assert len(result) == 1
        assert "Game/Content" in result
        assert "file1.txt" in result["Game/Content"]
        assert result["Game/Content"]["file1.txt"] == (100, 50)
        assert result["Game/Content"]["file2.txt"] == (200, 75)


class TestEncryptedIndex:
    """Test encrypted index parsing."""

    def _encrypt_index_blob(self, plaintext: bytes, key: bytes) -> bytes:
        """AES-ECB encrypt (for test fixture generation)."""
        aligned_size = (len(plaintext) + 15) & ~15
        padded = plaintext.ljust(aligned_size, b'\x00')
        cipher = Cipher(algorithms.AES(key), modes.ECB())
        encryptor = cipher.encryptor()
        return encryptor.update(padded) + encryptor.finalize()

    def test_encrypted_index_round_trip(self):
        """Parse an encrypted index with correct AES key."""
        key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
        mount_point = "../../../"
        path = "Game/Content/encrypted.txt"

        # Build plain index blob
        buf = io.BytesIO()
        mp_bytes = mount_point.encode('ascii')
        buf.write(struct.pack('<i', len(mp_bytes)))
        buf.write(mp_bytes)
        buf.write(b'\x00')
        buf.write(struct.pack('<i', 1))  # 1 entry

        # Entry
        entry = FPakEntry(
            offset=0,
            uncompressed_size=30,
            size=30,
            compression_method_index=0,
            compression_block_count=0,
            compression_block_size=0,
        )
        path_bytes = path.encode('ascii')
        buf.write(struct.pack('<i', len(path_bytes)))
        buf.write(path_bytes)
        buf.write(b'\x00')
        buf.write(struct.pack('<q', entry.offset))
        buf.write(struct.pack('<q', entry.uncompressed_size))
        buf.write(struct.pack('<q', entry.size))
        buf.write(struct.pack('<I', entry.compression_method_index))
        buf.write(struct.pack('<I', entry.compression_block_count))
        buf.write(struct.pack('<I', entry.compression_block_size))
        buf.write(b'\x00' * 20)  # hash

        index_blob = buf.getvalue()

        # Encrypt
        encrypted = self._encrypt_index_blob(index_blob, key)
        # Hash of the padded plaintext (what was actually encrypted)
        aligned_size = (len(index_blob) + 15) & ~15
        padded = index_blob.ljust(aligned_size, b'\x00')
        index_hash = hashlib.sha1(padded).digest()

        # Build FPakInfo with encrypted_index=True
        info = FPakInfo(
            version=8,
            index_offset=500,
            index_size=len(encrypted),
            index_hash=index_hash,
            encrypted_index=True,
            encryption_key_guid=b"\x01" * 16,
            compression_methods=["None", "Zlib"],
        )

        file_data = b"\x00" * 500 + encrypted
        stream = io.BytesIO(file_data)

        mount_out, entries, extra = parse_primary_index(stream, info, aes_key=key)
        assert mount_out == mount_point
        assert len(entries) == 1
        assert path in entries
