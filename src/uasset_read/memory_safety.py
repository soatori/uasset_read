from __future__ import annotations

"""Central memory policy, process RSS measurement, and parser checkpoints."""

import gc
import logging
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class FileSizeTier(Enum):
    """文件大小分级，用于决定是否需要子进程隔离。"""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"

    @classmethod
    def from_size(cls, file_size: int) -> "FileSizeTier":
        """根据文件大小返回对应分级。

        - SMALL: < 20MB
        - MEDIUM: 20MB - 100MB
        - LARGE: > 100MB
        """
        if file_size < 20 * 1024 * 1024:
            return cls.SMALL
        if file_size <= 100 * 1024 * 1024:
            return cls.MEDIUM
        return cls.LARGE


MEDIUM_FILE_ISOLATION_THRESHOLD = 50 * 1024 * 1024  # 50 MB


def should_isolate(file_size: int, tier: FileSizeTier) -> bool:
    """判断文件是否需要在隔离的子进程中处理。

    Args:
        file_size: 文件大小（字节）
        tier: 文件大小分级

    Returns:
        True 表示应在隔离子进程中处理
    """
    if tier == FileSizeTier.SMALL:
        return False
    elif tier == FileSizeTier.MEDIUM:
        return file_size > MEDIUM_FILE_ISOLATION_THRESHOLD
    elif tier == FileSizeTier.LARGE:
        return True
    return False


LARGE_FILE_THRESHOLD = 20 * 1024 * 1024
MAX_ASSET_COUNT = 200


@dataclass
class AllocationLimits:
    """分配限制配置 — 用于资源预算跟踪。"""
    max_single_read_bytes: int = 16 * 1024 * 1024  # 16 MB
    max_decompressed_block_bytes: int = 64 * 1024 * 1024  # 64 MB
    max_total_decompressed_bytes: int = 256 * 1024 * 1024  # 256 MB
    max_compression_ratio: float = 10.0
    stream_chunk_bytes: int = 1024 * 1024  # 1 MB
    max_output_buffer_bytes: int = 32 * 1024 * 1024  # 32 MB


