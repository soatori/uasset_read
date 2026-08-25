"""Tests for material expression input extraction from StructValue."""

from __future__ import annotations

from unittest.mock import MagicMock

from uasset_read.models.properties import StructValue
from uasset_read.ir_builder import _build_single_expression_ir


def _make_prop(prop_name: str, prop_value):
    """Create a mock property with the given name and value."""
    prop = MagicMock()
    prop.name = prop_name
    prop.value = prop_value
    return prop


def test_expression_input_from_struct_value():
    """Expression inputs should be extracted from StructValue properties."""
    expr_export = MagicMock()
    expr_export.properties = [
        _make_prop(
            "BaseColor",
            StructValue(
                struct_type="FExpressionInput",
                fields={
                    "expression_index": 5,
                    "output_index": 0,
                    "mask": 0,
                    "mask_r": 0,
                    "mask_g": 0,
                    "mask_b": 0,
                    "mask_a": 0,
                },
            ),
        ),
        _make_prop("MaterialExpressionEditorX", 100),
        _make_prop("MaterialExpressionEditorY", 200),
    ]
    expr_export.object_class = "MaterialExpressionTextureSample"
    expr_export.class_index = MagicMock()

    expr_guid_map = {5: "aaaa0000bbbb0000cccc0000dddd0000"}

    result = MagicMock()
    result.import_map = []
    result.export_map = []

    ir = _build_single_expression_ir(0, expr_export, expr_guid_map, result)
    assert len(ir.inputs) == 1
    assert ir.inputs[0].input_name == "BaseColor"
    assert ir.inputs[0].source_expression_guid == "aaaa0000bbbb0000cccc0000dddd0000"


def test_expression_input_from_dict_still_works():
    """Expression inputs should still work from plain dict properties."""
    expr_export = MagicMock()
    expr_export.properties = [
        _make_prop(
            "BaseColor",
            {
                "struct_type": "FExpressionInput",
                "fields": {
                    "expression_index": 3,
                    "output_index": 1,
                    "mask": 0,
                    "mask_r": 0,
                    "mask_g": 0,
                    "mask_b": 0,
                    "mask_a": 0,
                },
            },
        ),
        _make_prop("MaterialExpressionEditorX", 0),
        _make_prop("MaterialExpressionEditorY", 0),
    ]
    expr_export.object_class = "MaterialExpressionConstant"
    expr_export.class_index = MagicMock()

    expr_guid_map = {3: "11110000222200003333000044440000"}

    result = MagicMock()
    result.import_map = []
    result.export_map = []

    ir = _build_single_expression_ir(0, expr_export, expr_guid_map, result)
    assert len(ir.inputs) == 1
    assert ir.inputs[0].source_expression_guid == "11110000222200003333000044440000"
