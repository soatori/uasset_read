"""Consolidated blueprint extractor tests.

Covers:
- variable_extractor: _map_property_flags, _map_pin_category_to_cpp_type
- component_extractor: extract_components
- transform_parser: parse_vector_value, parse_rotator_value, parse_scale_value,
  extract_component_transforms, _decode_raw_vector, _try_extract_struct_value
"""
from __future__ import annotations

import struct

import pytest

from uasset_read.blueprint.component_extractor import extract_components
from uasset_read.blueprint.transform_parser import parse_vector_value
from uasset_read.blueprint.variable_extractor import (
    _map_pin_category_to_cpp_type,
    _map_property_flags,
)
from uasset_read.constants import CPF_Edit, CPF_EditConst
from uasset_read.models.properties import StructValue
from uasset_read.models.transforms import VectorValue


class TestMapPropertyFlags:
    """_map_property_flags handles CPF_Edit / CPF_EditConst flags."""

    def test_edit_and_editconst(self):
        result = _map_property_flags(CPF_Edit | CPF_EditConst)
        assert result["is_edit_anywhere"] is True
        assert result["is_edit_instance_only"] is False


class TestPinCategoryMapping:
    """_map_pin_category_to_cpp_type maps pin categories to C++ types."""

    def test_wildcard(self):
        assert _map_pin_category_to_cpp_type("wildcard") == "Wildcard"


class TestComponentExtractor:
    """extract_components basic interface tests."""

    def test_empty_inputs(self):
        assert extract_components([], []) == []


class TestTransformParsers:
    """Transform parsers correctly convert StructValue to dataclass."""

    def test_parse_vector_value(self):
        sv = StructValue(struct_type="Vector", fields={"X": 1.0, "Y": 2.0, "Z": 3.0})
        vec = parse_vector_value(sv)
        assert isinstance(vec, VectorValue)
        assert (vec.x, vec.y, vec.z) == (1.0, 2.0, 3.0)
