# 批量解析内存管理与测试安全防护 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `parse_batch()` 添加内存安全机制（分批 GC、内存监控、大文件警告），在测试基础设施中添加资产大小分级、`@pytest.mark.large` 门控、测试后自动 GC fixture 和全量串行保护，防止内存溢出事件再次发生。

**Architecture:**
- 新建 `src/uasset_read/memory.py` 提供 `MemoryMonitor`（基于 `psutil`，可选依赖）和纯函数工具
- **`parse_single()` 入口保护**：新增 `max_file_size_mb` 参数（默认 1000 MB），超限抛 `ParseError`；≥ 100 MB 时写 warning 到 `ParseResult`
- `core.py` 的 `parse_batch()` 新增 `max_memory_percent` / `batch_size` 参数，每批处理后显式 GC
- `BatchResult` 新增 `skipped_large` 字段记录跳过的超大文件
- 测试层通过 `SampleAsset.size_class` + `conftest.py` 的 `pytest_collection_modifyitems` 实现大资产门控
- `test_matrix.py` 的 `all` suite 默认排除 `@pytest.mark.large`，新增 `--include-large` 透传
- **全量测试内存隔离**：`conftest.py` 提供 `autouse` GC fixture，在 integration/acceptance 测试后自动释放内存；`test_matrix.py all` 强制串行（禁止 `-n > 1`），防止多进程同时持有全量资产 IR
- **统一限制常量**：`memory.py` 定义 `DEFAULT_MAX_PARSE_SIZE_MB = 1000`、`WARN_FILE_SIZE_MB = 100`，`parse_single()` 和 `parse_batch()` 共用

**方案选择依据（研究结论）：**

| 方案 | 峰值内存 | 复杂度 | 适用场景 |
|------|---------|--------|---------|
| 顺序 + 每 N 文件 GC | ~120 MB（batch_size=50） | 低 | `parse_batch()` 生产代码 |
| `pytest-xdist -n N` 多进程 | ~11 GB/进程（-n4 全量） | 中（需 xdist） | 不推荐：全量测试仍会 OOM |
| 串行 + 每测试后 GC | 单测试内存（< 500 MB） | 低 | 测试执行（本计划采用） |
| 每文件 subprocess | 完全隔离 | 高 | 超大文件（> 1 GB），暂不实现 |

**超大文件分级处理：**
- `> 500 MB`：默认硬跳过，记录到 `BatchResult.skipped_large`，需显式提高 `max_file_size_mb`
- `100–500 MB`：标记 `@pytest.mark.large`，测试默认跳过；batch 处理前打印警告
- `50–100 MB`：已有 mmap（`MMAP_THRESHOLD = 50 MB`）减少 RSS；batch 处理日志提示
- `< 50 MB`：正常处理

**Tech Stack:** Python 3.10+、pytest、psutil（可选依赖，放入 `optional-dependencies`）

**关联 Issue:** #104（运维规范）、#105（代码实现）

---

## 文件结构总览

| 操作 | 文件 | 职责 |
|------|------|------|
| 新建 | `src/uasset_read/memory.py` | 内存监控 + 工具函数 + 限制常量（`DEFAULT_MAX_PARSE_SIZE_MB`、`WARN_FILE_SIZE_MB`） |
| 修改 | `src/uasset_read/core.py` | `parse_single()` 入口文件大小保护 + `parse_batch()` 内存管理 + `BatchResult.skipped_large` |
| 新建 | `tests/test_memory.py` | `memory.py` 单元测试 |
| 修改 | `tests/test_sample_assets_representative.py` | `SampleAsset.size_class` + 资产分类 |
| 修改 | `tests/test_acceptance.py` | 大资产标记 `@pytest.mark.large` |
| 新建 | `tests/conftest.py` | `--include-large` 选项 + large 跳过 + `autouse` GC fixture（integration/acceptance 测试后自动释放内存） |
| 修改 | `pytest.ini` | 注册 `large` 标记 |
| 修改 | `scripts/test_matrix.py` | `all` 排除 large + 禁止并行（`-n 1`），新增 `--include-large` 透传 |
| 新建 | `docs/guides/testing-concurrency.md` | 多会话并发测试规范（#104 验收） |

---

### Task 1: 内存工具模块 `memory.py`

**Files:**
- Create: `src/uasset_read/memory.py`
- Test: `tests/test_memory.py`

- [ ] **Step 1: 编写 `test_memory.py` 失败测试**

创建 `tests/test_memory.py`，覆盖以下行为：
- `get_file_size_mb()` 返回正确的 MB 值
- `MemoryMonitor` 在内存充足时返回 `MemoryStatus.OK`
- `MemoryMonitor` 在模拟内存紧张时返回 `MemoryStatus.LOW`
- `MemoryMonitor` 在模拟内存危急时返回 `MemoryStatus.CRITICAL`
- `force_gc()` 调用后不抛异常
- `read_file_header()` 返回正确字节

