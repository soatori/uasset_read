"""渲染器核心测试 — 注册表、格式分发、JSON/Markdown 基础输出。"""
from __future__ import annotations

import json
from io import StringIO
from unittest.mock import MagicMock

import pytest

from uasset_read.renderers import (
    RENDERER_REGISTRY,
    get_renderer,
    list_formats,
)
from uasset_read.renderers.base import RenderOptions
from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
)


def _make_mock_ir(
    package_name: str = "/Game/Test/BP_Test",
    package_class: str = "BP_Test_C",
    package_flags: int = 0,
    export_count: int = 0,
    import_count: int = 0,
    ue_version: str = "5.4.0",
) -> PackageIR:
    """创建最小的 mock PackageIR，用于渲染器测试。"""
    header = PackageHeaderIR(
        package_name=package_name,
        package_class=package_class,
        package_flags=package_flags,
        total_export_count=export_count,
        total_import_count=import_count,
        ue_version=ue_version,
    )
    exports = []
    for i in range(export_count):
        exports.append(MagicMock(
            object_name=f"Export_{i}",
            object_class="None",
            serial_size=100,
            properties=[],
            graphs=[],
            parse_status="success",
            fallback_reason=None,
            error_message=None,
            parent_class=None,
        ))
    return PackageIR(
        header=header,
        name_map=(),
        imports=[],
        exports=exports,
        linker=None,
    )


class TestRendererRegistry:
    """渲染器注册表测试。"""

    def test_registry_has_json_and_markdown(self):
        """注册表应包含 json 和 markdown 格式，且可获取正确类型实例。"""
        assert "json" in RENDERER_REGISTRY
        assert "markdown" in RENDERER_REGISTRY
        assert isinstance(get_renderer("json"), JSONRenderer)
        assert isinstance(get_renderer("markdown"), MarkdownRenderer)
        # list_formats 应返回已排序的格式列表
        formats = list_formats()
        assert "json" in formats and "markdown" in formats
        assert formats == sorted(formats)

    def test_get_unknown_renderer_raises(self):
        """获取不存在的格式应抛出 ValueError。"""
        with pytest.raises(ValueError, match="Unknown render format"):
            get_renderer("nonexistent_format")


class TestJSONRenderer:
    """JSON 渲染器基础测试。"""

    def test_render_produces_valid_json(self):
        """JSON 渲染器输出应是可反序列化的 JSON，包含 summary 和 exports。"""
        ir = _make_mock_ir()
        renderer = get_renderer("json")
        options = RenderOptions()
        output = renderer.render(ir, options)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)
        assert parsed["summary"]["package_name"] == "/Game/Test/BP_Test"
        assert parsed["summary"]["package_class"] == "BP_Test_C"
        assert parsed["summary"]["ue_version"] == "5.4.0"
        assert parsed["exports"] == []

    def test_render_to_stream_matches_render(self):
        """render_to 写入 IO 流的内容应与 render 输出一致（尾部换行）。"""
        ir = _make_mock_ir()
        renderer = get_renderer("json")
        options = RenderOptions()
        from_render = renderer.render(ir, options)
        buf = StringIO()
        renderer.render_to(ir, buf, options)
        buf.seek(0)
        from_stream = buf.read()
        # render_to 使用 json.dump + writer.write("\n")，与 render 输出一致
        assert json.loads(from_stream) == json.loads(from_render)
        assert from_stream.endswith("\n")


class TestMarkdownRenderer:
    """Markdown 渲染器基础测试。"""

    def test_render_produces_heading_with_package_info(self):
        """Markdown 渲染器输出应以 # 标题开头，包含资产名、UE 版本和类名。"""
        ir = _make_mock_ir(ue_version="5.4.0")
        renderer = get_renderer("markdown")
        options = RenderOptions()
        output = renderer.render(ir, options)
        assert output.startswith("# ")
        assert "BP_Test" in output
        assert "5.4.0" in output
        assert "BP_Test_C" in output
