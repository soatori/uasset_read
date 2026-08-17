"""Benchmark 2: Memory usage during parsing.

Measures peak RSS for parsing the largest samples. Results are informational.

Marker: benchmark
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from uasset_read import parse_package


# Largest samples by file size (selected at design time)
_LARGE_SAMPLES = [
    "ALS_AnimBP.uasset",
    "ABP_RifleAnimLayers.uasset",
    "ALS_Mannequin_Skeleton.uasset",
]


def _get_rss_mb() -> float:
    """Get current process RSS in MB (Windows/POSIX)."""
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except ImportError:
        # Fallback: use resource module on POSIX
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            return usage.ru_maxrss / 1024  # KB to MB
        except (ImportError, AttributeError):
            return -1.0


@pytest.mark.benchmark
class TestMemoryUsage:
    """Informational: RSS peak during parsing."""

    @pytest.mark.parametrize(
        "filename",
        _LARGE_SAMPLES,
        ids=[s.split(".")[0] for s in _LARGE_SAMPLES],
    )
    def test_parse_memory(self, samples_dir: Path, filename: str):
        """Parse a large sample and report memory delta."""
        sample = samples_dir / filename
        if not sample.exists():
            pytest.skip(f"Sample not found: {filename}")

        before = _get_rss_mb()
        result = parse_package(str(sample), tolerant=True)
        after = _get_rss_mb()

        assert result is not None, f"Failed to parse {filename}"

        if before > 0 and after > 0:
            delta = after - before
            print(f"\n{filename}: RSS delta {delta:.1f} MB "
                  f"(before={before:.1f}, after={after:.1f})")
        else:
            print(f"\n{filename}: RSS measurement unavailable")

    def test_parse_all_rss_baseline(self, samples_dir: Path, sample_uassets: list[Path]):
        """Parse all samples sequentially and report RSS progression."""
        rss_before = _get_rss_mb()
        count = 0
        for sample in sample_uassets:
            parse_package(str(sample), tolerant=True)
            count += 1
        rss_after = _get_rss_mb()

        if rss_before > 0 and rss_after > 0:
            delta = rss_after - rss_before
            print(f"\nAll {count} samples: RSS delta {delta:.1f} MB "
                  f"(before={rss_before:.1f}, after={rss_after:.1f})")
