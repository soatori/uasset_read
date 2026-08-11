"""Public JSON contract validation tests.

Validates the complete contract:
- format: "uasset_read.asset_semantic"
- format_version: "1.0.0"
- mode: "standard" | "debug"
- Top-level fields: asset, references, content, coverage, diagnostics
- Deterministic output
- Projection invariant: project_debug(debug) == standard
"""
import json

from uasset_read.semantic.builder import build_semantic_ir
from uasset_read.semantic.validator import validate_semantic_ir
from uasset_read.semantic.projection import project_debug
from uasset_read.semantic.kinds import AssetKind
from uasset_read.renderers.semantic_json_renderer import SemanticJSONRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.models.ir import (
    PackageIR, PackageHeaderIR, ExportIR, ImportIR,
    DiagnosticsDataIR, LinkerSummaryIR,
)


def _make_package_ir(export_class="Texture2D", **kwargs) -> PackageIR:
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
                object_name="TestAsset",
                object_class=export_class,
                serial_size=2048,
                outer_index_resolved=None,
                super_index_resolved=None,
                parent_class=None,
                properties=[],
                graphs=[],
                bulk_data=None,
            ),
        ],
        linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
        diagnostics_data=DiagnosticsDataIR(),
    )
    defaults.update(kwargs)
    return PackageIR(**defaults)


class TestPublicContract:
    def test_format_field(self):
        ir = _make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.format == "uasset_read.asset_semantic"

    def test_version_field(self):
        ir = _make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.format_version == "1.0.0"

    def test_mode_standard(self):
        ir = _make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.mode == "standard"

    def test_mode_debug(self):
        ir = _make_package_ir()
        semantic = build_semantic_ir(ir, mode="debug")
        assert semantic.mode == "debug"

    def test_asset_kind_is_valid(self):
        ir = _make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        assert semantic.asset.kind in (AssetKind.GRAPH, AssetKind.STRUCTURED, AssetKind.RESOURCE, AssetKind.OPAQUE)

    def test_deterministic_output(self):
        ir = _make_package_ir()
        renderer = SemanticJSONRenderer()
        r1 = build_semantic_ir(ir, mode="standard")
        r2 = build_semantic_ir(ir, mode="standard")
        opts = RenderOptions()
        j1 = renderer.render_semantic(r1, opts)
        j2 = renderer.render_semantic(r2, opts)
        assert j1 == j2

    def test_projection_invariant(self):
        """project_debug(debug_ir) should produce identical data to standard_ir."""
        ir = _make_package_ir()
        standard = build_semantic_ir(ir, mode="standard")
        debug = build_semantic_ir(ir, mode="debug")
        projected = project_debug(debug)
        # Same data, different mode
        assert projected.asset == standard.asset
        assert projected.references == standard.references
        assert projected.coverage == standard.coverage
        assert projected.diagnostics == standard.diagnostics

    def test_validation_passes(self):
        ir = _make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        errors = validate_semantic_ir(semantic)
        assert errors == []

    def test_json_has_required_top_level_keys(self):
        ir = _make_package_ir()
        semantic = build_semantic_ir(ir, mode="standard")
        renderer = SemanticJSONRenderer()
        result = renderer.render_semantic(semantic, RenderOptions())
        data = json.loads(result)
        required = {"format", "format_version", "mode", "asset", "references", "content", "coverage", "diagnostics"}
        assert required.issubset(set(data.keys()))

    def test_asset_kind_values(self):
        """All asset kinds must be valid enum values."""
        for kind_str in ("graph", "structured", "resource", "opaque"):
            kind = AssetKind(kind_str)
            assert kind.value == kind_str
