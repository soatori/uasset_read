"""
Pak 文件 AES-ECB 加密/解密模块

用于加密索引和文件条目的 AES-ECB 解密。
"""
import hashlib

from uasset_read.exceptions import ParseError


def decrypt_aes_ecb(data: bytes, key: bytes) -> bytes:
    """使用 AES-ECB 解密数据（无填充，16-byte 对齐）。

    匹配 UE 引擎的 FAES::DecryptData。

    Args:
        data: 加密数据
        key: AES 密钥（16 bytes / 128-bit）

    Returns:
        解密后的数据（裁剪到原始长度）

    Raises:
        ValueError: 密钥长度不正确
        ImportError: 缺少 cryptography 包
    """
    if len(key) != 16:
        raise ValueError("AES key must be 16 bytes (128-bit)")

    original_len = len(data)

    # Align to 16-byte boundary
    aligned_size = (original_len + 15) & ~15
    if original_len < aligned_size:
        data = data + b'\x00' * (aligned_size - original_len)

    # Lazy import with helpful error
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError:
        raise ImportError(
            "AES decryption requires 'cryptography' package"
        )

    # ECB mode — mandated by UE PAK format (FAES::DecryptData).
    # This is a read-only parser matching UE's spec, not a security choice.
    # nosemgrep: python.lang.security.audit.cbc-not-used.cbc-not-used
    cipher = Cipher(algorithms.AES(key), modes.ECB())  # noqa: S305
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(data) + decryptor.finalize()

    # Trim to original length
    return decrypted[:original_len]


def validate_index_hash(decrypted_index_blob: bytes, expected_hash: bytes) -> bool:
    """验证解密后的索引 blob 的 SHA1 哈希。

    Args:
        decrypted_index_blob: 解密后的索引数据
        expected_hash: 期望的 SHA1 哈希（20 bytes）

    Returns:
        True 如果哈希匹配
    """
    computed_hash = hashlib.sha1(decrypted_index_blob).digest()
    return computed_hash == expected_hash


def decrypt_index_blob(index_data: bytes, key: bytes, expected_hash: bytes) -> bytes:
    """解密索引 blob 并验证哈希。

    便捷包装函数：先解密，后验证 SHA1。

    Args:
        index_data: 加密的索引数据
        key: AES 密钥（16 bytes）
        expected_hash: 期望的 SHA1 哈希

    Returns:
        解密并验证后的索引数据

    Raises:
        ParseError: 哈希验证失败
    """
    decrypted = decrypt_aes_ecb(index_data, key)
    if not validate_index_hash(decrypted, expected_hash):
        raise ParseError(
            "Index hash mismatch — decrypted index blob is corrupted or wrong AES key"
        )
    return decrypted
