"""Tests for debug -> standard projection."""
from uasset_read.semantic.projection import project_debug
from uasset_read.semantic.ir import (
    SemanticIR, AssetMeta, ReferenceEntry, CoverageInfo,
    DiagnosticEntry, ContentNode,
)
from uasset_read.semantic.kinds import AssetKind


def _make_ir(mode: str = "standard", **kwargs) -> SemanticIR:
    defaults = dict(
        format="uasset_read.asset_semantic",
        format_version="1.0.0",
        mode=mode,
        asset=AssetMeta(
            kind=AssetKind.RESOURCE,
            class_name="Texture2D",
            object_name="T_Default",
        ),
        references=(),
        content=ContentNode(key="root", children=()),
        coverage=CoverageInfo(
            fields_expected=5,
            fields_parsed=5,
            coverage_pct=100.0,
            unparsed_fields=(),
        ),
        diagnostics=(),
    )
    defaults.update(kwargs)
    return SemanticIR(**defaults)


class TestProjectDebug:
    def test_standard_passthrough(self):
        """A standard-mode IR should pass through unchanged."""
        ir = _make_ir(mode="standard")
        result = project_debug(ir)
        assert result.mode == "standard"
        assert result.format == ir.format

    def test_debug_projects_to_standard_mode(self):
        """project_debug() should set mode to 'standard'."""
        ir = _make_ir(mode="debug")
        result = project_debug(ir)
        assert result.mode == "standard"

    def test_projection_preserves_asset(self):
        ir = _make_ir(mode="debug")
        result = project_debug(ir)
        assert result.asset == ir.asset

    def test_projection_preserves_content(self):
        ir = _make_ir(mode="debug")
        result = project_debug(ir)
        assert result.content == ir.content

    def test_projection_preserves_references(self):
        refs = (
            ReferenceEntry(index=0, kind="import", class_name="C", object_name="O", package_path="/P"),
        )
        ir = _make_ir(mode="debug", references=refs)
        result = project_debug(ir)
        assert result.references == refs

    def test_projection_preserves_coverage(self):
        ir = _make_ir(mode="debug")
        result = project_debug(ir)
        assert result.coverage == ir.coverage

    def test_projection_preserves_diagnostics(self):
        diags = (DiagnosticEntry(severity="warning", code="X", message="msg"),)
        ir = _make_ir(mode="debug", diagnostics=diags)
        result = project_debug(ir)
        assert result.diagnostics == diags

    def test_projection_invariant(self):
        """project_debug(debug_ir) should equal a standard IR with same data."""
        debug_ir = _make_ir(mode="debug")
        standard_ir = _make_ir(mode="standard")
        projected = project_debug(debug_ir)
        # Same everything except mode
        assert projected.format == standard_ir.format
        assert projected.format_version == standard_ir.format_version
        assert projected.mode == "standard"
        assert projected.asset == standard_ir.asset
