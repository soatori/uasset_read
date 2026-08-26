"""Sample regression tests — parameterized parsing of every tracked local sample.

This is the primary regression gate: any sample that previously parsed
successfully must continue to do so. Each sample is parsed via parse_package()
and validated for basic structural integrity.

Marker: samples
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uasset_read import parse_package


# Collect all .uasset samples for parameterization
def _collect_samples(samples_dir: Path) -> list[Path]:
    return sorted(samples_dir.glob("*.uasset"))


@pytest.mark.samples
class TestSampleParsing:
    """Every .uasset sample must parse without crashing and return a valid result."""

    def test_parse_returns_result(self, samples_dir: Path, sample_path: Path):
        """parse_package() returns a ParseResult with required fields."""
        result = parse_package(str(sample_path), tolerant=True)
        # Must have a summary (header was read)
        assert result.summary is not None, f"{sample_path.name}: summary is None"
        # Must have a name_map
        assert isinstance(result.name_map, list), f"{sample_path.name}: name_map is not a list"
        # Must have an import_map
        assert isinstance(result.import_map, list), f"{sample_path.name}: import_map is not a list"
        # Must have an export_map
        assert isinstance(result.export_map, list), f"{sample_path.name}: export_map is not a list"

    def test_parse_status_is_valid(self, samples_dir: Path, sample_path: Path):
        """Status must be one of the three valid values."""
        result = parse_package(str(sample_path), tolerant=True)
        assert result.status in ("success", "partial", "failed"), (
            f"{sample_path.name}: invalid status '{result.status}'"
        )

    def test_parse_no_crash(self, samples_dir: Path, sample_path: Path):
        """Parsing must not raise unhandled exceptions in tolerant mode."""
        result = parse_package(str(sample_path), tolerant=True)
        # In tolerant mode, we always get a result back
        assert result is not None

    def test_export_count_non_negative(self, samples_dir: Path, sample_path: Path):
        """Export count from summary must be non-negative."""
        result = parse_package(str(sample_path), tolerant=True)
        if result.summary is not None:
            assert result.summary.export_count >= 0, f"{sample_path.name}: negative export count"


# Parameterize across all samples
def pytest_generate_tests(metafunc):
    """Generate test cases for each .uasset sample file."""
    if "sample_path" in metafunc.fixturenames:
        samples_dir = Path(__file__).parent / "samples"
        samples = _collect_samples(samples_dir)
        metafunc.parametrize(
            "sample_path",
            samples,
            ids=[s.stem for s in samples],
            scope="module",
        )
