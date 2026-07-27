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
