"""Benchmark 5: Semantic extractor coverage.

Measures which semantic extractors (Blueprint, AnimBlueprint, Material)
are hit across all samples. Results are informational.

Marker: benchmark
"""
from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read.pipeline.core import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir
from uasset_read.semantic.builder import build_semantic_ir


@pytest.mark.benchmark
class TestSemanticCoverage:
    """Informational: semantic extractor hit rates."""

    def test_semantic_asset_type_distribution(self, samples_dir: Path, sample_uassets: list[Path]):
        """Build SemanticIR for all samples and report asset type distribution."""
        from collections import Counter

        type_counts: Counter[str] = Counter()
        representation_counts: Counter[str] = Counter()
        format_counts: Counter[str] = Counter()

        for sample in sample_uassets:
            try:
                result = parse_uasset_with_linker(str(sample), tolerant=True)
                if not result or not result.is_success:
                    type_counts["_parse_failed"] += 1
                    continue
                ir = build_package_ir(result)
                semantic = build_semantic_ir(ir, source_path=str(sample))
                type_counts[semantic.asset_type] += 1
                representation_counts[semantic.status.representation] += 1
                format_counts[semantic.format] += 1
            except Exception:
                type_counts["_error"] += 1

        print("\nAsset type distribution:")
        for atype, count in type_counts.most_common():
            print(f"  {atype}: {count}")

        print("\nRepresentation distribution:")
        for rep, count in representation_counts.most_common():
            print(f"  {rep}: {count}")

        print("\nFormat distribution:")
        for fmt, count in format_counts.most_common():
            print(f"  {fmt}: {count}")

    def test_semantic_extractor_classes(self, samples_dir: Path, sample_uassets: list[Path]):
        """Report which UE classes have registered semantic extractors."""
        from uasset_read.semantic.extensions import _REGISTRY

        registered = set(_REGISTRY.keys())
        print(f"\nRegistered extractors ({len(registered)}):")
        for cls in sorted(registered):
            print(f"  {cls}")

    def test_domain_format_usage(self, samples_dir: Path, sample_uassets: list[Path]):
        """Report which domain formats are used across samples."""
        from uasset_read.semantic.extensions import _DOMAIN_FORMATS

        registered = set(_DOMAIN_FORMATS.keys())
        print(f"\nDomain formats ({len(registered)}):")
        for cls in sorted(registered):
            fmt, ver = _DOMAIN_FORMATS[cls]
            print(f"  {cls} -> {fmt} v{ver}")
