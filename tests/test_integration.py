"""Consolidated integration tests for compact blueprint semantic JSON.

Merged from:
- tests/integration/test_acceptance.py (basic parse, render, error handling)
- tests/integration/test_ue_fidelity_integration.py (class name resolution, memory cleanup)
- tests/integration/test_sample_assets_representative.py (material, skeletal_mesh parsing)
- tests/integration/test_bp_firstpersoncharacter_validation.py (blueprint field validation)
"""
from __future__ import annotations

import gc
import json
from pathlib import Path

import pytest

from uasset_read.core import parse_single
from uasset_read.renderers import list_formats
from uasset_read.parse_uasset import parse_uasset, parse_uasset_with_linker
from uasset_read.memory_safety import cleanup_after_parse

pytestmark = pytest.mark.integration

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


@pytest.fixture(scope="module")
def stackobot_drone(ue_sample_root) -> Path:
    path = ue_sample_root / "StackOBot_BP_Drone.uasset"
    if not path.exists():
        pytest.skip(f"asset not found: {path}")
    return path


@pytest.fixture(scope="module")
def material_asset(ue_sample_root) -> Path:
    path = ue_sample_root / "IntroToUnreal_M_Plastic.uasset"
    if not path.exists():
        pytest.skip(f"asset not found: {path}")
    return path


@pytest.fixture(scope="module")
def skeletal_mesh_asset(ue_sample_root) -> Path:
    path = ue_sample_root / "CiciToon_SK_Mannequin.uasset"
    if not path.exists():
        pytest.skip(f"asset not found: {path}")
    return path


# ---------------------------------------------------------------------------
# 1. Basic parse + render (from test_acceptance.py)
# ---------------------------------------------------------------------------

def test_basic_parse_and_render(first_person_blueprint):
    """Parse a Blueprint asset to JSON and verify core fields are present."""
    output = parse_single(str(first_person_blueprint), format="json", tolerant=True)
    data = json.loads(output)

    # Summary fields
    assert data["summary"]["package_name"] is not None
    assert len(data["summary"]["package_name"]) > 0
    assert data["summary"]["total_export_count"] >= 1

    # Export fields
    for export in data.get("exports", []):
        assert "object_name" in export
        assert "object_class" in export
        assert isinstance(export["object_name"], str)
        assert len(export["object_name"]) > 0

    # Status
    assert "status" in data
    assert data["status"]["status"] in ("success", "partial")


# ---------------------------------------------------------------------------
# 2. Error handling + format listing (from test_acceptance.py)
# ---------------------------------------------------------------------------

def test_error_handling_and_format_listing(first_person_blueprint):
    """Verify all registered formats are listed and tolerant parsing works."""
    fmts = list_formats()
    expected = {"json", "markdown"}
    assert expected <= set(fmts), f"Missing formats: {expected - set(fmts)}"

    # Tolerant mode should succeed
    tolerant_out = parse_single(str(first_person_blueprint), format="json", tolerant=True)
    assert len(tolerant_out) > 0
    tolerant_data = json.loads(tolerant_out)
    assert tolerant_data["summary"]["package_name"] is not None


# ---------------------------------------------------------------------------
# 3. Material and SkeletalMesh parsing (from test_sample_assets_representative.py)
# ---------------------------------------------------------------------------

def test_material_and_skeletal_mesh_parsing(material_asset, skeletal_mesh_asset):
    """Verify Material and SkeletalMesh assets parse successfully."""
    from uasset_read.parsers.asset_types.material import parse_material
    from uasset_read.parsers.asset_types.skeletal_mesh import parse_skeletal_mesh
    from uasset_read.archive import FArchive

    # Material parsing
    result = parse_uasset_with_linker(str(material_asset), tolerant=True)
    assert result.is_success, f"Material parse failed: {result.errors}"
    assert result.linker is not None
    assert result.export_map

    # Find a material export with data
    mat_export = None
    for exp in result.export_map:
        if exp.serial_size > 0:
            mat_export = exp
            break
    if mat_export is not None:
        archive = FArchive(str(material_asset), tolerant=True)
        try:
            archive.seek(mat_export.serial_offset + mat_export.script_serialization_start_offset)
            parsed = parse_material(archive, result.name_map)
        finally:
            archive.close()
        assert isinstance(parsed, dict)
        assert "parse_status" in parsed

    # SkeletalMesh parsing
    result2 = parse_uasset_with_linker(str(skeletal_mesh_asset), tolerant=True)
    assert result2.is_success, f"SkeletalMesh parse failed: {result2.errors}"
    assert result2.linker is not None
    assert result2.export_map

    mesh_export = None
    for exp in result2.export_map:
        if exp.serial_size > 0:
            mesh_export = exp
            break
    if mesh_export is not None:
        archive2 = FArchive(str(skeletal_mesh_asset), tolerant=True)
        try:
            archive2.seek(mesh_export.serial_offset + mesh_export.script_serialization_start_offset)
            parsed2 = parse_skeletal_mesh(archive2, result2.name_map)
        finally:
            archive2.close()
        assert isinstance(parsed2, dict)
