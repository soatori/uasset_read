"""
Pak 文件解压缩模块

支持 Zlib/LZ4/Zstd/Oodle 压缩方法分派。
- Zlib: Python stdlib，始终可用
- LZ4/Zstd: 可选 PyPI 包，延迟导入
- Oodle: 不支持（专有库），优雅降级
"""
import gzip
import zlib
from typing import BinaryIO

from uasset_read.exceptions import ParseError
from uasset_read.pak.structures import FPakEntry


def normalize_compression_method(method: str | int | None) -> str:
    """Return the canonical compression method name used by readers."""
    if method is None:
        return "None"
    if isinstance(method, int):
        return {
            0: "None",
            1: "Zlib",
            2: "Gzip",
            3: "Oodle",
            4: "LZ4",
            5: "Zstd",
        }.get(method, str(method))
    normalized = method.strip()
    if not normalized:
        return "None"
    aliases = {
        "none": "None",
        "zlib": "Zlib",
        "gzip": "Gzip",
        "gz": "Gzip",
        "lz4": "LZ4",
        "oodle": "Oodle",
        "zstd": "Zstd",
        "zstandard": "Zstd",
    }
    return aliases.get(normalized.lower(), normalized)


def decompress_block(data: bytes, uncompressed_size: int, method: str | int | None) -> bytes:
    """解压单个压缩块。

    Args:
        data: 压缩数据
        uncompressed_size: 期望的解压后大小
        method: 压缩方法名称（"None", "Zlib", "LZ4", "Zstd", "Oodle"）

    Returns:
        解压后的数据

    Raises:
        NotImplementedError: Oodle 不支持
        ValueError: 未知的压缩方法
        ImportError: 缺少必需的包（lz4/zstandard）
    """
    method = normalize_compression_method(method)
    if method == "None":
        return data[:uncompressed_size]
    elif method == "Zlib":
        try:
            return zlib.decompress(data, wbits=-15)  # raw deflate, no header
        except zlib.error:
            return zlib.decompress(data)
    elif method == "Gzip":
        return gzip.decompress(data)
    elif method == "LZ4":
        try:
            import lz4.block
        except ImportError:
            raise ImportError(
                "LZ4 decompression requires 'lz4' package"
            )
        return lz4.block.decompress(data, uncompressed_size=uncompressed_size)
    elif method == "Zstd":
        try:
            import zstandard
        except ImportError:
            raise ImportError(
                "Zstd decompression requires 'zstandard' package"
            )
        return zstandard.ZstdDecompressor().decompress(data, max_output_size=uncompressed_size)
    elif method == "Oodle":
        raise NotImplementedError(
            "Oodle decompression requires oo2core library — "
            "not available as open-source Python package. "
            "See https://github.com/Kaldaien/Oodle for proprietary options."
        )
    else:
        raise ValueError(f"Unknown compression method: {method}")


def decompress_entry(
    stream: BinaryIO,
    entry: FPakEntry,
    compression_method: str = "None",
    encryption_key: bytes | None = None,
) -> bytes:
    """解压整个文件条目（可能包含多个压缩块）。

    Args:
        stream: 文件流
        entry: FPakEntry 实例
        compression_method: 压缩方法名称（从 FPakInfo.compression_methods 获取）
        encryption_key: AES 密钥（如果条目被加密）

    Returns:
        解压后的完整数据
    """
    if entry.is_encrypted and encryption_key is None:
        raise ParseError("Encrypted pak entry requires AES key")

    if not entry.is_compressed:
        read_offset = entry.offset
        stream.seek(read_offset)
        raw_size = entry.uncompressed_size
        if entry.is_encrypted:
            raw_size = (raw_size + 15) & ~15
        raw = stream.read(raw_size)
        if len(raw) < raw_size:
            raise ParseError(
                f"Pak 非压缩短读: 读取 {len(raw)} < 预期 {raw_size} bytes "
                f"(uncompressed_size={entry.uncompressed_size})"
            )
        if entry.is_encrypted:
            raw = _decrypt_entry_data(raw, encryption_key)[:entry.uncompressed_size]
        return raw[:entry.uncompressed_size]

    # Compressed: process block by block
    alignment = 16 if entry.is_encrypted else 1
    result = bytearray()

    for i, block in enumerate(entry.compression_blocks):
        if block.compressed_end < block.compressed_start:
            raise ParseError(
                f"压缩块 {i}: compressed_end ({block.compressed_end}) < "
                f"compressed_start ({block.compressed_start})"
            )
        stream.seek(block.compressed_start)
        block_size = block.compressed_end - block.compressed_start

        # Apply 16-byte alignment for encrypted entries
        aligned_size = (block_size + alignment - 1) & ~(alignment - 1)
        raw = stream.read(aligned_size)

        if len(raw) < block_size:
            raise ParseError(
                f"压缩块 {i}: 读取不足 ({len(raw)} < {block_size} bytes)"
            )

        if entry.is_encrypted:
            raw = _decrypt_entry_data(raw, encryption_key)[:block_size]

        decompressed = decompress_block(raw[:block_size], entry.compression_block_size, compression_method)
        result.extend(decompressed)

    if len(result) < entry.uncompressed_size:
        raise ParseError(
            f"解压结果过短: {len(result)} < {entry.uncompressed_size} bytes"
        )

    return bytes(result[:entry.uncompressed_size])


def _decrypt_entry_data(data: bytes, encryption_key: bytes | None) -> bytes:
    if encryption_key is None:
        raise ParseError("Encrypted pak entry requires AES key")
    try:
        from uasset_read.pak.crypto import decrypt_aes_ecb
        return decrypt_aes_ecb(data, encryption_key)
    except ImportError as exc:
        raise ParseError(
            "AES decryption requires 'cryptography' package"
        ) from exc
