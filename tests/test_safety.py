"""Consolidated safety tests — memory policy, error propagation, isolation."""

from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.memory_safety import (
    FileSizeTier,
    MemoryLimitExceeded,
    MemoryPolicy,
    ResourceLimits,
    cleanup_after_parse,
    should_isolate,
)


# ---------------------------------------------------------------------------
# MemoryPolicy / ResourceLimits
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("size_bytes", "rss_limit_mb", "timeout_seconds"),
    [
        (20 * 1024 * 1024, 1024, 120.0),
        (20 * 1024 * 1024 + 1, 2048, 180.0),
        (100 * 1024 * 1024, 2048, 180.0),
        (100 * 1024 * 1024 + 1, 4096, 300.0),
    ],
)
def test_memory_policy_file_size_tiers(
    size_bytes: int,
    rss_limit_mb: int,
    timeout_seconds: float,
) -> None:
    """MemoryPolicy selects correct ResourceLimits based on file size tiers."""
    limits = MemoryPolicy().limits_for_size(size_bytes)
    assert limits == ResourceLimits(rss_limit_mb, timeout_seconds)


def test_memory_limit_exceeded_records_stage() -> None:
    """MemoryLimitExceeded checkpoint reports stage, RSS, limit, and path."""
    monitor = __import__("uasset_read.memory_safety", fromlist=["MemoryMonitor"]).MemoryMonitor(
        asset_path=Path("Content/Test.uasset"),
        limits=ResourceLimits(64, 30),
        rss_reader=lambda _pid=None: 65.5,
    )

    with pytest.raises(MemoryLimitExceeded) as exc_info:
        monitor.checkpoint("export_map")

    error = exc_info.value
    assert error.stage == "export_map"
    assert error.current_rss_mb == 65.5
    assert error.limit_mb == 64


# ---------------------------------------------------------------------------
# Tolerant parse / error deduplication
# ---------------------------------------------------------------------------


def test_tolerant_parse_deduplicates_errors() -> None:
    """tolerant_parse deduplicates repeated ParseError messages."""
    from uasset_read.core.error_handling import tolerant_parse
    from uasset_read.exceptions import ParseError

    class _Result:
        def __init__(self) -> None:
            self.errors: list[str] = []

    result = _Result()

    # First error is recorded
    try:
        with tolerant_parse(result, "stage"):
            raise ParseError("dup error")
    except ParseError:
        pass
    assert len(result.errors) == 1

    # Duplicate error is deduplicated
    try:
        with tolerant_parse(result, "stage"):
            raise ParseError("dup error")
    except ParseError:
        pass
    assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# Worker monitoring / isolation
# ---------------------------------------------------------------------------


class _FakeProcess:
    pid = 123
    exitcode = None

    def __init__(self) -> None:
        self.terminated = False

    def is_alive(self) -> bool:
        return not self.terminated

    def terminate(self) -> None:
        self.terminated = True

    def join(self, timeout: object = None) -> None:
        return None

    def kill(self) -> None:
        self.terminated = True


def test_monitor_terminates_worker_over_rss_limit() -> None:
    """_monitor_worker terminates process when RSS exceeds limit."""
    from uasset_read.batch_worker import _monitor_worker

    process = _FakeProcess()
    outcome = _monitor_worker(
        process=process,
        result_queue=None,
        limits=ResourceLimits(64, 30),
        poll_interval_seconds=0,
        rss_reader=lambda _pid: 65,
        monotonic=lambda: 0,
        sleep=lambda _seconds: None,
    )

    assert process.terminated is True
    assert outcome.succeeded is False
    assert "memory_limit" in outcome.error


# ---------------------------------------------------------------------------
# Hybrid isolation / should_isolate
# ---------------------------------------------------------------------------


def test_should_isolate_respects_file_size_tier() -> None:
    """should_isolate returns correct decision based on file size and tier."""
    assert should_isolate(10 * 1024 * 1024, FileSizeTier.SMALL) is False
    assert should_isolate(200 * 1024 * 1024, FileSizeTier.LARGE) is True
    assert should_isolate(30 * 1024 * 1024, FileSizeTier.MEDIUM) is False
    assert should_isolate(60 * 1024 * 1024, FileSizeTier.MEDIUM) is True
