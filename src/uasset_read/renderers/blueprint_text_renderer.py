"""蓝图翻译参考文本渲染器。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR

# 常用节点类型简称
_CLASS_SHORT_NAMES = {
    "K2Node_CallFunction": "CallFunc",
    "K2Node_Event": "Event",
    "K2Node_FunctionEntry": "FuncEntry",
    "K2Node_FunctionResult": "FuncResult",
    "K2Node_IfThenElse": "IfThenElse",
    "K2Node_Switch": "Switch",
    "K2Node_Knot": "Reroute",
    "EdGraphNode_Comment": "Comment",
}


class BlueprintTextRenderer(IRenderer):
    """紧凑节点列表，用于蓝图翻译参考。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        lines: list[str] = []

        lines.append(f"Package: {ir.header.package_name}")
        lines.append(f"Class: {ir.header.package_class}")
        lines.append("")

        for export in ir.exports:
            if not export.graphs:
                continue

            lines.append(f"Export: {export.object_name} ({export.object_class})")
            if export.parent_class:
                lines.append(f"  Parent: {export.parent_class}")
            lines.append("")

            for graph in export.graphs:
                lines.append(f"  Graph: {graph.graph_name} ({graph.graph_class})")
                lines.append(f"    Nodes: {len(graph.nodes)}")
                if graph.execution_chains:
                    lines.append(f"    Chains: {len(graph.execution_chains)}")
                lines.append("")

                for node in graph.nodes:
                    short_type = _CLASS_SHORT_NAMES.get(node.node_class, node.node_class)
                    guid_prefix = node.node_guid[:8] if node.node_guid else "????????"
                    comment = f" # {node.node_comment}" if node.node_comment else ""
                    lines.append(f"    [{short_type}] {guid_prefix}...{comment}")

                    for pin in node.pins:
                        direction = "in" if pin.direction == 0 else "out"
                        linked = f" -> {pin.linked_to}" if pin.linked_to else ""
                        default = f" = {pin.default_value}" if pin.default_value else ""
                        lines.append(f"      Pin({direction}): {pin.pin_name} ({pin.pin_type}){default}{linked}")
                lines.append("")

        return "\n".join(lines)

    @property
    def format_name(self) -> str:
        return "blueprint_text"


register_renderer("blueprint_text", BlueprintTextRenderer)
