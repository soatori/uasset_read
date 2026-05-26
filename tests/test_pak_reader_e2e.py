"""
End-to-end tests for PakFileReader.

Phase 77 — PAK-04.
"""
import io
import struct
import zlib
import hashlib
import tempfile
import os
import pytest

from uasset_read.exceptions import ParseError
from uasset_read.pak.constants import PAK_FILE_MAGIC, PakFileVersion, PAK_INFO_SIZES
from uasset_read.pak.structures import FPakInfo, FPakEntry, FPakCompressedBlock
from uasset_read.pak.reader import PakFileReader
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def _build_complete_pak(
    version: int,
    file_contents: dict[str, bytes],
    compression_method: str = "None",
    compress_entries: bool = False,
    encrypt_index: bool = False,
    aes_key: bytes | None = None,
) -> bytes:
    """Build a complete .pak file in memory for testing.

    Structure:
    [file content area] [index blob] [FPakInfo trailer]
    """
    content_start = 0
    entries: dict[str, FPakEntry] = {}
    content_data = bytearray()

    for path, content in file_contents.items():
        if compress_entries:
            compressed = zlib.compress(content, 9)[2:]  # raw deflate
            entry_offset = len(content_data)
            entry = FPakEntry(
                offset=entry_offset,
                uncompressed_size=len(content),
                size=len(compressed),
                compression_method_index=1,  # Zlib
                is_compressed=True,
                compression_block_count=1,
                compression_block_size=len(content),
                compression_blocks=[
                    FPakCompressedBlock(
                        compressed_start=entry_offset,
                        compressed_end=entry_offset + len(compressed),
                    )
                ],
            )
            content_data.extend(compressed)
        else:
            entry_offset = len(content_data)
            entry = FPakEntry(
                offset=entry_offset,
                uncompressed_size=len(content),
                size=len(content),
                compression_method_index=0,  # None
                compression_block_count=0,
                compression_block_size=0,
            )
            content_data.extend(content)

        entries[path] = entry

    # Build index blob
    mount_point = "../../../"
    index_blob = _build_index_blob(version, mount_point, entries, compress_entries)

    # Hash (of plaintext if encrypted; note: decrypt_aes_ecb pads to 16-byte alignment)
    if encrypt_index:
        aligned_size = (len(index_blob) + 15) & ~15
        padded = index_blob.ljust(aligned_size, b'\x00')
        index_hash = hashlib.sha1(padded).digest()
    else:
        index_hash = hashlib.sha1(index_blob).digest()

    if encrypt_index and aes_key:
        index_blob = _aes_encrypt(index_blob, aes_key)

    # Build FPakInfo trailer
    info_size = PAK_INFO_SIZES.get(
        f"v{version}" if version != 8 else "v8",
        PAK_INFO_SIZES["v10+"] if version >= 10 else PAK_INFO_SIZES["v8"],
    )

    index_offset = len(content_data)

    # Build trailer based on version
    trailer = _build_info_trailer(version, index_offset, len(index_blob), index_hash, encrypt_index)

    file_data = bytes(content_data) + index_blob + trailer
    return file_data


def _build_index_blob(version: int, mount_point: str, entries: dict[str, FPakEntry], compress: bool) -> bytes:
    """Build an index blob for the given version and entries."""
    buf = io.BytesIO()

    # Mount point
    mp_bytes = mount_point.encode('ascii')
    buf.write(struct.pack('<i', len(mp_bytes)))
    buf.write(mp_bytes)
    buf.write(b'\x00')

    buf.write(struct.pack('<i', len(entries)))

    if version < PakFileVersion.PathHashIndex:
        # Legacy: flat (path, FPakEntry) list
        for path, entry in entries.items():
            path_bytes = path.encode('ascii')
            buf.write(struct.pack('<i', len(path_bytes)))
            buf.write(path_bytes)
            buf.write(b'\x00')

            buf.write(struct.pack('<q', entry.offset))
            buf.write(struct.pack('<q', entry.uncompressed_size))
            buf.write(struct.pack('<q', entry.size))
            buf.write(struct.pack('<I', entry.compression_method_index))
            if version < 8:
                buf.write(struct.pack('<H', entry.compression_block_count))
            else:
                buf.write(struct.pack('<I', entry.compression_block_count))
            buf.write(struct.pack('<I', entry.compression_block_size))
            # Compression blocks
            for block in entry.compression_blocks:
                buf.write(struct.pack('<q', block.compressed_start))
                buf.write(struct.pack('<q', block.compressed_end))
            buf.write(b'\x00' * 20)  # hash
    else:
        # v10+: PathHashIndex format
        buf.write(struct.pack('<Q', 12345))  # PathHashSeed
        buf.write(struct.pack('<B', 0))      # bHasPathHashIndex = false
        buf.write(struct.pack('<B', 0))      # bHasDirectoryIndex = false

        # EncodedPakEntries: 0
        buf.write(struct.pack('<I', 0))

        # NonEncodedEntries
        buf.write(struct.pack('<I', len(entries)))
        for path, entry in entries.items():
            path_bytes = path.encode('ascii')
            bitfield = (1 << 31) | (1 << 30) | (1 << 29)
            bitfield |= (entry.compression_method_index & 0x3F) << 23
            bitfield |= (entry.compression_block_count & 0xFFFF) << 6
            bitfield |= 0x3F  # read block size from stream

            entry_buf = io.BytesIO()
            entry_buf.write(struct.pack('<I', bitfield))
            entry_buf.write(struct.pack('<I', entry.offset))
            entry_buf.write(struct.pack('<I', entry.uncompressed_size))
            entry_buf.write(struct.pack('<I', entry.size))
            entry_buf.write(struct.pack('<I', entry.compression_block_size))
            entry_data = entry_buf.getvalue()

            buf.write(struct.pack('<i', len(path_bytes)))
            buf.write(path_bytes)
            buf.write(b'\x00')
            buf.write(struct.pack('<I', len(entry_data)))
            buf.write(entry_data)

    return buf.getvalue()


