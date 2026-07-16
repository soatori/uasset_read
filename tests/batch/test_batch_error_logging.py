"""Tests for batch worker error logging (#414)."""

import logging
import queue
from unittest.mock import MagicMock

import pytest


def test_monitor_worker_logs_stderr_on_empty_result(caplog):
    """When result_queue.get() raises queue.Empty, stderr should be logged."""
    from uasset_read.batch_worker import _monitor_worker
    from uasset_read.memory_safety import ResourceLimits

    # Create a mock process that has already exited
    mock_process = MagicMock()
    mock_process.is_alive.return_value = False
    mock_process.exitcode = 1
    mock_process.pid = 12345
    mock_process.stderr_text = "TestError: something went wrong\n"

    # result_queue.get() will raise queue.Empty
    mock_queue = MagicMock()
    mock_queue.get.side_effect = queue.Empty

    limits = ResourceLimits(timeout_seconds=10, rss_limit_mb=1024)

    with caplog.at_level(logging.ERROR):
        result = _monitor_worker(
            process=mock_process,
            result_queue=mock_queue,
            limits=limits,
            poll_interval_seconds=0.01,
        )

    assert result.succeeded is False
    assert "TestError: something went wrong" in result.error_details
    assert "worker_exit" in result.error
    # Check that stderr was logged
    assert any("TestError: something went wrong" in record.message for record in caplog.records)


def test_monitor_worker_includes_stderr_in_outcome():
    """When result_queue.get() raises queue.Empty, stderr should be in outcome."""
    from uasset_read.batch_worker import _monitor_worker
    from uasset_read.memory_safety import ResourceLimits

    mock_process = MagicMock()
    mock_process.is_alive.return_value = False
    mock_process.exitcode = 1
    mock_process.pid = 12345
    mock_process.stderr_text = "ImportError: No module named 'foo'\n"

    mock_queue = MagicMock()
    mock_queue.get.side_effect = queue.Empty

    limits = ResourceLimits(timeout_seconds=10, rss_limit_mb=1024)

    result = _monitor_worker(
        process=mock_process,
        result_queue=mock_queue,
        limits=limits,
        poll_interval_seconds=0.01,
    )

    assert result.succeeded is False
    assert "ImportError: No module named 'foo'" in result.error_details