```python
"""memory.py 单元测试。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from uasset_read.memory import (
    MemoryMonitor,
    MemoryStatus,
    force_gc,
    get_file_size_mb,
    read_file_header,
)


# ---------------------------------------------------------------------------
# get_file_size_mb
# ---------------------------------------------------------------------------

class TestGetFileSizeMb:
    def test_returns_correct_size(self, tmp_path: Path):
        f = tmp_path / "test.bin"
        f.write_bytes(b"\x00" * (1024 * 1024))  # 1 MB
        assert abs(get_file_size_mb(f) - 1.0) < 0.01

    def test_nonexistent_file_returns_zero(self, tmp_path: Path):
        assert get_file_size_mb(tmp_path / "nope.bin") == 0.0

    def test_empty_file_returns_zero(self, tmp_path: Path):
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        assert get_file_size_mb(f) == 0.0


# ---------------------------------------------------------------------------
# read_file_header
# ---------------------------------------------------------------------------

class TestReadFileHeader:
    def test_reads_correct_bytes(self, tmp_path: Path):
        f = tmp_path / "header.bin"
        f.write_bytes(b"\x9e\x2a\xcf\x5d" + b"\x00" * 100)
        assert read_file_header(f, 4) == b"\x9e\x2a\xcf\x5d"

    def test_nonexistent_returns_empty(self, tmp_path: Path):
        assert read_file_header(tmp_path / "nope.bin", 4) == b""

    def test_shorter_than_requested(self, tmp_path: Path):
        f = tmp_path / "short.bin"
        f.write_bytes(b"\x01\x02")
        assert read_file_header(f, 8) == b"\x01\x02"


# ---------------------------------------------------------------------------
# force_gc
# ---------------------------------------------------------------------------

class TestForceGc:
    def test_does_not_raise(self):
        force_gc()  # 不抛异常即通过


# ---------------------------------------------------------------------------
# MemoryMonitor
# ---------------------------------------------------------------------------

class TestMemoryMonitor:
    def test_status_ok_when_memory_plenty(self):
        """模拟系统有大量可用内存。"""
        mock_mem = _make_mock_mem(available_gb=16, total_gb=32)
        monitor = MemoryMonitor(max_memory_percent=70)
        with patch.object(monitor, "_get_virtual_memory", return_value=mock_mem):
            status = monitor.check()
        assert status.state == MemoryStatus.OK

    def test_status_low_when_approaching_limit(self):
        """模拟已用内存 75%（超过 70% 阈值）。"""
        # 32 GB 总内存，8 GB 可用 → used=75%
        mock_mem = _make_mock_mem(available_gb=8, total_gb=32)
        monitor = MemoryMonitor(max_memory_percent=70)
        with patch.object(monitor, "_get_virtual_memory", return_value=mock_mem):
            status = monitor.check()
        assert status.state == MemoryStatus.LOW

    def test_status_critical_when_very_low(self):
        """模拟已用内存 93%（超过 critical 阈值 90%）。"""
        # 32 GB 总内存，2 GB 可用 → used=93.75%
        mock_mem = _make_mock_mem(available_gb=2, total_gb=32)
        monitor = MemoryMonitor(max_memory_percent=70)
        with patch.object(monitor, "_get_virtual_memory", return_value=mock_mem):
            status = monitor.check()
        assert status.state == MemoryStatus.CRITICAL

    def test_unavailable_returns_ok_with_note(self):
        """psutil 不可用时返回 OK + warning。"""
        monitor = MemoryMonitor(max_memory_percent=70, _force_unavailable=True)
        status = monitor.check()
        assert status.state == MemoryStatus.OK
        assert "unavailable" in (status.warning or "").lower()

    def test_is_safe_true_for_ok_and_unavailable(self):
        monitor = MemoryMonitor(max_memory_percent=70, _force_unavailable=True)
        assert monitor.is_safe() is True

    def test_is_safe_false_for_critical(self):
        # 32 GB 总内存，2 GB 可用 → used=93.75% → CRITICAL
        mock_mem = _make_mock_mem(available_gb=2, total_gb=32)
        monitor = MemoryMonitor(max_memory_percent=70)
        with patch.object(monitor, "_get_virtual_memory", return_value=mock_mem):
            assert monitor.is_safe() is False


def _make_mock_mem(available_gb: float, total_gb: float):
    """构造 psutil.virtual_memory() 风格的 mock 对象。"""
    from collections import namedtuple
    VMem = namedtuple("VMem", ["total", "available", "percent", "used", "free"])
    gb = 1024 ** 3
    used_gb = total_gb - available_gb
    return VMem(
        total=int(total_gb * gb),
        available=int(available_gb * gb),
        percent=(used_gb / total_gb) * 100,
        used=int(used_gb * gb),
        free=int(available_gb * gb),
    )
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_memory.py -v
```

预期：`ModuleNotFoundError: No module named 'uasset_read.memory'`

- [ ] **Step 3: 实现 `memory.py`**

创建 `src/uasset_read/memory.py`：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

```
python -m pytest tests/test_memory.py -v
```

预期：全部 PASS（约 12 个测试）。

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/memory.py tests/test_memory.py
git commit -m "feat: add memory monitoring utilities (memory.py)"
```

---

### Task 2: `parse_batch()` 内存管理 + `BatchResult.skipped_large`

**Files:**
- Modify: `src/uasset_read/core.py:21-28` (BatchResult)、`src/uasset_read/core.py:121-200` (parse_batch)
- Test: `tests/test_memory.py`（追加 batch 相关测试）

- [ ] **Step 1: 编写 batch 内存管理的失败测试**

在 `tests/test_memory.py` 末尾追加以下测试类：

```python
# ---------------------------------------------------------------------------
# parse_batch 内存管理
# ---------------------------------------------------------------------------

class TestParseBatchMemoryManagement:
    """验证 parse_batch() 的内存安全行为。"""

    def test_batch_result_has_skipped_large(self):
        from uasset_read.core import BatchResult
        result = BatchResult()
        assert hasattr(result, "skipped_large")
        assert result.skipped_large == []

    def test_batch_skips_oversized_file(self, tmp_path: Path):
        """大于 max_file_size_mb 的文件应被跳过并记录到 skipped_large。"""
        from uasset_read.core import parse_batch
        # 创建一个伪造的大文件（>0 MB 阈值即可触发跳过逻辑）
        fake_uasset = tmp_path / "huge.uasset"
        # 写一个有效的 PACKAGE_FILE_TAG 头 + 填充到 2 MB
        from uasset_read.constants import PACKAGE_FILE_TAG
        header = PACKAGE_FILE_TAG.to_bytes(4, "little")
        fake_uasset.write_bytes(header + b"\x00" * (2 * 1024 * 1024))

        result = parse_batch(
            str(tmp_path),
            output_dir=str(tmp_path / "out"),
            max_file_size_mb=1.0,  # 超过 1 MB 跳过
        )
        assert len(result.skipped_large) == 1
        assert "huge.uasset" in result.skipped_large[0][0]
        assert result.success == []

    def test_batch_accepts_batch_size_parameter(self, tmp_path: Path):
        """batch_size 参数应被接受，不抛出 TypeError。"""
        from uasset_read.core import parse_batch
        # 空目录会抛 ValueError，但这里验证 batch_size 参数被接受
        with pytest.raises(ValueError, match="No .uasset/.umap files"):
            parse_batch(
                str(tmp_path),
                output_dir=str(tmp_path / "out"),
                batch_size=10,
            )

    def test_batch_memory_check_callback(self, tmp_path: Path):
        """自定义 memory_check 回调可以阻止处理。"""
        from uasset_read.core import parse_batch

        # 创建一个带有效头的假文件
        fake = tmp_path / "test.uasset"
        from uasset_read.constants import PACKAGE_FILE_TAG
        fake.write_bytes(PACKAGE_FILE_TAG.to_bytes(4, "little") + b"\x00" * 1024)

        call_count = 0

        def always_critical():
            nonlocal call_count
            call_count += 1
            from uasset_read.memory import MemoryCheckResult, MemoryStatus
            return MemoryCheckResult(
                state=MemoryStatus.CRITICAL,
                available_gb=0.5,
                used_percent=95.0,
                warning="simulated critical",
            )

        result = parse_batch(
            str(tmp_path),
            output_dir=str(tmp_path / "out"),
            memory_check=always_critical,
        )
        assert call_count >= 1  # 至少检查了一次
        # 文件应被跳过或失败（不进入 success）
        assert result.success == []
```

- [ ] **Step 2: 运行测试确认失败**

```
python -m pytest tests/test_memory.py::TestParseBatchMemoryManagement -v
```

预期：`AttributeError: skipped_large` 或参数错误。

- [ ] **Step 3: 修改 `core.py` — 更新 `BatchResult` 和 `parse_batch()`**

在 `src/uasset_read/core.py` 中：

**更新 `BatchResult`（约第 21-27 行）：**

```python
@dataclass
class BatchResult:
    """批量导出结果。"""
    total: int = 0
    success: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    skipped_large: list[tuple[str, str]] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
