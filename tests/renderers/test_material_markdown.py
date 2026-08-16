"""Tests for Material Markdown rendering."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys_path = str(ROOT / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from uasset_read.renderers.markdown_renderer import MarkdownRenderer
from uasset_read.renderers.base import RenderOptions
from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    MaterialIR,
    MaterialExpressionIR,
    MaterialInputIR,
)


def _render_markdown(material: MaterialIR) -> str:
    ir = PackageIR(
        header=PackageHeaderIR(
            package_name="/Game/Test/M_Test",
            package_class="",
            package_flags=0,
            total_export_count=1,
            total_import_count=0,
            ue_version="5.x",
        ),
        name_map=(),
        imports=[],
        exports=[],
        linker=None,
        material=material,
    )
    renderer = MarkdownRenderer()
    options = RenderOptions()
    return renderer.render(ir, options)


class TestMaterialMarkdown:
    def test_material_header_present(self):
        mat = MaterialIR(
            material_type="Material",
            properties={},
            expressions=[],
            material_inputs=[],
            data_flow=[],
        )
        md = _render_markdown(mat)
        assert "Material" in md

    def test_properties_rendered(self):
        mat = MaterialIR(
            material_type="Material",
            properties={"domain": "Surface", "blend_mode": "Opaque"},
            expressions=[],
            material_inputs=[],
            data_flow=[],
        )
        md = _render_markdown(mat)
        assert "Surface" in md
        assert "Opaque" in md

    def test_expressions_rendered(self):
        expr = MaterialExpressionIR(
            expression_guid="abc123",
            expression_class="MaterialExpressionConstant",
            expression_type="constant",
            inputs=[],
            outputs=[],
        )
        mat = MaterialIR(
            material_type="Material",
            properties={},
            expressions=[expr],
            material_inputs=[],
            data_flow=[],
        )
        md = _render_markdown(mat)
        assert "MaterialExpressionConstant" in md
