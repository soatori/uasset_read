"""Shared fixtures and reporting for the minimal test suite."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
import tracemalloc

import pytest


TESTS_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = TESTS_DIR / "samples"
BLUEPRINT_SAMPLE_NAME = "FirstPerson_BP_FirstPersonCharacter.uasset"


@dataclass(frozen=True)
class BenchmarkResult:
    """One informational benchmark measurement."""

    name: str
    elapsed_seconds: float
    peak_python_bytes: int


Measure = Callable[[str], AbstractContextManager[None]]
_BENCHMARK_RESULTS: list[BenchmarkResult] = []


@pytest.fixture(scope="session")
def samples_dir() -> Path:
    """Return the tracked local sample directory."""
    if not SAMPLES_DIR.is_dir():
        pytest.fail(f"Sample directory is missing: {SAMPLES_DIR}")
    return SAMPLES_DIR


@pytest.fixture(scope="session")
def blueprint_sample(samples_dir: Path) -> Path:
    """Return the representative Blueprint used by all benchmarks."""
    sample = samples_dir / BLUEPRINT_SAMPLE_NAME
    if not sample.is_file():
        pytest.fail(f"Benchmark sample is missing: {sample}")
    return sample


@pytest.fixture
def measure() -> Measure:
    """Measure elapsed time and peak Python allocations without thresholds."""

    @contextmanager
    def _measure(name: str):
        already_tracing = tracemalloc.is_tracing()
        if not already_tracing:
            tracemalloc.start()
        tracemalloc.reset_peak()
        started = perf_counter()
        try:
            yield
        finally:
            elapsed = perf_counter() - started
            _, peak = tracemalloc.get_traced_memory()
            if not already_tracing:
                tracemalloc.stop()
            _BENCHMARK_RESULTS.append(
                BenchmarkResult(
                    name=name,
                    elapsed_seconds=elapsed,
                    peak_python_bytes=peak,
                )
            )

    return _measure


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    """Print the informational benchmark measurements at session end."""
    if not _BENCHMARK_RESULTS:
        return

    terminalreporter.section("benchmark metrics")
    for result in _BENCHMARK_RESULTS:
        peak_mib = result.peak_python_bytes / (1024 * 1024)
        terminalreporter.write_line(
            f"{result.name}: {result.elapsed_seconds:.3f}s, "
            f"peak_python={peak_mib:.2f} MiB"
        )
