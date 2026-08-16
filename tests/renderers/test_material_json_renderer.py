"""Tests for Material JSON rendering via semantic pipeline."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys_path = str(ROOT / "src")
if sys_path not in __import__("sys").path:
    __import__("sys").path.insert(0, sys_path)

from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    ExportIR,
    MaterialIR,
    MaterialExpressionIR,
    MaterialExpressionInputIR,
    MaterialExpressionOutputIR,
    MaterialInputIR,
    DiagnosticsDataIR,
    LinkerSummaryIR,
)
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.projection import project_semantic
from uasset_read.semantic.render import render_semantic_json


def _make_header() -> PackageHeaderIR:
    return PackageHeaderIR(
        package_name="/Game/Test/M_Test",
        package_class="",
        package_flags=0,
        total_export_count=1,
        total_import_count=0,
        ue_version="5.x",
    )


def _make_export() -> ExportIR:
    return ExportIR(
        index=0,
        object_name="M_Test",
        object_class="Material",
        serial_size=0,
        outer_index_resolved=None,
        super_index_resolved=None,
        parent_class=None,
        properties=[],
        graphs=[],
        bulk_data=None,
    )


def _render_json(material: MaterialIR, mode: str = "debug") -> dict:
    ir = PackageIR(
        header=_make_header(),
        name_map=(),
        imports=[],
        exports=[_make_export()],
        linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
        material=material,
    )
    ir.diagnostics_data = DiagnosticsDataIR(status="success", errors=None, warnings=None)
    semantic_ir = build_semantic_ir(ir, source_path="M_Test.uasset")
    semantic_ir = project_semantic(semantic_ir, mode)
    output = render_semantic_json(semantic_ir)
    return json.loads(output)


class TestMaterialRendering:
    def test_material_section_present(self):
        mat = MaterialIR(
            material_type="Material",
            properties={},
            expressions=[],
            material_inputs=[],
            data_flow=[],
        )
        data = _render_json(mat)
        assert "material" in data
        assert data["material"]["material_type"] == "Material"

    def test_material_with_expressions(self):
        expr = MaterialExpressionIR(
            expression_guid="abc123",
            expression_class="MaterialExpressionMultiply",
            expression_type="operator",
            inputs=[
                MaterialExpressionInputIR(
                    input_name="A",
                    source_expression_guid="def456",
                    source_output_index=0,
                ),
            ],
            outputs=[MaterialExpressionOutputIR()],
        )
        mat = MaterialIR(
            material_type="Material",
            properties={"domain": "Surface"},
            expressions=[expr],
            material_inputs=[],
            data_flow=[],
        )
        data = _render_json(mat)
        assert len(data["material"]["expressions"]) == 1
        assert data["material"]["expressions"][0]["expression_class"] == "MaterialExpressionMultiply"
        assert data["material"]["expressions"][0]["inputs"][0]["source_expression_guid"] == "def456"

    def test_material_inputs_rendered(self):
        mi = MaterialInputIR(
            input_name="BaseColor",
            source_expression_guid="abc123",
            source_output_index=0,
        )
        mat = MaterialIR(
            material_type="Material",
            properties={},
            expressions=[],
            material_inputs=[mi],
            data_flow=[],
        )
        data = _render_json(mat)
        assert len(data["material"]["material_inputs"]) == 1
        assert data["material"]["material_inputs"][0]["input_name"] == "BaseColor"

    def test_data_flow_rendered(self):
        mat = MaterialIR(
            material_type="Material",
            properties={},
            expressions=[],
            material_inputs=[],
            data_flow=[
                {
                    "source_expression_guid": "abc",
                    "source_output_index": 0,
                    "target_expression_guid": "def",
                    "target_input_name": "A",
                }
            ],
        )
        data = _render_json(mat)
        assert len(data["material"]["data_flow"]) == 1

    def test_material_instance_rendered(self):
        mat = MaterialIR(
            material_type="MaterialInstance",
            properties={},
            expressions=[],
            material_inputs=[],
            parameters={"scalar": {"x": {"value": 1.0}}},
            base_property_overrides={"BlendMode": "Opaque"},
            parent="/Game/Path/Parent",
            data_flow=[],
        )
        data = _render_json(mat)
        assert data["material"]["material_type"] == "MaterialInstance"
        assert data["material"]["parent"] == "/Game/Path/Parent"
        assert data["material"]["parameters"]["scalar"]["x"]["value"] == 1.0
