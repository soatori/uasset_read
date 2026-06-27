"""Memory policy and monitoring tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.memory_safety import (
    MemoryLimitExceeded,
    MemoryMonitor,
    MemoryPolicy,
    ResourceLimits,
    cleanup_after_parse,
)


@pytest.mark.parametrize(
    ("size_bytes", "rss_limit_mb", "timeout_seconds"),
    [
        (20 * 1024 * 1024, 1024, 120.0),
        (20 * 1024 * 1024 + 1, 2048, 180.0),
        (100 * 1024 * 1024, 2048, 180.0),
        (100 * 1024 * 1024 + 1, 4096, 300.0),
    ],
)
def test_default_policy_uses_file_size_tiers(
    size_bytes: int,
    rss_limit_mb: int,
    timeout_seconds: float,
) -> None:
    limits = MemoryPolicy().limits_for_size(size_bytes)

    assert limits == ResourceLimits(rss_limit_mb, timeout_seconds)


def test_policy_supports_custom_limits() -> None:
    policy = MemoryPolicy(
        small_limits=ResourceLimits(128, 10),
        medium_limits=ResourceLimits(256, 20),
        large_limits=ResourceLimits(512, 30),
        system_usage_limit=0.7,
        poll_interval_seconds=0.25,
    )

    assert policy.limits_for_size(1) == ResourceLimits(128, 10)
    assert policy.limits_for_size(50 * 1024 * 1024) == ResourceLimits(256, 20)
    assert policy.limits_for_size(200 * 1024 * 1024) == ResourceLimits(512, 30)
    assert policy.system_usage_limit == 0.7
    assert policy.poll_interval_seconds == 0.25


def test_memory_policy_types_are_public() -> None:
    from uasset_read import MemoryLimitExceeded as PublicError
    from uasset_read import MemoryPolicy as PublicPolicy
    from uasset_read import ResourceLimits as PublicLimits

    assert PublicPolicy is MemoryPolicy
    assert PublicLimits is ResourceLimits
    assert PublicError is MemoryLimitExceeded


def test_monitor_checkpoint_reports_stage_and_limit() -> None:
    monitor = MemoryMonitor(
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
    assert error.asset_path == "Content\\Test.uasset" or error.asset_path == "Content/Test.uasset"


def test_cleanup_after_parse_runs_one_gc_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr("uasset_read.memory_safety.gc.collect", lambda: calls.append(1))

    cleanup_after_parse()

    assert calls == [1]


def test_pytest_teardown_runs_one_gc_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests import conftest

    calls = []
    monkeypatch.setattr(conftest.gc, "collect", lambda: calls.append(1))

    conftest.pytest_runtest_teardown(None)

    assert calls == [1]
