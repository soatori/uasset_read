"""Tests for Material expression GUID extraction."""
from __future__ import annotations

from unittest.mock import MagicMock

from uasset_read.ir_builder import _extract_expression_guid
from uasset_read.models.properties import StructValue


def test_guid_extraction_from_string_property():
    export = MagicMock()
    prop = MagicMock()
    prop.name = "MaterialExpressionGuid"
    prop.value = "A1B2C3D4E5F6789012345678ABCDEF01"
    export.properties = [prop]

    result = _extract_expression_guid(export)
    assert result is not None
    assert len(result) == 32


def test_guid_extraction_from_struct_value():
    """GUID should be extracted from StructValue with struct_type='Guid'."""
    export = MagicMock()
    prop = MagicMock()
    prop.name = "MaterialExpressionGuid"
    prop.value = StructValue(
        struct_type="Guid",
        fields={"A": 0xA1B2C3D4, "B": 0xE5F67890, "C": 0x12345678, "D": 0xABCDEF01}
    )
    export.properties = [prop]

    result = _extract_expression_guid(export)
    assert result is not None
    assert len(result) == 32
    assert result == "a1b2c3d4e5f6789012345678abcdef01"


def test_guid_extraction_missing_property():
    export = MagicMock()
    export.properties = []

    result = _extract_expression_guid(export)
    assert result is None
