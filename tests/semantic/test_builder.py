"""Tests for semantic IR builder."""
from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.kinds import AssetKind
from uasset_read.semantic.ir import CoverageInfo
from uasset_read.models.ir import (
    PackageIR, PackageHeaderIR, ExportIR, ImportIR,
    DiagnosticsDataIR, LinkerSummaryIR,
)


def _make_package_ir(**kwargs) -> PackageIR:
    defaults = dict(
        header=PackageHeaderIR(
            package_name="/Game/Test",
            package_class="Package",
            package_flags=0,
            total_export_count=1,
            total_import_count=0,
            ue_version="5.1",
        ),
        name_map=(),
        imports=[],
        exports=[
            ExportIR(
                index=0,
                object_name="T_Default",
                object_class="Texture2D",
                serial_size=2048,
                outer_index_resolved=None,
                super_index_resolved=None,
                parent_class=None,
                properties=[],
                graphs=[],
                bulk_data=None,
            ),
        ],
        linker=LinkerSummaryIR(
            has_linker=False,
            import_paths=[],
            export_paths=[],
        ),
        diagnostics_data=DiagnosticsDataIR(),
    )
    defaults.update(kwargs)
    return PackageIR(**defaults)


class TestBuildSemanticIR:
    def test_resource_asset(self):
        ir = _make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.format == "uasset_read.asset_semantic"
        assert semantic.format_version == "1.0.0"
        assert semantic.mode == "standard"
        assert semantic.asset.kind == AssetKind.RESOURCE
        assert semantic.asset.class_name == "Texture2D"

    def test_standard_mode(self):
        ir = _make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.mode == "standard"

    def test_debug_mode(self):
        ir = _make_package_ir()
        semantic = build_semantic_ir(ir, mode="debug")
        assert semantic.mode == "debug"

    def test_opaque_asset(self):
        ir = _make_package_ir(exports=[
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
        ir = _make_package_ir(
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
        ir = _make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.coverage is not None
        assert semantic.coverage.fields_expected >= 0

    def test_no_exports_returns_opaque(self):
        ir = _make_package_ir(exports=[])
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.asset.kind == AssetKind.OPAQUE
        assert semantic.asset.class_name == "Unknown"
        assert semantic.asset.object_name == "Unknown"

    def test_content_is_content_node(self):
        ir = _make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.content is not None
        assert semantic.content.key == "root"

    def test_primary_export_prefers_b_is_asset(self):
        """When multiple exports exist, pick the one with b_is_asset=True."""
        from uasset_read.models.ir import ExportRawIR
        ir = _make_package_ir(
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
                    ue_export_raw=ExportRawIR(
                        b_is_asset=False,
                    ),
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
                    ue_export_raw=ExportRawIR(
                        b_is_asset=True,
                    ),
                ),
            ],
        )
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.asset.object_name == "M9"
        assert semantic.asset.class_name == "SkeletalMesh"

    def test_package_path_populated_from_header(self):
        """AssetMeta.package_path should be filled from header.package_name."""
        ir = _make_package_ir()
        ir.header.package_name = "/Game/Maps/M9_Skeleton"
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.asset.package_path == "/Game/Maps/M9_Skeleton"


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
