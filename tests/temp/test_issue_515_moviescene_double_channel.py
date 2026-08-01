"""Test for Issue #515: MovieSceneDoubleChannel parsing.

This is a red test that expects parsed fields for MovieSceneDoubleChannel.
The test should fail until the parser is implemented.
"""

from __future__ import annotations

import json
from pathlib import Path

from uasset_read import parse_single


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "samples" / "Lyra_SEQ_LobbyScreen_LevelSequence.uasset"


def test_moviescene_double_channel_has_fields():
    """MovieSceneDoubleChannel should have parsed fields, not be opaque."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    # Find a MovieSceneDoubleChannel property
    found = False
    for export in payload["exports"]:
        for prop in export.get("properties", []):
            if prop.get("type") == "StructProperty":
                value = prop.get("value", {})
                if isinstance(value, dict) and value.get("struct_type") == "MovieSceneDoubleChannel":
                    # This should fail until parser is implemented
                    assert value.get("parse_status") != "opaque", \
                        f"MovieSceneDoubleChannel is still opaque: {value}"
                    assert "fields" in value and len(value["fields"]) > 0, \
                        f"MovieSceneDoubleChannel has no fields: {value}"
                    found = True
                    break
        if found:
            break

    assert found, "No MovieSceneDoubleChannel found in test asset"


def test_moviescene_double_channel_keyframe_count():
    """MovieSceneDoubleChannel should expose keyframe count."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    for export in payload["exports"]:
        for prop in export.get("properties", []):
            if prop.get("type") == "StructProperty":
                value = prop.get("value", {})
                if isinstance(value, dict) and value.get("struct_type") == "MovieSceneDoubleChannel":
                    fields = value.get("fields", {})
                    # Should have keyframe_count or similar field
                    assert "keyframe_count" in fields or "num_keys" in fields, \
                        f"MovieSceneDoubleChannel missing keyframe count: {fields}"
                    return  # Test one instance

    pytest.skip("No MovieSceneDoubleChannel found")


def test_moviescene_double_channel_values():
    """MovieSceneDoubleChannel should expose keyframe values."""
    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    for export in payload["exports"]:
        for prop in export.get("properties", []):
            if prop.get("type") == "StructProperty":
                value = prop.get("value", {})
                if isinstance(value, dict) and value.get("struct_type") == "MovieSceneDoubleChannel":
                    fields = value.get("fields", {})
                    # Should have values or keyframes field
                    assert "values" in fields or "keyframes" in fields, \
                        f"MovieSceneDoubleChannel missing values: {fields}"
                    return  # Test one instance

    pytest.skip("No MovieSceneDoubleChannel found")
