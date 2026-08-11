"""Consolidated tests for tagged fallback struct schemas.

Covers FBlendSample, FEditorElement, FScalarParameterValue, and their
alias variants (without the F prefix) as registered in the tagged
fallback system.
"""
import pytest

from uasset_read.parsers.property_types import (
    _TAGGED_FALLBACK_STRUCTS,
    _TAGGED_FALLBACK_STRUCT_SCHEMAS,
)


class TestFBlendSampleSchema:
    """Verify FBlendSample / BlendSample tagged fallback registration and schema."""

    def test_schema_fields_and_alias_consistency(self):
        """FBlendSample and BlendSample must have identical schemas with correct fields."""
        for name in ("FBlendSample", "BlendSample"):
            assert name in _TAGGED_FALLBACK_STRUCTS
            assert name in _TAGGED_FALLBACK_STRUCT_SCHEMAS

        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FBlendSample"]
        field_names = [f[0] for f in schema]
        assert field_names == ["SampleValue", "Time", "RateScale", "bIsValid"]
        assert len(schema) == 4
        assert schema[0] == ("SampleValue", "StructProperty")
        assert schema[1] == ("Time", "FloatProperty")
        assert schema[2] == ("RateScale", "IntProperty")
        assert schema[3] == ("bIsValid", "BoolProperty")

        # Alias must match
        assert _TAGGED_FALLBACK_STRUCT_SCHEMAS["FBlendSample"] == \
            _TAGGED_FALLBACK_STRUCT_SCHEMAS["BlendSample"]


class TestFEditorElementSchema:
    """Verify FEditorElement / EditorElement tagged fallback registration and schema."""

    def test_schema_fields_and_alias_consistency(self):
        """FEditorElement and EditorElement must have identical schemas with correct fields."""
        for name in ("FEditorElement", "EditorElement"):
            assert name in _TAGGED_FALLBACK_STRUCTS
            assert name in _TAGGED_FALLBACK_STRUCT_SCHEMAS

        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FEditorElement"]
        field_names = [f[0] for f in schema]
        assert field_names == ["DisplayName", "Value", "bIsDefault"]
        assert len(schema) == 3
        assert schema[0] == ("DisplayName", "TextProperty")
        assert schema[1] == ("Value", "StrProperty")
        assert schema[2] == ("bIsDefault", "BoolProperty")

        # Alias must match
        assert _TAGGED_FALLBACK_STRUCT_SCHEMAS["FEditorElement"] == \
            _TAGGED_FALLBACK_STRUCT_SCHEMAS["EditorElement"]


class TestFScalarParameterValueSchema:
    """Verify ScalarParameterValue / FScalarParameterValue tagged fallback."""

    def test_schema_fields_and_types(self):
        """ScalarParameterValue must have correct fields and alias equivalence."""
        for name in ("ScalarParameterValue", "FScalarParameterValue"):
            assert name in _TAGGED_FALLBACK_STRUCTS
            assert name in _TAGGED_FALLBACK_STRUCT_SCHEMAS

        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["ScalarParameterValue"]
        assert len(schema) == 3
        field_names = [f[0] for f in schema]
        assert "ParameterInfo" in field_names
        assert "ParameterValue" in field_names
        assert "bOverride" in field_names

        schema_dict = dict(schema)
        assert schema_dict["ParameterInfo"] == "StructProperty"
        assert schema_dict["ParameterValue"] == "FloatProperty"
        assert schema_dict["bOverride"] == "BoolProperty"

        # Alias must match
        assert (
            _TAGGED_FALLBACK_STRUCT_SCHEMAS["ScalarParameterValue"]
            == _TAGGED_FALLBACK_STRUCT_SCHEMAS["FScalarParameterValue"]
        )

    def test_material_parameter_info_dependency(self):
        """FMaterialParameterInfo must also be registered as ScalarParameterValue depends on it."""
        assert "FMaterialParameterInfo" in _TAGGED_FALLBACK_STRUCTS
        assert "FMaterialParameterInfo" in _TAGGED_FALLBACK_STRUCT_SCHEMAS
        schema = _TAGGED_FALLBACK_STRUCT_SCHEMAS["FMaterialParameterInfo"]
        assert len(schema) == 3
        assert schema[0] == ("ParameterName", "NameProperty")
        assert schema[1] == ("Index", "IntProperty")
        assert schema[2] == ("bOverride", "BoolProperty")
