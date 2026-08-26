"""Benchmark 4: Property type coverage.

Measures how many distinct property types were encountered across all samples.
Results are informational.

Marker: benchmark
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read import parse_package


@pytest.mark.benchmark
class TestPropertyCoverage:
    """Informational: property type diversity across all samples."""

    def test_property_type_coverage(self, samples_dir: Path, sample_uassets: list[Path]):
        """Parse all samples and report distinct property types found."""
        seen_types: set[str] = set()
        total_properties = 0

        for sample in sample_uassets:
            result = parse_package(str(sample), tolerant=True)
            if result is None or result.export_map is None:
                continue

            for export in result.export_map:
                props = getattr(export, "properties", None) or []
                for prop in props:
                    total_properties += 1
                    prop_type = getattr(prop, "type", None)
                    if prop_type:
                        seen_types.add(str(prop_type))

        print(f"\nProperty coverage: {len(seen_types)} distinct types across {total_properties} total properties")
        if seen_types:
            sorted_types = sorted(seen_types)
            print(f"Types: {', '.join(sorted_types[:30])}")
            if len(sorted_types) > 30:
                print(f"  ... and {len(sorted_types) - 30} more")

    def test_name_map_diversity(self, samples_dir: Path, sample_uassets: list[Path]):
        """Report name map size distribution across samples."""
        sizes = []
        for sample in sample_uassets:
            result = parse_package(str(sample), tolerant=True)
            if result and result.name_map:
                sizes.append((sample.name, len(result.name_map)))

        if not sizes:
            pytest.skip("No name maps found")

        sizes.sort(key=lambda x: x[1], reverse=True)
        total = sum(s for _, s in sizes)
        avg = total / len(sizes)
        print(f"\nName map: avg={avg:.0f}, max={sizes[0][1]}, min={sizes[-1][1]}")
        print(f"Top 5: {', '.join(f'{n}({s})' for n, s in sizes[:5])}")
