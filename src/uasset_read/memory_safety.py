"""Central memory policy, process RSS measurement, and parser checkpoints."""
from __future__ import annotations

import gc
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

LARGE_FILE_THRESHOLD = 20 * 1024 * 1024
MAX_ASSET_COUNT = 200


@dataclass
class MemoryStats:
    """内存使用统计。"""
    total_mb: float = 0.0
    available_mb: float = 0.0
    used_mb: float = 0.0
    usage_percent: float = 0.0
    process_rss_mb: float = 0.0  # 当前进程 RSS


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
            f"Memory limit exceeded for {self.asset_path} at {stage}: "
            f"{current_rss_mb:.1f}MB > {limit_mb:.1f}MB"
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
    except (ImportError, OSError) as e:
        logger.debug("psutil RSS 获取失败: %s", e, exc_info=True)

    # Windows 降级方案：使用 ctypes 调用 GetProcessMemoryInfo
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
                if handle and psapi.GetProcessMemoryInfo(
                    handle, ctypes.byref(counters), counters.cb
                ):
                    return counters.WorkingSetSize / 1024 / 1024
            finally:
                if close_handle:
                    kernel32.CloseHandle(handle)
        except (OSError, ValueError, OverflowError) as e:
            logger.debug("Windows GetProcessMemoryInfo 获取 RSS 失败: %s", e, exc_info=True)

    if sys.platform.startswith("linux"):
        try:
            resident_pages = int(
                Path(f"/proc/{target_pid}/statm").read_text(encoding="ascii").split()[1]
            )
            return resident_pages * os.sysconf("SC_PAGE_SIZE") / 1024 / 1024
        except (OSError, ValueError, IndexError) as e:
            logger.debug("Linux /proc RSS 获取失败: %s", e)

    if pid is not None and not (
        sys.platform == "win32" or sys.platform.startswith("linux")
    ):
        raise RuntimeError(
            "Per-process RSS monitoring requires psutil on this platform"
        )

    return 0.0


def get_memory_stats() -> MemoryStats:
    """获取当前内存使用情况（系统级 + 进程级）。

    Returns:
        MemoryStats 包含总内存、可用内存、已用内存、使用百分比和进程 RSS
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
    """估算内存使用（无 psutil 时的降级方案）。

    使用 ctypes 获取系统内存信息（Windows），而非假设 16GB。
    """
    total_mb = 0.0
    available_mb = 0.0

    # Windows: 使用 ctypes 调用 GlobalMemoryStatusEx
    if sys.platform == "win32":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            kernel32 = ctypes.windll.kernel32
            if kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_mb = stat.ullTotalPhys / 1024 / 1024
                available_mb = stat.ullAvailPhys / 1024 / 1024
        except (OSError, ValueError, OverflowError) as e:
            logger.debug("Windows GlobalMemoryStatusEx 获取内存信息失败: %s", e, exc_info=True)

    if total_mb <= 0:
        total_mb = 16 * 1024  # 最终降级
        available_mb = 8 * 1024

    used_mb = total_mb - available_mb
    usage_percent = used_mb / total_mb if total_mb > 0 else 0.0

    return MemoryStats(
        total_mb=total_mb,
        available_mb=available_mb,
        used_mb=used_mb,
        usage_percent=usage_percent,
        process_rss_mb=process_rss_mb,
    )


def check_file_size(path: Path) -> int:
    """获取文件大小（字节）。

    Args:
        path: 文件路径

    Returns:
        文件大小（字节）

    Raises:
        ValueError: 如果文件不存在
    """
    if not path.exists():
        raise ValueError(f"File not found: {path}")
    return path.stat().st_size


def cleanup_after_parse() -> None:
    """Compatibility cleanup hook: perform exactly one cyclic-GC pass."""
    gc.collect()
