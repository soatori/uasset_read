"""Central resource budget for parser read/decompress checkpoints."""

from __future__ import annotations


class ResourceBudget:
    """Resource budget tracker — checks quota before actual reads or expansion."""

    MAX_SINGLE_READ_BYTES = 16 * 1024 * 1024
    MAX_TOTAL_DECOMPRESSED_BYTES = 256 * 1024 * 1024

    def __init__(self) -> None:
        self._total_decompressed = 0

    def reserve(self, bytes_needed: int, stage: str, asset: str = "") -> None:
        """Reserve resources; raise MemoryLimitExceeded if quota exceeded."""
        if bytes_needed > self.MAX_SINGLE_READ_BYTES:
            raise MemoryLimitExceeded(
                f"Memory limit exceeded for {asset} at {stage}: "
                f"{bytes_needed / 1024 / 1024:.1f}MB > {self.MAX_SINGLE_READ_BYTES / 1024 / 1024:.1f}MB"
            )
        self._total_decompressed += bytes_needed
        if self._total_decompressed > self.MAX_TOTAL_DECOMPRESSED_BYTES:
            raise MemoryLimitExceeded(
                f"Memory limit exceeded for {asset} at {stage}: "
                f"{self._total_decompressed / 1024 / 1024:.1f}MB > "
                f"{self.MAX_TOTAL_DECOMPRESSED_BYTES / 1024 / 1024:.1f}MB"
            )


class MemoryLimitExceeded(MemoryError):
    """Raised when a parser checkpoint exceeds its configured limit."""
