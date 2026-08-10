"""Regression test for Issue #542: FMeshSectionInfo fields not recovered in MeshSectionInfoMap.

When parsing StaticMesh assets (e.g. StarterContent_SM_Chair.uasset), the
SectionInfoMap and OriginalSectionInfoMap properties contain TMap<int, FMeshSectionInfo>.
Currently the map values resolve to plain IntProperty (opaque int 77) instead of
FMeshSectionInfo structs with fields like MaterialIndex, bEnableCollision, bCastShadow.

This test captures the current (broken) behavior so the fix can be verified by
changing the assertions to reflect the target behavior.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from uasset_read.core import parse_single

LOCAL_SAMPLES = Path(__file__).resolve().parents[2] / "tests" / "samples"
CHAIR_ASSET = LOCAL_SAMPLES / "StarterContent_SM_Chair.uasset"


def _parse_chair_json() -> dict:
    """Parse the chair asset and return parsed JSON as a dict."""
    output = parse_single(str(CHAIR_ASSET), format="json", tolerant=True)
    return json.loads(output)


def _find_static_mesh_export(data: dict) -> dict | None:
    """Find the SM_Chair StaticMesh export in parsed JSON."""
    for exp in data.get("exports", []):
        if exp.get("object_name") == "SM_Chair":
            return exp
    return None


def _find_property(properties: list[dict], name: str) -> dict | None:
    """Find a property by name in a property list."""
    for prop in properties:
        if prop.get("name") == name:
            return prop
    return None


@pytest.fixture(scope="module")
def chair_data() -> dict:
    """Module-scoped fixture: parsed JSON of StarterContent_SM_Chair.uasset."""
    if not CHAIR_ASSET.exists():
        pytest.skip(f"Sample asset not found: {CHAIR_ASSET}")
    return _parse_chair_json()


@pytest.fixture(scope="module")
def static_mesh_export(chair_data: dict) -> dict:
    """Module-scoped fixture: the SM_Chair export dict."""
    exp = _find_static_mesh_export(chair_data)
    if exp is None:
        pytest.fail("SM_Chair export not found in parsed output")
    return exp


# ---------------------------------------------------------------------------
# Current (broken) behavior assertions
# ---------------------------------------------------------------------------


class TestSectionInfoMapCurrentBehavior:
    """Assert the CURRENT broken behavior of SectionInfoMap parsing.

    The map values are currently parsed as plain integers (IntProperty) instead
    of FMeshSectionInfo structs. These tests document the defect so the fix
    can be verified by flipping the assertions.
    """

    def test_section_info_map_exists(self, static_mesh_export: dict) -> None:
        """SectionInfoMap property must be present in StaticMesh exports."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "SectionInfoMap")
        assert prop is not None, "SectionInfoMap property not found"

    def test_section_info_map_is_struct_property(self, static_mesh_export: dict) -> None:
        """SectionInfoMap must be a StructProperty wrapping MeshSectionInfoMap."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "SectionInfoMap")
        assert prop is not None
        assert prop["type"] == "StructProperty"
        value = prop["value"]
        assert value["struct_type"] == "MeshSectionInfoMap"

    def test_section_info_map_has_map_field(self, static_mesh_export: dict) -> None:
        """MeshSectionInfoMap struct must contain a 'Map' field."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "SectionInfoMap")
        assert prop is not None
        fields = prop["value"]["fields"]
        assert "Map" in fields, f"Expected 'Map' field, got: {list(fields.keys())}"

    def test_section_info_map_has_entries(self, static_mesh_export: dict) -> None:
        """The inner map must have at least one entry."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "SectionInfoMap")
        assert prop is not None
        inner_map = prop["value"]["fields"]["Map"]
        assert len(inner_map["entries"]) > 0, "Map has no entries"

    def test_section_info_map_value_type_is_int(self, static_mesh_export: dict) -> None:
        """BROKEN: Map value_type is 'IntProperty' instead of a struct type.

        TARGET: value_type should be 'StructProperty' (or similar) representing
        FMeshSectionInfo, with each entry value being a dict containing fields:
        MaterialIndex (int), bEnableCollision (bool), bCastShadow (bool),
        bVisibleInRayTracing (bool), bAffectDistanceFieldLighting (bool),
        bForceOpaque (bool).
        """
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "SectionInfoMap")
        assert prop is not None
        inner_map = prop["value"]["fields"]["Map"]

        # --- Current broken behavior: value_type is IntProperty ---
        assert inner_map["value_type"] == "IntProperty", (
            f"Expected IntProperty (broken), got: {inner_map['value_type']}"
        )

        # --- TARGET (uncomment after fix): ---
        # assert inner_map["value_type"] == "StructProperty", (
        #     f"Expected StructProperty (FMeshSectionInfo), got: {inner_map['value_type']}"
        # )

    def test_section_info_map_entry_value_is_int(self, static_mesh_export: dict) -> None:
        """BROKEN: Each map entry value is a plain int (e.g. 77) instead of a struct.

        TARGET: Each entry value should be a dict (struct) with fields:
        - MaterialIndex: int (e.g. 0)
        - bEnableCollision: bool (default True)
        - bCastShadow: bool (default True)
        - bVisibleInRayTracing: bool (default True)
        - bAffectDistanceFieldLighting: bool (default True)
        - bForceOpaque: bool (default False)
        """
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "SectionInfoMap")
        assert prop is not None
        inner_map = prop["value"]["fields"]["Map"]
        entries = inner_map["entries"]
        assert len(entries) > 0

        first_entry = entries[0]
        # --- Current broken behavior: value is an int ---
        assert isinstance(first_entry["value"], int), (
            f"Expected int (broken), got: {type(first_entry['value']).__name__}: {first_entry['value']}"
        )

        # --- TARGET (uncomment after fix): ---
        # value = first_entry["value"]
        # assert isinstance(value, dict), f"Expected dict (struct), got: {type(value).__name__}"
        # assert "MaterialIndex" in value, f"Missing MaterialIndex in: {list(value.keys())}"
        # assert isinstance(value["MaterialIndex"], int)


class TestOriginalSectionInfoMapCurrentBehavior:
    """Same assertions for OriginalSectionInfoMap.

    This property should have the same broken behavior as SectionInfoMap.
    """

    def test_original_section_info_map_exists(self, static_mesh_export: dict) -> None:
        """OriginalSectionInfoMap property must be present."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "OriginalSectionInfoMap")
        assert prop is not None, "OriginalSectionInfoMap property not found"

    def test_original_section_info_map_value_type_is_int(
        self, static_mesh_export: dict
    ) -> None:
        """BROKEN: OriginalSectionInfoMap map value_type is 'IntProperty'."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "OriginalSectionInfoMap")
        assert prop is not None
        inner_map = prop["value"]["fields"]["Map"]

        # --- Current broken behavior ---
        assert inner_map["value_type"] == "IntProperty", (
            f"Expected IntProperty (broken), got: {inner_map['value_type']}"
        )

    def test_original_section_info_map_entry_value_is_int(
        self, static_mesh_export: dict
    ) -> None:
        """BROKEN: OriginalSectionInfoMap entry values are plain ints."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "OriginalSectionInfoMap")
        assert prop is not None
        entries = prop["value"]["fields"]["Map"]["entries"]
        assert len(entries) > 0

        first_entry = entries[0]
        # --- Current broken behavior ---
        assert isinstance(first_entry["value"], int), (
            f"Expected int (broken), got: {type(first_entry['value']).__name__}"
        )

    def test_section_and_original_have_same_structure(
        self, static_mesh_export: dict
    ) -> None:
        """Both maps should have identical structure (same key/value types)."""
        props = static_mesh_export.get("properties", [])
        sec = _find_property(props, "SectionInfoMap")
        orig = _find_property(props, "OriginalSectionInfoMap")
        assert sec is not None
        assert orig is not None

        sec_map = sec["value"]["fields"]["Map"]
        orig_map = orig["value"]["fields"]["Map"]
        assert sec_map["key_type"] == orig_map["key_type"]
        assert sec_map["value_type"] == orig_map["value_type"]
