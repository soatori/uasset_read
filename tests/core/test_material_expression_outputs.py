"""Tests for material expression output extraction from StructValue."""

from __future__ import annotations

from unittest.mock import MagicMock

from uasset_read.models.properties import StructValue
from uasset_read.ir_builder import _build_expression_outputs


def _make_outputs_prop(value):
    """Create a MagicMock property named 'Outputs' with the given value list."""
    prop = MagicMock()
    prop.name = "Outputs"
    prop.value = value
    return prop


def test_expression_output_from_struct_value():
    """Expression outputs should be extracted from StructValue list items."""
    expr_export = MagicMock()
    expr_export.properties = [
        _make_outputs_prop(
            [
                StructValue(
                    struct_type="FExpressionOutput",
                    fields={
                        "output_name": "RGB",
                        "mask": 7,
                        "mask_r": 1,
                        "mask_g": 1,
                        "mask_b": 1,
                        "mask_a": 0,
                    },
                ),
            ],
        ),
    ]

    outputs = _build_expression_outputs(expr_export)
    assert len(outputs) == 1
    assert outputs[0].output_name == "RGB"
    assert outputs[0].mask == 7


def test_expression_output_from_dict_still_works():
    """Expression outputs should still work from plain dict list items."""
    expr_export = MagicMock()
    expr_export.properties = [
        _make_outputs_prop(
            [
                {
                    "output_name": "R",
                    "mask": 1,
                    "mask_r": 1,
                    "mask_g": 0,
                    "mask_b": 0,
                    "mask_a": 0,
                },
            ],
        ),
    ]

    outputs = _build_expression_outputs(expr_export)
    assert len(outputs) == 1
    assert outputs[0].output_name == "R"
