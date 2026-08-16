"""Tests for _build_material_ir IR builder."""
from __future__ import annotations

from unittest.mock import Mock

from uasset_read.ir_builder import _build_material_ir


def _make_export(
    object_name: str = "",
    object_class: str = "",
    serial_size: int = 0,
    properties=None,
    parse_status: str = "success",
    b_is_asset: bool = False,
):
    """Create a mock export object."""
    export = Mock()
    export.object_name = object_name
    export.object_class = object_class
    export.serial_size = serial_size
    export.properties = properties or []
    export.parse_status = parse_status
    export.b_is_asset = b_is_asset
    export.class_index = None
    export.outer_index = 0
    export.super_index = 0
    export.graphs = []
    export.bulk_data_header = None
    export._asset_type_data = None
    export.custom_data = {}
    export.transforms = {}
    export.fallback_reason = None
    export.error_message = None
    export.guid = ""
    export.object_flags = 0
    export.serial_offset = 0
    export.package_flags = 0
    export.b_forced_export = False
    export.b_not_for_client = False
    export.b_not_for_server = False
    export.b_is_inherited_instance = False
    export.b_not_always_loaded_for_editor_game = True
    export.b_generate_public_hash = False
    export.script_serialization_start_offset = 0
    export.script_serialization_end_offset = 0
    export.template_index = None
    return export


def _make_property(name: str, value, prop_type: str = "FloatProperty"):
    """Create a mock property object."""
    prop = Mock()
    prop.name = name
    prop.value = value
    prop.type = prop_type
    prop.array_index = -1
    prop.guid = None
    return prop


def _make_result(exports, summary=None):
    """Create a mock ParseResult."""
    result = Mock()
    result.export_map = exports
    result.import_map = []
    result.summary = summary or Mock()
    result.summary.package_name = "/Game/Test"
    result.summary.package_flags = 0
    result.linker = None
    result.name_map = []
    result.blueprint = None
    result.decompiled_functions = []
    result.graphs = []
    result.components = None
    result.diagnostics = []
    result.errors = []
    result.warnings = []
    result.metadata = {}
    result.version_container = Mock()
    result.version_container.is_ue5 = True
    result.version_container.get_ue_version_string = Mock(return_value="5.x")
    result.resolved_parent_assets = []
    result.inherited_blueprint_graphs = []
    result.soft_references = []
    result.soft_package_references = []
    result.logic_sources = []
    result.hex_view_entries = []
    return result


class TestBuildMaterialIr:
    def test_no_material_returns_none(self):
        """When no Material/MaterialInstance export exists, returns None."""
        result = _make_result([_make_export(object_name="Foo", object_class="Texture2D")])
        ir = _build_material_ir(result)
        assert ir is None

    def test_material_with_no_expressions(self):
        """A Material export with no expression exports."""
        mat_export = _make_export(
            object_name="M_Test",
            object_class="Material",
            b_is_asset=True,
            properties=[_make_property("MaterialDomain", 0, "IntProperty")],
        )
        result = _make_result([mat_export])
        ir = _build_material_ir(result)
        assert ir is not None
        assert ir.material_type == "Material"
        assert len(ir.expressions) == 0

    def test_material_with_expression(self):
        """A Material export with one MaterialExpressionConstant."""
        mat_export = _make_export(
            object_name="M_Test",
            object_class="Material",
            b_is_asset=True,
        )
        expr_export = _make_export(
            object_name="MaterialExpressionConstant_1",
            object_class="MaterialExpressionConstant",
            properties=[
                _make_property("R", 1.0, "FloatProperty"),
                _make_property("MaterialExpressionGuid", "abc123", "StructProperty"),
            ],
        )
        result = _make_result([mat_export, expr_export])
        ir = _build_material_ir(result)
        assert ir is not None
        assert ir.material_type == "Material"
        assert len(ir.expressions) == 1
        assert ir.expressions[0].expression_class == "MaterialExpressionConstant"
        assert ir.expressions[0].expression_type == "constant"

    def test_material_instance(self):
        """A MaterialInstance export."""
        mi_export = _make_export(
            object_name="MI_Test",
            object_class="MaterialInstanceConstant",
            b_is_asset=True,
            properties=[
                _make_property("Parent", {"object_name": "M_Parent"}, "ObjectProperty"),
            ],
        )
        result = _make_result([mi_export])
        ir = _build_material_ir(result)
        assert ir is not None
        assert ir.material_type == "MaterialInstance"
