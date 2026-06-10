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
        mock_psutil = type("MockPsutil", (), {"virtual_memory": lambda self: mock_mem})()
        monitor = MemoryMonitor(max_memory_percent=70)
        # 直接设置 _psutil 属性来模拟 psutil 可用
        object.__setattr__(monitor, "_psutil", mock_psutil)
        status = monitor.check()
        assert status.state == MemoryStatus.OK

    def test_status_low_when_approaching_limit(self):
        """模拟已用内存 75%（超过 70% 阈值）。"""
        # 32 GB 总内存，8 GB 可用 → used=75%
        mock_mem = _make_mock_mem(available_gb=8, total_gb=32)
        mock_psutil = type("MockPsutil", (), {"virtual_memory": lambda self: mock_mem})()
        monitor = MemoryMonitor(max_memory_percent=70)
        object.__setattr__(monitor, "_psutil", mock_psutil)
        status = monitor.check()
        assert status.state == MemoryStatus.LOW

    def test_status_critical_when_very_low(self):
        """模拟已用内存 93%（超过 critical 阈值 90%）。"""
        # 32 GB 总内存，2 GB 可用 → used=93.75%
        mock_mem = _make_mock_mem(available_gb=2, total_gb=32)
        mock_psutil = type("MockPsutil", (), {"virtual_memory": lambda self: mock_mem})()
        monitor = MemoryMonitor(max_memory_percent=70)
        object.__setattr__(monitor, "_psutil", mock_psutil)
        status = monitor.check()
        assert status.state == MemoryStatus.CRITICAL

    def test_unavailable_returns_unavailable_with_note(self):
        """psutil 不可用时返回 UNAVAILABLE + warning。"""
        monitor = MemoryMonitor(max_memory_percent=70, _force_unavailable=True)
        status = monitor.check()
        assert status.state == MemoryStatus.UNAVAILABLE
        assert "not installed" in (status.warning or "").lower()

    def test_is_safe_true_for_unavailable(self):
        monitor = MemoryMonitor(max_memory_percent=70, _force_unavailable=True)
        assert monitor.is_safe() is True

    def test_is_safe_false_for_critical(self):
        # 32 GB 总内存，2 GB 可用 → used=93.75% → CRITICAL
        mock_mem = _make_mock_mem(available_gb=2, total_gb=32)
        mock_psutil = type("MockPsutil", (), {"virtual_memory": lambda self: mock_mem})()
        monitor = MemoryMonitor(max_memory_percent=70)
        object.__setattr__(monitor, "_psutil", mock_psutil)
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
        from uasset_read.constants import PACKAGE_FILE_TAG
        fake_uasset = tmp_path / "huge.uasset"
        header = PACKAGE_FILE_TAG.to_bytes(4, "little")
        fake_uasset.write_bytes(header + b"\x00" * (2 * 1024 * 1024))

        result = parse_batch(
            str(tmp_path),
            output_dir=str(tmp_path / "out"),
            max_file_size_mb=1.0,
        )
        assert len(result.skipped_large) == 1
        assert "huge.uasset" in result.skipped_large[0][0]
        assert result.success == []

    def test_batch_accepts_batch_size_parameter(self, tmp_path: Path):
        """batch_size 参数应被接受，空目录抛 ValueError。"""
        from uasset_read.core import parse_batch
        with pytest.raises(ValueError, match="No .uasset/.umap files"):
            parse_batch(
                str(tmp_path),
                output_dir=str(tmp_path / "out"),
                batch_size=10,
            )

    def test_batch_memory_check_callback(self, tmp_path: Path):
        """自定义 memory_check 回调可以阻止处理。"""
        from uasset_read.core import parse_batch
        from uasset_read.constants import PACKAGE_FILE_TAG

        fake = tmp_path / "test.uasset"
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
        assert call_count >= 1
        assert result.success == []


# ---------------------------------------------------------------------------
# parse_single 单文件入口保护
# ---------------------------------------------------------------------------

class TestParseSingleSizeProtection:
    """验证 parse_single() 的文件大小保护。"""

    def test_rejects_file_over_max_size(self, tmp_path: Path):
        """超过 max_file_size_mb 的文件应抛 ParseError。"""
        from uasset_read.core import parse_single
        from uasset_read.exceptions import ParseError

        fake = tmp_path / "big.uasset"
        fake.write_bytes(b"\x00" * (2 * 1024 * 1024))

        with pytest.raises(ParseError, match="too large"):
            parse_single(str(fake), max_file_size_mb=1.0)

    def test_none_disables_check(self, tmp_path: Path):
        """max_file_size_mb=None 应禁用大小检查（不抛 'too large' ParseError）。
        文件内容无效可能导致其他行为（容错模式返回字符串），但不应是 'too large'。"""
        from uasset_read.core import parse_single
        from uasset_read.exceptions import ParseError

        fake = tmp_path / "big2.uasset"
        fake.write_bytes(b"\x00" * (2 * 1024 * 1024))

        try:
            result = parse_single(str(fake), max_file_size_mb=None)
            # 容错模式可能返回字符串而不是抛异常
            assert isinstance(result, str)
        except ParseError as e:
            # 如果抛出了 ParseError，不应是 'too large'
            assert "too large" not in str(e).lower()

    def test_warns_for_file_over_warn_threshold(self, tmp_path: Path, caplog):
        """≥ WARN_FILE_SIZE_MB 的文件应产生 warning 日志。"""
        import logging
        from uasset_read.core import parse_single
        from uasset_read.constants import WARN_FILE_SIZE_MB

        fake = tmp_path / "warn.uasset"
        fake.write_bytes(b"\x00" * ((WARN_FILE_SIZE_MB + 1) * 1024 * 1024))

        with caplog.at_level(logging.WARNING, logger="uasset_read.core"):
            # 容错模式下不会抛异常，只验证警告日志
            result = parse_single(str(fake), max_file_size_mb=500)
            assert isinstance(result, str)

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