# tests/temp/test_resolved_references.py
"""Test resolved references in ObjectProperty values."""

import json
from pathlib import Path

import pytest

from uasset_read import parse_single


def test_object_property_has_resolved_name():
    """ObjectProperty values should include resolved_name when name_map available."""
    sample = Path(__file__).resolve().parent.parent / "samples" / "FirstPerson_BP_FirstPersonCharacter.uasset"
    if not sample.exists():
        pytest.skip("sample not available")
    output = parse_single(str(sample), format="json", tolerant=True)
    data = json.loads(output)
    found_object_property = False
    for export in data["exports"]:
        for prop in export.get("properties", []):
            if prop.get("type") == "ObjectProperty" and isinstance(prop.get("value"), dict):
                val = prop["value"]
                found_object_property = True
                # Should have object_name
                assert "object_name" in val
                # If object_name is a numeric index, resolved_name should be present
                obj_name = val.get("object_name", "")
                if obj_name and obj_name.lstrip("-").isdigit():
                    assert "resolved_name" in val, f"Missing resolved_name for index {obj_name}"
    assert found_object_property, "No ObjectProperty found in exports"
