"""
Pak file AES-ECB encryption/decryption module.

AES-ECB decryption for encrypted index and file entries.
"""

import hashlib

from uasset_read.exceptions import ParseError


def decrypt_aes_ecb(data: bytes, key: bytes) -> bytes:
    """Decrypt data using AES-ECB (no padding, 16-byte aligned).

    Matches UE engine's FAES::DecryptData.

    Args:
        data: Encrypted data
        key: AES key (16 bytes / 128-bit)

    Returns:
        Decrypted data (trimmed to original length)

    Raises:
        ValueError: Incorrect key length
        ImportError: Missing cryptography package
    """
    if len(key) != 16:
        raise ValueError("AES key must be 16 bytes (128-bit)")

    original_len = len(data)

    # Align to 16-byte boundary
    aligned_size = (original_len + 15) & ~15
    if original_len < aligned_size:
        data = data + b"\x00" * (aligned_size - original_len)

    # Lazy import with helpful error
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError:
        raise ImportError("AES decryption requires 'cryptography' package")

    # ECB mode — mandated by UE PAK format (FAES::DecryptData).
    # This is a read-only parser matching UE's spec, not a security choice.
    # nosemgrep: python.lang.security.audit.cbc-not-used.cbc-not-used
    cipher = Cipher(algorithms.AES(key), modes.ECB())  # noqa: S305
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(data) + decryptor.finalize()

    # Trim to original length
    return decrypted[:original_len]


def validate_index_hash(decrypted_index_blob: bytes, expected_hash: bytes) -> bool:
    """Validate SHA1 hash of decrypted index blob.

    Args:
        decrypted_index_blob: Decrypted index data
        expected_hash: Expected SHA1 hash (20 bytes)

    Returns:
        True if hash matches
    """
    computed_hash = hashlib.sha1(decrypted_index_blob).digest()
    return computed_hash == expected_hash


def decrypt_index_blob(index_data: bytes, key: bytes, expected_hash: bytes) -> bytes:
    """Decrypt index blob and validate hash.

    Convenience wrapper: decrypt first, then validate SHA1.

    Args:
        index_data: Encrypted index data
        key: AES key (16 bytes)
        expected_hash: Expected SHA1 hash

    Returns:
        Decrypted and validated index data

    Raises:
        ParseError: Hash validation failed
    """
    decrypted = decrypt_aes_ecb(index_data, key)
    if not validate_index_hash(decrypted, expected_hash):
        raise ParseError("Index hash mismatch — decrypted index blob is corrupted or wrong AES key")
    return decrypted
