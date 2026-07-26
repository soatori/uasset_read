from __future__ import annotations

"""
Pak file decompression module.

Supports Zlib/LZ4/Zstd/Oodle compression method dispatch.
- Zlib: Python stdlib, always available
- LZ4/Zstd: optional PyPI packages, lazy import
- Oodle: not supported (proprietary library), graceful degradation
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
    """Decompress a single compressed block.

    Args:
        data: Compressed data
        uncompressed_size: Expected decompressed size
        method: Compression method name ("Zlib", "Gzip", "LZ4", "Zstd", "Oodle")

    Returns:
        Decompressed data

    Raises:
        ValueError: method is None or unknown compression method
        NotImplementedError: Oodle not supported
        ImportError: Missing required package (lz4/zstandard)
    """
    if method is None:
        raise ValueError(
            "compression_method is required, cannot default to Zlib"
        )
    method = normalize_compression_method(method)

    # Compression ratio check: prevent decompression bomb
    MAX_COMPRESSION_RATIO = 10.0
    if uncompressed_size > 0 and len(data) > 0:
        ratio = uncompressed_size / len(data)
        if ratio > MAX_COMPRESSION_RATIO:
            raise ParseError(
                f"Decompression ratio too high: {ratio:.1f}:1 (limit {MAX_COMPRESSION_RATIO}:1), "
                f"compressed {len(data)} bytes -> declared {uncompressed_size} bytes"
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
                "Zlib decompression output %d bytes exceeds declared size %d bytes, truncated (decompression bomb protection)",
                len(raw), uncompressed_size,
            )
            warnings.warn(
                f"Zlib decompression output {len(raw)} bytes exceeds declared size {uncompressed_size} bytes, truncated",
                ResourceWarning,
                stacklevel=2,
            )
            return raw[:uncompressed_size]
        return raw
    elif method == "Gzip":
        raw = gzip.decompress(data)
        if len(raw) > uncompressed_size:
            logger.warning(
                "Gzip decompression output %d bytes exceeds declared size %d bytes, truncated (decompression bomb protection)",
                len(raw), uncompressed_size,
            )
            warnings.warn(
                f"Gzip decompression output {len(raw)} bytes exceeds declared size {uncompressed_size} bytes, truncated",
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
    """Chunked decompression with budget checking.

    Similar to ``decompress_block``, but yields decompressed data in chunks
    as an iterator, and can check decompressed size against a ``ResourceBudget``
    limit before decompression to prevent compression bombs.

    Args:
        data: Compressed data
        uncompressed_size: Expected decompressed size
        method: Compression method ("Zlib", "Gzip", "LZ4", "Zstd", "Oodle")
        budget: Resource budget (optional), checked before decompression
        chunk_size: Size of each yielded chunk (default 64KB)

    Yields:
        Decompressed data chunks

    Raises:
        MemoryError: Budget exceeded (via ``MemoryLimitExceeded``)
        ParseError: Decompression failed
        ValueError: Unknown compression method
        NotImplementedError: Oodle not supported
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
    """Zlib (raw deflate) chunked decompression.

    Uses ``decompressobj`` with ``max_length`` to control chunk output size.
    All input is passed in the first ``decompress()`` call; subsequent calls
    pass empty bytes to drain remaining output from the internal buffer.
    """
    decompressor = zlib.decompressobj(wbits=-15)

    try:
        output = decompressor.decompress(data, expected_size)
        pos = 0
        while pos < len(output):
            yield output[pos : pos + chunk_size]
            pos += chunk_size
        # Drain remaining output from the internal buffer
        while True:
            tail = decompressor.decompress(b"", chunk_size)
            if not tail:
                break
            yield tail
    except zlib.error:
        # raw deflate failed -> try format with zlib header
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
    """Gzip chunked decompression."""
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
        total_yielded = 0
        while total_yielded < expected_size:
            chunk = f.read(min(chunk_size, expected_size - total_yielded))
            if not chunk:
                break
            yield chunk
            total_yielded += len(chunk)


def _decompress_lz4(data: bytes, uncompressed_size: int) -> bytes:
    """LZ4 decompression (requires full decompression)."""
    try:
        import lz4.block
    except ImportError:
        raise ImportError("LZ4 decompression requires 'lz4' package")
    return lz4.block.decompress(data, uncompressed_size=uncompressed_size)


def _decompress_zstd(data: bytes, uncompressed_size: int) -> bytes:
    """Zstd decompression (requires full decompression)."""
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
    """Decompress an entire file entry (may contain multiple compressed blocks).

    Args:
        stream: File stream
        entry: FPakEntry instance
        compression_method: Compression method name (from FPakInfo.compression_methods)
        encryption_key: AES key (if the entry is encrypted)

    Returns:
        Fully decompressed data
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
                f"Pak uncompressed short read: read {len(raw)} < expected {raw_size} bytes "
                f"(uncompressed_size={entry.uncompressed_size})"
            )
        if entry.is_encrypted:
            raw = _decrypt_entry_data(raw, encryption_key)[:entry.uncompressed_size]
        return raw[:entry.uncompressed_size]

    # Compressed: process block by block
    if not entry.compression_blocks:
        raise ParseError(
            f"Compressed entry missing compression_blocks data "
            f"(compression_block_count={entry.compression_block_count})"
        )

    alignment = 16 if entry.is_encrypted else 1
    result = bytearray()

    for i, block in enumerate(entry.compression_blocks):
        if block.compressed_end < block.compressed_start:
            raise ParseError(
                f"Compression block {i}: compressed_end ({block.compressed_end}) < "
                f"compressed_start ({block.compressed_start})"
            )
        stream.seek(block.compressed_start)
        block_size = block.compressed_end - block.compressed_start

        # Apply 16-byte alignment for encrypted entries
        aligned_size = (block_size + alignment - 1) & ~(alignment - 1)
        raw = stream.read(aligned_size)

        if len(raw) < block_size:
            raise ParseError(
                f"Compression block {i}: insufficient read ({len(raw)} < {block_size} bytes)"
            )

        if entry.is_encrypted:
            raw = _decrypt_entry_data(raw, encryption_key)[:block_size]

        decompressed = decompress_block(raw[:block_size], entry.compression_block_size, compression_method)
        result.extend(decompressed)

    if len(result) < entry.uncompressed_size:
        raise ParseError(
            f"Decompressed result too short: {len(result)} < {entry.uncompressed_size} bytes"
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
