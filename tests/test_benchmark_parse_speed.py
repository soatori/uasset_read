"""Benchmark 1: Parse speed per asset category.

Measures wall-clock time for parsing representative samples from each
asset category. Results are informational only (no pass/fail thresholds).

Marker: benchmark
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from uasset_read import parse_package


# Representative samples per category (small set to keep benchmark fast)
_BENCHMARK_SAMPLES = {
    "blueprint": "FirstPerson_BP_FirstPersonCharacter.uasset",
    "anim_blueprint": "ABP_RifleAnimLayers.uasset",
    "material": "FirstPerson_M_FlatCol.uasset",
    "skeleton": "ALS_Mannequin_Skeleton.uasset",
    "data_table": "ALS_FootstepDataTable.uasset",
    "static_mesh": "StarterContent_SM_Chair.uasset",
    "texture": "FirstPerson_T_GridChecker_A.uasset",
}


@pytest.mark.benchmark
class TestParseSpeed:
    """Informational: parse time per asset category."""

    @pytest.mark.parametrize(
        "category,filename",
        list(_BENCHMARK_SAMPLES.items()),
        ids=list(_BENCHMARK_SAMPLES.keys()),
    )
    def test_parse_time(self, samples_dir: Path, category: str, filename: str):
        """Parse a single sample and report elapsed time."""
        sample = samples_dir / filename
        if not sample.exists():
            pytest.skip(f"Sample not found: {filename}")

        start = time.perf_counter()
        result = parse_package(str(sample), tolerant=True)
        elapsed = time.perf_counter() - start

        # Report (no assertion on speed — informational only)
        assert result is not None, f"Failed to parse {filename}"
        # Attach timing info for reporting
        print(f"\n{category}: {elapsed:.3f}s ({sample.stat().st_size / 1024:.0f} KB)")

    def test_parse_all_samples_total_time(self, samples_dir: Path, sample_uassets: list[Path]):
        """Parse all samples and report total time (informational)."""
        start = time.perf_counter()
        failures = 0
        for sample in sample_uassets:
            try:
                result = parse_package(str(sample), tolerant=True)
                if result is None:
                    failures += 1
            except Exception:
                failures += 1
        elapsed = time.perf_counter() - start

        total = len(sample_uassets)
        print(f"\nTotal: {elapsed:.1f}s for {total} samples "
              f"({elapsed / total:.2f}s avg, {failures} failures)")
