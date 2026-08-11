"""
Consolidated PAK module tests.

Selected tests from:
- tests/pak/test_decompress_bomb.py (compression bomb guard)
- tests/pak/test_pak_index_coverage.py (index parsing, encrypted flag)
- tests/pak/test_fpak_entry_layout.py (entry deserialization)
- tests/test_pak_codec_symmetry.py (bitfield roundtrip)
"""
from __future__ import annotations

import struct
import zlib
from io import BytesIO
from unittest.mock import patch

from uasset_read.pak.constants import PakFileVersion
from uasset_read.pak.decompress import decompress_block
from uasset_read.pak.index import parse_primary_index
from uasset_read.pak.structures import FPakCompressedBlock, FPakEntry, FPakInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_pak_info(
    version: int = PakFileVersion.Initial,
    index_offset: int = 0,
    index_size: int = 100,
    encrypted_index: bool = False,
) -> FPakInfo:
    """Create a test FPakInfo."""
    info = FPakInfo()
    info.version = version
    info.index_offset = index_offset
    info.index_size = index_size
    info.index_hash = b'\x00' * 20
    info.encrypted_index = encrypted_index
    return info


def _mock_validate_index_hash(blob: bytes, expected_hash: bytes) -> bool:
    """Stub index hash validation — always returns True."""
    return True


def _write_fstring(stream: BytesIO, text: str, version: int = 0) -> None:
    """Write an FString to stream."""
    if version >= PakFileVersion.Utf8PakDirectory:
        data = text.encode('utf-8')
        stream.write(struct.pack('<I', len(data)))
        stream.write(data)
        stream.write(b'\x00')
    else:
        data = text.encode('ascii')
        stream.write(struct.pack('<i', len(data)))
        stream.write(data)
        stream.write(b'\x00')


def _write_legacy_entry(stream: BytesIO, entry: FPakEntry, version: int) -> None:
    """Write a legacy-format FPakEntry (aligned with UE FPakEntry::Serialize)."""
    stream.write(struct.pack('<q', entry.offset))
    stream.write(struct.pack('<q', entry.size))
    stream.write(struct.pack('<q', entry.uncompressed_size))
    stream.write(struct.pack('<I', entry.compression_method_index))

    if version < PakFileVersion.NoTimestamps:
        stream.write(struct.pack('<q', 0))

    stream.write(entry.hash.ljust(20, b'\x00')[:20])

    if version >= PakFileVersion.CompressionEncryption:
        if entry.compression_method_index != 0:
            if version < PakFileVersion.FNameBasedCompressionMethod:
                stream.write(struct.pack('<H', entry.compression_block_count))
            else:
                stream.write(struct.pack('<I', entry.compression_block_count))
            for _ in range(entry.compression_block_count):
                stream.write(struct.pack('<q', 0))
                stream.write(struct.pack('<q', 0))

        stream.write(struct.pack('<B', entry.flags))
        stream.write(struct.pack('<I', entry.compression_block_size))


def _create_legacy_index_blob(
    mount_point: str,
    entries: list[tuple[str, FPakEntry]],
    version: int = PakFileVersion.Initial,
) -> bytes:
    """Create a legacy-format index blob."""
    stream = BytesIO()
    _write_fstring(stream, mount_point, version)
    stream.write(struct.pack('<i', len(entries)))
    for path, entry in entries:
        _write_fstring(stream, path, version)
        _write_legacy_entry(stream, entry, version)
    return stream.getvalue()


