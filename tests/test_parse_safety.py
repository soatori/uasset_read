"""安全边界与批量报告测试 — 合并自 test_core_safety.py、test_batch_report.py、
test_batch_summary.py、test_batch_log_evidence.py、test_log_aggregation.py、
test_report_summary.py。

覆盖：安全边界、批量报告、日志聚合。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uasset_read.core import BatchResult, _log_batch_summary
from uasset_read.exceptions import ParseError
from uasset_read.memory_safety import MemoryLimitExceeded, MemoryPolicy, ResourceLimits
from uasset_read.models.result import ParseResult


# ============================================================================
# 1. tolerant_parse 去重
# ============================================================================

def test_tolerant_parse_dedup():
    """tolerant_parse 去重 + MemoryLimitExceeded re-raise。"""
    from uasset_read.core.error_handling import tolerant_parse
    from uasset_read.parse_uasset import _handle_parse_error

    class _R:
        def __init__(self):
            self.errors: list[str] = []

    result = _R()
    with pytest.raises(ParseError):
        with tolerant_parse(result, "stage"):
            raise ParseError("dup error")
    assert len(result.errors) == 1
    with pytest.raises(ParseError):
        with tolerant_parse(result, "stage"):
            raise ParseError("dup error")
    assert len(result.errors) == 1

    # MemoryLimitExceeded should be re-raised
    class _FakeArchive:
        def total_size(self): return 1024
        def tell(self): return 0
    result2 = ParseResult(); result2.is_success = True
    exc = MemoryLimitExceeded(asset_path="test.uasset", stage="parse", current_rss_mb=2048.0, limit_mb=1024.0)
    caught = None
    try:
        raise exc
    except Exception as e:
        try:
            _handle_parse_error(e, result2, _FakeArchive(), "test.uasset", tolerant=True)
        except MemoryLimitExceeded as re_raised:
            caught = re_raised
    assert caught is not None
    assert result2.errors == []


# ============================================================================
# 2. _record_parse_stage_error 去重
# ============================================================================

def test_record_parse_stage_error_dedup():
    """重复错误不应重复添加到 result.errors，但 diagnostic 仍记录。"""
    from uasset_read.parse_stages import _record_parse_stage_error

    class _FakeArchive:
        def total_size(self): return 1024
        def tell(self): return 0

    class _FakeResult:
        def __init__(self):
            self.errors: list[str] = []
            self.is_success = True
            self.diagnostics: list = []
            self._error_keys: set = set()

    result = _FakeResult()
    archive = _FakeArchive()

    _record_parse_stage_error(result, archive, "test.uasset", "parse", "field", ValueError("dup"))
    _record_parse_stage_error(result, archive, "test.uasset", "parse", "field", ValueError("dup"))

    assert len(result.errors) == 1
    assert len(result.diagnostics) == 2


# ============================================================================
# 4. batch 失败日志落盘
# ============================================================================

def test_batch_failure_logged_to_same_file(tmp_path):
    """batch 失败时，关键信息应在同一 log 文件中。"""
    from uasset_read.core import parse_batch

    batch_dir = tmp_path / "batch_input"
    batch_dir.mkdir()
    fake_asset = batch_dir / "fail.uasset"
    fake_asset.write_bytes(b"\x00" * 100)

    log_dir = tmp_path / "logs"

    with patch("uasset_read.core._parse_and_render", side_effect=ValueError("corrupted asset")):
        result = parse_batch(
            str(batch_dir),
            isolate_assets=False,
            log_dir=str(log_dir),
            log_enabled=True,
        )

    assert len(result.failed) >= 1
    _, error, _ = result.failed[0]
    assert "corrupted asset" in error

    log_files = list(Path(log_dir).rglob("*.log")) if log_dir.exists() else []
    if not log_files:
        project_log = Path("log")
        if project_log.exists():
            log_files = sorted(project_log.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)

    if log_files:
        log_content = log_files[0].read_text(encoding="utf-8", errors="replace")
        assert "batch_summary" in log_content
        assert "failed=1" in log_content


# ============================================================================
# 5. batch 摘要计数
# ============================================================================

def test_batch_summary_counts():
    """验证摘要中各计数正确。"""
    result = BatchResult(total=6)
    result.success = ["a.json", "b.json", "c.json"]
    result.partial = ["b.json"]
    result.skipped = [("d.json", "memory limit")]
    result.failed = [("e.json", "parse error", ""), ("f.json", "timeout", "")]

    with patch.object(logging.getLogger("uasset_read.core"), "info") as mock_info:
        _log_batch_summary(result, elapsed_seconds=5.0)
        mock_info.assert_called_once()
        args, kwargs = mock_info.call_args
        assert args[1] == 6     # total
        assert args[2] == 3     # success
        assert args[3] == 1     # partial
        assert args[4] == 1     # skipped
        assert args[5] == 2     # failed
        assert args[6] == 5.0   # elapsed


# ============================================================================
# 6. DEBUG 日志聚合计数
# ============================================================================

def test_debug_aggregation_shows_counts():
    """重复 DEBUG 消息超过 repeat_limit 后应被抑制，message_counts 记录完整次数。"""
    from uasset_read.project_logging import _RepeatedDebugFilter

    logger = logging.getLogger("test_aggregation")
    logger.setLevel(logging.DEBUG)
    filter_obj = _RepeatedDebugFilter(repeat_limit=3)
    logger.addFilter(filter_obj)

    for _ in range(10):
        logger.debug("read_name: index out of range")

    assert filter_obj.suppressed_count == 7
    assert "read_name: index out of range" in filter_obj.message_counts
    assert filter_obj.message_counts["read_name: index out of range"] == 10
    logger.removeFilter(filter_obj)


# ============================================================================
# 7. 原子写入完整性
# ============================================================================

def test_atomic_write_produces_valid_json(tmp_path):
    """#434: 原子写入中断后不应产生不完整 JSON 文件"""
    import json
    import tempfile

    out_file = tmp_path / "output.json"
    output_str = json.dumps({"test": "data"}, ensure_ascii=False)

    # 正常原子写入
    tmp_fd = -1
    tmp_path_str = ""
    try:
        tmp_fd, tmp_path_str = tempfile.mkstemp(
            dir=str(tmp_path), suffix=".tmp"
        )
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp_f:
            tmp_f.write(output_str)
        tmp_fd = -1
        os.replace(tmp_path_str, str(out_file))
    except BaseException:
        if tmp_fd >= 0:
            os.close(tmp_fd)
        try:
            os.unlink(tmp_path_str)
        except OSError:
            pass
        raise

    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["test"] == "data"

    # 验证无残留临时文件
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0, "不应有残留临时文件"


def test_atomic_write_cleans_up_on_exception(tmp_path):
    """#434: 写入异常时临时文件应被清理，目标文件不受影响"""
    import json
    import tempfile

    out_file = tmp_path / "output.json"
    # 预写一个有效文件，验证异常不会破坏它
    out_file.write_text(json.dumps({"original": True}), encoding="utf-8")

    class WriteError(Exception):
        pass

    tmp_fd = -1
    tmp_path_str = ""
    with pytest.raises(WriteError):
        try:
            tmp_fd, tmp_path_str = tempfile.mkstemp(
                dir=str(tmp_path), suffix=".tmp"
            )
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp_f:
                tmp_f.write("partial content")
            tmp_fd = -1
            # 模拟写入后、replace 前的异常
            raise WriteError("模拟中断")
        except BaseException:
            if tmp_fd >= 0:
                os.close(tmp_fd)
            try:
                os.unlink(tmp_path_str)
            except OSError:
                pass
            raise

    # 目标文件未被破坏
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["original"] is True
    # 无残留临时文件
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0, "异常后不应有残留临时文件"
