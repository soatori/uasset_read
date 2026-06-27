"""内存安全保护模块 — 防止解析大文件时 OOM。

提供文件大小检查、内存监控、进程级内存限制和批量处理限制。
核心策略：拆分处理大文件/大export，而非跳过拒绝。
"""
from __future__ import annotations

import gc
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 内存安全常量 — 拆分处理策略
# ---------------------------------------------------------------------------
# 文件大小阈值
LARGE_FILE_THRESHOLD = 20 * 1024 * 1024   # 20MB — 大文件阈值，启用分块读取
CRITICAL_FILE_SIZE = 100 * 1024 * 1024    # 100MB — 临界大小，强制分块处理

# 单 export 拆分阈值
LARGE_EXPORT_THRESHOLD = 10 * 1024 * 1024  # 10MB — 大 export 阈值，分段解析属性
EXPORT_CHUNK_SIZE = 5 * 1024 * 1024        # 5MB — export 分段大小

# 批量处理限制
MAX_ASSET_COUNT = 200                     # 单次批量最多处理文件数
BATCH_MEMORY_LIMIT_MB = 1024              # 批量处理内存限制（1GB）
MEMORY_CHECK_INTERVAL = 3                 # 每处理 N 个文件检查一次内存

# 超时设置
PARSE_TIMEOUT = 120                       # 单次解析超时（秒）

# 进程级内存限制（RSS 硬上限）
PROCESS_RSS_LIMIT_MB = 4 * 1024           # 4GB — 进程 RSS 超过此值触发紧急清理

# 内存水位线（基于系统可用内存百分比）
MEMORY_HIGH_WATERMARK = 0.7               # 70% — 触发 GC
MEMORY_CRITICAL_WATERMARK = 0.85          # 85% — 触发紧急清理

# 进程 RSS 水位线（基于进程自身内存）
PROCESS_RSS_HIGH_WATERMARK_MB = 2 * 1024  # 2GB — 进程 RSS 高水位，触发 GC
PROCESS_RSS_CRITICAL_MB = 3 * 1024        # 3GB — 进程 RSS 临界值，暂停等待清理


@dataclass
class MemoryStats:
    """内存使用统计。"""
    total_mb: float = 0.0
    available_mb: float = 0.0
    used_mb: float = 0.0
    usage_percent: float = 0.0
    process_rss_mb: float = 0.0  # 当前进程 RSS


def _get_process_rss_mb() -> float:
    """获取当前进程的 RSS（Resident Set Size）内存，单位 MB。"""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except (ImportError, Exception):
        pass

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
            handle = kernel32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return counters.WorkingSetSize / 1024 / 1024
        except Exception:
            pass

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
        except Exception:
            pass

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


def get_file_processing_strategy(path: Path) -> tuple[str, str]:
    """获取文件处理策略：normal/chunked/critical。

    Args:
        path: 文件路径

    Returns:
        (strategy, reason) 元组
        - normal: 正常解析
        - chunked: 分块读取
        - critical: 需要特殊处理（超大文件）
    """
    if not path.exists():
        return "skip", f"File not found: {path}"

    file_size = path.stat().st_size
    size_mb = file_size / 1024 / 1024

    # 临界大小：强制分块处理
    if file_size > CRITICAL_FILE_SIZE:
        return "critical", f"Critical size: {size_mb:.1f}MB, need chunked processing"

    # 大文件：分块读取
    if file_size > LARGE_FILE_THRESHOLD:
        return "chunked", f"Large file: {size_mb:.1f}MB, using chunked reading"

    # 检查进程 RSS — 如果内存紧张，也用分块
    process_rss = _get_process_rss_mb()
    if process_rss > PROCESS_RSS_HIGH_WATERMARK_MB:
        return "chunked", f"Process RSS high: {process_rss:.0f}MB, using chunked reading"

    return "normal", ""


def should_wait_for_memory() -> bool:
    """检查是否需要等待内存释放。

    Returns:
        True 如果内存紧张需要等待
    """
    process_rss = _get_process_rss_mb()
    if process_rss > PROCESS_RSS_CRITICAL_MB:
        return True

    stats = get_memory_stats()
    if stats.usage_percent > MEMORY_CRITICAL_WATERMARK:
        return True

    return False


