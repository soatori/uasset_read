"""内存管理与安全防护工具。

提供 MemoryMonitor（内存水位监控）和轻量工具函数，供 parse_batch()
和测试代码使用，防止内存溢出。

psutil 是可选依赖：未安装时 MemoryMonitor 返回 OK + warning，
工具函数（get_file_size_mb / read_file_header / force_gc）不依赖 psutil。
"""
from __future__ import annotations

import gc
import logging
import platform
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

__all__ = [
    "MemoryMonitor",
    "MemoryStatus",
    "force_gc",
    "get_file_size_mb",
    "read_file_header",
    "get_available_memory_gb",
]

_logger = logging.getLogger(__name__)

# 常量：字节换算
_MB = 1024 ** 2  # 1 MB
_GB = 1024 ** 3  # 1 GB


# ---------------------------------------------------------------------------
# 枚举与数据类
# ---------------------------------------------------------------------------

class MemoryStatus(Enum):
    """内存状态。"""
    OK = "ok"               # 可用内存 > 30%
    LOW = "low"             # 可用内存 10%-30%
    CRITICAL = "critical"   # 可用内存 < 10%
    UNAVAILABLE = "unavailable"  # 无法检测（psutil 未安装）


@dataclass(frozen=True)
class MemoryCheckResult:
    """MemoryMonitor.check() 的返回值。"""
    state: MemoryStatus
    available_gb: float
    used_percent: float  # 已用百分比（0-100）
    warning: str | None = None

    @property
    def is_safe(self) -> bool:
        return self.state in (MemoryStatus.OK, MemoryStatus.UNAVAILABLE)


# ---------------------------------------------------------------------------
# MemoryMonitor
# ---------------------------------------------------------------------------

class MemoryMonitor:
    """系统内存水位监控器。

    基于 psutil（可选）。未安装时所有检查返回 OK + warning。

    Args:
        max_memory_percent: 已用内存百分比上限（默认 70%）。
            超过此值 → LOW；超过 max_memory_percent + 20 → CRITICAL。
        _force_unavailable: 测试用，强制标记 psutil 不可用。
    """

    def __init__(
        self,
        max_memory_percent: float = 70.0,
        *,
        _force_unavailable: bool = False,
    ) -> None:
        self.max_memory_percent = max_memory_percent
        self._critical_threshold = min(max_memory_percent + 20.0, 95.0)
        self._force_unavailable = _force_unavailable
        self._psutil = None if _force_unavailable else _try_import_psutil()
        if self._psutil is None and not _force_unavailable:
            _logger.info(
                "psutil not installed — memory monitoring disabled. "
                "Install with: pip install psutil"
            )

    @property
    def is_available(self) -> bool:
        """psutil 是否可用。"""
        return self._psutil is not None

    def check(self) -> MemoryCheckResult:
        """检查当前内存状态。"""
        if self._psutil is None:
            return MemoryCheckResult(
                state=MemoryStatus.UNAVAILABLE,
                available_gb=-1.0,
                used_percent=-1.0,
                warning="psutil not installed — memory monitoring disabled",
            )
        mem = self._get_virtual_memory()
        available_gb = mem.available / _GB
        used_pct = mem.percent  # psutil 直接给出已用百分比

        if used_pct >= self._critical_threshold:
            state = MemoryStatus.CRITICAL
        elif used_pct >= self.max_memory_percent:
            state = MemoryStatus.LOW
        else:
            state = MemoryStatus.OK

        warning = None
        if state != MemoryStatus.OK:
            warning = (
                f"Memory {state.value}: {used_pct:.0f}% used, "
                f"{available_gb:.1f} GB available "
                f"(threshold: {self.max_memory_percent:.0f}%)"
            )
            _logger.warning(warning)

        return MemoryCheckResult(
            state=state,
            available_gb=available_gb,
            used_percent=used_pct,
            warning=warning,
        )

    def is_safe(self) -> bool:
        """快捷判断：当前内存是否安全（OK 或 UNAVAILABLE）。"""
        return self.check().is_safe

    def _get_virtual_memory(self) -> Any:
        """获取虚拟内存信息（可被 mock 替换）。"""
        return self._psutil.virtual_memory()


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def get_file_size_mb(path: str | Path) -> float:
    """获取文件大小（MB）。文件不存在返回 0.0。"""
    try:
        return Path(path).stat().st_size / _MB
    except (OSError, ValueError):
        return 0.0


def read_file_header(path: str | Path, size: int = 8) -> bytes:
    """读取文件头部字节。文件不存在返回 b''。"""
    try:
        with open(path, "rb") as f:
            return f.read(size)
    except (OSError, ValueError):
        return b""


def force_gc() -> None:
    """强制垃圾回收，释放解析中间产物。"""
    gc.collect()


def get_available_memory_gb() -> float:
    """获取系统可用内存（GB）。psutil 不可用返回 -1.0。"""
    psutil = _try_import_psutil()
    if psutil is None:
        return -1.0
    return psutil.virtual_memory().available / _GB


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _try_import_psutil():
    """尝试导入 psutil，失败返回 None。"""
    try:
        import psutil  # type: ignore[import-not-found]
        return psutil
    except ImportError:
        return None
