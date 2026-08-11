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
