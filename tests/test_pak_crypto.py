"""
Tests for pak module AES-ECB crypto.

Phase 77 — PAK-03.
"""
import hashlib
import pytest

from uasset_read.exceptions import ParseError

# Skip all crypto tests if cryptography package is not available
pytest.importorskip("cryptography", reason="cryptography package not installed")

from uasset_read.pak.crypto import (
    decrypt_aes_ecb,
    validate_index_hash,
    decrypt_index_blob,
)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class TestDecryptAesEcb:
    def test_nist_test_vector(self):
        """AES-ECB decrypt of NIST test vector.

        NIST AES-128-ECB test vector:
        Key: 2b7e151628aed2a6abf7158809cf4f3c
        Plaintext: 6bc1bee22e409f96e93d7e117393172a
        Ciphertext: 3ad77bb40d7a3660a89ecaf32466ef97
        """
        key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
        ciphertext = bytes.fromhex("3ad77bb40d7a3660a89ecaf32466ef97")
        expected_plaintext = bytes.fromhex("6bc1bee22e409f96e93d7e117393172a")

        result = decrypt_aes_ecb(ciphertext, key)
        assert result == expected_plaintext

    def test_16_byte_alignment(self):
        """Aligned data decrypts correctly."""
        key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
        plaintext = b"\x42" * 16  # Exactly one block

        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        cipher = Cipher(algorithms.AES(key), modes.ECB())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(plaintext) + encryptor.finalize()

        result = decrypt_aes_ecb(encrypted, key)
        assert len(result) == 16
        assert result == plaintext

    def test_invalid_key_length(self):
        """Non-16-byte key should raise ValueError."""
        with pytest.raises(ValueError, match="AES key must be 16 bytes"):
            decrypt_aes_ecb(b"\x00" * 16, b"\x00" * 8)

    def test_key_16_bytes_accepted(self):
        """16-byte key should be accepted."""
        key = bytes(range(16))
        data = b"\x00" * 16
        result = decrypt_aes_ecb(data, key)
        assert len(result) == 16  # No exception means valid key


class TestValidateIndexHash:
    def test_valid_hash(self):
        """SHA1 of valid data should match."""
        data = b"test index blob content"
        expected_hash = hashlib.sha1(data).digest()
        assert validate_index_hash(data, expected_hash) is True

    def test_tampered_data(self):
        """SHA1 of tampered data should not match."""
        data = b"original data"
        expected_hash = hashlib.sha1(data).digest()
        tampered = b"tampered data"
        assert validate_index_hash(tampered, expected_hash) is False

    def test_empty_data(self):
        """Empty data hash validation."""
        data = b""
        expected_hash = hashlib.sha1(data).digest()
        assert validate_index_hash(data, expected_hash) is True


class TestDecryptIndexBlob:
    def test_round_trip(self):
        """Encrypt, decrypt, validate — round trip."""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

        key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
        plaintext = b"index blob content here!!!"  # Must be 16-byte aligned

        # Pad to 16 bytes
        aligned = len(plaintext)
        if aligned % 16 != 0:
            aligned = (aligned + 15) & ~15
            plaintext_padded = plaintext.ljust(aligned, b'\x00')
        else:
            plaintext_padded = plaintext

        # Encrypt
        cipher = Cipher(algorithms.AES(key), modes.ECB())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(plaintext_padded) + encryptor.finalize()

        # Compute hash of padded data (what was actually encrypted)
        expected_hash = hashlib.sha1(plaintext_padded).digest()

        # Decrypt and validate
        decrypted = decrypt_index_blob(encrypted, key, expected_hash)
        assert decrypted == plaintext_padded

    def test_wrong_key_raises_parse_error(self):
        """Wrong AES key should raise ParseError."""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

        key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
        wrong_key = bytes.fromhex("00000000000000000000000000000000")
        plaintext = b"index blob content!!"

        # Pad and encrypt
        aligned = (len(plaintext) + 15) & ~15
        plaintext_padded = plaintext.ljust(aligned, b'\x00')
        cipher = Cipher(algorithms.AES(key), modes.ECB())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(plaintext_padded) + encryptor.finalize()

        expected_hash = hashlib.sha1(plaintext).digest()

        with pytest.raises(ParseError, match="Index hash mismatch"):
            decrypt_index_blob(encrypted, wrong_key, expected_hash)
