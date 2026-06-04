"""YAML 风格文本渲染器。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


def _format_value(value: Any) -> str:
    """格式化属性值为字符串。"""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    return repr(value)


class TextRenderer(IRenderer):
    """YAML 风格缩进文本渲染器。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        lines: list[str] = []
        lines.append(f"Package: {ir.header.package_name}")
        lines.append(f"  Class: {ir.header.package_class}")
        lines.append(f"  Flags: {ir.header.package_flags}")
        lines.append(f"  Exports: {ir.header.total_export_count}")
        lines.append(f"  Imports: {ir.header.total_import_count}")
        lines.append(f"  UE Version: {ir.header.ue_version}")
        lines.append("")

        if ir.exports:
            lines.append("Exports:")
            for export in ir.exports:
                self._render_export(lines, export, options)

        if ir.linker is not None:
            lines.append("Linker:")
            lines.append(f"  HasLinker: {ir.linker.has_linker}")
            if ir.linker.import_paths:
                lines.append(f"  Imports: {len(ir.linker.import_paths)}")
            if ir.linker.export_paths:
                lines.append(f"  Exports: {len(ir.linker.export_paths)}")
            lines.append("")

        return "\n".join(lines)

    def _render_export(self, lines: list[str], export, options: RenderOptions) -> None:
        lines.append(f"  - Name: {export.object_name}")
        lines.append(f"    Class: {export.object_class}")
        lines.append(f"    SerialSize: {export.serial_size}")
        if export.parent_class:
            lines.append(f"    Parent: {export.parent_class}")
        if export.properties:
            lines.append(f"    Properties ({len(export.properties)}):")
            for prop in export.properties:
                val = _format_value(prop.value)
                lines.append(f"      - {prop.name} ({prop.type}): {val}")
        if export.graphs:
            lines.append(f"    Graphs ({len(export.graphs)}):")
            for graph in export.graphs:
                lines.append(f"      - {graph.graph_name} ({len(graph.nodes)} nodes)")
        lines.append("")

    @property
    def format_name(self) -> str:
        return "text"


class TextSummaryRenderer(IRenderer):
    """精简 YAML 风格摘要渲染器。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        lines: list[str] = []
        lines.append(f"Package: {ir.header.package_name}")
        lines.append(f"  Exports: {ir.header.total_export_count}")
        lines.append("")

        for export in ir.exports:
            parent_info = f" (Parent: {export.parent_class})" if export.parent_class else ""
            lines.append(f"  - {export.object_name} ({export.object_class}){parent_info}")

        return "\n".join(lines)

    @property
    def format_name(self) -> str:
        return "text_summary"


register_renderer("text", TextRenderer)
register_renderer("text_summary", TextSummaryRenderer)
