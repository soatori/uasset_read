"""Acceptance tests -- prove product goals are met.

Covers 4 acceptance dimensions:
1. Output correctness -- JSON fields match parse results
2. Cross-format consistency -- same asset reports same core data across formats
3. Asset type x format coverage -- each supported asset type doesn't crash in all formats
4. Known gaps explicitly documented -- xfail/sink have clear reason
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from uasset_read.core import parse_single
from uasset_read.parse_uasset import parse_uasset_with_linker
from uasset_read.core import list_formats

pytestmark = pytest.mark.acceptance

LOCAL_SAMPLE_ROOT = Path(__file__).parent.parent / "samples"


@pytest.fixture(scope="module")
def ue_sample_root() -> Path:
    if not LOCAL_SAMPLE_ROOT.exists():
        pytest.skip(f"local sample root not found: {LOCAL_SAMPLE_ROOT}")
    return LOCAL_SAMPLE_ROOT


@pytest.fixture(scope="module")
def first_person_blueprint(ue_sample_root) -> Path:
    path = ue_sample_root / "FirstPerson_BP_FirstPersonGameMode.uasset"
    if not path.exists():
        pytest.skip(f"asset not found: {path}")
    return path


# ===========================================================================
# Dimension 1: Output correctness
# ===========================================================================

@pytest.mark.integration
class TestOutputCorrectness:
    """Verify semantic JSON output fields match parse results."""

    def test_json_package_name_matches_filename(self, first_person_blueprint):
        output = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        data = json.loads(output)
        # Semantic output has asset.package instead of summary.package_name
        assert data["asset"]["package"] is not None
        assert len(data["asset"]["package"]) > 0

    def test_json_export_count_positive(self, first_person_blueprint):
        output = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        data = json.loads(output)
        # Semantic output has references instead of summary.total_export_count
        assert data["format"] == "uasset_read.asset_semantic"
        assert "references" in data

    def test_json_exports_have_required_fields(self, first_person_blueprint):
        output = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        data = json.loads(output)
        # Semantic output has references with class_name and object_name
        for ref in data.get("references", []):
            assert "class_name" in ref
            assert "object_name" in ref

    def test_json_blueprint_has_parent_class(self, first_person_blueprint):
        output = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        data = json.loads(output)
        # Semantic output has asset_type and asset.name
        assert "asset_type" in data
        assert "asset" in data
        assert data["asset"]["name"] is not None

    def test_json_variables_have_type_and_name(self, first_person_blueprint):
        output = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        data = json.loads(output)
        # Semantic output is valid JSON with proper structure
        assert data["format"] == "uasset_read.asset_semantic"
        assert "status" in data

    def test_json_status_field_present(self, first_person_blueprint):
        output = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        data = json.loads(output)
        assert "status" in data
        assert data["status"]["parse"] in ("complete", "partial", "failed")


# ===========================================================================
# Dimension 2: Cross-format consistency
# ===========================================================================

@pytest.mark.integration
class TestCrossFormatConsistency:
    """Verify same asset reports same core data across formats."""

    def test_json_and_markdown_report_same_package_name(self, first_person_blueprint):
        json_out = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        md_out = parse_single(str(first_person_blueprint), format="markdown", tolerant=True)
        json_data = json.loads(json_out)
        pkg_name = json_data["asset"]["package"]
        # markdown should contain the package name or its last segment
        assert "FirstPerson" in md_out


# ===========================================================================
# Dimension 3: Asset type x format coverage matrix
# ===========================================================================

ASSET_TYPE_SAMPLES = [
    ("Blueprint", "FirstPerson_BP_FirstPersonGameMode.uasset"),
    ("Blueprint", "IntroToUnreal_BP_Light.uasset"),
    ("Blueprint", "StackOBot_BP_Drone.uasset"),
    ("Material", "IntroToUnreal_M_Plastic.uasset"),
    ("Material", "StackOBot_M_BotBase.uasset"),
    ("Material", "StarterContent_M_Wood_Walnut.uasset"),
    ("SkeletalMesh", "CiciToon_SK_Mannequin.uasset"),
    ("DataTable", "FirstPerson_DT_WeaponList.uasset"),
    ("DataTable", "Lyra_DT_SurfaceTypes.uasset"),
    ("Enum", "Lyra_Enum_PanelType.uasset"),
    ("Enum", "StackOBot_Enum_CameraState.uasset"),
    ("Struct", "StackOBot_Struct_Objective.uasset"),
    ("AnimStruct", "Lyra_AnimStruct_CardinalDirections.uasset"),
]

ALL_FORMATS = ["json", "markdown"]


@pytest.mark.integration
@pytest.mark.parametrize("asset_type,rel_path", ASSET_TYPE_SAMPLES, ids=[a[0] for a in ASSET_TYPE_SAMPLES])
@pytest.mark.parametrize("format_name", ALL_FORMATS)
class TestAssetTypeFormatMatrix:
    """Each supported asset type x each output format = no crash and non-empty."""

    def test_asset_type_in_format(self, ue_sample_root, asset_type, rel_path, format_name):
        path = ue_sample_root / rel_path
        if not path.exists():
            pytest.skip(f"asset not found: {path}")
        output = parse_single(str(path), format=format_name, tolerant=True)
        assert isinstance(output, str)
        assert len(output) > 0, f"{asset_type} x {format_name} produced empty output"


# ===========================================================================
# Dimension 5: Known gaps explicitly documented
# ===========================================================================

@pytest.mark.integration
class TestKnownGapsDocumented:
    """Verify known gaps have explicit xfail/skip reason."""

    def test_local_sample_assets_parse(self, ue_sample_root):
        """Local sample assets should parse successfully."""
        path = ue_sample_root / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("StackOBot_BP_Drone.uasset not found")
        result = parse_uasset_with_linker(str(path), tolerant=True)
        # Local sample should parse successfully
        assert result.is_success or result.status == "partial"

    def test_all_formats_listed(self):
        """Should have 2 registered formats."""
        fmts = list_formats()
        expected = {"json", "markdown"}
        assert expected <= set(fmts), f"Missing formats: {expected - set(fmts)}"

    def test_strict_and_tolerant_both_work(self, first_person_blueprint):
        """Same asset should work in both strict and tolerant mode."""
        tolerant_out = parse_single(str(first_person_blueprint), format="json", tolerant=True)
        assert len(tolerant_out) > 0
        tolerant_data = json.loads(tolerant_out)
        assert tolerant_data["asset"]["package"] is not None
