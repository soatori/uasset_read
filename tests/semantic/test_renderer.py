"""Tests for SemanticJSONRenderer."""
import json

from uasset_read.renderers.semantic_json_renderer import SemanticJSONRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.semantic.ir import (
    SemanticIR, AssetMeta, ReferenceEntry, CoverageInfo,
    DiagnosticEntry, ContentNode,
)
from uasset_read.semantic.kinds import AssetKind


def _make_ir(**kwargs) -> SemanticIR:
    defaults = dict(
        format="uasset_read.asset_semantic",
        format_version="1.0.0",
        mode="standard",
        asset=AssetMeta(
            kind=AssetKind.RESOURCE,
            class_name="Texture2D",
            object_name="T_Default",
        ),
        references=(),
        content=ContentNode(key="root", children=(
            ContentNode(key="class_name", value="Texture2D"),
            ContentNode(key="serial_size", value=2048),
        )),
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


class TestSemanticJSONRenderer:
    def test_format_name(self):
        renderer = SemanticJSONRenderer()
        assert renderer.format_name == "semantic_json"

    def test_render_produces_valid_json(self):
        renderer = SemanticJSONRenderer()
        ir = _make_ir()
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_render_has_required_fields(self):
        renderer = SemanticJSONRenderer()
        ir = _make_ir()
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert "format" in data
        assert "format_version" in data
        assert "mode" in data
        assert "asset" in data
        assert "references" in data
        assert "content" in data
        assert "coverage" in data
        assert "diagnostics" in data

    def test_render_format_value(self):
        renderer = SemanticJSONRenderer()
        ir = _make_ir()
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert data["format"] == "uasset_read.asset_semantic"
        assert data["format_version"] == "1.0.0"

    def test_render_canonical_key_order(self):
        renderer = SemanticJSONRenderer()
        ir = _make_ir()
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        keys = list(data.keys())
        assert keys[0] == "format"
        assert keys[1] == "format_version"
        assert keys[2] == "mode"

    def test_render_deterministic(self):
        renderer = SemanticJSONRenderer()
        ir = _make_ir()
        r1 = renderer.render(ir, RenderOptions())
        r2 = renderer.render(ir, RenderOptions())
        assert r1 == r2

    def test_render_debug_mode(self):
        renderer = SemanticJSONRenderer()
        ir = _make_ir(mode="debug")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert data["mode"] == "debug"

    def test_render_with_references(self):
        refs = (
            ReferenceEntry(index=0, kind="import", class_name="C", object_name="O", package_path="/P"),
        )
        renderer = SemanticJSONRenderer()
        ir = _make_ir(references=refs)
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert len(data["references"]) == 1

    def test_render_with_diagnostics(self):
        diags = (DiagnosticEntry(severity="warning", code="X", message="msg"),)
        renderer = SemanticJSONRenderer()
        ir = _make_ir(diagnostics=diags)
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert len(data["diagnostics"]) == 1