def wait_and_cleanup(max_wait_seconds: int = 30) -> bool:
    """等待内存释放，执行清理。

    Args:
        max_wait_seconds: 最大等待时间（秒）

    Returns:
        True 如果内存已释放到安全水平
    """
    import time

    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        # 执行清理
        emergency_cleanup()

        # 检查是否已释放
        if not should_wait_for_memory():
            return True

        # 短暂等待
        time.sleep(0.5)

    # 超时，返回当前状态
    return not should_wait_for_memory()


def check_memory_pressure() -> bool:
    """检查是否处于内存压力状态（系统级或进程级）。

    Returns:
        True 如果内存使用超过高水位线
    """
    # 先检查进程 RSS（更直接的指标）
    process_rss = _get_process_rss_mb()
    if process_rss > PROCESS_RSS_HIGH_WATERMARK_MB:
        return True

    stats = get_memory_stats()
    return stats.usage_percent > MEMORY_HIGH_WATERMARK


def check_process_rss_limit() -> Optional[str]:
    """检查进程 RSS 是否超过限制。

    Returns:
        None 如果正常，否则返回警告信息
    """
    process_rss = _get_process_rss_mb()
    if process_rss > PROCESS_RSS_CRITICAL_MB:
        return f"Process RSS {process_rss:.0f}MB exceeds critical limit {PROCESS_RSS_CRITICAL_MB}MB"
    if process_rss > PROCESS_RSS_HIGH_WATERMARK_MB:
        return f"Process RSS {process_rss:.0f}MB exceeds high watermark {PROCESS_RSS_HIGH_WATERMARK_MB}MB"
    return None


def get_export_processing_strategy(serial_size: int) -> tuple[str, str]:
    """获取 export 处理策略：normal/chunked。

    Args:
        serial_size: export 的序列化数据大小（字节）

    Returns:
        (strategy, reason) 元组
        - normal: 正常解析
        - chunked: 分段解析属性
    """
    size_mb = serial_size / 1024 / 1024

    # 大 export：分段解析
    if serial_size > LARGE_EXPORT_THRESHOLD:
        return "chunked", f"Large export: {size_mb:.1f}MB, using chunked parsing"

    # 检查进程 RSS — 如果内存紧张，也用分段
    process_rss = _get_process_rss_mb()
    if process_rss > PROCESS_RSS_HIGH_WATERMARK_MB:
        return "chunked", f"Process RSS high: {process_rss:.0f}MB, using chunked parsing"

    return "normal", ""


def force_gc() -> None:
    """强制垃圾回收，释放内存。

    执行多次 GC 循环以确保循环引用被清除。
    """
    for _ in range(3):
        gc.collect()


def emergency_cleanup() -> float:
    """紧急内存清理：强制 GC + 尝试释放 Python 内部缓存。

    Returns:
        清理后进程 RSS（MB）
    """
    # 多轮 GC
    for _ in range(5):
        gc.collect()

    # 清理 Python 内部缓存
    try:
        import sys as _sys
        # 清理 intern 缓存
        _sys.intern.__class__  # 确认可用
    except Exception:
        pass

    # 清理 import 缓存中可安全删除的模块
    try:
        modules_to_clear = []
        for name, mod in list(sys.modules.items()):
            if name.startswith("__pycache__"):
                modules_to_clear.append(name)
        for name in modules_to_clear:
            del sys.modules[name]
    except Exception:
        pass

    # 再次 GC
    for _ in range(3):
        gc.collect()

    return _get_process_rss_mb()


