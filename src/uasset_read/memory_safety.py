from __future__ import annotations

"""Central memory policy, process RSS measurement, and parser checkpoints."""

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


MEDIUM_FILE_ISOLATION_THRESHOLD = 50 * 1024 * 1024  # 50 MB
SMALL_FILE_THRESHOLD = 20 * 1024 * 1024  # 20 MB
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100 MB


def should_isolate(file_size: int) -> bool:
    """Determine whether a file needs subprocess isolation.

    - SMALL (<20MB): never isolate
    - MEDIUM (20-100MB): isolate if > 50MB
    - LARGE (>100MB): always isolate
    """
    if file_size < SMALL_FILE_THRESHOLD:
        return False
    if file_size <= LARGE_FILE_THRESHOLD:
        return file_size > MEDIUM_FILE_ISOLATION_THRESHOLD
    return True


class ResourceBudget:
    """Resource budget tracker — checks quota before actual reads or expansion."""

    def __init__(
        self,
        max_single_read_bytes: int = 16 * 1024 * 1024,
        max_decompressed_block_bytes: int = 64 * 1024 * 1024,
        max_total_decompressed_bytes: int = 256 * 1024 * 1024,
    ):
        self.max_single_read_bytes = max_single_read_bytes
        self.max_decompressed_block_bytes = max_decompressed_block_bytes
        self.max_total_decompressed_bytes = max_total_decompressed_bytes
        self._total_decompressed = 0
        self._checkpoints: list[int] = []

    def reserve(self, bytes_needed: int, stage: str, asset: str = "") -> None:
        """Reserve resources, raises MemoryLimitExceeded if quota exceeded."""
        if bytes_needed > self.max_single_read_bytes:
            raise MemoryLimitExceeded(
                asset_path=asset,
                stage=stage,
                current_rss_mb=0,
                limit_mb=self.max_single_read_bytes / 1024 / 1024,
            )
        if bytes_needed > self.max_decompressed_block_bytes:
            raise MemoryLimitExceeded(
                asset_path=asset,
                stage=stage,
                current_rss_mb=bytes_needed / 1024 / 1024,
                limit_mb=self.max_decompressed_block_bytes / 1024 / 1024,
            )
        self._total_decompressed += bytes_needed
        if self._total_decompressed > self.max_total_decompressed_bytes:
            raise MemoryLimitExceeded(
                asset_path=asset,
                stage=stage,
                current_rss_mb=self._total_decompressed / 1024 / 1024,
                limit_mb=self.max_total_decompressed_bytes / 1024 / 1024,
            )

    def checkpoint(self) -> None:
        """Save current state."""
        self._checkpoints.append(self._total_decompressed)

    def rollback(self) -> None:
        """Roll back to the previous checkpoint."""
        if self._checkpoints:
            self._total_decompressed = self._checkpoints.pop()


@dataclass
class MemoryStats:
    """Memory usage statistics."""

    total_mb: float = 0.0
    available_mb: float = 0.0
    used_mb: float = 0.0
    usage_percent: float = 0.0
    process_rss_mb: float = 0.0  # Current process RSS


@dataclass(frozen=True)
class ResourceLimits:
    """RSS and elapsed-time limits for one asset."""

    rss_limit_mb: float
    timeout_seconds: float


@dataclass(frozen=True)
class MemoryPolicy:
    """Central resource policy selected solely from package file size."""

    small_file_max_bytes: int = 20 * 1024 * 1024
    medium_file_max_bytes: int = 100 * 1024 * 1024
    small_limits: ResourceLimits = ResourceLimits(1024, 120.0)
    medium_limits: ResourceLimits = ResourceLimits(2048, 180.0)
    large_limits: ResourceLimits = ResourceLimits(4096, 300.0)
    system_usage_limit: float = 0.85
    poll_interval_seconds: float = 0.1

    def limits_for_size(self, size_bytes: int) -> ResourceLimits:
        if size_bytes <= self.small_file_max_bytes:
            return self.small_limits
        if size_bytes <= self.medium_file_max_bytes:
            return self.medium_limits
        return self.large_limits

    def limits_for_path(self, path: str | Path) -> ResourceLimits:
        return self.limits_for_size(Path(path).stat().st_size)


