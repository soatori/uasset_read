"""Text 渲染器废弃警告测试。"""
import warnings
import pytest
from uasset_read.models.ir import PackageIR, PackageHeaderIR


def _make_minimal_ir() -> PackageIR:
    """创建最小 PackageIR 用于测试。"""
    header = PackageHeaderIR(
        package_name="Test",
        package_class="None",
        package_flags=0,
        total_export_count=0,
        total_import_count=0,
        ue_version="5.4.0",
    )
    return PackageIR(
        header=header,
        name_map=(),
        imports=[],
        exports=[],
        linker=None,
    )


class TestTextDeprecated:
    def test_text_format_emits_deprecation_warning(self):
        """--text 格式应发出 DeprecationWarning。"""
        from uasset_read.renderers.text_renderer import TextRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = _make_minimal_ir()
        renderer = TextRenderer()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            renderer.render(ir, RenderOptions())

        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) >= 1
        assert "markdown" in str(dep_warnings[0].message).lower()

    def test_markdown_format_no_deprecation_warning(self):
        """--markdown 格式不应发出 DeprecationWarning。"""
        from uasset_read.renderers.markdown_renderer import MarkdownRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = _make_minimal_ir()
        renderer = MarkdownRenderer()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            renderer.render(ir, RenderOptions())

        dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(dep_warnings) == 0

    def test_text_renderer_still_works(self):
        """废弃后 Text 渲染器仍应正常工作。"""
        from uasset_read.renderers.text_renderer import TextRenderer
        from uasset_read.renderers.base import RenderOptions

        ir = _make_minimal_ir()
        renderer = TextRenderer()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = renderer.render(ir, RenderOptions())
        assert "=== Test ===" in result
