"""Test JSON schema consistency — required fields always present."""

import json
from pathlib import Path

import pytest

from uasset_read import parse_single


def test_all_samples_have_references_and_diagnostics():
    """All output files should include references and diagnostics fields.

    Blueprint format omits the references table by design; only asset_semantic
    samples are checked for references.  Blueprint samples may also lack
    diagnostics (opaque blueprints include coverage instead), so skip both
    checks for that format.
    """
    samples_dir = Path(__file__).resolve().parent.parent / "samples"
    samples = list(sorted(samples_dir.glob("*.uasset")))
    if not samples:
        pytest.skip("no samples available")
    for sample in samples:
        output = parse_single(str(sample), format="json", tolerant=True)
        data = json.loads(output)
        is_blueprint = data.get("format") == "uasset_read.blueprint_semantic"
        if is_blueprint:
            # Blueprint format omits references by design and may omit diagnostics
            continue
        assert "references" in data, f"{sample.name}: missing references"
        assert "diagnostics" in data, f"{sample.name}: missing diagnostics"
        assert isinstance(data["references"], list), f"{sample.name}: references not list"
        assert isinstance(data["diagnostics"], list), f"{sample.name}: diagnostics not list"


def test_all_samples_have_asset_info():
    """All output files should include asset info with required fields."""
    samples_dir = Path(__file__).resolve().parent.parent / "samples"
    samples = list(sorted(samples_dir.glob("*.uasset")))
    if not samples:
        pytest.skip("no samples available")
    for sample in samples:
        output = parse_single(str(sample), format="json", tolerant=True)
        data = json.loads(output)
        assert "asset" in data, f"{sample.name}: missing asset"
        asset = data["asset"]
        assert "package" in asset, f"{sample.name}: missing asset.package"
        assert "name" in asset, f"{sample.name}: missing asset.name"


def test_all_samples_have_status():
    """All output files should include status with parse and representation."""
    samples_dir = Path(__file__).resolve().parent.parent / "samples"
    samples = list(sorted(samples_dir.glob("*.uasset")))
    if not samples:
        pytest.skip("no samples available")
    for sample in samples:
        output = parse_single(str(sample), format="json", tolerant=True)
        data = json.loads(output)
        assert "status" in data, f"{sample.name}: missing status"
        status = data["status"]
        assert "parse" in status, f"{sample.name}: missing status.parse"
        assert "representation" in status, f"{sample.name}: missing status.representation"
        assert status["parse"] in ("complete", "partial", "failed"), f"{sample.name}: invalid status.parse"


def test_all_samples_have_format():
    """All output files should include format and format_version."""
    samples_dir = Path(__file__).resolve().parent.parent / "samples"
    samples = list(sorted(samples_dir.glob("*.uasset")))
    if not samples:
        pytest.skip("no samples available")
    for sample in samples:
        output = parse_single(str(sample), format="json", tolerant=True)
        data = json.loads(output)
        assert "format" in data, f"{sample.name}: missing format"
        assert "format_version" in data, f"{sample.name}: missing format_version"
        valid_formats = {"uasset_read.asset_semantic", "uasset_read.blueprint_semantic"}
        assert data["format"] in valid_formats, f"{sample.name}: wrong format {data['format']!r}"
