from __future__ import annotations

from uasset_read.batch_worker import BatchWorkerOutcome, _monitor_worker
from uasset_read.memory_safety import ResourceLimits


class _HangingProcess:
    pid = 4321

    def __init__(self) -> None:
        self._alive = True
        self.terminate_calls = 0
        self.join_timeouts: list[float | None] = []

    def is_alive(self) -> bool:
        return self._alive

    def terminate(self) -> None:
        self.terminate_calls += 1
        self._alive = False

    def join(self, timeout: float | None = None) -> None:
        self.join_timeouts.append(timeout)


class _ExitedProcess:
    pid = 4322
    exitcode = 0

    def __init__(self) -> None:
        self.join_timeouts: list[float | None] = []

    def is_alive(self) -> bool:
        return False

    def join(self, timeout: float | None = None) -> None:
        self.join_timeouts.append(timeout)


class _ResultQueue:
    def __init__(self, outcome: BatchWorkerOutcome) -> None:
        self.outcome = outcome
        self.timeouts: list[float] = []

    def get(self, timeout: float) -> BatchWorkerOutcome:
        self.timeouts.append(timeout)
        return self.outcome


def test_monitor_worker_terminates_at_the_configured_timeout() -> None:
    process = _HangingProcess()
    clock_values = iter((10.0, 12.0))

    outcome = _monitor_worker(
        process=process,
        result_queue=None,
        limits=ResourceLimits(rss_limit_mb=1024, timeout_seconds=2.0),
        poll_interval_seconds=0.1,
        rss_reader=lambda _pid: (_ for _ in ()).throw(AssertionError("RSS must not be read at the deadline")),
        monotonic=lambda: next(clock_values),
        sleep=lambda _seconds: (_ for _ in ()).throw(AssertionError("must not sleep past the deadline")),
    )

    assert not outcome.succeeded
    assert outcome.error == "timeout: 2.0s > 2.0s"
    assert process.terminate_calls == 1
    assert process.join_timeouts == [5]


def test_monitor_worker_returns_result_after_clean_worker_exit() -> None:
    process = _ExitedProcess()
    expected = BatchWorkerOutcome(True, "output.json")
    results = _ResultQueue(expected)

    outcome = _monitor_worker(
        process=process,
        result_queue=results,
        limits=ResourceLimits(rss_limit_mb=1024, timeout_seconds=2.0),
        poll_interval_seconds=0.1,
        rss_reader=lambda _pid: (_ for _ in ()).throw(AssertionError("RSS must not be read after worker exit")),
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: (_ for _ in ()).throw(AssertionError("must not sleep after worker exit")),
    )

    assert outcome == expected
    assert process.join_timeouts == [1]
    assert results.timeouts == [1]
