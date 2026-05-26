"""
Pak 文件解压缩模块

支持 Zlib/LZ4/Zstd/Oodle 压缩方法分派。
- Zlib: Python stdlib，始终可用
- LZ4/Zstd: 可选 PyPI 包，延迟导入
- Oodle: 不支持（专有库），优雅降级

Phase 77 — PAK-02.
"""
import logging
from typing import BinaryIO

from uasset_read.exceptions import ParseError
from uasset_read.pak.structures import FPakEntry

logger = logging.getLogger(__name__)


def decompress_block(data: bytes, uncompressed_size: int, method: str) -> bytes:
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
    if method == "None" or method == "":
        return data[:uncompressed_size]
    elif method == "Zlib":
        import zlib
        return zlib.decompress(data, wbits=-15)  # raw deflate, no header
    elif method == "LZ4":
        try:
            import lz4.block
        except ImportError:
            raise ImportError(
                "LZ4 decompression requires 'lz4' package. "
                "Install with: pip install uasset_read[pak]"
            )
        return lz4.block.decompress(data, uncompressed_size=uncompressed_size)
    elif method == "Zstd":
        try:
            import zstandard
        except ImportError:
            raise ImportError(
                "Zstd decompression requires 'zstandard' package. "
                "Install with: pip install uasset_read[pak]"
            )
        return zstandard.decompress(data, max_output_size=uncompressed_size)
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
    if not entry.is_compressed:
        # Uncompressed: read directly
        read_offset = entry.offset
        stream.seek(read_offset)
        return stream.read(entry.uncompressed_size)

    # Compressed: process block by block
    alignment = 16 if entry.is_encrypted else 1
    result = bytearray()

    for i, block in enumerate(entry.compression_blocks):
        stream.seek(block.compressed_start)
        block_size = block.compressed_end - block.compressed_start

        # Apply 16-byte alignment for encrypted entries
        aligned_size = (block_size + alignment - 1) & ~(alignment - 1)
        raw = stream.read(aligned_size)

        if entry.is_encrypted and encryption_key:
            try:
                from uasset_read.pak.crypto import decrypt_aes_ecb
                raw = decrypt_aes_ecb(raw, encryption_key)[:block_size]
            except ImportError:
                logger.warning(
                    "Encrypted entry but 'cryptography' package not available. "
                    "Install with: pip install uasset_read[pak]"
                )
                continue

        try:
            decompressed = decompress_block(raw[:block_size], entry.compression_block_size, compression_method)
            result.extend(decompressed)
        except NotImplementedError as e:
            logger.warning("Skipping Oodle-compressed block: %s", e)
            continue

    return bytes(result)
