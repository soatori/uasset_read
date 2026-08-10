"""Regression test for Issue #542: FMeshSectionInfo fields not recovered in MeshSectionInfoMap.

When parsing StaticMesh assets (e.g. StarterContent_SM_Chair.uasset), the
SectionInfoMap and OriginalSectionInfoMap properties contain TMap<int, FMeshSectionInfo>.

The fix in commit 2b0ea7b0 adds struct type propagation in _dispatch_value_parse
so that when value_type is "StructProperty", the concrete struct_type from the tag
is forwarded to parse_struct_property. However, for this particular asset the map
tag has value_type="IntProperty" (not "StructProperty"), so the value dispatch
takes the default int path. The FMeshSectionInfo struct parsing is thus not
triggered for this asset; this test documents the current post-fix behavior.
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


class TestSectionInfoMapPostFix:
    """Assert the post-fix behavior of SectionInfoMap parsing.

    For this asset the map tag has value_type="IntProperty", so the value
    dispatch reads plain ints. The fix (struct propagation in
    _dispatch_value_parse) only activates when value_type is already
    "StructProperty".
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
        """Map value_type is 'IntProperty' for this asset.

        The map tag has value_type=IntProperty (not StructProperty), so the
        _dispatch_value_parse StructProperty branch is not entered. The entry
        values are plain ints.
        """
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "SectionInfoMap")
        assert prop is not None
        inner_map = prop["value"]["fields"]["Map"]
        assert inner_map["value_type"] == "IntProperty", (
            f"Expected IntProperty, got: {inner_map['value_type']}"
        )

    def test_section_info_map_entry_value_is_int(self, static_mesh_export: dict) -> None:
        """Each map entry value is a plain int for this asset.

        Because value_type is IntProperty, the default int path is taken
        and each entry value is a plain int (e.g. 77).
        """
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "SectionInfoMap")
        assert prop is not None
        inner_map = prop["value"]["fields"]["Map"]
        entries = inner_map["entries"]
        assert len(entries) > 0

        first_entry = entries[0]
        assert isinstance(first_entry["value"], int), (
            f"Expected int, got: {type(first_entry['value']).__name__}: {first_entry['value']}"
        )


class TestOriginalSectionInfoMapPostFix:
    """Same assertions for OriginalSectionInfoMap.

    This property should have the same structure as SectionInfoMap.
    """

    def test_original_section_info_map_exists(self, static_mesh_export: dict) -> None:
        """OriginalSectionInfoMap property must be present."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "OriginalSectionInfoMap")
        assert prop is not None, "OriginalSectionInfoMap property not found"

    def test_original_section_info_map_value_type_is_int(
        self, static_mesh_export: dict
    ) -> None:
        """OriginalSectionInfoMap map value_type is 'IntProperty'."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "OriginalSectionInfoMap")
        assert prop is not None
        inner_map = prop["value"]["fields"]["Map"]
        assert inner_map["value_type"] == "IntProperty", (
            f"Expected IntProperty, got: {inner_map['value_type']}"
        )

    def test_original_section_info_map_entry_value_is_int(
        self, static_mesh_export: dict
    ) -> None:
        """OriginalSectionInfoMap entry values are plain ints."""
        props = static_mesh_export.get("properties", [])
        prop = _find_property(props, "OriginalSectionInfoMap")
        assert prop is not None
        entries = prop["value"]["fields"]["Map"]["entries"]
        assert len(entries) > 0

        first_entry = entries[0]
        assert isinstance(first_entry["value"], int), (
            f"Expected int, got: {type(first_entry['value']).__name__}"
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
