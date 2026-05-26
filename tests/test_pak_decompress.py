"""
Tests for pak module decompression dispatch.

Phase 77 — PAK-02.
"""
import io
import struct
import zlib
import pytest

from uasset_read.pak.structures import FPakEntry, FPakCompressedBlock
from uasset_read.pak.decompress import decompress_block, decompress_entry


class TestDecompressBlock:
    def test_none_returns_unchanged(self):
        assert decompress_block(b"test", 4, "None") == b"test"
        assert decompress_block(b"test", 4, "") == b"test"

    def test_zlib_round_trip(self):
        original = b"Hello, World! This is a test of zlib compression."
        compressed = zlib.compress(original, 9)[2:]  # Strip zlib header (raw deflate)
        result = decompress_block(compressed, len(original), "Zlib")
        assert result == original

    def test_oodle_raises_not_implemented(self):
        with pytest.raises(NotImplementedError, match="Oodle decompression"):
            decompress_block(b"\x00", 10, "Oodle")

    def test_unknown_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown compression method"):
            decompress_block(b"\x00", 10, "Brotli")


class TestDecompressEntry:
    def test_uncompressed_entry(self):
        """Uncompressed entry reads directly."""
        content = b"uncompressed file content here"
        stream = io.BytesIO(content)
        entry = FPakEntry(
            offset=0,
            uncompressed_size=len(content),
            is_compressed=False,
        )
        result = decompress_entry(stream, entry)
        assert result == content

    def test_compressed_entry_single_block(self):
        """Compressed entry with single block decompresses correctly."""
        original = b"This is test content that will be compressed"
        compressed = zlib.compress(original, 9)[2:]  # raw deflate

        stream = io.BytesIO(compressed)
        entry = FPakEntry(
            offset=0,
            uncompressed_size=len(original),
            size=len(compressed),
            compression_method_index=1,
            is_compressed=True,
            compression_block_count=1,
            compression_block_size=len(original),
            compression_blocks=[
                FPakCompressedBlock(compressed_start=0, compressed_end=len(compressed))
            ],
        )
        result = decompress_entry(stream, entry, compression_method="Zlib")
        assert result == original
