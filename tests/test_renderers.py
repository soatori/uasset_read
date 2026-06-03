"""渲染器测试。"""
import pytest
from uasset_read.renderers.base import RenderOptions, IRenderer
from uasset_read.renderers import get_renderer, RENDERER_REGISTRY


class TestRenderOptions:
    def test_defaults(self):
        opts = RenderOptions()
        assert opts.verbose is False
        assert opts.indent == 2
        assert opts.include_schema is False

    def test_custom(self):
        opts = RenderOptions(verbose=True, indent=4, include_function_graphs=True)
        assert opts.verbose is True
        assert opts.indent == 4


class TestRendererRegistry:
    def test_get_renderer_json(self):
        from uasset_read.renderers.json_renderer import JSONRenderer  # noqa: F401
        r = get_renderer("json")
        assert r.format_name == "json"

    def test_get_renderer_unknown(self):
        with pytest.raises(ValueError, match="Unknown render format"):
            get_renderer("nonexistent")

    def test_list_formats(self):
        from uasset_read.renderers.json_renderer import JSONRenderer  # noqa: F401
        from uasset_read.renderers import list_formats
        fmts = list_formats()
        assert "json" in fmts

    def test_duplicate_registration_raises(self):
        from uasset_read.renderers import register_renderer
        from uasset_read.renderers.base import IRenderer

        class _TestRenderer(IRenderer):
            def render(self, ir, options): return ""
            @property
            def format_name(self): return "_test_dup"

        register_renderer("_test_dup", _TestRenderer)
        with pytest.raises(ValueError, match="already registered"):
            register_renderer("_test_dup", _TestRenderer)
        # cleanup
        RENDERER_REGISTRY.pop("_test_dup", None)