"""Test IRenderer contract compliance for SemanticJSONRenderer."""
import pytest
from uasset_read.renderers.semantic_json_renderer import SemanticJSONRenderer
from uasset_read.renderers.base import RenderOptions, IRenderer


def test_semantic_json_renderer_is_irenderer():
    """Verify SemanticJSONRenderer implements IRenderer."""
    renderer = SemanticJSONRenderer()
    assert isinstance(renderer, IRenderer)


def test_semantic_json_renderer_render_accepts_semantic_ir():
    """Verify render() accepts SemanticIR and produces valid output."""
    from uasset_read.semantic.ir import (
        SemanticIR, AssetMeta, CoverageInfo, ContentNode,
    )
    from uasset_read.semantic.kinds import AssetKind

    ir = SemanticIR(
        format="uasset_read.asset_semantic",
        format_version="1.0.0",
        mode="standard",
        asset=AssetMeta(kind=AssetKind.OPAQUE, class_name="Test", object_name="Test_C"),
        references=(),
        content=ContentNode(key="root"),
        coverage=CoverageInfo(
            fields_expected=0, fields_parsed=0, coverage_pct=0.0,
        ),
        diagnostics=(),
    )

    renderer = SemanticJSONRenderer()
    result = renderer.render(ir, RenderOptions())
    assert isinstance(result, str)
    assert "uasset_read.asset_semantic" in result
