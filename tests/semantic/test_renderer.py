"""Tests for SemanticJSONRenderer."""
import json

from uasset_read.renderers.semantic_json_renderer import SemanticJSONRenderer
from uasset_read.renderers.base import RenderOptions, IRenderer
from .conftest import make_ir


class TestSemanticJSONRenderer:
    def test_format_name(self):
        renderer = SemanticJSONRenderer()
        assert renderer.format_name == "semantic_json"

    def test_is_irenderer(self):
        """Verify SemanticJSONRenderer implements IRenderer."""
        renderer = SemanticJSONRenderer()
        assert isinstance(renderer, IRenderer)

    def test_render_produces_valid_json(self):
        renderer = SemanticJSONRenderer()
        ir = make_ir()
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_render_has_required_fields(self):
        renderer = SemanticJSONRenderer()
        ir = make_ir()
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
        ir = make_ir()
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert data["format"] == "uasset_read.asset_semantic"
        assert data["format_version"] == "1.0.0"

    def test_render_canonical_key_order(self):
        renderer = SemanticJSONRenderer()
        ir = make_ir()
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        keys = list(data.keys())
        assert keys[0] == "format"
        assert keys[1] == "format_version"
        assert keys[2] == "mode"

    def test_render_deterministic(self):
        renderer = SemanticJSONRenderer()
        ir = make_ir()
        r1 = renderer.render(ir, RenderOptions())
        r2 = renderer.render(ir, RenderOptions())
        assert r1 == r2

    def test_render_debug_mode(self):
        renderer = SemanticJSONRenderer()
        ir = make_ir(mode="debug")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert data["mode"] == "debug"

    def test_render_with_references(self):
        from uasset_read.semantic.ir import ReferenceEntry
        refs = (
            ReferenceEntry(index=0, kind="import", class_name="C", object_name="O", package_path="/P"),
        )
        renderer = SemanticJSONRenderer()
        ir = make_ir(references=refs)
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert len(data["references"]) == 1

    def test_render_with_diagnostics(self):
        from uasset_read.semantic.ir import DiagnosticEntry
        diags = (DiagnosticEntry(severity="warning", code="X", message="msg"),)
        renderer = SemanticJSONRenderer()
        ir = make_ir(diagnostics=diags)
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert len(data["diagnostics"]) == 1

    def test_render_accepts_semantic_ir(self):
        """Verify render() accepts SemanticIR and produces valid output."""
        from uasset_read.semantic.ir import AssetMeta, CoverageInfo, ContentNode
        from uasset_read.semantic.kinds import AssetKind
        ir = make_ir(
            asset=AssetMeta(kind=AssetKind.OPAQUE, class_name="Test", object_name="Test_C"),
            content=ContentNode(key="root"),
            coverage=CoverageInfo(fields_expected=0, fields_parsed=0, coverage_pct=0.0),
        )
        renderer = SemanticJSONRenderer()
        result = renderer.render(ir, RenderOptions())
        assert isinstance(result, str)
        assert "uasset_read.asset_semantic" in result

    def test_rendered_output_validates_against_schema(self) -> None:
        """Rendered semantic_json output must validate against the JSON Schema."""
        import json
        from pathlib import Path

        from uasset_read.renderers.semantic_json_renderer import SemanticJSONRenderer

        schema_path = Path(__file__).resolve().parents[2] / "schemas" / "semantic.schema.json"
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)

        renderer = SemanticJSONRenderer()
        ir = make_ir()
        output = renderer.render_semantic(ir, RenderOptions())
        data = json.loads(output)

        # Validate structure manually (no jsonschema dependency allowed)
        assert data["format"] == schema["properties"]["format"]["const"]
        assert data["format_version"] == schema["properties"]["format_version"]["const"]
        assert data["mode"] in schema["properties"]["mode"]["enum"]

        # Validate asset
        asset = data["asset"]
        assert asset["kind"] in ["graph", "structured", "resource", "opaque"]
        assert len(asset["class_name"]) > 0
        assert len(asset["object_name"]) > 0

        # Validate coverage
        cov = data["coverage"]
        assert cov["fields_expected"] >= 0
        assert cov["fields_parsed"] >= 0
        assert 0 <= cov["coverage_pct"] <= 100

        # Validate diagnostics
        for diag in data["diagnostics"]:
            assert diag["severity"] in ["error", "warning", "info"]
            assert len(diag["code"]) > 0
            assert len(diag["message"]) > 0
