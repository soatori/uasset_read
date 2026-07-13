from __future__ import annotations

"""
Pak 文件解压缩模块

支持 Zlib/LZ4/Zstd/Oodle 压缩方法分派。
- Zlib: Python stdlib，始终可用
- LZ4/Zstd: 可选 PyPI 包，延迟导入
- Oodle: 不支持（专有库），优雅降级
"""
import gzip
import io
import logging
import warnings
import zlib
from typing import TYPE_CHECKING, BinaryIO, Iterator

logger = logging.getLogger(__name__)

from uasset_read.exceptions import ParseError
from uasset_read.pak.structures import FPakEntry

if TYPE_CHECKING:
    from uasset_read.memory_safety import ResourceBudget


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
        method: 压缩方法名称（"Zlib", "Gzip", "LZ4", "Zstd", "Oodle"）

    Returns:
        解压后的数据

    Raises:
        ValueError: method 为 None 或未知的压缩方法
        NotImplementedError: Oodle 不支持
        ImportError: 缺少必需的包（lz4/zstandard）
    """
    if method is None:
        raise ValueError(
            "compression_method is required, cannot default to Zlib"
        )
    method = normalize_compression_method(method)

    # 压缩比检查：防止解压炸弹
    MAX_COMPRESSION_RATIO = 10.0
    if uncompressed_size > 0 and len(data) > 0:
        ratio = uncompressed_size / len(data)
        if ratio > MAX_COMPRESSION_RATIO:
            raise ParseError(
                f"解压压缩比过高: {ratio:.1f}:1（上限 {MAX_COMPRESSION_RATIO}:1），"
                f"压缩 {len(data)} 字节 → 声明 {uncompressed_size} 字节"
            )

    if method == "None":
        return data[:uncompressed_size]
    elif method == "Zlib":
        try:
            raw = zlib.decompress(data, wbits=-15)  # raw deflate, no header
        except zlib.error:
            raw = zlib.decompress(data)
        if len(raw) > uncompressed_size:
            logger.warning(
                "Zlib 解压输出 %d 字节超过声明大小 %d 字节，已截断（解压炸弹防护）",
                len(raw), uncompressed_size,
            )
            warnings.warn(
                f"Zlib 解压输出 {len(raw)} 字节超过声明大小 {uncompressed_size} 字节，已截断",
                ResourceWarning,
                stacklevel=2,
            )
            return raw[:uncompressed_size]
        return raw
    elif method == "Gzip":
        raw = gzip.decompress(data)
        if len(raw) > uncompressed_size:
            logger.warning(
                "Gzip 解压输出 %d 字节超过声明大小 %d 字节，已截断（解压炸弹防护）",
                len(raw), uncompressed_size,
            )
            warnings.warn(
                f"Gzip 解压输出 {len(raw)} 字节超过声明大小 {uncompressed_size} 字节，已截断",
                ResourceWarning,
                stacklevel=2,
            )
            return raw[:uncompressed_size]
        return raw
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


def decompress_block_chunked(
    data: bytes,
    uncompressed_size: int,
    method: str | int | None,
    budget: "ResourceBudget | None" = None,
    chunk_size: int = 64 * 1024,
) -> Iterator[bytes]:
    """分块解压，支持预算检查。

    与 ``decompress_block`` 类似，但以迭代器方式逐块产出解压数据，
    并可在解压前通过 ``ResourceBudget`` 检查解压大小是否超限，
    防止压缩炸弹。

    Args:
        data: 压缩数据
        uncompressed_size: 期望的解压后大小
        method: 压缩方法（"Zlib", "Gzip", "LZ4", "Zstd", "Oodle"）
        budget: 资源预算（可选），传入时会在解压前检查额度
        chunk_size: 每次产出的数据块大小（默认 64KB）

    Yields:
        解压后的数据块

    Raises:
        MemoryError: 预算超限（通过 ``MemoryLimitExceeded``）
        ParseError: 解压失败
        ValueError: 未知压缩方法
        NotImplementedError: Oodle 不支持
    """
    method = normalize_compression_method(method)

    if method == "None":
        yield data[:uncompressed_size]
        return

    if budget is not None:
        budget.reserve(uncompressed_size, "decompress")

    try:
        if method == "Zlib":
            yield from _decompress_zlib_chunked(data, uncompressed_size, chunk_size)
        elif method == "Gzip":
            yield from _decompress_gzip_chunked(data, uncompressed_size, chunk_size)
        elif method == "LZ4":
            result = _decompress_lz4(data, uncompressed_size)
            for i in range(0, len(result), chunk_size):
                yield result[i : i + chunk_size]
        elif method == "Zstd":
            result = _decompress_zstd(data, uncompressed_size)
            for i in range(0, len(result), chunk_size):
                yield result[i : i + chunk_size]
        elif method == "Oodle":
            raise NotImplementedError(
                "Oodle decompression requires oo2core library — "
                "not available as open-source Python package. "
                "See https://github.com/Kaldaien/Oodle for proprietary options."
            )
        else:
            raise ValueError(f"Unknown compression method: {method}")
    except (MemoryError, ParseError, ValueError, NotImplementedError):
        raise
    except Exception as exc:
        raise ParseError(f"Chunked decompression failed ({method}): {exc}") from exc


def _decompress_zlib_chunked(
    data: bytes, expected_size: int, chunk_size: int
) -> Iterator[bytes]:
    """Zlib (raw deflate) 分块解压。

    使用 ``decompressobj`` 以 ``max_length`` 控制每次产出大小，
    全部输入在第一次 ``decompress()`` 调用中传入，后续调用传入
    空字节以取出内部缓冲的剩余输出。
    """
    decompressor = zlib.decompressobj(wbits=-15)

    try:
        output = decompressor.decompress(data, expected_size)
        pos = 0
        while pos < len(output):
            yield output[pos : pos + chunk_size]
            pos += chunk_size
        # 取出内部缓冲的剩余输出
        while True:
            tail = decompressor.decompress(b"", chunk_size)
            if not tail:
                break
            yield tail
    except zlib.error:
        # raw deflate 失败 → 尝试带 zlib header 的格式
        try:
            decompressor = zlib.decompressobj()
            output = decompressor.decompress(data, expected_size)
            pos = 0
            while pos < len(output):
                yield output[pos : pos + chunk_size]
                pos += chunk_size
            while True:
                tail = decompressor.decompress(b"", chunk_size)
                if not tail:
                    break
                yield tail
        except zlib.error as exc2:
            raise ParseError(f"Zlib decompression failed: {exc2}") from exc2


def _decompress_gzip_chunked(
    data: bytes, expected_size: int, chunk_size: int
) -> Iterator[bytes]:
    """Gzip 分块解压。"""
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
        total_yielded = 0
        while total_yielded < expected_size:
            chunk = f.read(min(chunk_size, expected_size - total_yielded))
            if not chunk:
                break
            yield chunk
            total_yielded += len(chunk)


def _decompress_lz4(data: bytes, uncompressed_size: int) -> bytes:
    """LZ4 解压（需要完整解压）。"""
    try:
        import lz4.block
    except ImportError:
        raise ImportError("LZ4 decompression requires 'lz4' package")
    return lz4.block.decompress(data, uncompressed_size=uncompressed_size)


def _decompress_zstd(data: bytes, uncompressed_size: int) -> bytes:
    """Zstd 解压（需要完整解压）。"""
    try:
        import zstandard
    except ImportError:
        raise ImportError("Zstd decompression requires 'zstandard' package")
    return zstandard.ZstdDecompressor().decompress(
        data, max_output_size=uncompressed_size
    )


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
    if not entry.compression_blocks:
        raise ParseError(
            f"压缩条目缺少 compression_blocks 数据 "
            f"(compression_block_count={entry.compression_block_count})"
        )

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
