"""模拟 UE Ctrl+C 文本格式渲染器。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


def _escape_ue_value(value: str) -> str:
    """转义 UE 格式字符串中的特殊字符。"""
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_ue_value(value: Any) -> str:
    """格式化值为 UE 风格字符串。"""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return _escape_ue_value(value)
    return str(value)


class BlueprintUERenderer(IRenderer):
    """模拟 UE 编辑器 Ctrl+C 复制的蓝图文本格式。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        lines: list[str] = []

        lines.append(f'Begin Object Class="{ir.header.package_class}" Name="{ir.header.package_name}"')

        for export in ir.exports:
            lines.append(f'   Begin Object Class="{export.object_class}" Name="{export.object_name}"')

            if export.parent_class:
                lines.append(f'      SuperClass="{export.parent_class}"')

            if export.properties:
                for prop in export.properties:
                    val = _format_ue_value(prop.value)
                    lines.append(f"      {prop.name}={val}")

            # 节点信息
            for graph in export.graphs:
                for node in graph.nodes:
                    guid_upper = node.node_guid.upper() if node.node_guid else ""
                    lines.append(f'   Begin Object Name="{node.node_class}"')
                    lines.append(f"      NodeGuid={guid_upper}")
                    if node.node_comment:
                        lines.append(f'      NodeComment="{_escape_ue_value(node.node_comment)}"')
                    for pin in node.pins:
                        pin_id = pin.linked_to[0][:8].upper() if pin.linked_to else ""
                        lines.append(
                            f'      Pin: {pin.pin_name} ({pin.pin_type}) '
                            f'LinkedTo=({pin_id})' if pin.linked_to else
                            f"      Pin: {pin.pin_name} ({pin.pin_type})"
                        )
                    lines.append("   End Object")

            lines.append("   End Object")

        lines.append("End Object")
        return "\n".join(lines)

    @property
    def format_name(self) -> str:
        return "blueprint_ue_text"


register_renderer("blueprint_ue_text", BlueprintUERenderer)
