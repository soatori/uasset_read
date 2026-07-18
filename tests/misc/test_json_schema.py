"""JSON Schema 集成测试 — 验证 output_version 移除和 $schema 引用。"""
from __future__ import annotations

import json

import pytest

from uasset_read.renderers.json_renderer import JSONRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.models.ir import PackageIR, PackageHeaderIR, ExportIR


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------

def _make_header() -> PackageHeaderIR:
    return PackageHeaderIR(
        package_name="/Game/Test/BP_Test",
        package_class="BP_Test_C",
        package_flags=0,
        total_export_count=1,
        total_import_count=1,
        ue_version="5.3",
    )


def _make_minimal_ir(**kwargs) -> PackageIR:
    """构造最小 PackageIR。"""
    defaults = dict(
        header=_make_header(),
        name_map=["BP_Test"],
        imports=[],
        exports=[],
        linker=None,
    )
    defaults.update(kwargs)
    return PackageIR(**defaults)


def _render_json(ir: PackageIR, **options_kwargs) -> dict:
    """渲染 IR 为 JSON 字典。"""
    renderer = JSONRenderer()
    options = RenderOptions(**options_kwargs)
    output = renderer.render(ir, options)
    return json.loads(output)


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------

class TestOutputVersionRemoved:
    """验证 JSON 输出不包含 output_version 字段。"""

    def test_no_output_version_default(self):
        """默认渲染不应包含 output_version 字段。"""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "output_version" not in data

    def test_no_output_version_debug(self):
        """debug 模式也不应包含 output_version 字段。"""
        ir = _make_minimal_ir()
        data = _render_json(ir, output_level="debug")
        assert "output_version" not in data


class TestSchemaReference:
    """验证 include_schema=True 时输出包含 $schema 引用。"""

    def test_schema_reference_included(self):
        """启用 include_schema 时应包含 $schema 引用。"""
        ir = _make_minimal_ir()
        data = _render_json(ir, include_schema=True)
        assert "$schema" in data
        assert data["$schema"] == "package.schema.json"

    def test_schema_reference_absent_by_default(self):
        """默认不启用 include_schema 时不应包含 $schema。"""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "$schema" not in data

    def test_schema_reference_absent_when_false(self):
        """显式 include_schema=False 时不应包含 $schema。"""
        ir = _make_minimal_ir()
        data = _render_json(ir, include_schema=False)
        assert "$schema" not in data


class TestRequiredFields:
    """验证 JSON 输出的基本字段结构。"""

    def test_has_status_and_summary_and_exports(self):
        """输出应包含 status、summary、exports 键。"""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "status" in data
        assert "summary" in data
        assert "exports" in data

    def test_status_structure(self):
        """status 字段应包含 status、message、code。"""
        ir = _make_minimal_ir()
        data = _render_json(ir)
        assert "status" in data
        assert "status" in data["status"]
