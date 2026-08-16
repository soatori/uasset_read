"""Benchmark 3: Export table coverage.

Measures how many exports from the export table were successfully parsed
across all samples. Results are informational.

Marker: benchmark
"""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read import parse_package


@pytest.mark.benchmark
class TestExportCoverage:
    """Informational: export parse coverage across all samples."""

    def test_export_coverage(self, samples_dir: Path, sample_uassets: list[Path]):
        """Parse all samples and report export coverage stats."""
        total_exports = 0
        successful_exports = 0
        failed_exports = 0
        partial_exports = 0
        opaque_exports = 0

        for sample in sample_uassets:
            result = parse_package(str(sample), tolerant=True)
            if result is None or result.export_map is None:
                continue

            for export in result.export_map:
                total_exports += 1
                status = getattr(export, "parse_status", None) or "success"
                if status == "success":
                    successful_exports += 1
                elif status in ("partial", "partial_metadata"):
                    partial_exports += 1
                elif status == "opaque":
                    opaque_exports += 1
                elif status == "failed":
                    failed_exports += 1

        if total_exports == 0:
            pytest.skip("No exports found in any sample")

        success_rate = successful_exports / total_exports * 100
        print(
            f"\nExport coverage: {successful_exports}/{total_exports} "
            f"({success_rate:.1f}% success, "
            f"{partial_exports} partial, "
            f"{opaque_exports} opaque, "
            f"{failed_exports} failed)"
        )

    def test_sample_level_success_rate(self, samples_dir: Path, sample_uassets: list[Path]):
        """Report how many samples parsed successfully vs partially vs failed."""
        success = 0
        partial = 0
        failed = 0

        for sample in sample_uassets:
            result = parse_package(str(sample), tolerant=True)
            status = result.status if result else "failed"
            if status == "success":
                success += 1
            elif status == "partial":
                partial += 1
            else:
                failed += 1

        total = len(sample_uassets)
        print(
            f"\nSample status: {success}/{total} success, "
            f"{partial} partial, {failed} failed"
        )
