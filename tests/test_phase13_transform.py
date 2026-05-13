"""
Phase 13 Transform Properties Extraction Tests

Tests for EXTR-04 requirement:
- Component transform extraction from ExportMap properties
- parse_component_transform function behavior
- Dict return type with correct key names

Updated: 2026-05-12 (Phase 31 Wave 2)
"""

import pytest
import os
from uasset_read import (
    StructValue,
    PropertyValue,
    parse_component_transform,
    parse_uasset,
)


# Test asset path
FIRST_PERSON_CHARACTER_PATH = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"


def get_test_asset_path():
    """Get available test asset path"""
    if os.path.exists(FIRST_PERSON_CHARACTER_PATH):
        return FIRST_PERSON_CHARACTER_PATH
    return None


class TestParseComponentTransform:
    """Test parse_component_transform function (per Phase 31 update)"""

    def test_empty_returns_empty_dict(self):
        """parse_component_transform should return empty dict for empty props"""
        result = parse_component_transform([])
        assert result == {}

    def test_relative_location_returns_dict(self):
        """Should extract RelativeLocation as dict with X/Y/Z keys"""
        props = [
            PropertyValue(
                name="RelativeLocation",
                type="StructProperty",
                value=StructValue(
                    struct_type="Vector",
                    fields={"X": 100.0, "Y": 200.0, "Z": 0.0}
                )
            )
        ]
        result = parse_component_transform(props)
        assert "relative_location" in result
        assert result["relative_location"]["X"] == 100.0
        assert result["relative_location"]["Y"] == 200.0
        assert result["relative_location"]["Z"] == 0.0

    def test_relative_rotation_returns_dict(self):
        """Should extract RelativeRotation as dict with Pitch/Yaw/Roll keys"""
        props = [
            PropertyValue(
                name="RelativeRotation",
                type="StructProperty",
                value=StructValue(
                    struct_type="Rotator",
                    fields={"Roll": 0.0, "Pitch": 0.0, "Yaw": 90.0}
                )
            )
        ]
        result = parse_component_transform(props)
        assert "relative_rotation" in result
        assert result["relative_rotation"]["Pitch"] == 0.0
        assert result["relative_rotation"]["Yaw"] == 90.0
        assert result["relative_rotation"]["Roll"] == 0.0

    def test_relative_scale3d_returns_dict(self):
        """Should extract RelativeScale3D as dict with X/Y/Z keys (note: 'relative_scale3d' key)"""
        props = [
            PropertyValue(
                name="RelativeScale3D",
                type="StructProperty",
                value=StructValue(
                    struct_type="Vector",
                    fields={"X": 1.5, "Y": 1.5, "Z": 1.5}
                )
            )
        ]
        result = parse_component_transform(props)
        assert "relative_scale3d" in result  # Note: 'relative_scale3d' not 'relative_scale'
        assert result["relative_scale3d"]["X"] == 1.5
        assert result["relative_scale3d"]["Y"] == 1.5
        assert result["relative_scale3d"]["Z"] == 1.5

    def test_all_three_transforms(self):
        """Should extract all three transform properties"""
        props = [
            PropertyValue(
                name="RelativeLocation",
                type="StructProperty",
                value=StructValue(
                    struct_type="Vector",
                    fields={"X": 100.0, "Y": 200.0, "Z": 0.0}
                )
            ),
            PropertyValue(
                name="RelativeRotation",
                type="StructProperty",
                value=StructValue(
                    struct_type="Rotator",
                    fields={"Roll": 0.0, "Pitch": 0.0, "Yaw": 90.0}
                )
            ),
            PropertyValue(
                name="RelativeScale3D",
                type="StructProperty",
                value=StructValue(
                    struct_type="Vector",
                    fields={"X": 1.5, "Y": 1.5, "Z": 1.5}
                )
            )
        ]
        result = parse_component_transform(props)
        assert len(result) == 3
        assert "relative_location" in result
        assert "relative_rotation" in result
        assert "relative_scale3d" in result

    def test_ignores_non_transform_properties(self):
        """Should ignore non-transform properties"""
        props = [
            PropertyValue(name="SomeOtherProp", type="IntProperty", value=42),
            PropertyValue(
                name="RelativeLocation",
                type="StructProperty",
                value=StructValue(
                    struct_type="Vector",
                    fields={"X": 100.0, "Y": 200.0, "Z": 0.0}
                )
            )
        ]
        result = parse_component_transform(props)
        assert "relative_location" in result
        assert len(result) == 1

    def test_mobility_extraction(self):
        """Should extract Mobility property if present"""
        props = [
            PropertyValue(
                name="Mobility",
                type="EnumProperty",
                value={"value": "Movable"}
            )
        ]
        result = parse_component_transform(props)
        assert "mobility" in result
        assert result["mobility"] == "Movable"


class TestIntegration:
    """Integration tests with actual UAsset files"""

    def test_parse_uasset_has_transforms_attribute(self):
        """parse_uasset should provide export.transforms attribute (accessible per EXTR-04)"""
        if not os.path.exists(FIRST_PERSON_CHARACTER_PATH):
            pytest.skip("Test asset not available")

        result = parse_uasset(FIRST_PERSON_CHARACTER_PATH)

        # Verify transforms attribute is accessible on all exports (per D-01a)
        for exp in result.export_map:
            assert hasattr(exp, 'transforms'), f"Export {exp.object_name} should have transforms attribute"
            assert isinstance(exp.transforms, dict), f"transforms should be a dict"

    def test_transforms_have_expected_fields(self):
        """Extracted transforms should have expected dict keys"""
        if not os.path.exists(FIRST_PERSON_CHARACTER_PATH):
            pytest.skip("Test asset not available")

        result = parse_uasset(FIRST_PERSON_CHARACTER_PATH)

        for exp in result.export_map:
            if hasattr(exp, 'transforms') and exp.transforms:
                if "relative_location" in exp.transforms:
                    loc = exp.transforms["relative_location"]
                    assert isinstance(loc, dict), "relative_location should be a dict"
                    assert "X" in loc
                    assert "Y" in loc
                    assert "Z" in loc
                if "relative_rotation" in exp.transforms:
                    rot = exp.transforms["relative_rotation"]
                    assert isinstance(rot, dict), "relative_rotation should be a dict"
                    assert "Pitch" in rot
                    assert "Yaw" in rot
                    assert "Roll" in rot
                if "relative_scale3d" in exp.transforms:
                    scale = exp.transforms["relative_scale3d"]
                    assert isinstance(scale, dict), "relative_scale3d should be a dict"
                    assert "X" in scale
                    assert "Y" in scale
                    assert "Z" in scale