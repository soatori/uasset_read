"""Memory safety limits for parser read/decompress checkpoints."""

from __future__ import annotations

MAX_SINGLE_READ_BYTES = 16 * 1024 * 1024
MAX_TOTAL_DECOMPRESSED_BYTES = 256 * 1024 * 1024


def reserve_memory(
    bytes_needed: int,
    stage: str,
    asset: str = "",
    *,
    total_decompressed: int = 0,
) -> int:
    """Validate one reserve; return updated total_decompressed. Raise MemoryLimitExceeded."""
    if bytes_needed < 0:
        raise MemoryLimitExceeded(f"Memory limit exceeded for {asset} at {stage}: negative request {bytes_needed}")
    if bytes_needed > MAX_SINGLE_READ_BYTES:
        raise MemoryLimitExceeded(
            f"Memory limit exceeded for {asset} at {stage}: "
            f"{bytes_needed / 1024 / 1024:.1f}MB > {MAX_SINGLE_READ_BYTES / 1024 / 1024:.1f}MB"
        )
    total_decompressed += bytes_needed
    if total_decompressed > MAX_TOTAL_DECOMPRESSED_BYTES:
        raise MemoryLimitExceeded(
            f"Memory limit exceeded for {asset} at {stage}: "
            f"{total_decompressed / 1024 / 1024:.1f}MB > "
            f"{MAX_TOTAL_DECOMPRESSED_BYTES / 1024 / 1024:.1f}MB"
        )
    return total_decompressed


class MemoryLimitExceeded(MemoryError):
    """Raised when a parser checkpoint exceeds its configured limit."""
