"""Verification coverage for AES-aligned encrypted IoStore range reads."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest

from uasset_read.exceptions import ParseError
from uasset_read.iostore import reader as iostore_reader


AES_BLOCK_SIZE = 16
AES_KEY = b"k" * AES_BLOCK_SIZE


def _make_reader(ciphertext: bytes, *, compression_blocks: list[object]):
    reader = iostore_reader.IoStoreReader("container.utoc", aes_key=AES_KEY)
    reader._header = SimpleNamespace(is_encrypted=True, partition_size=0)
    reader._ucas_files = [BytesIO(ciphertext)]
    reader._compression_blocks = compression_blocks
    reader._compression_block_size = 64
    return reader


def _assert_aligned_decryption(monkeypatch, plaintext: bytes, ciphertext: bytes):
    decrypted_inputs: list[bytes] = []

    def decrypt(data: bytes, key: bytes) -> bytes:
        assert key == AES_KEY
        assert len(data) % AES_BLOCK_SIZE == 0
        decrypted_inputs.append(data)
        assert data == ciphertext
        return plaintext

    monkeypatch.setattr(iostore_reader, "decrypt_aes_ecb", decrypt)
    return decrypted_inputs


def test_encrypted_uncompressed_partitions_aligns_range_before_decryption(monkeypatch):
    plaintext = bytes(range(32))
    ciphertext = b"c" * 32
    reader = _make_reader(ciphertext, compression_blocks=[])
    decrypted_inputs = _assert_aligned_decryption(monkeypatch, plaintext, ciphertext)

    assert reader._read_data(5, 19) == plaintext[5:24]
    assert decrypted_inputs == [ciphertext]


def test_encrypted_single_uncompressed_block_aligns_range_before_decryption(monkeypatch):
    plaintext = bytes(range(32))
    ciphertext = b"c" * 32
    block = SimpleNamespace(offset=0, compression_method_index=0)
    reader = _make_reader(ciphertext, compression_blocks=[block])
    decrypted_inputs = _assert_aligned_decryption(monkeypatch, plaintext, ciphertext)

    assert reader._read_data(5, 19) == plaintext[5:24]
    assert decrypted_inputs == [ciphertext]


def test_encrypted_single_uncompressed_block_uses_physical_block_range(monkeypatch):
    plaintext = bytes(range(32))
    ciphertext = b"p" * 32
    block = SimpleNamespace(offset=80, compression_method_index=0)
    reader = _make_reader(b"l" * 64, compression_blocks=[block])
    reader._header.partition_size = 64
    reader._ucas_files = [
        BytesIO(b"l" * 64),
        BytesIO(b"x" * 16 + ciphertext + b"y" * 16),
    ]
    decrypted_inputs = _assert_aligned_decryption(monkeypatch, plaintext, ciphertext)

    assert reader._read_data(5, 19) == plaintext[5:24]
    assert decrypted_inputs == [ciphertext]


def test_encrypted_uncompressed_partition_raises_when_aligned_ciphertext_is_short(monkeypatch):
    reader = _make_reader(b"c" * 24, compression_blocks=[])
    monkeypatch.setattr(iostore_reader, "decrypt_aes_ecb", lambda data, key: data)

    with pytest.raises(ParseError, match="IoStore partition read insufficient"):
        reader._read_data(5, 19)
