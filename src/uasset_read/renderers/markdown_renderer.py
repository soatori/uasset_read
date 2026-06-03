"""Markdown + Mermaid 流程图渲染器。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


def _escape_md_cell(text: str) -> str:
    """转义会破坏 Markdown 表格格式的字符。"""
    return str(text).replace("|", "\\|").replace("\n", " ")


class MarkdownRenderer(IRenderer):
    """Markdown + Mermaid 流程图渲染器。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        lines: list[str] = []

        # 标题
        asset_name = ir.header.package_name.split("/")[-1] if "/" in ir.header.package_name else ir.header.package_name
        lines.append(f"# {asset_name}")
        lines.append("")

        # 概述表
        lines.append("## Asset Overview")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| Package | {_escape_md_cell(ir.header.package_name)} |")
        lines.append(f"| Class | {_escape_md_cell(ir.header.package_class)} |")
        lines.append(f"| Flags | {ir.header.package_flags} |")
        lines.append(f"| Exports | {ir.header.total_export_count} |")
        lines.append(f"| Imports | {ir.header.total_import_count} |")
        lines.append(f"| UE Version | {_escape_md_cell(ir.header.ue_version)} |")
        lines.append("")

        # 导出
        if ir.exports:
            lines.append("## Exports")
            lines.append("| Name | Class | Size | Properties |")
            lines.append("|------|-------|------|------------|")
            for export in ir.exports:
                prop_count = len(export.properties) if export.properties else 0
                lines.append(
                    f"| {_escape_md_cell(export.object_name)} "
                    f"| {_escape_md_cell(export.object_class)} "
                    f"| {export.serial_size} "
                    f"| {prop_count} |"
                )
            lines.append("")

        # 图 + Mermaid
        for export in ir.exports:
            for graph in export.graphs:
                lines.append(f"## Graph: {graph.graph_name}")
                lines.append(f"- **Nodes**: {len(graph.nodes)}")
                if graph.execution_chains:
                    lines.append(f"- **Execution Chains**: {len(graph.execution_chains)}")
                lines.append("")

                if graph.nodes:
                    lines.append("```mermaid")
                    lines.append("graph TD")
                    self._render_mermaid_nodes(lines, graph)
                    lines.append("```")
                    lines.append("")

                # 属性详情
                if export.properties:
                    lines.append("### Properties")
                    lines.append("")
                    lines.append("| Name | Type | Value |")
                    lines.append("|------|------|-------|")
                    for prop in export.properties:
                        val = _escape_md_cell(str(prop.value)[:50]) if prop.value is not None else "null"
                        lines.append(f"| {prop.name} | {prop.type} | {val} |")
                    lines.append("")

        if ir.linker is not None:
            lines.append("## Linker")
            lines.append(f"- **Has Linker**: {ir.linker.has_linker}")
            if ir.linker.import_paths:
                lines.append(f"- **Imports**: {len(ir.linker.import_paths)}")
            if ir.linker.export_paths:
                lines.append(f"- **Exports**: {len(ir.linker.export_paths)}")
            lines.append("")

        return "\n".join(lines)

    def _render_mermaid_nodes(self, lines: list[str], graph) -> None:
        """渲染 Mermaid 节点和连接。"""
        # 定义节点
        for node in graph.nodes:
            label = node.node_comment or node.node_class
            safe_guid = node.node_guid[:8] if node.node_guid else "unknown"
            lines.append(f'    {safe_guid}["{label}"]')

        # 定义连接
        for node in graph.nodes:
            for pin in node.pins:
                for target in (pin.linked_to or []):
                    source_guid = (node.node_guid or "")[:8]
                    target_guid = target[:8] if len(target) >= 8 else target
                    lines.append(f"    {source_guid} --> {target_guid}")

    @property
    def format_name(self) -> str:
        return "markdown"


register_renderer("markdown", MarkdownRenderer)
