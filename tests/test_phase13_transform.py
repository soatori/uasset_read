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