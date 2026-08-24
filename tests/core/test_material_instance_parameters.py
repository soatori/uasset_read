"""Tests for MaterialInstance parameter extraction."""

from __future__ import annotations

from unittest.mock import MagicMock

from uasset_read.models.properties import StructValue
from uasset_read.ir_builder import _extract_parameter_values


def test_extract_parameter_values_from_struct_value():
    """Parameters should be extracted from StructValue items."""
    item = StructValue(
        struct_type="ScalarParameterValue",
        fields={
            "ParameterInfo": {"Name": "Opacity", "ExpressionGUID": "abc123"},
            "ParameterValue": 0.5,
        },
    )
    result = _extract_parameter_values([item], "ParameterValue")
    assert len(result) == 1
    assert "Opacity" in result
    assert result["Opacity"]["value"] == 0.5


def test_extract_parameter_values_from_dict():
    """Parameters should still work from plain dict items."""
    item = {
        "ParameterInfo": {"Name": "Roughness", "ExpressionGUID": "def456"},
        "ParameterValue": 0.8,
    }
    result = _extract_parameter_values([item], "ParameterValue")
    assert len(result) == 1
    assert "Roughness" in result
    assert result["Roughness"]["value"] == 0.8


def test_extract_parameter_values_empty_source():
    """Empty source should return empty dict."""
    result = _extract_parameter_values([], "ParameterValue")
    assert result == {}


def test_extract_parameter_values_non_list():
    """Non-list source should return empty dict."""
    result = _extract_parameter_values(None, "ParameterValue")
    assert result == {}
