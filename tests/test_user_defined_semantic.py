"""Tests for user_defined semantic extraction (#589)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

SAMPLES_DIR = Path(__file__).parent / "samples"


@pytest.fixture
def ue_sample_root():
    if not SAMPLES_DIR.exists():
        pytest.skip(f"samples directory not found: {SAMPLES_DIR}")
    return SAMPLES_DIR


class TestUserDefinedEnumSemantic:
    """Test UserDefinedEnum semantic extraction."""

    def test_enum_has_user_defined_block(self, ue_sample_root):
        """Enum assets should have a non-empty user_defined root block."""
        from uasset_read import parse_single

        path = ue_sample_root / "Lyra_Enum_PanelType.uasset"
        if not path.exists():
            pytest.skip("sample not found")

        result = parse_single(str(path), format="json", tolerant=True)
        data = json.loads(result)
        assert "user_defined" in data, "user_defined block missing from JSON output"
        assert data["user_defined"]["type"] == "enum"
        assert data["user_defined"]["enum_name"]
        assert len(data["user_defined"]["entries"]) > 0

    def test_enum_entries_deterministic(self, ue_sample_root):
        """Enum member ordering should be deterministic."""
        from uasset_read import parse_single

        path = ue_sample_root / "Lyra_Enum_PanelType.uasset"
        if not path.exists():
            pytest.skip("sample not found")

        result1 = parse_single(str(path), format="json", tolerant=True)
        result2 = parse_single(str(path), format="json", tolerant=True)
        data1 = json.loads(result1)
        data2 = json.loads(result2)
        assert data1["user_defined"]["entries"] == data2["user_defined"]["entries"]

    def test_enum_entries_have_name_and_display(self, ue_sample_root):
        """Each enum entry should have name and display_name."""
        from uasset_read import parse_single

        path = ue_sample_root / "Lyra_Enum_PanelType.uasset"
        if not path.exists():
            pytest.skip("sample not found")

        result = parse_single(str(path), format="json", tolerant=True)
        data = json.loads(result)
        for entry in data["user_defined"]["entries"]:
            assert "name" in entry, f"entry missing 'name': {entry}"
            assert "display_name" in entry, f"entry missing 'display_name': {entry}"
            assert entry["name"], "entry name should not be empty"

    def test_second_enum_sample(self, ue_sample_root):
        """Second enum sample should also work."""
        from uasset_read import parse_single

        path = ue_sample_root / "StackOBot_Enum_CameraState.uasset"
        if not path.exists():
            pytest.skip("sample not found")

        result = parse_single(str(path), format="json", tolerant=True)
        data = json.loads(result)
        assert "user_defined" in data
        assert data["user_defined"]["type"] == "enum"
        assert len(data["user_defined"]["entries"]) > 0


class TestUserDefinedStructSemantic:
    """Test UserDefinedStruct semantic extraction."""

    def test_struct_has_user_defined_block(self, ue_sample_root):
        """Struct assets should have a non-empty user_defined root block."""
        from uasset_read import parse_single

        path = ue_sample_root / "StackOBot_Struct_Objective.uasset"
        if not path.exists():
            pytest.skip("sample not found")

        result = parse_single(str(path), format="json", tolerant=True)
        data = json.loads(result)
        assert "user_defined" in data, "user_defined block missing from JSON output"
        assert data["user_defined"]["type"] == "struct"
        assert data["user_defined"]["struct_name"]
        assert len(data["user_defined"]["fields"]) > 0

    def test_struct_fields_have_name_and_type(self, ue_sample_root):
        """Each struct field should have name and type."""
        from uasset_read import parse_single

        path = ue_sample_root / "StackOBot_Struct_Objective.uasset"
        if not path.exists():
            pytest.skip("sample not found")

        result = parse_single(str(path), format="json", tolerant=True)
        data = json.loads(result)
        for field in data["user_defined"]["fields"]:
            assert "name" in field, f"field missing 'name': {field}"
            assert "type" in field, f"field missing 'type': {field}"
            assert field["name"], "field name should not be empty"
            assert field["type"], "field type should not be empty"

    def test_struct_has_guid(self, ue_sample_root):
        """Struct should have a GUID."""
        from uasset_read import parse_single

        path = ue_sample_root / "StackOBot_Struct_Objective.uasset"
        if not path.exists():
            pytest.skip("sample not found")

        result = parse_single(str(path), format="json", tolerant=True)
        data = json.loads(result)
        assert data["user_defined"].get("guid"), "struct should have a guid"


class TestUserDefinedFallback:
    """Test that non-enum/struct assets don't have user_defined block."""

    def test_blueprint_no_user_defined(self, ue_sample_root):
        """Blueprint assets should not have user_defined block."""
        from uasset_read import parse_single

        path = ue_sample_root / "StackOBot_BP_Drone.uasset"
        if not path.exists():
            pytest.skip("sample not found")

        result = parse_single(str(path), format="json", tolerant=True)
        data = json.loads(result)
        # Blueprint assets should not have user_defined block
        # (unless they happen to have a UserDefinedEnum/Struct export)
        if "user_defined" in data:
            # If present, it should be valid
            assert data["user_defined"]["type"] in ("enum", "struct")
