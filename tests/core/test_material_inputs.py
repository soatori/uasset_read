"""Tests for material input extraction from StructValue."""

from __future__ import annotations

from unittest.mock import MagicMock

from uasset_read.models.properties import StructValue
from uasset_read.ir_builder import _build_material_inputs


def _make_prop(prop_name: str, prop_value):
    """Create a mock property with the given name and value."""
    prop = MagicMock()
    prop.name = prop_name
    prop.value = prop_value
    return prop


def test_material_input_from_struct_value():
    """Material inputs should be extracted from StructValue properties."""
    material_export = MagicMock()
    material_export.properties = [
        _make_prop(
            "BaseColor",
            StructValue(
                struct_type="FColorMaterialInput",
                fields={
                    "expression_index": 2,
                    "output_index": 0,
                    "mask": 0,
                    "mask_r": 0,
                    "mask_g": 0,
                    "mask_b": 0,
                    "mask_a": 0,
                },
            ),
        ),
    ]

    expr_guid_map = {2: "aaaa0000bbbb0000cccc0000dddd0000"}
    inputs = _build_material_inputs(material_export, expr_guid_map)
    assert len(inputs) == 1
    assert inputs[0].input_name == "BaseColor"
    assert inputs[0].source_expression_guid == "aaaa0000bbbb0000cccc0000dddd0000"


def test_material_input_from_dict_still_works():
    """Material inputs should still work from plain dict properties."""
    material_export = MagicMock()
    material_export.properties = [
        _make_prop(
            "Normal",
            {
                "struct_type": "FMaterialInput",
                "fields": {
                    "expression_index": 4,
                    "output_index": 0,
                    "mask": 0,
                    "mask_r": 0,
                    "mask_g": 0,
                    "mask_b": 0,
                    "mask_a": 0,
                },
            },
        ),
    ]

    expr_guid_map = {4: "11110000222200003333000044440000"}
    inputs = _build_material_inputs(material_export, expr_guid_map)
    assert len(inputs) == 1
    assert inputs[0].source_expression_guid == "11110000222200003333000044440000"
