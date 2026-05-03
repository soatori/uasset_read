"""
Phase 13 Transform Properties Extraction Tests

Tests for EXTR-04 requirement:
- VectorValue/RotatorValue/ScaleValue dataclass construction
- StructValue to specialized value conversion
- Transform extraction from ExportMap component properties
- Precision handling (location 3 decimals, rotation 3 decimals, scale 4 decimals)

Created: 2026-05-03 (Phase 13 Wave 3)
"""

import pytest
import os
import json
from uasset_read import (
    VectorValue,
    RotatorValue,
    ScaleValue,
    StructValue,
    PropertyValue,
    parse_vector_value,
    parse_rotator_value,
    parse_scale_value,
    format_transform_value,
    extract_component_transforms,
    parse_uasset,
)


# Test asset path
FIRST_PERSON_CHARACTER_PATH = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"


def get_test_asset_path():
    """Get available test asset path"""
    if os.path.exists(FIRST_PERSON_CHARACTER_PATH):
        return FIRST_PERSON_CHARACTER_PATH
    return None


class TestTransformValuesConstructor:
    """Test Transform dataclass construction (per 13-01, D-04, D-04a)"""

    def test_vector_value_construct(self):
        """VectorValue should construct with x, y, z floats"""
        v = VectorValue(x=1.0, y=2.0, z=3.0)
        assert v.x == 1.0
        assert v.y == 2.0
        assert v.z == 3.0
        assert v.property_type == "StructProperty"  # inherited

    def test_rotator_value_construct(self):
        """RotatorValue should construct with roll, pitch, yaw, unit"""
        r = RotatorValue(roll=100.0, pitch=200.0, yaw=300.0)
        assert r.roll == 100.0
        assert r.pitch == 200.0
        assert r.yaw == 300.0
        assert r.unit == "degrees"  # default value (per D-02a)

    def test_scale_value_construct(self):
        """ScaleValue should construct with x, y, z floats"""
        s = ScaleValue(x=1.5, y=1.5, z=1.5)
        assert s.x == 1.5
        assert s.y == 1.5
        assert s.z == 1.5

    def test_vector_value_json_serializable(self):
        """VectorValue should be JSON serializable"""
        v = VectorValue(x=1.0, y=2.0, z=3.0)
        data = json.dumps(v.__dict__)
        parsed = json.loads(data)
        assert parsed["x"] == 1.0
        assert parsed["y"] == 2.0
        assert parsed["z"] == 3.0

    def test_rotator_value_json_serializable(self):
        """RotatorValue should be JSON serializable with unit field"""
        r = RotatorValue(roll=100.0, pitch=200.0, yaw=300.0)
        data = json.dumps(r.__dict__)
        parsed = json.loads(data)
        assert parsed["unit"] == "degrees"

    def test_scale_value_json_serializable(self):
        """ScaleValue should be JSON serializable"""
        s = ScaleValue(x=1.5, y=1.5, z=1.5)
        data = json.dumps(s.__dict__)
        parsed = json.loads(data)
        assert parsed["x"] == 1.5
        assert parsed["y"] == 1.5
        assert parsed["z"] == 1.5


class TestStructValueConversion:
    """Test StructValue to specialized value conversion (per 13-02)"""

    def test_parse_vector_value(self):
        """parse_vector_value should convert StructValue to VectorValue"""
        struct_val = StructValue(
            property_type="StructProperty",
            struct_type="Vector",
            fields={"X": 10.0, "Y": 20.0, "Z": 30.0}
        )
        result = parse_vector_value(struct_val)
        assert isinstance(result, VectorValue)
        assert result.x == 10
        assert result.y == 20
        assert result.z == 30

    def test_parse_rotator_value(self):
        """parse_rotator_value should convert StructValue to RotatorValue"""
        struct_val = StructValue(
            property_type="StructProperty",
            struct_type="Rotator",
            fields={"Roll": 100.0, "Pitch": 200.0, "Yaw": 300.0}
        )
        result = parse_rotator_value(struct_val)
        assert isinstance(result, RotatorValue)
        assert result.roll == 100.0
        assert result.pitch == 200.0
        assert result.yaw == 300.0

    def test_parse_scale_value(self):
        """parse_scale_value should convert StructValue to ScaleValue"""
        struct_val = StructValue(
            property_type="StructProperty",
            struct_type="Vector",  # Scale3D uses same struct type
            fields={"X": 1.5, "Y": 1.5, "Z": 1.5}
        )
        result = parse_scale_value(struct_val)
        assert isinstance(result, ScaleValue)
        assert result.x == 1.5
        assert result.y == 1.5
        assert result.z == 1.5

    def test_parse_rotator_value_includes_unit(self):
        """RotatorValue should have unit='degrees' field"""
        struct_val = StructValue(
            property_type="StructProperty",
            struct_type="Rotator",
            fields={"Roll": 0.0, "Pitch": 0.0, "Yaw": 0.0}
        )
        result = parse_rotator_value(struct_val)
        assert result.unit == "degrees"