def _build_info_trailer(
    version: int,
    index_offset: int,
    index_size: int,
    index_hash: bytes,
    encrypted_index: bool = False,
) -> bytes:
    """Build FPakInfo trailer for the given version."""
    if version >= PakFileVersion.EncryptionKeyGuid:
        encryption_key_guid = b"\x01" * 16
        b_encrypted = struct.pack('<B', 1 if encrypted_index else 0)
    else:
        encryption_key_guid = b""
        b_encrypted = b""

    magic = struct.pack('<I', PAK_FILE_MAGIC)
    ver = struct.pack('<i', version)
    idx_off = struct.pack('<q', index_offset)
    idx_size = struct.pack('<q', index_size)

    trailer = encryption_key_guid + b_encrypted + magic + ver + idx_off + idx_size + index_hash

    if version == 9:
        trailer += struct.pack('<B', 0)  # bFrozenIndex

    if version >= PakFileVersion.FNameBasedCompressionMethod:
        for method in ["None", "Zlib", "LZ4", "Zstd", "Oodle"]:
            trailer += method.encode('ascii').ljust(32, b'\x00')

    return trailer


def _aes_encrypt(plaintext: bytes, key: bytes) -> bytes:
    """AES-ECB encrypt for test fixtures."""
    aligned_size = (len(plaintext) + 15) & ~15
    padded = plaintext.ljust(aligned_size, b'\x00')
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    encryptor = cipher.encryptor()
    return encryptor.update(padded) + encryptor.finalize()


class TestPakFileReaderLegacy:
    """Test PakFileReader with legacy (v8) format."""

    def test_open_legacy_pak(self):
        """Open a crafted legacy .pak file."""
        content = b"Hello from legacy pak file!!!"
        pak_data = _build_complete_pak(8, {"Game/Content/test.txt": content})

        with tempfile.NamedTemporaryFile(suffix='.pak', delete=False) as f:
            f.write(pak_data)
            f.flush()

            with PakFileReader(f.name) as reader:
                assert reader.info is not None
                assert reader.info.version == 8
                assert reader.mount_point == "../../../"
                assert len(reader.entries) == 1
                assert "Game/Content/test.txt" in reader.entries

    def test_extract_uncompressed(self):
        """Extract an uncompressed file from a legacy pak."""
        content = b"Extract me if you can! Padding to reasonable length."
        pak_data = _build_complete_pak(8, {"Game/Content/data.bin": content})

        with tempfile.NamedTemporaryFile(suffix='.pak', delete=False) as f:
            f.write(pak_data)
            f.flush()

            with PakFileReader(f.name) as reader:
                data = reader.extract("Game/Content/data.bin")
                assert data == content

    def test_list_files(self):
        """list_files returns all non-deleted paths."""
        files = {
            "Game/Content/a.txt": b"content a",
            "Game/Content/b.txt": b"content b",
            "Game/Content/c.txt": b"content c",
        }
        pak_data = _build_complete_pak(8, files)

        with tempfile.NamedTemporaryFile(suffix='.pak', delete=False) as f:
            f.write(pak_data)
            f.flush()

            with PakFileReader(f.name) as reader:
                listed = reader.list_files()
                assert len(listed) == 3
                assert "Game/Content/a.txt" in listed

    def test_get_entry_not_found(self):
        """get_entry returns None for unknown path."""
        pak_data = _build_complete_pak(8, {"Game/Content/test.txt": b"data"})

        with tempfile.NamedTemporaryFile(suffix='.pak', delete=False) as f:
            f.write(pak_data)
            f.flush()

            with PakFileReader(f.name) as reader:
                assert reader.get_entry("nonexistent.txt") is None

    def test_extract_not_found(self):
        """extract returns None for unknown path."""
        pak_data = _build_complete_pak(8, {"Game/Content/test.txt": b"data"})

        with tempfile.NamedTemporaryFile(suffix='.pak', delete=False) as f:
            f.write(pak_data)
            f.flush()

            with PakFileReader(f.name) as reader:
                assert reader.extract("nonexistent.txt") is None


