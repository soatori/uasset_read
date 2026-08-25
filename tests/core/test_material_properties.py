"""Tests for material property extraction."""

from __future__ import annotations

from unittest.mock import MagicMock

from uasset_read.models.properties import EnumValue
from uasset_read.ir_builder import _build_material_properties


def _make_prop(name: str, value):
    """Create a MagicMock property with correct name/value attributes."""
    prop = MagicMock()
    prop.name = name
    prop.value = value
    return prop


def test_blend_mode_from_enum_value():
    """BlendMode from EnumValue should resolve correctly."""
    material_export = MagicMock()
    material_export.properties = [
        _make_prop(
            "BlendMode",
            EnumValue(value_name="EBlendMode::BLEND_Masked", enum_type="EBlendMode"),
        ),
        _make_prop("MaterialDomain", 1),
        _make_prop("ShadingModel", 1),
    ]

    props = _build_material_properties(material_export)
    assert props["blend_mode"] == "Masked"