class TestPrecisionHandling:
    """Test transform precision handling (per 13-01, D-03, D-03a)"""

    def test_format_transform_value_location_integer(self):
        """Location: integer value should output as int"""
        result = format_transform_value(10.0, 'location')
        assert result == 10  # int, not float
        assert isinstance(result, int)

    def test_format_transform_value_location_decimal(self):
        """Location: decimal value should round to 3 decimal places"""
        result = format_transform_value(10.123456, 'location')
        assert result == 10.123  # 3 decimals

    def test_format_transform_value_rotation(self):
        """Rotation: should round to 3 decimal places"""
        result = format_transform_value(1.23456789, 'rotation')
        assert result == 1.235  # 3 decimals

    def test_format_transform_value_scale(self):
        """Scale: should round to 4 decimal places"""
        result = format_transform_value(1.23456789, 'scale')
        assert result == 1.2346  # 4 decimals

    def test_parse_vector_value_precision(self):
        """parse_vector_value should apply location precision"""
        struct_val = StructValue(
            property_type="StructProperty",
            struct_type="Vector",
            fields={"X": 10.0, "Y": 1.2345678, "Z": 100.9999}
        )
        result = parse_vector_value(struct_val)
        assert result.x == 10  # int
        assert result.y == 1.235  # 3 decimals
        assert result.z == 101.0  # rounds to 101.0


class TestComponentTransforms:
    """Test component transform extraction from ExportMap (per 13-02, D-01, D-01a)"""

    def test_extract_component_transforms_empty(self):
        """extract_component_transforms should return empty dict for empty props"""
        result = extract_component_transforms([])
        assert result == {}

    def test_extract_component_transforms_relative_location(self):
        """Should extract RelativeLocation property"""
        props = [
            PropertyValue(
                name="RelativeLocation",
                type="StructProperty",
                value=StructValue(
                    property_type="StructProperty",
                    struct_type="Vector",
                    fields={"X": 100.0, "Y": 200.0, "Z": 0.0}
                )
            )
        ]
        result = extract_component_transforms(props)
        assert "relative_location" in result
        assert result["relative_location"].x == 100

    def test_extract_component_transforms_relative_rotation(self):
        """Should extract RelativeRotation property"""
        props = [
            PropertyValue(
                name="RelativeRotation",
                type="StructProperty",
                value=StructValue(
                    property_type="StructProperty",
                    struct_type="Rotator",
                    fields={"Roll": 0.0, "Pitch": 0.0, "Yaw": 90.0}
                )
            )
        ]
        result = extract_component_transforms(props)
        assert "relative_rotation" in result
        assert result["relative_rotation"].yaw == 90.0

    def test_extract_component_transforms_relative_scale(self):
        """Should extract RelativeScale3D property"""
        props = [
            PropertyValue(
                name="RelativeScale3D",
                type="StructProperty",
                value=StructValue(
                    property_type="StructProperty",
                    struct_type="Vector",
                    fields={"X": 1.5, "Y": 1.5, "Z": 1.5}
                )
            )
        ]
        result = extract_component_transforms(props)
        assert "relative_scale" in result
        assert result["relative_scale"].x == 1.5

    def test_extract_component_transforms_all_three(self):
        """Should extract all three transform properties"""
        props = [
            PropertyValue(
                name="RelativeLocation",
                type="StructProperty",
                value=StructValue(
                    property_type="StructProperty",
                    struct_type="Vector",
                    fields={"X": 100.0, "Y": 200.0, "Z": 0.0}
                )
            ),
            PropertyValue(
                name="RelativeRotation",
                type="StructProperty",
                value=StructValue(
                    property_type="StructProperty",
                    struct_type="Rotator",
                    fields={"Roll": 0.0, "Pitch": 0.0, "Yaw": 90.0}
                )
            ),
            PropertyValue(
                name="RelativeScale3D",
                type="StructProperty",
                value=StructValue(
                    property_type="StructProperty",
                    struct_type="Vector",
                    fields={"X": 1.5, "Y": 1.5, "Z": 1.5}
                )
            )
        ]
        result = extract_component_transforms(props)
        assert len(result) == 3
        assert "relative_location" in result
        assert "relative_rotation" in result
        assert "relative_scale" in result

    def test_extract_component_transforms_ignores_other_properties(self):
        """Should ignore non-transform properties"""
        props = [
            PropertyValue(name="SomeOtherProp", type="IntProperty", value=42),
            PropertyValue(
                name="RelativeLocation",
                type="StructProperty",
                value=StructValue(
                    property_type="StructProperty",
                    struct_type="Vector",
                    fields={"X": 100.0, "Y": 200.0, "Z": 0.0}
                )
            )
        ]
        result = extract_component_transforms(props)
        assert "relative_location" in result
        assert len(result) == 1