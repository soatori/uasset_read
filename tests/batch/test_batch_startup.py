"""Tests for batch worker startup behavior (#415)."""

import subprocess
import sys


def test_batch_worker_no_runtime_warning():
    """batch worker 启动不应触发 RuntimeWarning"""
    result = subprocess.run(
        [sys.executable, "-m", "uasset_read.batch_worker", "--help"],
        capture_output=True,
        text=True,
    )
    assert "RuntimeWarning" not in result.stderr