class MemoryLimitExceeded(MemoryError):
    """Raised when a parser checkpoint exceeds its configured RSS limit."""

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


class MemoryMonitor:
    """Lightweight in-process RSS checkpoints for parser stage boundaries."""

    def __init__(
        self,
        *,
        asset_path: str | Path,
        limits: ResourceLimits,
        rss_reader: Callable[[Optional[int]], float] | None = None,
    ) -> None:
        self.asset_path = str(asset_path)
        self.limits = limits
        self._rss_reader = rss_reader or _get_process_rss_mb

    def checkpoint(self, stage: str) -> float:
        current_rss_mb = self._rss_reader(None)
        if current_rss_mb > self.limits.rss_limit_mb:
            raise MemoryLimitExceeded(
                asset_path=self.asset_path,
                stage=stage,
                current_rss_mb=current_rss_mb,
                limit_mb=self.limits.rss_limit_mb,
            )
        return current_rss_mb

    def __enter__(self) -> "MemoryMonitor":
        self.checkpoint("start")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is None:
            self.checkpoint("complete")
        return False


def _get_process_rss_mb(pid: Optional[int] = None) -> float:
    """Return RSS in MB for *pid*, or the current process when omitted."""
    target_pid = os.getpid() if pid is None else pid
    try:
        import psutil

        process = psutil.Process(target_pid)
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        logger.debug("psutil not installed, cannot read RSS")
    except Exception as e:
        try:
            import psutil

            if isinstance(e, psutil.Error):
                logger.debug("psutil RSS retrieval failed (%s): %s", type(e).__name__, e)
                return 0.0
        except ImportError:
            pass
        raise

    # Windows fallback: use ctypes to call GetProcessMemoryInfo
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            close_handle = False
            if target_pid == os.getpid():
                handle = kernel32.GetCurrentProcess()
            else:
                PROCESS_QUERY_INFORMATION = 0x0400
                PROCESS_VM_READ = 0x0010
                handle = kernel32.OpenProcess(
                    PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
                    False,
                    target_pid,
                )
                close_handle = bool(handle)
            try:
                if handle and psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                    return counters.WorkingSetSize / 1024 / 1024
            finally:
                if close_handle:
                    kernel32.CloseHandle(handle)
        except (OSError, ValueError, OverflowError) as e:
            logger.debug("Windows GetProcessMemoryInfo failed to get RSS: %s", e, exc_info=True)

    logger.debug("Cannot retrieve process RSS, memory protection disabled")
    return 0.0


def get_memory_stats() -> MemoryStats:
    """Get current memory usage (system-level + process-level).

    Returns:
        MemoryStats containing total memory, available memory, used memory, usage percentage, and process RSS
    """
    process_rss = _get_process_rss_mb()

    try:
        import psutil

        mem = psutil.virtual_memory()
        return MemoryStats(
            total_mb=mem.total / 1024 / 1024,
            available_mb=mem.available / 1024 / 1024,
            used_mb=mem.used / 1024 / 1024,
            usage_percent=mem.percent / 100.0,
            process_rss_mb=process_rss,
        )
    except ImportError:
        logger.debug("psutil not available, using estimated memory stats")
        return _estimate_memory_stats(process_rss)


def _estimate_memory_stats(process_rss_mb: float = 0.0) -> MemoryStats:
    """Estimate memory usage (fallback when psutil is unavailable).

    Returns default estimates when system info is not available.
    """
    total_mb = 16 * 1024  # 16 GB default
    available_mb = 8 * 1024  # 8 GB default

    used_mb = total_mb - available_mb
    usage_percent = used_mb / total_mb if total_mb > 0 else 0.0

    return MemoryStats(
        total_mb=total_mb,
        available_mb=available_mb,
        used_mb=used_mb,
        usage_percent=usage_percent,
        process_rss_mb=process_rss_mb,
    )
