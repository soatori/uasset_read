"""Test JSON schema consistency — required fields always present."""

import json
from pathlib import Path

import pytest

from uasset_read import parse_single


def test_all_samples_have_import_map_and_name_map():
    """All output files should include import_map and name_map fields."""
    samples_dir = Path(__file__).resolve().parent.parent / "samples"
    samples = list(sorted(samples_dir.glob("*.uasset")))
    if not samples:
        pytest.skip("no samples available")
    for sample in samples:
        output = parse_single(str(sample), format="json", tolerant=True)
        data = json.loads(output)
        assert "import_map" in data, f"{sample.name}: missing import_map"
        assert "name_map" in data, f"{sample.name}: missing name_map"
        assert isinstance(data["import_map"], list), f"{sample.name}: import_map not list"
        assert isinstance(data["name_map"], list), f"{sample.name}: name_map not list"


def test_all_samples_have_warnings_and_diagnostics():
    """All output files should include warnings and diagnostics (even if empty)."""
    samples_dir = Path(__file__).resolve().parent.parent / "samples"
    samples = list(sorted(samples_dir.glob("*.uasset")))
    if not samples:
        pytest.skip("no samples available")
    for sample in samples:
        output = parse_single(str(sample), format="json", tolerant=True)
        data = json.loads(output)
        assert "warnings" in data, f"{sample.name}: missing warnings"
        assert "diagnostics" in data, f"{sample.name}: missing diagnostics"
        assert isinstance(data["warnings"], list), f"{sample.name}: warnings not list"
        assert isinstance(data["diagnostics"], list), f"{sample.name}: diagnostics not list"


def test_summary_enriched_fields():
    """Summary should include total_properties and total_name_entries."""
    sample = Path(__file__).resolve().parent.parent / "samples" / "FirstPerson_BP_FirstPersonCharacter.uasset"
    if not sample.exists():
        pytest.skip("sample not available")
    output = parse_single(str(sample), format="json", tolerant=True)
    data = json.loads(output)
    summary = data["summary"]
    assert "total_properties" in summary, "Missing total_properties"
    assert "total_name_entries" in summary, "Missing total_name_entries"
    assert summary["total_name_entries"] > 0, "name_map should not be empty"
