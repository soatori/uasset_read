"""Regression tests for memory safety guards.

Covers:
- MemoryPolicy tier selection based on file size
- MemoryMonitor checkpoint raising MemoryLimitExceeded
- cleanup_after_parse hook
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from uasset_read.memory_safety import (
    MemoryPolicy,
    MemoryMonitor,
    ResourceLimits,
    MemoryLimitExceeded,
    cleanup_after_parse,
)


# ---------------------------------------------------------------------------
# Test: MemoryPolicy tier selection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "size_bytes,expected_limits_attr",
    [
        (0, "small_limits"),
        (1024, "small_limits"),
        (20 * 1024 * 1024, "small_limits"),                    # exactly 20MB
        (20 * 1024 * 1024 + 1, "medium_limits"),               # just above 20MB
        (50 * 1024 * 1024, "medium_limits"),                    # 50MB
        (100 * 1024 * 1024, "medium_limits"),                   # exactly 100MB
        (100 * 1024 * 1024 + 1, "large_limits"),               # just above 100MB
        (200 * 1024 * 1024, "large_limits"),                    # 200MB
    ],
    ids=[
        "zero_bytes",
        "1KB",
        "exactly_20MB",
        "20MB_plus_1",
        "50MB",
        "exactly_100MB",
        "100MB_plus_1",
        "200MB",
    ],
)
def test_default_policy_uses_file_size_tiers(size_bytes, expected_limits_attr):
    """MemoryPolicy.limits_for_size() returns the correct tier for each boundary."""
    policy = MemoryPolicy()
    result = policy.limits_for_size(size_bytes)
    expected = getattr(policy, expected_limits_attr)
    assert result == expected


# ---------------------------------------------------------------------------
# Test: MemoryMonitor checkpoint raises on limit exceeded
# ---------------------------------------------------------------------------

def test_monitor_checkpoint_raises_when_rss_exceeds_limit():
    """MemoryMonitor.checkpoint() must raise MemoryLimitExceeded when RSS > limit."""
    limits = ResourceLimits(rss_limit_mb=100.0, timeout_seconds=60.0)
    # rss_reader always returns 200.0 MB, which exceeds the 100 MB limit
    monitor = MemoryMonitor(
        asset_path="test.uasset",
        limits=limits,
        rss_reader=lambda pid: 200.0,
    )

    with pytest.raises(MemoryLimitExceeded) as exc_info:
        monitor.checkpoint("test_stage")

    exc = exc_info.value
    assert exc.stage == "test_stage"
    assert exc.limit_mb == 100.0
    assert exc.current_rss_mb == 200.0
    assert exc.asset_path == "test.uasset"


def test_monitor_checkpoint_succeeds_when_within_limit():
    """MemoryMonitor.checkpoint() returns RSS value when within limit."""
    limits = ResourceLimits(rss_limit_mb=100.0, timeout_seconds=60.0)
    monitor = MemoryMonitor(
        asset_path="test.uasset",
        limits=limits,
        rss_reader=lambda pid: 50.0,
    )

    result = monitor.checkpoint("test_stage")
    assert result == 50.0


# ---------------------------------------------------------------------------
# Test: cleanup_after_parse
# ---------------------------------------------------------------------------

def test_cleanup_after_parse_runs_gc():
    """cleanup_after_parse() must invoke gc.collect() without error."""
    with patch("uasset_read.memory_safety.gc.collect") as mock_gc:
        cleanup_after_parse()
        mock_gc.assert_called_once()