class ResourceBudget:
    """资源预算跟踪器 — 在实际读取或扩容前检查配额。"""

    def __init__(self, limits: AllocationLimits | None = None):
        self.limits = limits or AllocationLimits()
        self._total_decompressed = 0
        self._checkpoints: list[int] = []
        self._work_units: int = 0
        self._max_work_units: int = 10_000_000  # 10M work units

    def reserve(self, bytes_needed: int, stage: str, asset: str = "") -> None:
        """预留资源，超限抛 MemoryLimitExceeded。"""
        if bytes_needed > self.limits.max_single_read_bytes:
            raise MemoryLimitExceeded(
                asset_path=asset,
                stage=stage,
                current_rss_mb=0,
                limit_mb=self.limits.max_single_read_bytes / 1024 / 1024,
            )
        if bytes_needed > self.limits.max_decompressed_block_bytes:
            raise MemoryLimitExceeded(
                asset_path=asset,
                stage=stage,
                current_rss_mb=bytes_needed / 1024 / 1024,
                limit_mb=self.limits.max_decompressed_block_bytes / 1024 / 1024,
            )
        self._total_decompressed += bytes_needed
        if self._total_decompressed > self.limits.max_total_decompressed_bytes:
            raise MemoryLimitExceeded(
                asset_path=asset,
                stage=stage,
                current_rss_mb=self._total_decompressed / 1024 / 1024,
                limit_mb=self.limits.max_total_decompressed_bytes / 1024 / 1024,
            )

    def checkpoint(self) -> None:
        """保存当前状态。"""
        self._checkpoints.append(self._total_decompressed)

    def rollback(self) -> None:
        """回滚到上一个检查点。"""
        if self._checkpoints:
            self._total_decompressed = self._checkpoints.pop()

    def consume_work(self, units: int, stage: str) -> None:
        """消耗工作量单位，超限抛 MemoryLimitExceeded。"""
        self._work_units += units
        if self._work_units > self._max_work_units:
            raise MemoryLimitExceeded(
                asset_path="",
                stage=stage,
                current_rss_mb=self._work_units / 1_000_000,
                limit_mb=self._max_work_units / 1_000_000,
            )

    @property
    def total_decompressed(self) -> int:
        """当前累计解压字节数。"""
        return self._total_decompressed


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

    import warnings
    warnings.warn(
        "无法获取进程 RSS，内存保护已禁用。建议安装 psutil: pip install psutil",
        stacklevel=2,
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


# ---------------------------------------------------------------------------
# 跨平台硬限制
# ---------------------------------------------------------------------------

def set_hard_rss_limit(limit_mb: int) -> Callable[[], None]:
    """设置当前进程的硬性 RSS 内存上限。

    在 Windows 上使用 WorkingSet 限制，在 Linux/macOS 上使用 ``resource.setrlimit``。
    返回一个清理函数，用于恢复原始限制。

    Args:
        limit_mb: RSS 上限（MB）

    Returns:
        清理函数，调用后恢复原始限制
    """
    limit_bytes = limit_mb * 1024 * 1024
    original_limit: Any = None

    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # GetCurrentProcess 返回 -1 (伪句柄)
            handle = kernel32.GetCurrentProcess()
            # c_size_t 在 64 位 Windows 上是 8 字节，但 32 位应用上是 4 字节
            # SetProcessWorkingSetSize 期望 SIZE_T 参数，用 c_size_t 即可
            try:
                result = kernel32.SetProcessWorkingSetSize(
                    handle, ctypes.c_size_t(limit_bytes), ctypes.c_size_t(limit_bytes)
                )
                if not result:
                    logger.debug("SetProcessWorkingSetSize 返回失败")
            except OverflowError as e:
                logger.debug("SetProcessWorkingSetSize 参数溢出: %s", e)
        except (OSError, OverflowError) as e:
            logger.debug("Windows 设置 RSS 硬限制失败: %s", e)
    else:
        try:
            import resource
            # 保存原始限制
            original_limit = resource.getrlimit(resource.RLIMIT_AS)
            # 设置虚拟内存上限（RSS 的上限）
            resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
        except (ImportError, ValueError, OSError) as e:
            logger.debug("Unix 设置 RSS 硬限制失败: %s", e)

    def _cleanup() -> None:
        if sys.platform != "win32" and original_limit is not None:
            try:
                import resource
                resource.setrlimit(resource.RLIMIT_AS, original_limit)
            except (ImportError, ValueError, OSError) as exc:
                logger.debug("恢复 RSS 硬限制失败: %s", exc)

    return _cleanup


def get_platform_limits() -> dict[str, Any]:
    """返回当前平台的资源限制信息。

    Returns:
        包含 platform、pid、rss_limit_source 等字段的字典
    """
    info: dict[str, Any] = {
        "platform": sys.platform,
        "pid": os.getpid(),
        "rss_limit_source": "none",
    }

    if sys.platform == "win32":
        info["rss_limit_source"] = "SetProcessWorkingSetSize"
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            _handle = kernel32.GetCurrentProcess()  # noqa: F841 - API call for context
            # Windows 没有直接 API 查询 WorkingSet 限制
            # 只能报告当前 RSS
            info["current_rss_mb"] = _get_process_rss_mb()
        except Exception as exc:
            logger.debug("获取 Windows 平台限制失败: %s", exc)
    else:
        try:
            import resource
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            info["rss_limit_source"] = "RLIMIT_AS"
            info["virtual_memory_soft_limit_bytes"] = soft
            info["virtual_memory_hard_limit_bytes"] = hard
            info["current_rss_mb"] = _get_process_rss_mb()
        except (ImportError, ValueError, OSError) as exc:
            logger.debug("获取 Unix 平台限制失败: %s", exc)

    return info