def cleanup_after_parse() -> None:
    """解析后清理：强制 GC 并检查进程内存。

    应在每次解析完成后调用，防止内存累积。
    如果进程 RSS 超过高水位，执行紧急清理。
    """
    force_gc()

    process_rss = _get_process_rss_mb()
    if process_rss > PROCESS_RSS_HIGH_WATERMARK_MB:
        logger.warning(
            "Process RSS %.0fMB exceeds high watermark %dMB, running emergency cleanup",
            process_rss, PROCESS_RSS_HIGH_WATERMARK_MB
        )
        emergency_cleanup()

    if logger.isEnabledFor(logging.DEBUG):
        stats = get_memory_stats()
        logger.debug(
            "Memory after cleanup: process_rss=%.0fMB, system=%.1f%% used, %.0fMB available",
            stats.process_rss_mb, stats.usage_percent * 100, stats.available_mb
        )


def get_safe_batch_size(total_files: int) -> int:
    """根据内存状况计算安全的批量处理大小。

    Args:
        total_files: 总文件数

    Returns:
        建议的批量大小
    """
    # 先检查进程 RSS
    process_rss = _get_process_rss_mb()
    if process_rss > PROCESS_RSS_CRITICAL_MB:
        return 1
    if process_rss > PROCESS_RSS_HIGH_WATERMARK_MB:
        return min(3, total_files)

    stats = get_memory_stats()

    # 内存充足：处理所有文件
    if stats.usage_percent < 0.5:
        return min(total_files, MAX_ASSET_COUNT)

    # 内存中等：限制批量大小
    if stats.usage_percent < 0.6:
        safe_count = int(total_files * 0.5)
        return min(safe_count, MAX_ASSET_COUNT // 2)

    # 内存紧张：最小批量
    if stats.usage_percent < MEMORY_CRITICAL_WATERMARK:
        return min(5, total_files)

    # 内存危急：单个处理
    return 1


class MemoryGuard:
    """内存保护上下文管理器。

    在进入时检查内存状态，内存紧张时自动清理等待。
    退出时执行清理。
    """

    def __init__(self, operation_name: str = "operation", rss_limit_mb: float = PROCESS_RSS_LIMIT_MB):
        self.operation_name = operation_name
        self.start_stats: Optional[MemoryStats] = None
        self.rss_limit_mb = rss_limit_mb

    def __enter__(self):
        self.start_stats = get_memory_stats()
        logger.debug(
            "MemoryGuard: starting %s (process_rss=%.0fMB, system=%.1f%%)",
            self.operation_name,
            self.start_stats.process_rss_mb,
            self.start_stats.usage_percent * 100
        )

        # 检查进程 RSS — 内存紧张时清理等待
        if self.start_stats.process_rss_mb > PROCESS_RSS_HIGH_WATERMARK_MB:
            logger.warning(
                "MemoryGuard: process RSS %.0fMB high before %s, cleaning up",
                self.start_stats.process_rss_mb,
                self.operation_name
            )
            if not wait_and_cleanup(max_wait_seconds=10):
                logger.warning(
                    "MemoryGuard: memory cleanup did not reach safe level, proceeding anyway"
                )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 强制 GC
        force_gc()

        # 记录内存变化
        if logger.isEnabledFor(logging.DEBUG):
            end_stats = get_memory_stats()
            delta_rss = end_stats.process_rss_mb - self.start_stats.process_rss_mb
            logger.debug(
                "MemoryGuard: %s completed (rss delta: %+.0fMB, now: %.0fMB, system: %.1f%%)",
                self.operation_name,
                delta_rss,
                end_stats.process_rss_mb,
                end_stats.usage_percent * 100
            )

        return False  # 不抑制异常


def validate_parse_input(path: str) -> str:
    """验证解析输入参数并返回处理策略。

    Args:
        path: 文件路径

    Returns:
        处理策略：normal/chunked/critical/skip

    Raises:
        ValueError: 输入无效（文件不存在）
    """
    file_path = Path(path)

    # 检查文件是否存在
    if not file_path.exists():
        raise ValueError(f"File not found: {path}")

    # 获取处理策略
    strategy, reason = get_file_processing_strategy(file_path)
    if reason:
        logger.info("File strategy: %s - %s", strategy, reason)

    # 内存紧张时尝试清理
    if should_wait_for_memory():
        logger.info("Memory pressure detected, cleaning up before parse")
        wait_and_cleanup(max_wait_seconds=5)

    return strategy