def _ue_serialize_legacy_entry(
    entry: FPakEntry,
    version: int,
    *,
    extra_hash: bytes | None = None,
) -> bytes:
    """Serialize an FPakEntry exactly per UE FPakEntry::Serialize."""
    buf = BytesIO()
    buf.write(struct.pack('<q', entry.offset))
    buf.write(struct.pack('<q', entry.size))
    buf.write(struct.pack('<q', entry.uncompressed_size))
    buf.write(struct.pack('<I', entry.compression_method_index))

    if version < PakFileVersion.NoTimestamps:
        buf.write(struct.pack('<q', 0))

    h = extra_hash if extra_hash is not None else entry.hash
    buf.write(h.ljust(20, b'\x00')[:20])

    if version >= PakFileVersion.CompressionEncryption:
        if entry.compression_method_index != 0:
            if version < PakFileVersion.FNameBasedCompressionMethod:
                buf.write(struct.pack('<H', entry.compression_block_count))
            else:
                buf.write(struct.pack('<I', entry.compression_block_count))
            for blk in entry.compression_blocks:
                buf.write(struct.pack('<q', blk.compressed_start))
                buf.write(struct.pack('<q', blk.compressed_end))
        buf.write(struct.pack('<B', entry.flags))
        buf.write(struct.pack('<I', entry.compression_block_size))

    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. Compression bomb guard
# ---------------------------------------------------------------------------

class TestDecompressBombGuard:
    """Decompress output must be clamped to declared uncompressed_size."""

    def test_zlib_output_clamped_to_declared_size(self):
        """Zlib bomb: 5 MB payload declared as 1 byte must not inflate past limit."""
        payload = b"A" * (5 * 1024 * 1024)
        bomb = zlib.compress(payload, 9)
        result = decompress_block(bomb, uncompressed_size=1, method="Zlib")
        assert len(result) <= 1024, f"Output {len(result)} bytes, expected <= 1024"


# ---------------------------------------------------------------------------
# 2. Index parsing — legacy v1 with entry
# ---------------------------------------------------------------------------

class TestIndexParsingLegacy:
    """parse_primary_index legacy format roundtrip."""

    @patch('uasset_read.pak.crypto.validate_index_hash', _mock_validate_index_hash)
    def test_legacy_index_v1_roundtrip(self):
        """Legacy v1 index: mount point + one entry parsed correctly."""
        entries = [("/Game/Test.uasset", FPakEntry(offset=100, size=200))]
        index_blob = _create_legacy_index_blob("/", entries, version=1)
        pak_info = _create_pak_info(version=1, index_offset=0, index_size=len(index_blob))

        stream = BytesIO(index_blob)
        mount_point, entries_dict, extra_info = parse_primary_index(stream, pak_info)

        assert mount_point == "/"
        assert "/Game/Test.uasset" in entries_dict
        assert entries_dict["/Game/Test.uasset"].offset == 100
        assert extra_info == {}


# ---------------------------------------------------------------------------
# 3. FPakEntry legacy deserialization — hash before compression blocks
# ---------------------------------------------------------------------------

class TestFpakEntryLegacyDeserialization:
    """Hash must be read before CompressionBlocks (UE IPlatformFilePak.h)."""

    def test_v8_compressed_hash_position(self):
        """v8 compressed entry: hash preserved, compression blocks intact."""
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

        assert decoded.hash == b'\xAA' * 20
        assert decoded.compression_block_count == 1
        assert decoded.compression_blocks[0].compressed_start == 0
        assert decoded.compression_blocks[0].compressed_end == 0x80


# ---------------------------------------------------------------------------
# 4. Bitfield encode/decode roundtrip
# ---------------------------------------------------------------------------

class TestBitfieldRoundtrip:
    """encode_bitfield -> decode_bitfield must be symmetric."""

    def test_compressed_entry_roundtrip(self):
        entry = FPakEntry(
            offset=0x1000,
            uncompressed_size=4096,
            size=2048,
            compression_method_index=1,
            is_encrypted=False,
            compression_block_count=4,
            compression_block_size=4096,
        )
        encoded = entry.encode_bitfield()
        pak_info = _create_pak_info()
        decoded, consumed = FPakEntry.decode_bitfield(encoded, 0, pak_info)

        assert decoded.offset == entry.offset
        assert decoded.uncompressed_size == entry.uncompressed_size
        assert decoded.size == entry.size
        assert decoded.compression_method_index == entry.compression_method_index
        assert decoded.compression_block_count == entry.compression_block_count
        assert decoded.compression_block_size == entry.compression_block_size
