"""Schema validation tests for Material semantic JSON."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    import jsonschema
except ImportError:
    pytest.skip("jsonschema not available", allow_module_level=True)


SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "material_semantic.schema.json"


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


class TestMaterialSchemaDef:
    def test_material_data_def_exists(self, schema):
        assert "MaterialData" in schema.get("$defs", {})

    def test_material_top_level_property(self, schema):
        assert "material" in schema.get("properties", {})

    def test_material_data_has_required_material_type(self, schema):
        mat_def = schema["$defs"]["MaterialData"]
        assert "material_type" in mat_def.get("required", [])

    def test_material_expression_entry_def(self, schema):
        assert "MaterialExpressionEntry" in schema["$defs"]

    def test_material_input_entry_def(self, schema):
        assert "MaterialInputEntry" in schema["$defs"]

    def test_material_data_flow_entry_def(self, schema):
        assert "MaterialDataFlowEntry" in schema["$defs"]

    def test_material_parameters_def(self, schema):
        assert "MaterialParameters" in schema["$defs"]

    def test_material_properties_def(self, schema):
        assert "MaterialProperties" in schema["$defs"]


class TestSchemaValidation:
    def test_valid_material_output(self, schema):
        """Validate a minimal valid Material output against the schema."""
        data = {
            "format": "uasset_read.material_semantic",
            "format_version": "1.0.0",
            "mode": "standard",
            "asset_type": "material",
            "asset": {"package": "/Game/Test", "name": "M_Test"},
            "status": {"parse": "complete", "representation": "full"},
            "references": [],
            "material": {
                "material_type": "Material",
                "properties": {"domain": "Surface"},
                "expressions": [],
                "material_inputs": [],
                "data_flow": [],
            },
            "coverage": [],
            "diagnostics": [],
            "evidence": [],
        }
        jsonschema.validate(data, schema)

    def test_valid_material_instance_output(self, schema):
        data = {
            "format": "uasset_read.material_semantic",
            "format_version": "1.0.0",
            "mode": "standard",
            "asset_type": "material",
            "asset": {"package": "/Game/Test", "name": "MI_Test"},
            "status": {"parse": "complete", "representation": "full"},
            "references": [],
            "material": {
                "material_type": "MaterialInstance",
                "parent": "/Game/Path/Parent",
                "parameters": {"scalar": {"x": {"value": 1.0}}},
            },
            "coverage": [],
            "diagnostics": [],
            "evidence": [],
        }
        jsonschema.validate(data, schema)