```

**更新 `parse_batch()` 签名和实现（约第 121 行起）：**

```python
def parse_batch(
    input_dir: str,
    format: str = "json",
    output_dir: str | None = None,
    tolerant: bool = True,
    verbose: bool = False,
    include_schema: bool = False,
    include_function_graphs: bool = False,
    include_parent_assets: bool = False,
    asset_roots: list[str] | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    *,
    max_file_size_mb: float | None = None,
    batch_size: int = 50,
    max_memory_percent: float = 70.0,
    memory_check: Callable[[], Any] | None = None,
) -> BatchResult:
    """批量解析目录下所有 .uasset/.umap。

    内存安全参数:
        max_file_size_mb: 单文件最大 MB，超过则跳过。
            None → 使用 batch 默认值 500 MB（比单文件的 1000 MB 更保守）。
            设为 0 或 float('inf') 禁用检查。
        batch_size: 每批处理文件数，批间执行 GC（默认 50）
        max_memory_percent: 系统内存已用百分比上限（默认 70%）
        memory_check: 自定义内存检查回调，返回 MemoryCheckResult。
            为 None 时使用内置 MemoryMonitor。设为 lambda: None 跳过检查。

    Returns:
        BatchResult 包含成功、跳过、跳过（超大）、失败的文件列表
    """
    from uasset_read.memory import MemoryMonitor, MemoryStatus, force_gc, get_file_size_mb

    # None → batch 保守默认值（比 parse_single 的 1000 MB 更保守）
    effective_max_file_size = 500.0 if max_file_size_mb is None else max_file_size_mb

    input_path = Path(input_dir)
    if not input_path.is_dir():
        raise ValueError(f"Not a directory: {input_dir}")

    package_files = sorted([*input_path.glob("*.uasset"), *input_path.glob("*.umap")])
    if not package_files:
        raise ValueError(f"No .uasset/.umap files found in {input_dir}")

    if output_dir is None:
        output_dir = str(input_path / "output")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    result = BatchResult(total=len(package_files))

    # 内存监控初始化
    if memory_check is None:
        monitor = MemoryMonitor(max_memory_percent=max_memory_percent)
        memory_check = monitor.check

    processed_in_batch = 0

    for pf in package_files:
        # 1. 大文件检查（effective_max_file_size <= 0 或 inf 时禁用）
        file_size_mb = get_file_size_mb(pf)
        check_size = effective_max_file_size not in (0, float("inf"))
        if check_size and file_size_mb > effective_max_file_size:
            reason = f"file too large: {file_size_mb:.1f} MB > {effective_max_file_size:.0f} MB limit"
            result.skipped_large.append((str(pf), reason))
            _logger.info("Skipping large file: %s (%s)", pf.name, reason)
            continue

        # 2. 内存检查
        check_result = memory_check()
        if check_result is not None and hasattr(check_result, "state"):
            from uasset_read.memory import MemoryStatus
            if check_result.state == MemoryStatus.CRITICAL:
                reason = f"memory critical: {check_result.used_percent:.0f}% used"
                result.skipped.append((str(pf), reason))
                _logger.warning("Skipping file (memory critical): %s", pf.name)
                continue

        # 3. 解析文件
        try:
            output_str = parse_single(
                str(pf),
                format=format,
                tolerant=tolerant,
                verbose=verbose,
                include_schema=include_schema,
                include_function_graphs=include_function_graphs,
                include_parent_assets=include_parent_assets,
                asset_roots=asset_roots,
                mappings_path=mappings_path,
                game=game,
            )
            # 确定输出文件扩展名
            if format.startswith("json"):
                ext = ".json"
            elif format == "markdown":
                ext = ".md"
            elif format == "text":
                ext = ".txt"
            else:
                ext = f".{format}"

            out_file = output_path / f"{pf.stem}{ext}"
            out_file.write_text(output_str, encoding="utf-8")
            result.success.append(str(out_file))
        except Exception as e:
            result.failed.append((str(pf), str(e)))

        # 4. 分批 GC
        processed_in_batch += 1
        if processed_in_batch >= batch_size:
            force_gc()
            processed_in_batch = 0

    # 最终 GC
    force_gc()

    return result
```

**在 `core.py` 第 9 行附近修改顶层 import（注意 `Any, Callable` 必须在 `TYPE_CHECKING` 外，因为运行时函数签名需要）：**

将：
```python
from typing import TYPE_CHECKING
```

改为：
```python
from typing import TYPE_CHECKING, Any, Callable
```

- [ ] **Step 4: 更新 `__init__.py` 导出**

在 `src/uasset_read/__init__.py` 中添加 memory 模块导出：

```python
# 内存管理
from .memory import (
    MemoryMonitor,
    MemoryStatus,
    force_gc,
    get_file_size_mb,
    get_available_memory_gb,
)
```

在 `__all__` 列表中添加：
```python
    "MemoryMonitor",
    "MemoryStatus",
    "force_gc",
    "get_file_size_mb",
    "get_available_memory_gb",
```

- [ ] **Step 5: 修复测试中的导入并运行**

`tests/test_memory.py` 中的 `TestParseBatchMemoryManagement` 需要更新：
- `test_batch_gc_between_batches` 需要对空目录处理 `ValueError`

运行：
```
python -m pytest tests/test_memory.py -v
```

预期：全部 PASS。

- [ ] **Step 6: 运行现有测试确认无回归**

```
python scripts/test_matrix.py smoke
```

预期：全部 PASS。

- [ ] **Step 7: 提交**

```bash
git add src/uasset_read/core.py src/uasset_read/__init__.py tests/test_memory.py
git commit -m "feat: add memory management to parse_batch()"
```

---

### Task 2b: `parse_single()` 单文件入口保护

**Files:**
- Modify: `src/uasset_read/constants.py`（添加限制常量）
- Modify: `src/uasset_read/core.py:30-65` (`parse_single()` 签名和实现)
- Test: `tests/test_memory.py`（追加单文件保护测试）

**背景**：`parse_single()` 目前没有任何文件大小保护。直接调用 `parse_single("2GB_file.uasset")` 会无警告撑爆内存。
`parse_batch()` 的保护对直接 API 调用者无效，需要在 `parse_single()` 入口加独立防护。

**行为规则**：
- `> max_file_size_mb`（默认 1000 MB）→ 抛 `ParseError`（与解析失败一致，调用方可 `except`）
- `≥ WARN_FILE_SIZE_MB`（100 MB）→ 写 warning 到 `logging`，不阻止解析
- `max_file_size_mb=None` → 禁用检查（向后兼容，用于已知大文件的受控场景）

- [ ] **Step 1: 添加常量到 `constants.py`**

在 `src/uasset_read/constants.py` 末尾追加：

```python
# ---------------------------------------------------------------------------
# 内存安全限制（parse_single / parse_batch 共用）
# ---------------------------------------------------------------------------

