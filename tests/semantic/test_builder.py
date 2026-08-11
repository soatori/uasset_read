"""Tests for semantic IR builder."""
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.kinds import AssetKind
from uasset_read.semantic.validator import validate_semantic_ir
from uasset_read.models.ir import (
    ExportIR, ImportIR, ExportRawIR,
)
from .conftest import make_package_ir


class TestBuildSemanticIR:
    def test_resource_asset(self):
        ir = make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.format == "uasset_read.asset_semantic"
        assert semantic.format_version == "1.0.0"
        assert semantic.mode == "standard"
        assert semantic.asset.kind == AssetKind.RESOURCE
        assert semantic.asset.class_name == "Texture2D"

    def test_debug_mode(self):
        ir = make_package_ir()
        semantic = build_semantic_ir(ir, mode="debug")
        assert semantic.mode == "debug"

    def test_opaque_asset(self):
        ir = make_package_ir(exports=[
            ExportIR(
                index=0,
                object_name="Unknown",
                object_class="SomeUnknownClass",
                serial_size=100,
                outer_index_resolved=None,
                super_index_resolved=None,
                parent_class=None,
                properties=[],
                graphs=[],
                bulk_data=None,
            ),
        ])
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.asset.kind == AssetKind.OPAQUE

    def test_references_populated(self):
        ir = make_package_ir(
            imports=[
                ImportIR(
                    index=0,
                    class_package="/Game/T_Imported",
                    class_name="Texture2D",
                    object_name="T_Imported",
                ),
            ],
        )
        semantic = build_semantic_ir(ir, mode="standard")
        assert len(semantic.references) >= 1

    def test_coverage_present(self):
        ir = make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.coverage is not None
        assert semantic.coverage.fields_expected >= 0

    def test_no_exports_returns_opaque(self):
        ir = make_package_ir(exports=[])
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.asset.kind == AssetKind.OPAQUE
        assert semantic.asset.class_name == "Unknown"
        assert semantic.asset.object_name == "Unknown"

    def test_content_is_content_node(self):
        ir = make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.content is not None
        assert semantic.content.key == "root"

    def test_primary_export_prefers_b_is_asset(self):
        """When multiple exports exist, pick the one with b_is_asset=True."""
        ir = make_package_ir(
            exports=[
                ExportIR(
                    index=0,
                    object_name="MetaData_0",
                    object_class="MetaData",
                    serial_size=100,
                    outer_index_resolved=None,
                    super_index_resolved=None,
                    parent_class=None,
                    properties=[],
                    graphs=[],
                    bulk_data=None,
                    ue_export_raw=ExportRawIR(b_is_asset=False),
                ),
                ExportIR(
                    index=1,
                    object_name="M9",
                    object_class="SkeletalMesh",
                    serial_size=4096,
                    outer_index_resolved=None,
                    super_index_resolved=None,
                    parent_class=None,
                    properties=[],
                    graphs=[],
                    bulk_data=None,
                    ue_export_raw=ExportRawIR(b_is_asset=True),
                ),
            ],
        )
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.asset.object_name == "M9"
        assert semantic.asset.class_name == "SkeletalMesh"

    def test_package_path_populated_from_header(self):
        """AssetMeta.package_path should be filled from header.package_name."""
        ir = make_package_ir()
        ir.header.package_name = "/Game/Maps/M9_Skeleton"
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.asset.package_path == "/Game/Maps/M9_Skeleton"

    def test_validates_after_build(self):
        """Built IR should pass validation."""
        ir = make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        errors = validate_semantic_ir(semantic)
        assert errors == []

    def test_asset_kind_is_valid(self):
        """Asset kind must be a valid enum value."""
        ir = make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.asset.kind in (AssetKind.GRAPH, AssetKind.STRUCTURED, AssetKind.RESOURCE, AssetKind.OPAQUE)

    def test_asset_kind_values(self):
        """All asset kinds must be valid enum values."""
        for kind_str in ("graph", "structured", "resource", "opaque"):
            kind = AssetKind(kind_str)
            assert kind.value == kind_str


def test_opaque_partial_coverage_not_100():
    """Opaque asset with parse_status='partial' must not report 100% coverage."""
    from uasset_read.semantic.builder import build_semantic_ir
    pkg = make_package_ir(
        export_class="BlueprintGeneratedClass",
        parse_status="partial",
    )
    ir = build_semantic_ir(pkg)
    assert ir.coverage.coverage_pct < 100.0 or len(ir.coverage.unparsed_fields) > 0


def test_partial_asset_has_diagnostic():
    """Asset with parse_status='partial' must have at least one diagnostic."""
    from uasset_read.semantic.builder import build_semantic_ir
    pkg = make_package_ir(
        export_class="SomeOpaqueClass",
        parse_status="partial",
    )
    ir = build_semantic_ir(pkg)
    assert len(ir.diagnostics) > 0
    assert any(d.severity in ("warning", "error") for d in ir.diagnostics)


def test_can_render_tolerant_semantic_json():
    """_can_render_tolerant_json should allow semantic_json format."""
    from uasset_read.core import _can_render_tolerant_json
    from uasset_read.link.result import LinkerParseResult
    result = LinkerParseResult(
        is_success=False,
        errors=["partial parse"],
        diagnostics=[],
        metadata={"test": True},
    )
    assert _can_render_tolerant_json(result, "semantic_json", True) is True
