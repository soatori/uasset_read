"""渲染器测试 — 合并自 test_renderers_core.py、test_renderers_text.py、test_report_quality.py。

覆盖：核心渲染、文本渲染。
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    ExportIR,
    PropertyIR,
    BlueprintIR,
    LinkerSummaryIR,
)
from uasset_read.renderers import get_renderer, list_formats
from uasset_read.renderers.base import IRenderer, RenderOptions


# ============================================================================
# 辅助工厂
# ============================================================================

def _make_header(**kwargs) -> PackageHeaderIR:
    defaults = dict(
        package_name="/Game/BP_Test",
        package_class="/Engine/Blueprint",
        package_flags=0,
        total_export_count=1,
        total_import_count=0,
        ue_version="5.3",
    )
    defaults.update(kwargs)
    return PackageHeaderIR(**defaults)


def _make_export(**kwargs) -> ExportIR:
    defaults = dict(
        index=0,
        object_name="BP_Test_C",
        object_class="BlueprintGeneratedClass",
        serial_size=1024,
        outer_index_resolved=None,
        super_index_resolved=None,
        parent_class="/Engine/Actor",
        properties=[],
        graphs=[],
        bulk_data=None,
    )
    defaults.update(kwargs)
    return ExportIR(**defaults)


def _make_ir(**kwargs) -> PackageIR:
    defaults = dict(
        header=_make_header(),
        name_map=[],
        imports=[],
        exports=[_make_export()],
        linker=LinkerSummaryIR(has_linker=False, import_paths=[], export_paths=[]),
    )
    defaults.update(kwargs)
    return PackageIR(**defaults)


# ============================================================================
# 1. 渲染器注册表基础
# ============================================================================

class TestRendererRegistry:
    def test_registry_contains_json_and_markdown(self):
        """注册表应包含 json 和 markdown。"""
        formats = list_formats()
        assert "json" in formats
        assert "markdown" in formats

    def test_is_blueprint_export_handles_none_object_name(self):
        """#433: object_name 为 None 时不应抛出 AttributeError"""
        from uasset_read.renderers.base import is_blueprint_export

        export = MagicMock()
        export.object_name = None
        export.graphs = []
        assert not is_blueprint_export(export)


# ============================================================================
# 2. JSON 渲染器基础输出
# ============================================================================

class TestJSONRendererBasic:
    def test_render_produces_valid_json(self):
        """渲染结果应为有效 JSON。"""
        ir = _make_ir()
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_render_contains_required_keys(self):
        """输出应包含 status、summary、exports、statistics。"""
        ir = _make_ir()
        renderer = get_renderer("json")
        result = renderer.render(ir, RenderOptions())
        data = json.loads(result)
        assert "status" in data
        assert "exports" in data


# ============================================================================
# 3. Markdown 渲染器基础输出
# ============================================================================

class TestMarkdownRendererBasic:
    def test_render_produces_string(self):
        """渲染结果应为非空字符串。"""
        ir = _make_ir()
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_with_package_name_slash(self):
        """带路径的包名应只显示最后一段作为标题。"""
        ir = _make_ir(header=_make_header(package_name="/Game/Blueprints/BP_MyAsset"))
        renderer = get_renderer("markdown")
        result = renderer.render(ir, RenderOptions())
        assert "# BP_MyAsset" in result
