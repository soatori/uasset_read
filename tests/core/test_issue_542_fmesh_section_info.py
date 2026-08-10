"""Regression test for Issue #542: FMeshSectionInfo fields not recovered in MeshSectionInfoMap.

When parsing StaticMesh assets (e.g. StarterContent_SM_Chair.uasset), the
SectionInfoMap and OriginalSectionInfoMap properties contain TMap<uint32, FMeshSectionInfo>.

The fix resolves two bugs:
1. parse_map_property fallback logic overwrites correct value_type="StructProperty"
   with "IntProperty" because tag.key_type is None (legacy format stores it in tag.inner_type).
2. _apply_property_type_to_tag for MapProperty does not extract value_type_struct from
   the value child's children, so even with correct value_type, the struct type is unknown.

After the fix, the map values are correctly parsed as FMeshSectionInfo structs with
all expected fields (MaterialIndex, bEnableCollision, bCastShadow, etc.).
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
# SectionInfoMap assertions (post-fix behavior)
# ---------------------------------------------------------------------------


class TestSectionInfoMap:
    """Assert the corrected behavior of SectionInfoMap parsing.

    After the fix, the map tag correctly has value_type="StructProperty" and
    the value_type_struct is set to "FMeshSectionInfo" via the registry lookup.
    Each entry value is a dict representing an FMeshSectionInfo struct.
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

    def test_section_info_map_value_type_is_struct(self, static_mesh_export: dict) -> None:
        """Map value_type is 'StructProperty' after fix.

        Bug 1 was that fallback logic overwrote value_type="StructProperty" with
        "IntProperty" because key_type was None (stored in inner_type in legacy format).
        """
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "SectionInfoMap")
        assert prop is not None
        inner_map = prop["value"]["fields"]["Map"]
        assert inner_map["value_type"] == "StructProperty", (
            f"Expected StructProperty, got: {inner_map['value_type']}"
        )

    def test_section_info_map_entry_value_is_struct(self, static_mesh_export: dict) -> None:
        """Each map entry value is a dict (FMeshSectionInfo struct) after fix."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "SectionInfoMap")
        assert prop is not None
        inner_map = prop["value"]["fields"]["Map"]
        entries = inner_map["entries"]
        assert len(entries) > 0

        first_entry = entries[0]
        assert isinstance(first_entry["value"], dict), (
            f"Expected dict (struct), got: {type(first_entry['value']).__name__}: {first_entry['value']}"
        )

    def test_section_info_map_entry_struct_type(self, static_mesh_export: dict) -> None:
        """Entry value struct_type is FMeshSectionInfo."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "SectionInfoMap")
        assert prop is not None
        inner_map = prop["value"]["fields"]["Map"]
        first_entry = inner_map["entries"][0]
        value = first_entry["value"]
        assert "struct_type" in value
        assert value["struct_type"] in ("FMeshSectionInfo", "MeshSectionInfo")

    def test_section_info_map_entry_has_expected_fields(self, static_mesh_export: dict) -> None:
        """FMeshSectionInfo struct has all expected fields."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "SectionInfoMap")
        assert prop is not None
        inner_map = prop["value"]["fields"]["Map"]
        first_entry = inner_map["entries"][0]
        value = first_entry["value"]
        fields = value.get("fields", {})
        expected = {
            "MaterialIndex",
            "bEnableCollision",
            "bCastShadow",
            "bVisibleInRayTracing",
            "bAffectDistanceFieldLighting",
            "bForceOpaque",
        }
        assert set(fields.keys()) == expected, (
            f"Expected fields {expected}, got: {set(fields.keys())}"
        )

    def test_section_info_map_material_index_is_int(self, static_mesh_export: dict) -> None:
        """MaterialIndex field is an int."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "SectionInfoMap")
        assert prop is not None
        inner_map = prop["value"]["fields"]["Map"]
        first_entry = inner_map["entries"][0]
        value = first_entry["value"]
        assert isinstance(value["fields"]["MaterialIndex"], int)

    def test_section_info_map_bools_are_bool(self, static_mesh_export: dict) -> None:
        """Bool fields are Python bool type."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "SectionInfoMap")
        assert prop is not None
        inner_map = prop["value"]["fields"]["Map"]
        first_entry = inner_map["entries"][0]
        value = first_entry["value"]
        for name in ("bEnableCollision", "bCastShadow", "bVisibleInRayTracing",
                      "bAffectDistanceFieldLighting", "bForceOpaque"):
            assert isinstance(value["fields"][name], bool), f"{name} should be bool"


class TestOriginalSectionInfoMap:
    """Same assertions for OriginalSectionInfoMap.

    This property should have the same structure as SectionInfoMap.
    """

    def test_original_section_info_map_exists(self, static_mesh_export: dict) -> None:
        """OriginalSectionInfoMap property must be present."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "OriginalSectionInfoMap")
        assert prop is not None, "OriginalSectionInfoMap property not found"

    def test_original_section_info_map_value_type_is_struct(
        self, static_mesh_export: dict
    ) -> None:
        """OriginalSectionInfoMap map value_type is 'StructProperty' after fix."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "OriginalSectionInfoMap")
        assert prop is not None
        inner_map = prop["value"]["fields"]["Map"]
        assert inner_map["value_type"] == "StructProperty", (
            f"Expected StructProperty, got: {inner_map['value_type']}"
        )

    def test_original_section_info_map_entry_value_is_struct(
        self, static_mesh_export: dict
    ) -> None:
        """OriginalSectionInfoMap entry values are FMeshSectionInfo structs."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "OriginalSectionInfoMap")
        assert prop is not None
        entries = prop["value"]["fields"]["Map"]["entries"]
        assert len(entries) > 0

        first_entry = entries[0]
        assert isinstance(first_entry["value"], dict), (
            f"Expected dict (struct), got: {type(first_entry['value']).__name__}"
        )

    def test_original_section_info_map_entry_has_expected_fields(
        self, static_mesh_export: dict
    ) -> None:
        """OriginalSectionInfoMap FMeshSectionInfo has all expected fields."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "OriginalSectionInfoMap")
        assert prop is not None
        entries = prop["value"]["fields"]["Map"]["entries"]
        first_entry = entries[0]
        value = first_entry["value"]
        fields = value.get("fields", {})
        expected = {
            "MaterialIndex",
            "bEnableCollision",
            "bCastShadow",
            "bVisibleInRayTracing",
            "bAffectDistanceFieldLighting",
            "bForceOpaque",
        }
        assert set(fields.keys()) == expected

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