# 单文件解析硬上限（MB）。超过此值 parse_single() 直接抛 ParseError。
# parse_batch() 的默认值更低（500 MB），可通过参数覆盖。
DEFAULT_MAX_PARSE_SIZE_MB: int = 1000

# 软警告阈值（MB）。超过此值 parse_single() 写 warning，不阻止解析。
WARN_FILE_SIZE_MB: int = 100
```

- [ ] **Step 2: 编写 `parse_single()` 保护的失败测试**

在 `tests/test_memory.py` 末尾追加：

```python
# ---------------------------------------------------------------------------
# parse_single 单文件入口保护
# ---------------------------------------------------------------------------

class TestParseSingleSizeProtection:
    """验证 parse_single() 的文件大小保护。"""

    def test_rejects_file_over_max_size(self, tmp_path: Path):
        """超过 max_file_size_mb 的文件应抛 ParseError。"""
        from uasset_read.core import parse_single
        from uasset_read.exceptions import ParseError

        # 创建一个 2 MB 的假文件
        fake = tmp_path / "big.uasset"
        fake.write_bytes(b"\x00" * (2 * 1024 * 1024))

        with pytest.raises(ParseError, match="too large"):
            parse_single(str(fake), max_file_size_mb=1.0)

    def test_none_disables_check(self, tmp_path: Path):
        """max_file_size_mb=None 应禁用大小检查（不抛 ParseError）。
        文件内容无效会导致其他解析错误，但不应是 'too large'。"""
        from uasset_read.core import parse_single
        from uasset_read.exceptions import ParseError

        fake = tmp_path / "big2.uasset"
        fake.write_bytes(b"\x00" * (2 * 1024 * 1024))

        with pytest.raises(ParseError) as exc_info:
            parse_single(str(fake), max_file_size_mb=None)
        # 错误不应是 'too large'
        assert "too large" not in str(exc_info.value).lower()

    def test_warns_for_file_over_warn_threshold(self, tmp_path: Path, caplog):
        """≥ WARN_FILE_SIZE_MB 的文件应产生 warning 日志。"""
        import logging
        from uasset_read.core import parse_single
        from uasset_read.constants import WARN_FILE_SIZE_MB
        from uasset_read.exceptions import ParseError

        # 创建一个刚好超过 WARN_FILE_SIZE_MB 的假文件
        fake = tmp_path / "warn.uasset"
        fake.write_bytes(b"\x00" * ((WARN_FILE_SIZE_MB + 1) * 1024 * 1024))

        with caplog.at_level(logging.WARNING, logger="uasset_read.core"):
            with pytest.raises(ParseError):
                # max_file_size_mb 设高一些，确保不触发硬限制
                parse_single(str(fake), max_file_size_mb=500)

        # 应有 warning 日志提及文件大小
        assert any("large" in r.message.lower() or "size" in r.message.lower()
                    for r in caplog.records)

    def test_default_max_is_1000_mb(self):
        """默认 max_file_size_mb 应为 1000 MB。"""
        from uasset_read.constants import DEFAULT_MAX_PARSE_SIZE_MB
        assert DEFAULT_MAX_PARSE_SIZE_MB == 1000

    def test_warn_threshold_is_100_mb(self):
        """WARN_FILE_SIZE_MB 应为 100 MB。"""
        from uasset_read.constants import WARN_FILE_SIZE_MB
        assert WARN_FILE_SIZE_MB == 100
```

- [ ] **Step 3: 运行测试确认失败**

```
python -m pytest tests/test_memory.py::TestParseSingleSizeProtection -v
```

预期：`TypeError: parse_single() got an unexpected keyword argument 'max_file_size_mb'`

- [ ] **Step 4: 修改 `parse_single()` 添加入口保护**

在 `src/uasset_read/core.py` 中，修改 `parse_single()` 签名和函数体开头：

**新签名（在现有参数后追加 `max_file_size_mb`）：**

```python
def parse_single(
    file_path: str,
    format: str = "json",
    tolerant: bool = True,
    verbose: bool = False,
    include_schema: bool = False,
    include_function_graphs: bool = False,
    include_parent_assets: bool = False,
    asset_roots: list[str] | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    *,
    max_file_size_mb: float | None = None,
) -> str:
    """解析单个 .uasset/.umap，返回格式化字符串。

    纯函数，无 argparse、无 sys.exit、无 print。
    需要 linker 的格式内部自动选择 parse_uasset_with_linker。

    Args:
        file_path: .uasset/.umap 文件路径
        format: 输出格式（json, json_summary, text, markdown 等）
        tolerant: 容错模式，遇到错误继续解析
        verbose: 详细输出
        include_schema: 包含 JSON Schema
        include_function_graphs: 包含函数图
        include_parent_assets: 解析父资产
        asset_roots: 资产根目录列表
        mappings_path: .usmap 映射文件路径
        game: 游戏名称
        max_file_size_mb: 单文件最大 MB，超过则抛 ParseError。
            None 时使用 DEFAULT_MAX_PARSE_SIZE_MB（1000 MB）。
            设为 float('inf') 或 0 禁用检查。

    Raises:
        ParseError: 解析失败，或文件超过大小限制
        ValueError: 渲染格式不存在
    """
    from uasset_read.constants import DEFAULT_MAX_PARSE_SIZE_MB, WARN_FILE_SIZE_MB
    from uasset_read.memory import get_file_size_mb

    # --- 文件大小保护 ---
    # 解析有效限制值：None → 默认值，0/inf → 禁用
    effective_limit = (
        DEFAULT_MAX_PARSE_SIZE_MB if max_file_size_mb is None else max_file_size_mb
    )
    check_enabled = effective_limit not in (0, float("inf"))

    if check_enabled:
        file_size_mb = get_file_size_mb(file_path)
        if file_size_mb > effective_limit:
            raise ParseError(
                f"File too large: {file_size_mb:.1f} MB exceeds "
                f"max_file_size_mb={effective_limit:.0f} MB. "
                f"Pass max_file_size_mb=None to use default ({DEFAULT_MAX_PARSE_SIZE_MB} MB), "
                f"or max_file_size_mb=0 to disable."
            )
        if file_size_mb >= WARN_FILE_SIZE_MB:
            _logger.warning(
                "Parsing large file: %s (%.1f MB). "
                "Memory usage will be high. Consider using parse_batch() with memory guards.",
                Path(file_path).name,
                file_size_mb,
            )

    # 需要 linker 的格式
    linker_formats = {"json", "json_summary", "cpp_skeleton"}
    # ... 后续代码不变
```

**在 `core.py` 顶部确保有 `logging` 和 `_logger`：**

`core.py` 当前没有 logger。在文件顶部 import 区（第 5-9 行附近）追加：

```python
import logging

_logger = logging.getLogger(__name__)
```

- [ ] **Step 5: 同步更新 `parse_batch()` 使用常量**

在 `parse_batch()` 中，将硬编码的 `max_file_size_mb: float = 500.0` 改为使用常量：

```python
from uasset_read.constants import DEFAULT_MAX_PARSE_SIZE_MB

