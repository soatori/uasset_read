"""Batch 摘要测试"""
import logging
from unittest.mock import patch

from uasset_read.core import BatchResult, _log_batch_summary


def test_batch_summary_includes_timing():
    """验证 batch 摘要包含耗时信息"""
    result = BatchResult(total=10)
    result.success = ["a.json", "b.json"]
    result.failed = [("c.json", "error", "")]

    with patch.object(logging.getLogger("uasset_read.core"), "info") as mock_info:
        _log_batch_summary(result, elapsed_seconds=12.3)
        mock_info.assert_called_once()
        call_args_str = str(mock_info.call_args)
        assert "elapsed" in call_args_str
        assert "12.3" in call_args_str


def test_batch_summary_default_elapsed():
    """验证不传 elapsed_seconds 时默认为 0"""
    result = BatchResult(total=5)
    result.success = ["a.json"]

    with patch.object(logging.getLogger("uasset_read.core"), "info") as mock_info:
        _log_batch_summary(result)
        args = mock_info.call_args[0]
        # 格式字符串包含 elapsed，最后一个参数是默认的 0.0
        assert "elapsed" in args[0]
        assert args[-1] == 0.0


def test_batch_summary_counts():
    """验证摘要中各计数正确"""
    result = BatchResult(total=6)
    result.success = ["a.json", "b.json", "c.json"]
    result.partial = ["b.json"]
    result.skipped = [("d.json", "memory limit")]
    result.failed = [("e.json", "parse error", ""), ("f.json", "timeout", "")]

    with patch.object(logging.getLogger("uasset_read.core"), "info") as mock_info:
        _log_batch_summary(result, elapsed_seconds=5.0)
        mock_info.assert_called_once()
        args, kwargs = mock_info.call_args
        # 格式字符串 + 6 个参数（total, success, partial, skipped, failed, elapsed）
        assert args[1] == 6    # total
        assert args[2] == 3    # success
        assert args[3] == 1    # partial
        assert args[4] == 1    # skipped
        assert args[5] == 2    # failed
        assert args[6] == 5.0  # elapsed
