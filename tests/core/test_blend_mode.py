"""Tests for Material blend_mode decoding."""

from __future__ import annotations

from unittest.mock import MagicMock

from uasset_read.constants import BLEND_MODE_MAP


def test_blend_mode_masked_not_opaque():
    """Masked blend mode (1) must not map to Opaque (0)."""
    masked = BLEND_MODE_MAP.get(1)
    opaque = BLEND_MODE_MAP.get(0)

    assert masked is not None, "Masked (1) not in BLEND_MODE_MAP"
    assert opaque is not None, "Opaque (0) not in BLEND_MODE_MAP"
    assert masked != opaque, "Masked and Opaque must be different values"
    assert masked.lower() == "masked", f"Expected 'Masked', got '{masked}'"
    assert opaque.lower() == "opaque", f"Expected 'Opaque', got '{opaque}'"


def test_blend_mode_all_values_unique():
    """All blend mode values must be unique strings."""
    values = list(BLEND_MODE_MAP.values())
    assert len(values) == len(set(values)), f"Duplicate values found: {values}"


def test_blend_mode_from_enum_dict():
    """BlendMode should be decoded from enum dict format."""
    from uasset_read.ir_builder import _build_material_properties

    export = MagicMock()
    prop = MagicMock()
    prop.name = "BlendMode"
    prop.value = {"enum_type": "EBlendMode", "value_name": "EBlendMode::BLEND_Masked"}
    export.properties = [prop]

    result = _build_material_properties(export)
    assert result.get("blend_mode") == "Masked"
