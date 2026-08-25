"""Tests for material parent resolution with PackageIndex wrapping."""

from __future__ import annotations

from unittest.mock import MagicMock

from uasset_read.models.properties import StructValue
from uasset_read.ir_builder import _resolve_material_parent


def test_parent_from_raw_int_wraps_package_index():
    """Raw int parent value should be wrapped in PackageIndex before resolution."""
    material_export = MagicMock()
    prop = MagicMock()
    prop.name = "Parent"
    prop.value = 7
    material_export.properties = [prop]

    result = MagicMock()
    # Mock linker that accepts PackageIndex objects
    mock_ref = MagicMock()
    mock_ref.get_full_name.return_value = "/Game/Materials/BaseMaterial"
    result.linker = MagicMock()
    result.linker.resolve_package_index.return_value = mock_ref

    path = _resolve_material_parent(material_export, result)
    assert path == "/Game/Materials/BaseMaterial"


def test_parent_from_struct_value():
    """StructValue parent should be resolved via _get_fields."""
    material_export = MagicMock()
    prop = MagicMock()
    prop.name = "Parent"
    prop.value = StructValue(
        struct_type="ObjectProperty",
        fields={"object_name": "/Game/Materials/ParentMat"},
    )
    material_export.properties = [prop]

    result = MagicMock()
    result.linker = None

    path = _resolve_material_parent(material_export, result)
    assert path == "/Game/Materials/ParentMat"


def test_parent_from_string():
    """String parent value should be returned directly."""
    material_export = MagicMock()
    prop = MagicMock()
    prop.name = "Parent"
    prop.value = "/Game/Materials/Simple"
    material_export.properties = [prop]

    result = MagicMock()
    result.linker = None

    path = _resolve_material_parent(material_export, result)
    assert path == "/Game/Materials/Simple"
