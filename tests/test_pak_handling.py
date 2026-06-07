from __future__ import annotations

from io import BytesIO
import struct
import zlib

import pytest

from uasset_read.exceptions import ParseError
import uasset_read.pak.crypto as pak_crypto
import uasset_read.pak.reader as pak_reader_module
from uasset_read.pak.constants import PakFileVersion
from uasset_read.pak.decompress import decompress_entry
from uasset_read.pak.reader import PakFileReader
from uasset_read.pak.structures import FPakCompressedBlock, FPakEntry, FPakInfo


def test_decompress_entry_reads_uncompressed_plain_bytes():
    entry = FPakEntry(offset=2, uncompressed_size=5, is_compressed=False)

    assert decompress_entry(BytesIO(b"xxhello trailing"), entry) == b"hello"


def test_decompress_entry_rejects_uncompressed_encrypted_without_key():
    entry = FPakEntry(
        offset=0,
        uncompressed_size=5,
        is_encrypted=True,
        is_compressed=False,
    )

    with pytest.raises(ParseError, match="requires AES key"):
        decompress_entry(BytesIO(b"ciphertext"), entry)


def test_decompress_entry_decrypts_uncompressed_encrypted_bytes(monkeypatch):
    calls = []

    def fake_decrypt(data: bytes, key: bytes) -> bytes:
        calls.append((data, key))
        return b"hello decrypted"

    monkeypatch.setattr(pak_crypto, "decrypt_aes_ecb", fake_decrypt)
    entry = FPakEntry(
        offset=0,
        uncompressed_size=5,
        is_encrypted=True,
        is_compressed=False,
    )

    result = decompress_entry(BytesIO(b"ciphertext000000"), entry, encryption_key=b"k" * 16)

    assert result == b"hello"
    assert calls == [(b"ciphertext000000", b"k" * 16)]


def test_decompress_entry_wraps_missing_crypto_as_parse_error(monkeypatch):
    def missing_crypto(data: bytes, key: bytes) -> bytes:
        raise ImportError("cryptography is missing")

    monkeypatch.setattr(pak_crypto, "decrypt_aes_ecb", missing_crypto)
    entry = FPakEntry(
        offset=0,
        uncompressed_size=5,
        is_encrypted=True,
        is_compressed=False,
    )

    with pytest.raises(ParseError, match="cryptography"):
        decompress_entry(BytesIO(b"ciphertext000000"), entry, encryption_key=b"k" * 16)


def test_decompress_entry_rejects_compressed_encrypted_without_key():
    entry = FPakEntry(
        is_encrypted=True,
        is_compressed=True,
        compression_block_size=5,
        compression_blocks=[FPakCompressedBlock(0, 5)],
    )

    with pytest.raises(ParseError, match="requires AES key"):
        decompress_entry(BytesIO(b"ciphertext"), entry, compression_method="None")


def test_reader_maps_compression_method_index_from_one(monkeypatch):
    seen = {}

    def fake_decompress(stream, entry, compression_method, encryption_key):
        seen["method"] = compression_method
        return b"payload"

    monkeypatch.setattr(pak_reader_module, "decompress_entry", fake_decompress)
    reader = PakFileReader("unused.pak")
    reader._file = BytesIO(b"payload")
    reader._file_size = 7
    reader._info = FPakInfo(compression_methods=["LZ4"])
    reader._entries = {
        "Game/A.uasset": FPakEntry(
            offset=0,
            uncompressed_size=7,
            compression_method_index=1,
            is_compressed=True,
        )
    }

    assert reader.extract("Game/A.uasset") == b"payload"
    assert seen["method"] == "LZ4"


def test_reader_resolves_paths_like_package_provider(monkeypatch):
    def fake_decompress(stream, entry, compression_method, encryption_key):
        return b"payload"

    monkeypatch.setattr(pak_reader_module, "decompress_entry", fake_decompress)
    reader = PakFileReader("unused.pak")
    reader._file = BytesIO(b"payload")
    reader._file_size = 7
    reader._info = FPakInfo(compression_methods=[])
    reader._entries = {
        "Game/Folder/A.uasset": FPakEntry(offset=0, uncompressed_size=7),
    }

    assert reader.get_entry("folder/a") is reader._entries["Game/Folder/A.uasset"]
    assert reader.extract("/game/folder/a.uasset") == b"payload"
    assert reader.extract("A") == b"payload"
    assert reader.extract("Missing") is None


def test_reader_rejects_traversal_path_before_exact_match():
    reader = PakFileReader("unused.pak")
    reader._entries = {
        "../evil.uasset": FPakEntry(offset=0, uncompressed_size=7),
    }

    assert reader.get_entry("../evil.uasset") is None
    assert reader.extract("../evil.uasset") is None


def test_reader_rejects_out_of_range_compression_method_index():
    reader = PakFileReader("unused.pak")
    reader._file = BytesIO(b"payload")
    reader._file_size = 7
    reader._info = FPakInfo(compression_methods=["Zlib"])
    reader._entries = {
        "Game/A.uasset": FPakEntry(
            offset=0,
            uncompressed_size=7,
            compression_method_index=2,
            is_compressed=True,
        )
    }

    with pytest.raises(ParseError, match="out of range"):
        reader.extract("Game/A.uasset")


def test_decompress_entry_reads_compressed_block_and_bad_method():
    payload = b"pak compressed payload"
    compressed = zlib.compress(payload)
    entry = FPakEntry(
        offset=0,
        uncompressed_size=len(payload),
        is_compressed=True,
        compression_block_size=len(payload),
        compression_blocks=[FPakCompressedBlock(0, len(compressed))],
    )

    assert decompress_entry(BytesIO(compressed), entry, compression_method="zlib") == payload

    with pytest.raises(ValueError, match="Unknown compression method"):
        decompress_entry(BytesIO(compressed), entry, compression_method="NoSuchMethod")


def _legacy_entry_bytes(version: int, timestamp: bool) -> bytes:
    parts = [
        struct.pack("<q", 10),
        struct.pack("<q", 5),
        struct.pack("<q", 5),
        struct.pack("<I", 0),
    ]
    if timestamp:
        parts.append(struct.pack("<q", 123456))
    count_fmt = "<H" if version < PakFileVersion.FNameBasedCompressionMethod else "<I"
    parts.extend([
        struct.pack(count_fmt, 0),
        struct.pack("<I", 65536),
        b"h" * 20,
    ])
    return b"".join(parts)


def test_legacy_v1_entry_consumes_timestamp():
    stream = BytesIO(_legacy_entry_bytes(PakFileVersion.Initial, timestamp=True))

    entry = FPakEntry.deserialize_legacy(stream, PakFileVersion.Initial)

    assert entry.compression_block_count == 0
    assert entry.compression_block_size == 65536
    assert stream.tell() == len(stream.getvalue())


def test_legacy_v2_entry_does_not_consume_timestamp():
    stream = BytesIO(_legacy_entry_bytes(PakFileVersion.NoTimestamps, timestamp=False))

    entry = FPakEntry.deserialize_legacy(stream, PakFileVersion.NoTimestamps)

    assert entry.compression_block_count == 0
    assert entry.compression_block_size == 65536
    assert stream.tell() == len(stream.getvalue())
