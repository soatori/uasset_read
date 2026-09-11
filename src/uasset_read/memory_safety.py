"""Central resource budget for parser read/decompress checkpoints."""

from __future__ import annotations

from pathlib import Path


class ResourceBudget:
    """Resource budget tracker — checks quota before actual reads or expansion."""

    def __init__(
        self,
        max_single_read_bytes: int = 16 * 1024 * 1024,
        max_total_decompressed_bytes: int = 256 * 1024 * 1024,
    ):
        self.max_single_read_bytes = max_single_read_bytes
        self.max_total_decompressed_bytes = max_total_decompressed_bytes
        self._total_decompressed = 0

    def reserve(self, bytes_needed: int, stage: str, asset: str = "") -> None:
        """Reserve resources, raises MemoryLimitExceeded if quota exceeded."""
        if bytes_needed > self.max_single_read_bytes:
            raise MemoryLimitExceeded(
                asset_path=asset,
                stage=stage,
                current_rss_mb=bytes_needed / 1024 / 1024,
                limit_mb=self.max_single_read_bytes / 1024 / 1024,
            )
        self._total_decompressed += bytes_needed
        if self._total_decompressed > self.max_total_decompressed_bytes:
            raise MemoryLimitExceeded(
                asset_path=asset,
                stage=stage,
                current_rss_mb=self._total_decompressed / 1024 / 1024,
                limit_mb=self.max_total_decompressed_bytes / 1024 / 1024,
            )


class MemoryLimitExceeded(MemoryError):
    """Raised when a parser checkpoint exceeds its configured limit."""

    def __init__(
        self,
        *,
        asset_path: str | Path,
        stage: str,
        current_rss_mb: float,
        limit_mb: float,
    ) -> None:
        self.asset_path = str(asset_path)
        self.stage = stage
        self.current_rss_mb = current_rss_mb
        self.limit_mb = limit_mb
        super().__init__(
            f"Memory limit exceeded for {self.asset_path} at {stage}: {current_rss_mb:.1f}MB > {limit_mb:.1f}MB"
        )
