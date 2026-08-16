"""MaterialIR dataclass construction and defaults tests."""
from __future__ import annotations

from uasset_read.models.ir import (
    MaterialIR,
    MaterialExpressionIR,
    MaterialExpressionInputIR,
    MaterialExpressionOutputIR,
    MaterialInputIR,
    PackageIR,
    PackageHeaderIR,
)


class TestMaterialExpressionInputIR:
    def test_defaults(self):
        inp = MaterialExpressionInputIR(
            input_name="A",
            source_expression_guid=None,
            source_output_index=0,
        )
        assert inp.input_name == "A"
        assert inp.source_expression_guid is None
        assert inp.source_output_index == 0
        assert inp.mask == 0
        assert inp.mask_r == 0

    def test_with_mask(self):
        inp = MaterialExpressionInputIR(
            input_name="B",
            source_expression_guid="abc123",
            source_output_index=1,
            mask=1, mask_r=1, mask_g=1, mask_b=0, mask_a=0,
        )
        assert inp.mask == 1
        assert inp.mask_r == 1


class TestMaterialExpressionOutputIR:
    def test_defaults(self):
        out = MaterialExpressionOutputIR()
        assert out.output_name == ""
        assert out.mask == 0


class TestMaterialExpressionIR:
    def test_construction(self):
        expr = MaterialExpressionIR(
            expression_guid="abc123",
            expression_class="MaterialExpressionMultiply",
            expression_type="operator",
            inputs=[],
            outputs=[],
        )
        assert expr.expression_guid == "abc123"
        assert expr.expression_class == "MaterialExpressionMultiply"
        assert expr.expression_type == "operator"
        assert expr.parameter is None
        assert expr.constant_value is None
        assert expr.editor_position is None
        assert expr.description is None


class TestMaterialInputIR:
    def test_construction(self):
        mi = MaterialInputIR(
            input_name="BaseColor",
            source_expression_guid="abc123",
            source_output_index=0,
        )
        assert mi.input_name == "BaseColor"
        assert mi.source_expression_guid == "abc123"
        assert mi.mask == 0


class TestMaterialIR:
    def test_material_type(self):
        mat = MaterialIR(
            material_type="Material",
            properties={},
            expressions=[],
            material_inputs=[],
            data_flow=[],
        )
        assert mat.material_type == "Material"
        assert mat.parameters is None
        assert mat.base_property_overrides is None
        assert mat.parent is None

    def test_instance_type(self):
        mat = MaterialIR(
            material_type="MaterialInstance",
            properties={},
            expressions=[],
            material_inputs=[],
            parameters={"scalar": {"x": 1.0}},
            base_property_overrides={"BlendMode": "Opaque"},
            parent="/Game/Path/Parent",
            data_flow=[],
        )
        assert mat.material_type == "MaterialInstance"
        assert mat.parameters["scalar"]["x"] == 1.0
        assert mat.parent == "/Game/Path/Parent"


class TestPackageIRMaterialField:
    def test_material_field_defaults_none(self):
        header = PackageHeaderIR(
            package_name="/Game/Test",
            package_class="",
            package_flags=0,
            total_export_count=0,
            total_import_count=0,
            ue_version="5.x",
        )
        ir = PackageIR(
            header=header,
            name_map=(),
            imports=[],
            exports=[],
            linker=None,
        )
        assert ir.material is None
