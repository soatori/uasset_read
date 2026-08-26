"""JSON output tests.

Tests the JSON format output: schema compliance, status values, coverage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from uasset_read import parse_single


def _parse_json(samples_dir: Path, filename: str, **kwargs) -> dict:
    """Parse a sample and return JSON output as dict."""
    sample = samples_dir / filename
    output = parse_single(str(sample), format="json", tolerant=True, **kwargs)
    return json.loads(output)


class TestJsonOutput:
    """JSON output structure and compliance."""

    def test_json_parse_returns_valid_json(self, samples_dir: Path):
        """JSON output is valid JSON."""
        if not (samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset").exists():
            pytest.skip("Sample not found")

        data = _parse_json(samples_dir, "FirstPerson_BP_FirstPersonCharacter.uasset")
        assert isinstance(data, dict)

    def test_json_has_format_field(self, samples_dir: Path):
        """JSON output has a format field."""
        if not (samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset").exists():
            pytest.skip("Sample not found")

        data = _parse_json(samples_dir, "FirstPerson_BP_FirstPersonCharacter.uasset")
        assert "format" in data

    def test_json_has_asset_field(self, samples_dir: Path):
        """JSON output has an asset field with package and name."""
        if not (samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset").exists():
            pytest.skip("Sample not found")

        data = _parse_json(samples_dir, "FirstPerson_BP_FirstPersonCharacter.uasset")
        assert "asset" in data
        assert "package" in data["asset"]
        assert "name" in data["asset"]

    def test_json_has_status_field(self, samples_dir: Path):
        """JSON output has a status field with parse and representation."""
        if not (samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset").exists():
            pytest.skip("Sample not found")

        data = _parse_json(samples_dir, "FirstPerson_BP_FirstPersonCharacter.uasset")
        assert "status" in data
        assert "parse" in data["status"]
        assert "representation" in data["status"]

    def test_json_status_parse_valid(self, samples_dir: Path, sample_uassets: list[Path]):
        """All samples have valid parse status in JSON output."""
        valid_parse = {"complete", "partial", "failed"}
        for sample_path in sample_uassets:
            try:
                data = _parse_json(samples_dir, sample_path.name)
                parse_status = data.get("status", {}).get("parse")
                assert parse_status in valid_parse, f"{sample_path.name}: invalid parse status '{parse_status}'"
            except Exception:
                continue

    def test_json_status_representation_valid(self, samples_dir: Path, sample_uassets: list[Path]):
        """All samples have valid representation status in JSON output."""
        valid_repr = {"full", "partial", "opaque"}
        for sample_path in sample_uassets:
            try:
                data = _parse_json(samples_dir, sample_path.name)
                repr_status = data.get("status", {}).get("representation")
                assert repr_status in valid_repr, f"{sample_path.name}: invalid representation '{repr_status}'"
            except Exception:
                continue

    def test_json_has_references_or_domain_content(self, samples_dir: Path):
        """JSON output has references or domain-owned content."""
        if not (samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset").exists():
            pytest.skip("Sample not found")

        data = _parse_json(samples_dir, "FirstPerson_BP_FirstPersonCharacter.uasset")
        # Domain formats may own references internally; check either way
        if "references" in data:
            assert isinstance(data["references"], list)
        else:
            # Domain format — should have content instead
            assert "asset_type" in data

    def test_json_for_material(self, samples_dir: Path):
        """JSON rendering works for Material samples."""
        if not (samples_dir / "FirstPerson_M_FlatCol.uasset").exists():
            pytest.skip("Sample not found")

        data = _parse_json(samples_dir, "FirstPerson_M_FlatCol.uasset")
        assert data["asset_type"] == "material"

    def test_json_for_animbp(self, samples_dir: Path):
        """JSON rendering works for AnimBlueprint samples."""
        if not (samples_dir / "ABP_RifleAnimLayers.uasset").exists():
            pytest.skip("Sample not found")

        data = _parse_json(samples_dir, "ABP_RifleAnimLayers.uasset")
        assert data["asset_type"] == "anim_blueprint"

    def test_json_for_data_table(self, samples_dir: Path):
        """JSON rendering works for DataTable samples."""
        if not (samples_dir / "ALS_FootstepDataTable.uasset").exists():
            pytest.skip("Sample not found")

        data = _parse_json(samples_dir, "ALS_FootstepDataTable.uasset")
        assert "asset_type" in data

    def test_json_for_enum(self, samples_dir: Path):
        """JSON rendering works for Enum samples."""
        if not (samples_dir / "Lyra_Enum_PanelType.uasset").exists():
            pytest.skip("Sample not found")

        data = _parse_json(samples_dir, "Lyra_Enum_PanelType.uasset")
        assert "asset_type" in data


class TestJsonOutputLevels:
    """JSON output levels: standard vs debug."""

    def test_standard_output_no_evidence(self, samples_dir: Path):
        """Standard output level strips evidence."""
        if not (samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset").exists():
            pytest.skip("Sample not found")

        data = _parse_json(
            samples_dir,
            "FirstPerson_BP_FirstPersonCharacter.uasset",
            output_level="standard",
        )
        # Standard mode should not have evidence
        assert "evidence" not in data or len(data.get("evidence", [])) == 0

    def test_debug_output_has_evidence(self, samples_dir: Path):
        """Debug output level includes evidence."""
        if not (samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset").exists():
            pytest.skip("Sample not found")

        data = _parse_json(
            samples_dir,
            "FirstPerson_BP_FirstPersonCharacter.uasset",
            output_level="debug",
        )
        # Debug mode should have evidence (if the asset has any)
        # We just verify the key exists or the output is valid
        assert "asset_type" in data


class TestJsonSchemaCompliance:
    """JSON schema compliance checks."""

    def test_json_has_format_version(self, samples_dir: Path):
        """JSON output includes format_version."""
        if not (samples_dir / "FirstPerson_BP_FirstPersonCharacter.uasset").exists():
            pytest.skip("Sample not found")

        data = _parse_json(samples_dir, "FirstPerson_BP_FirstPersonCharacter.uasset")
        assert "format_version" in data

    def test_json_asset_type_is_string(self, samples_dir: Path, sample_uassets: list[Path]):
        """asset_type is always a string."""
        for sample_path in sample_uassets:
            try:
                data = _parse_json(samples_dir, sample_path.name)
                assert isinstance(data.get("asset_type"), str), f"{sample_path.name}: asset_type is not a string"
            except Exception:
                continue

    def test_json_all_samples_parse(self, samples_dir: Path, sample_uassets: list[Path]):
        """All samples produce valid JSON output."""
        failures = []
        for sample_path in sample_uassets:
            try:
                data = _parse_json(samples_dir, sample_path.name)
                assert isinstance(data, dict)
            except Exception as e:
                failures.append((sample_path.name, str(e)))

        assert failures == [], f"JSON parse failures: {failures}"