class TestPakFileReaderV10:
    """Test PakFileReader with v10+ format."""

    def test_open_v10_pak(self):
        """Open a crafted v10+ .pak file."""
        content = b"Hello from v10 pak file!!! Extended for size"
        pak_data = _build_complete_pak(10, {"Game/Content/test_v10.txt": content})

        with tempfile.NamedTemporaryFile(suffix='.pak', delete=False) as f:
            f.write(pak_data)
            f.flush()

            with PakFileReader(f.name) as reader:
                assert reader.info is not None
                assert reader.info.version == 10
                assert len(reader.entries) == 1
                assert "Game/Content/test_v10.txt" in reader.entries

    def test_extract_v10(self):
        """Extract a file from v10+ pak."""
        content = b"Extract from v10! Some padding here too!!"
        pak_data = _build_complete_pak(10, {"Game/Content/v10_file.bin": content})

        with tempfile.NamedTemporaryFile(suffix='.pak', delete=False) as f:
            f.write(pak_data)
            f.flush()

            with PakFileReader(f.name) as reader:
                data = reader.extract("Game/Content/v10_file.bin")
                assert data == content


class TestPakFileReaderCompressed:
    """Test PakFileReader with compressed entries."""

    def test_extract_compressed_entry(self):
        """Extract a Zlib-compressed entry."""
        content = b"This is compressed content that will be zlib compressed for testing"
        pak_data = _build_complete_pak(8, {"Game/Content/compressed.txt": content}, compress_entries=True)

        with tempfile.NamedTemporaryFile(suffix='.pak', delete=False) as f:
            f.write(pak_data)
            f.flush()

            with PakFileReader(f.name) as reader:
                entry = reader.get_entry("Game/Content/compressed.txt")
                assert entry is not None
                assert entry.is_compressed is True

                data = reader.extract("Game/Content/compressed.txt")
                assert data == content


class TestPakFileReaderEncryptedIndex:
    """Test PakFileReader with encrypted index."""

    def test_encrypted_index_correct_key(self):
        """Open pak with encrypted index using correct AES key."""
        key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
        content = b"Encrypted index test content!!"
        pak_data = _build_complete_pak(
            8, {"Game/Content/encrypted.bin": content},
            encrypt_index=True, aes_key=key,
        )

        with tempfile.NamedTemporaryFile(suffix='.pak', delete=False) as f:
            f.write(pak_data)
            f.flush()

            with PakFileReader(f.name, aes_key=key) as reader:
                assert reader.info is not None
                assert reader.info.encrypted_index is True
                assert len(reader.entries) == 1

    def test_encrypted_index_wrong_key(self):
        """Wrong AES key should raise ParseError."""
        key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
        wrong_key = bytes.fromhex("00000000000000000000000000000000")
        content = b"Encrypted index test content!!"
        pak_data = _build_complete_pak(
            8, {"Game/Content/encrypted.bin": content},
            encrypt_index=True, aes_key=key,
        )

        with tempfile.NamedTemporaryFile(suffix='.pak', delete=False) as f:
            f.write(pak_data)
            f.flush()

            with pytest.raises(ParseError, match="Index hash mismatch"):
                with PakFileReader(f.name, aes_key=wrong_key) as reader:
                    pass

    def test_encrypted_index_no_key(self):
        """No AES key for encrypted index should raise ParseError."""
        key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
        content = b"Encrypted index test content!!"
        pak_data = _build_complete_pak(
            8, {"Game/Content/encrypted.bin": content},
            encrypt_index=True, aes_key=key,
        )

        with tempfile.NamedTemporaryFile(suffix='.pak', delete=False) as f:
            f.write(pak_data)
            f.flush()

            with pytest.raises(ParseError, match="Encrypted index requires AES key"):
                with PakFileReader(f.name, aes_key=None) as reader:
                    pass


class TestPakFileReaderContextManager:
    """Test context manager behavior."""

    def test_context_manager_opens_and_closes(self):
        """Context manager should open on enter and close on exit."""
        pak_data = _build_complete_pak(8, {"test.txt": b"data"})

        with tempfile.NamedTemporaryFile(suffix='.pak', delete=False) as f:
            f.write(pak_data)
            f.flush()
            path = f.name

        reader = PakFileReader(path)
        with reader:
            assert reader._file is not None
            assert reader.info is not None

        assert reader._file is None


class TestRealPakIntegration:
    """Integration tests with real .pak files (skip if not available)."""

    @pytest.mark.integration
    def test_real_pak_parse(self):
        """Open a real .pak file and verify basic parsing."""
        pak_path = os.environ.get("PAK_TEST_FILE")
        if not pak_path or not os.path.exists(pak_path):
            pytest.skip("No real .pak file available (set PAK_TEST_FILE env var)")

        with PakFileReader(pak_path) as reader:
            assert reader.info is not None
            assert reader.info.version > 0
            assert len(reader.entries) > 0

            files = reader.list_files()
            assert len(files) > 0

            # Extract first file
            first = files[0]
            data = reader.extract(first)
            assert data is not None
            assert len(data) > 0
