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