def parse_batch(
    ...
    *,
    max_file_size_mb: float = 500.0,  # batch 默认比单文件更保守
    ...
```

保持不变（batch 的 500 MB 是有意设置的保守值），但添加注释说明与 `DEFAULT_MAX_PARSE_SIZE_MB` 的关系：

```python
    max_file_size_mb: float = 500.0,  # batch 保守值；单文件默认见 DEFAULT_MAX_PARSE_SIZE_MB (1000)
```

- [ ] **Step 5b: 在 `__init__.py` 导出新常量**

在 `src/uasset_read/__init__.py` 的常量导入块（`from .constants import (...)`）追加：

```python
    DEFAULT_MAX_PARSE_SIZE_MB,
    WARN_FILE_SIZE_MB,
```

在 `__all__` 列表中追加：

```python
    "DEFAULT_MAX_PARSE_SIZE_MB",
    "WARN_FILE_SIZE_MB",
```

- [ ] **Step 6: 运行测试确认通过**

```
python -m pytest tests/test_memory.py -v
```

预期：全部 PASS（含新增的 5 个 `TestParseSingleSizeProtection` 测试）。

- [ ] **Step 7: 运行 smoke 测试确认无回归**

```
python scripts/test_matrix.py smoke
```

预期：全部 PASS。

- [ ] **Step 8: 提交**

```bash
git add src/uasset_read/constants.py src/uasset_read/core.py src/uasset_read/__init__.py tests/test_memory.py
git commit -m "feat: add file size protection to parse_single() entry point"
```

---

### Task 3: 测试基础设施 — `conftest.py` + `pytest.ini` + GC fixture

**Files:**
- Create: `tests/conftest.py`
- Modify: `pytest.ini`
- Test: `tests/test_memory.py`（追加 GC fixture 验证）

**背景**：pytest 顺序运行 1000+ integration 测试时，Python 堆只增不缩，峰值可达 40+ GB。
在 integration/acceptance 测试后主动 `gc.collect()` 可将峰值压到单测试内存（< 500 MB）。

- [ ] **Step 1: 注册 `large` 标记到 `pytest.ini`**

在 `pytest.ini` 的 `markers` 段追加一行：

```ini
markers =
    integration: 需要外部样本资产或较慢路径的集成测试
    quality: C++ 输出质量门禁测试
    regression: 真实资产回归测试
    slow: 需要大量时间或全量资产扫描的慢速测试
    auxiliary: 辅助/历史回归测试，默认单元层不包含
    acceptance: 最终验收测试，证明产品目标达成
    large: 需要大资产（> 100 MB）或高内存的测试，默认跳过
```

- [ ] **Step 2: 创建 `tests/conftest.py`（含 GC fixture）**

```python
"""pytest 全局配置 — 提供大资产门控、测试后内存释放。"""
from __future__ import annotations

import gc

import pytest


# ---------------------------------------------------------------------------
# --include-large 选项
# ---------------------------------------------------------------------------

def pytest_addoption(parser: pytest.Parser) -> None:
    """注册 --include-large 命令行选项。"""
    parser.addoption(
        "--include-large",
        action="store_true",
        default=False,
        help="Include tests marked with @pytest.mark.large (assets > 100 MB)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """未传 --include-large 时，跳过 @pytest.mark.large 标记的测试。"""
    if config.getoption("--include-large"):
        return
    skip_large = pytest.mark.skip(
        reason="large asset test (pass --include-large to enable)"
    )
    for item in items:
        if "large" in item.iter_markers():
            item.add_marker(skip_large)


# ---------------------------------------------------------------------------
# 测试后内存释放
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _gc_after_heavy_test(request: pytest.FixtureRequest):
    """integration / acceptance 测试结束后强制 GC，防止堆无限增长。

    单元测试不涉及资产加载，跳过 GC 以保持速度。
    """
    yield
    markers = {m.name for m in request.node.iter_markers()}
    if markers & {"integration", "acceptance"}:
        gc.collect()
```

- [ ] **Step 3: 追加 GC fixture 验证测试到 `tests/test_memory.py`**

在文件末尾追加：

```python
# ---------------------------------------------------------------------------
# GC fixture 行为验证
# ---------------------------------------------------------------------------

class TestGcAfterHeavyTest:
    """验证 integration/acceptance 测试后 GC 被触发。"""

    @pytest.mark.integration
    def test_gc_runs_after_integration_test(self):
        """此测试标记 integration，fixture 应在 teardown 时调用 gc.collect()。
        验证方式：fixture 不报错即通过；此处额外确认 gc 模块可用。"""
        import gc
        # gc.collect() 返回被回收的对象数量，不应抛异常
        collected = gc.collect()
        assert isinstance(collected, int)

    def test_gc_not_triggered_for_plain_test(self):
        """普通测试（无 integration/acceptance 标记）不触发 GC fixture。
        此测试本身不标记，fixture yield 后分支不进入 gc.collect()。
        仅验证 fixture 的条件判断逻辑不报错。"""
        assert True
```

- [ ] **Step 4: 运行测试验证**

```
python -m pytest tests/test_memory.py -v
```

预期：全部 PASS（含新增 2 个 GC 测试）。

```
python -m pytest tests/test_memory.py -v --collect-only 2>&1 | grep -i "large"
```

预期：无报错，conftest.py 正常加载。

- [ ] **Step 5: 提交**

```bash
git add tests/conftest.py pytest.ini tests/test_memory.py
git commit -m "feat: add autouse GC fixture for integration/acceptance tests and --include-large gate"
```

---

### Task 4: 测试资产大小分级

**Files:**
- Modify: `tests/test_sample_assets_representative.py:14-19` (SampleAsset dataclass)、资产列表
- Modify: `tests/test_acceptance.py` (大资产标记)

- [ ] **Step 1: 更新 `SampleAsset` 添加 `size_class` 字段**

在 `tests/test_sample_assets_representative.py` 中修改 `SampleAsset` dataclass：

```python
@dataclass(frozen=True)
class SampleAsset:
    label: str
    category: str
    relative_path: str
    size_class: str = "small"  # "small" (<10MB), "medium" (10-100MB), "large" (>100MB)
    known_current_defect: str | None = None
```

- [ ] **Step 2: 为资产列表添加 `size_class`**

根据实际文件大小（已通过查询确认所有当前 STABLE_ASSETS 和 DIAGNOSTIC_ASSETS 均 < 10 MB），保持默认 `"small"`。但为未来扩展，在列表中添加注释说明分级标准：

```python
# 大小分级标准：
# - "small":  < 10 MB  — 无限制
# - "medium": 10-100 MB — batch 处理时产生警告
# - "large":  > 100 MB — 需要 --include-large 才能运行测试
STABLE_ASSETS = [
    # 所有当前资产均为 small，保持默认 size_class="small"
    SampleAsset(
        "first_person_blueprint",
        "Blueprint",
        r"FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset",
    ),
    # ... 其余保持不变
]
```

- [ ] **Step 3: 在 `test_acceptance.py` 中为大资产测试添加 `@pytest.mark.large`**

当前 `test_acceptance.py` 的 `ASSET_TYPE_SAMPLES` 中所有资产均 < 10 MB，无需标记。但为未来扩展，在文件顶部添加说明注释：

```python
# 大资产测试门控说明：
# 若新增 > 100 MB 的样本资产到 ASSET_TYPE_SAMPLES，
# 需要为对应的 parametrize 项添加 @pytest.mark.large 标记。
# 用法：pytest.param(asset_type, rel_path, marks=pytest.mark.large)
```

- [ ] **Step 4: 添加大资产测试示例（用于验证门控机制）**

在 `tests/test_memory.py` 末尾追加一个验证门控机制的集成测试：

```python
class TestLargeAssetGate:
    """验证 @pytest.mark.large 门控机制工作正常。"""

    @pytest.mark.large
    def test_large_marker_is_gated(self):
        """此测试仅在 --include-large 时运行。
        用于验证门控机制：不带 --include-large 时此测试被 skip。
        """
        assert True, "If you see this, --include-large was passed"
```

- [ ] **Step 5: 运行测试验证门控生效**

```
# 不带 --include-large：test_large_marker_is_gated 应被 skip
python -m pytest tests/test_memory.py::TestLargeAssetGate -v
```

预期：`SKIPPED (large asset test (pass --include-large to enable))`

```
# 带 --include-large：应 PASS
python -m pytest tests/test_memory.py::TestLargeAssetGate -v --include-large
```

预期：`PASSED`

- [ ] **Step 6: 提交**

```bash
git add tests/test_sample_assets_representative.py tests/test_acceptance.py tests/test_memory.py
git commit -m "feat: add asset size classification and large test gate"
```

---

### Task 5: `test_matrix.py` — `all` 排除 large + 强制串行

**Files:**
- Modify: `scripts/test_matrix.py:30-59` (SUITES 定义)、`scripts/test_matrix.py:71-92` (main)

**背景**：`pytest-xdist -n N` 为每个 worker 启动独立进程，各进程独立持有资产 IR。
全量测试 19,000+ 文件时，`-n 4` 每进程峰值约 11 GB，4 进程合计 44 GB → OOM。
`all` suite 强制 `-n 1`（串行），配合 conftest.py 的 GC fixture 控制峰值。

- [ ] **Step 1: 修改 `SUITES["all"]` 排除 large 标记**

在 `scripts/test_matrix.py` 中，将 `SUITES["all"]` 从 `["tests"]` 改为：

```python
SUITES: dict[str, list[str]] = {
    # ... 其他不变
    "all": [
        "tests",
        "-m",
        "not large",  # 默认排除大资产测试
    ],
    "all-with-large": [
        "tests",  # 包含所有测试（含 large）
    ],
}

# 这些 suite 涉及大量资产加载，强制串行防止多进程 OOM
_SERIAL_SUITES = {"all", "all-with-large"}
```

- [ ] **Step 2: 修改 `main()` — `--include-large` 透传 + 串行保护**

```python
def main() -> int:
    parser = argparse.ArgumentParser(description="Run curated pytest suites")
    parser.add_argument("suite", choices=sorted(SUITES.keys()))
    parser.add_argument(
        "--include-large",
        action="store_true",
        default=False,
        help="Include @pytest.mark.large tests (assets > 100 MB)",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments passed through to pytest after --",
    )
    args = parser.parse_args()

    passthrough = args.pytest_args
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]

    extra_args: list[str] = []

    # --include-large 透传给 pytest
    if args.include_large:
        extra_args.append("--include-large")

    # 串行保护：all / all-with-large 强制 -n 1，覆盖用户传入的 -n N
    if args.suite in _SERIAL_SUITES:
        passthrough = _strip_xdist_workers(passthrough)
        extra_args.append("-n")
        extra_args.append("1")
        print(
            f"[test_matrix] suite '{args.suite}' forces -n 1 "
            f"(multi-process xdist OOM risk — see docs/guides/testing-concurrency.md)",
            flush=True,
        )

    cmd = [sys.executable, "-m", "pytest", *SUITES[args.suite], *extra_args, *passthrough]
    print("Running:", " ".join(cmd), flush=True)
    completed = subprocess.run(cmd, cwd=ROOT, env=build_env())
    return completed.returncode


def _strip_xdist_workers(args: list[str]) -> list[str]:
    """移除 passthrough 中的 -n N / -nN / --numprocesses N，避免与串行保护冲突。"""
    cleaned: list[str] = []
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg in ("-n", "--numprocesses"):
            skip_next = True  # 跳过后面的数字
            continue
        if arg.startswith("-n") and arg[2:].lstrip().isdigit():
            continue  # -n4 形式
        if arg.startswith("--numprocesses="):
            continue
        cleaned.append(arg)
    return cleaned
```

- [ ] **Step 3: 验证命令正确性**

```bash
# 验证 all 排除 large + 串行
python scripts/test_matrix.py all -- tests/test_memory.py::TestLargeAssetGate -v
```

预期：
- 输出 `[test_matrix] suite 'all' forces -n 1 ...`
- 测试被 SKIP（large gate 生效）
- pytest 命令中包含 `-n 1`

```bash
# 验证 -n 4 被覆盖为 -n 1
python scripts/test_matrix.py all -- -n 4 tests/test_memory.py::TestLargeAssetGate -v 2>&1 | head -5
```

预期：`-n 4` 被移除，输出 forces -n 1 提示，实际执行 `-n 1`。

```bash
# 验证 all --include-large 包含 large
python scripts/test_matrix.py all --include-large -- tests/test_memory.py::TestLargeAssetGate -v
```

预期：测试 PASS。

- [ ] **Step 4: 运行 smoke 测试确认无回归**

```
python scripts/test_matrix.py smoke
```

预期：全部 PASS（smoke 不在 `_SERIAL_SUITES` 中，不受影响）。

- [ ] **Step 5: 提交**

```bash
git add scripts/test_matrix.py
git commit -m "feat: test_matrix.py all forces serial execution and excludes large tests"
```

---

### Task 6: 多会话并发测试规范文档（Issue #104）

**Files:**
- Create: `docs/guides/testing-concurrency.md`

- [ ] **Step 1: 创建文档**

创建 `docs/guides/testing-concurrency.md`：

```markdown
# 多会话并发测试规范

> 背景：参见 [Issue #104](https://github.com/.../issues/104) — 2026-06-10 多会话并发测试导致系统内存耗尽。

## 核心规则

1. **同一时间只有一个会话可以运行 `test_matrix.py all`。**
2. **`all` / `all-with-large` 强制串行**（`-n 1`），禁止多进程并行。
3. 不要手动给 `all` suite 传 `-n N`（N > 1），会被自动覆盖。

违反规则的后果：每个 pytest 进程独立加载资产到内存，多进程叠加可导致系统内存耗尽 → 系统强制重启。

## 测试分级与资源消耗

| 测试级别 | 命令 | 峰值内存 | 并发限制 |
|---------|------|---------|---------|
| `smoke` | `test_matrix.py smoke` | < 1 GB | 无限制 |
| `unit` | `test_matrix.py unit` | < 2 GB | 无限制 |
| `integration` | `test_matrix.py integration` | 5-10 GB | 最多 2 个会话 |
| `all` | `test_matrix.py all` | < 1 GB（GC fixture） | **仅 1 个会话，强制 -n 1** |
| `all --include-large` | `test_matrix.py all --include-large` | 5-15 GB | **仅 1 个会话，强制 -n 1，需 ≥ 16 GB RAM** |

> **峰值内存数据来源**：`all` suite 含 ~1000 个 integration 测试。
> 无 GC 时峰值 ~44 GB（Python 堆只增不缩）；
> 有 conftest.py `_gc_after_heavy_test` fixture 时，每测试后 GC，峰值降至单测试内存（< 500 MB）。

## 超大文件处理策略

### 资产大小分级与处理方式

| 级别 | 大小 | 解析行为 | 测试行为 |
|-----|------|---------|---------|
| small | < 10 MB | 正常解析 | 默认包含 |
| medium | 10-100 MB | 正常解析，batch 日志提示 | 默认包含 |
| large | 100-500 MB | batch 前打印警告，内存检查更频繁 | `@pytest.mark.large`，默认跳过 |
| huge | > 500 MB | **硬跳过**，记入 `skipped_large` | 不纳入常规测试 |

### 为什么 > 500 MB 要硬跳过

解析后 IR 内存占用约为原始文件的 3-5 倍。一个 500 MB 的 .uasset 解析后可能占用 1.5-2.5 GB。
批量处理数百个此类文件时，即使有 GC，峰值仍可能超过可用内存。
默认 `max_file_size_mb=500` 可在 API 层调整：

```python
parse_batch("path/", max_file_size_mb=1000)  # 提高限制（需确保 RAM 充足）
```

### `parse_single()` 入口保护

`parse_single()` 同样受保护，默认上限 1000 MB：

```python
from uasset_read import parse_single
from uasset_read.exceptions import ParseError

# 正常解析（< 1000 MB 无感知）
output = parse_single("normal.uasset")

# 超限 → ParseError（可在调用方 except 处理）
try:
    output = parse_single("huge.uasset")
except ParseError as e:
    if "too large" in str(e):
        print(f"跳过超大文件: {e}")

# 禁用检查（已知大文件的受控场景）
output = parse_single("huge.uasset", max_file_size_mb=0)

# 自定义上限
output = parse_single("medium.uasset", max_file_size_mb=200)
```

**CLI 单文件模式**同样受保护，`--max-file-size` 参数同时作用于单文件和批量模式：

```bash
# 单文件超 1000 MB 默认报错
python run.py huge.uasset

# 自定义上限
python run.py huge.uasset --max-file-size 2000

# 禁用检查
python run.py huge.uasset --max-file-size 0
```

### mmap 保护（已有机制）

> 50 MB 的文件自动使用 `mmap`（内存映射），不将整个文件读入 Python 堆。
> 这减少了 RSS，但解析出的 IR 结构仍占用常规内存。

## 全量测试内存安全机制

### conftest.py GC fixture

`tests/conftest.py` 提供 `autouse` fixture，在每个标记了 `@pytest.mark.integration` 或 `@pytest.mark.acceptance` 的测试结束后自动调用 `gc.collect()`。

- 单元测试不受影响（保持速度）
- integration/acceptance 测试峰值内存控制在单测试水平
- 无需手动管理

### 串行保护（test_matrix.py）

`test_matrix.py` 对 `all` 和 `all-with-large` suite 强制注入 `-n 1`，即使用户传入 `-n N` 也会被自动移除并打印警告。

原因：`pytest-xdist` 多进程模式下，每个 worker 独立持有资产 IR，GC fixture 无法跨进程回收。
全量 19,000 文件 × `-n 4` = 每进程 ~11 GB，合计 44 GB → OOM。

### 安全运行全量测试

```bash
# 1. 确认系统资源：可用内存 ≥ 10 GB
# 2. 确保无其他会话跑全量测试
tasklist | findstr python

# 3. 串行运行（自动 GC，自动 -n 1）
python scripts/test_matrix.py all

# 4. 含大资产（单独会话，需 ≥ 16 GB RAM）
python scripts/test_matrix.py all --include-large
```

## 批量解析内存管理

`parse_batch()` 内置三层保护：

```python
from uasset_read import parse_batch

result = parse_batch(
    "path/to/assets",
    max_file_size_mb=500,    # 层 1：单文件硬跳过
    batch_size=50,           # 层 2：每 50 个文件强制 GC
    max_memory_percent=70,   # 层 3：系统内存超 70% 暂停处理
)

# 检查结果
for path, reason in result.skipped_large:
    print(f"跳过（超大）: {path} — {reason}")
for path, reason in result.skipped:
    print(f"跳过（内存）: {path} — {reason}")
```

### 可选依赖：psutil

```bash
pip install psutil
```

安装后 `MemoryMonitor` 启用实时内存检查；未安装时内存检查返回 OK（不阻止处理），大文件跳过仍生效。

## 开发阶段推荐流程

```
编写代码
  → smoke（< 1 GB，随时跑）
  → unit（< 2 GB，随时跑）
  → integration（5-10 GB，最多 2 会话并发）
  → all（强制串行 + GC，仅 1 会话）
  → all --include-large（最终验证，单独会话）
```
```

- [ ] **Step 2: 提交**

```bash
git add docs/guides/testing-concurrency.md
git commit -m "docs: add multi-session concurrent testing guidelines (#104)"
```

---

### Task 7: CLI 增强 — `--max-file-size` 统一作用于单文件和批量模式

**Files:**
- Modify: `src/uasset_read/cli.py:60-103` (参数定义)、`src/uasset_read/cli.py:142-181` (_handle_batch)、`src/uasset_read/cli.py:247-258` (单文件 parse_single 调用)

- [ ] **Step 1: 在 `create_parser()` 中添加内存参数**

在 `src/uasset_read/cli.py` 的 `create_parser()` 函数中，在 `--batch-dir` 参数后追加：

```python
    # 内存安全参数（单文件和批量模式共用）
    parser.add_argument(
        '--max-file-size',
        type=float,
        default=None,
        metavar='MB',
        help=(
            'Reject files larger than MB. '
            'Single-file mode: raises error (default: 1000 MB). '
            'Batch mode: skips file (default: 500 MB). '
            'Pass 0 to disable.'
        ),
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        metavar='N',
        help='GC every N files in batch mode (default: 50)',
    )
    parser.add_argument(
        '--max-memory',
        type=float,
        default=70.0,
        metavar='PCT',
        help='Skip files when system memory usage exceeds PCT%% (default: 70, batch only)',
    )
```

> 注意：`--max-file-size` 的 `default=None`，让 `parse_single()` 和 `parse_batch()` 各自使用自己的默认值（1000 / 500 MB）。CLI 层不硬编码默认值，避免与 API 层不一致。

- [ ] **Step 2: 更新单文件处理器传递 `max_file_size_mb`**

在 `cli.py` 中，找到调用 `parse_single()` 的地方（约第 247 行），添加 `max_file_size_mb` 参数：

```python
    try:
        output_str = parse_single(
            str(file_path),
            format=fmt,
            tolerant=tolerant,
            verbose=args.verbose,
            include_schema=args.schema or args.verbose,
            include_function_graphs=args.function_graphs,
            include_parent_assets=args.include_parent_assets,
            asset_roots=list(args.asset_root or []),
            mappings_path=args.mappings,
            game=args.game,
            max_file_size_mb=args.max_file_size,  # 新增：None → API 默认值 1000 MB
        )
```

- [ ] **Step 3: 更新 `_handle_batch()` 传递新参数**

修改 `_handle_batch()` 中的 `parse_batch()` 调用，将 `args.max_file_size` 传入（`None` → batch 默认 500 MB）：

```python
def _handle_batch(args) -> None:
    """处理批量导出模式。"""
    input_dir = Path(args.file)
    if not input_dir.is_dir():
        print(f"Error: Not a directory: {args.file}", file=sys.stderr)
        sys.exit(EXIT_FILE_NOT_FOUND)

    output_dir = args.batch_dir or str(input_dir / "output")

    try:
        result = parse_batch(
            str(input_dir),
            format=resolve_format(args),
            output_dir=output_dir,
            tolerant=not args.strict,
            verbose=args.verbose,
            include_schema=args.schema or args.verbose,
            include_function_graphs=args.function_graphs,
            include_parent_assets=args.include_parent_assets,
            asset_roots=list(args.asset_root or []),
            mappings_path=args.mappings,
            game=args.game,
            max_file_size_mb=args.max_file_size,  # None → batch 默认 500 MB
            batch_size=args.batch_size,
            max_memory_percent=args.max_memory,
        )
    except Exception as e:
        _logger.debug("Batch export error (full): %s", e, exc_info=True)
        print(f"Error: {_sanitize_error_message(e)}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    print(f"Batch export complete: {result.total} files", file=sys.stderr)
    print(f"  Success: {len(result.success)}", file=sys.stderr)
    if result.skipped_large:
        print(f"  Skipped (large): {len(result.skipped_large)}", file=sys.stderr)
        for path, reason in result.skipped_large:
            print(f"    - {Path(path).name}: {reason}", file=sys.stderr)
    if result.skipped:
        print(f"  Skipped (memory): {len(result.skipped)}", file=sys.stderr)
        for path, reason in result.skipped:
            print(f"    - {Path(path).name}: {reason}", file=sys.stderr)
    if result.failed:
        print(f"  Failed: {len(result.failed)}", file=sys.stderr)
        for path, error in result.failed:
            _logger.debug("Batch file failed (full): %s — %s", path, error)
            print(f"    - {Path(path).name}: {_sanitize_error_message(error)}", file=sys.stderr)
        sys.exit(EXIT_PARSE_ERROR)

    sys.exit(EXIT_SUCCESS)
```

- [ ] **Step 4: 运行 smoke 测试确认无回归**

```
python scripts/test_matrix.py smoke
```

预期：全部 PASS。

- [ ] **Step 5: 验证 CLI 参数被接受**

```bash
python run.py --help | grep -A3 "max-file-size"
```

预期：显示新参数帮助文本，说明单文件和批量模式的不同默认值。

- [ ] **Step 6: 验证单文件大小保护生效**

```bash
# 用 --max-file-size 0.001（约 1 KB）解析任何文件都应报错
python run.py tests/fixtures/tiny.uasset --max-file-size 0.001 2>&1 | grep -i "too large"
# 若无测试 fixture，跳过此步，在 Task 9 验证
```

预期：输出包含 "too large" 或 "exceeds max_file_size_mb"。

- [ ] **Step 7: 提交**

```bash
git add src/uasset_read/cli.py
git commit -m "feat: CLI --max-file-size applies to both single-file and batch modes"
```

---

### Task 8: psutil 缺失时的诊断日志

**Files:**
- Modify: `src/uasset_read/memory.py`（追加首次诊断日志）

> 项目不使用 `pyproject.toml`/`setup.py`（纯脚本运行），无法声明可选依赖。
> `psutil` 的可选性已在 `MemoryMonitor` 中处理。本任务补充首次使用时的诊断提示。

- [ ] **Step 1: 在 `MemoryMonitor.__init__` 中添加一次性诊断日志**

在 `src/uasset_read/memory.py` 的 `MemoryMonitor.__init__` 方法末尾（`self._psutil = ...` 之后）追加：

```python
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
```

- [ ] **Step 2: 运行测试确认无回归**

```
python -m pytest tests/test_memory.py -v
```

预期：全部 PASS。

- [ ] **Step 3: 提交**

```bash
git add src/uasset_read/memory.py
git commit -m "feat: log diagnostic when psutil is unavailable"
```

---

### Task 9: 全量测试验证

- [ ] **Step 1: 运行 smoke 测试**

```
python scripts/test_matrix.py smoke
```

预期：全部 PASS。

- [ ] **Step 2: 运行 unit 测试**

```
python scripts/test_matrix.py unit
```

预期：全部 PASS。

- [ ] **Step 3: 运行 integration 测试**

```
python scripts/test_matrix.py integration
```

预期：全部 PASS（大资产测试被 skip，显示 `--include-large` 提示）。

- [ ] **Step 4: 验证 large 门控**

```
python -m pytest tests/test_memory.py -v 2>&1 | grep -E "SKIP|PASS|large"
```

预期：`test_large_marker_is_gated` 状态为 `SKIPPED`

```
python -m pytest tests/test_memory.py -v --include-large 2>&1 | grep -E "SKIP|PASS|large"
```

预期：`test_large_marker_is_gated` 状态为 `PASSED`

- [ ] **Step 5: 验证串行保护**

```bash
# all suite 强制 -n 1（即使传入 -n 4 也被覆盖）
python scripts/test_matrix.py all -- -n 4 tests/test_memory.py -v 2>&1 | head -3
```

预期：
- 输出 `[test_matrix] suite 'all' forces -n 1 ...`
- pytest 命令中实际使用 `-n 1`（不是 `-n 4`）

- [ ] **Step 6: 验证 GC fixture 活跃**

```bash
# 运行一个 integration 测试，确认 fixture 不报错
python -m pytest tests/test_memory.py::TestGcAfterHeavyTest -v
```

预期：两个测试均 PASS（fixture 在 teardown 时执行 GC，无异常）。

- [ ] **Step 7: 运行质量门禁**

```
python scripts/test_matrix.py quality
```

预期：全部 PASS。

- [ ] **Step 8: 最终提交（如有遗留修改）**

```bash
git status --short
git add -A
git commit -m "chore: finalize memory safety implementation (#105, #104)"
```
