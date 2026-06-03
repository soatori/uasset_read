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

        # === Event Graph ===
        self._render_event_graph(lines, ir)

        # === Functions ===
        self._render_functions(lines, ir)

        # === Variables ===
        self._render_variables(lines, ir)

        if ir.linker is not None:
            lines.append("## Linker")
            lines.append(f"- **Has Linker**: {ir.linker.has_linker}")
            if ir.linker.import_paths:
                lines.append(f"- **Imports**: {len(ir.linker.import_paths)}")
            if ir.linker.export_paths:
                lines.append(f"- **Exports**: {len(ir.linker.export_paths)}")
            lines.append("")

        return "\n".join(lines)

    def _render_event_graph(self, lines: list[str], ir: PackageIR) -> None:
        """渲染 Event Graph 章节 — 每个事件函数一个子章节，包含 C++ 代码块。"""
        events = ir.blueprint.events if ir.blueprint and ir.blueprint.events else []
        if not events and not ir.execution_chains:
            return

        lines.append("## Event Graph")
        lines.append("")

        # 使用 execution_chains 中的事件信息
        chains_by_event: dict[str, list[str]] = {}
        for chain in ir.execution_chains:
            chains_by_event.setdefault(chain.event, []).extend(chain.chain)

        # 去重后的事件名
        seen_events: set[str] = set()
        for event in events:
            if event.name in seen_events:
                continue
            seen_events.add(event.name)

            lines.append(f"### {event.name}")
            lines.append("")

            # 查找匹配的反编译函数
            decompiled = self._find_decompiled(ir, event.name)
            if decompiled:
                lines.append(f"```cpp")
                lines.append(decompiled.signature)
                lines.append("{")
                if decompiled.cpp_code.strip():
                    for code_line in decompiled.cpp_code.strip().splitlines():
                        lines.append(f"    {code_line}")
                lines.append("}")
                lines.append("```")
            else:
                # 生成事件 override 签名
                lines.append("```cpp")
                lines.append(self._gen_event_signature(event))
                lines.append("{")
                lines.append("    // Event handler")
                lines.append("}")
                lines.append("```")
            lines.append("")

            # 调用链
            chain = chains_by_event.get(event.name, [])
            if chain:
                lines.append("**Execution Chain:**")
                lines.append("")
                lines.append(" -> ".join(chain))
                lines.append("")

        # 处理 execution_chains 中未在 events 里列出的事件
        for event_name, chain in chains_by_event.items():
            if event_name not in seen_events:
                seen_events.add(event_name)
                lines.append(f"### {event_name}")
                lines.append("")
                lines.append("```cpp")
                lines.append(f"// {event_name}")
                lines.append("```")
                lines.append("")
                lines.append("**Execution Chain:**")
                lines.append("")
                lines.append(" -> ".join(chain))
                lines.append("")

    def _render_functions(self, lines: list[str], ir: PackageIR) -> None:
        """渲染 Functions 章节 — 每个蓝图函数一个子章节，含签名、参数、C++ 代码。"""
        # 收集所有函数：反编译函数 + 蓝图函数元数据（去重）
        func_map: dict[str, dict] = {}

        for func in ir.decompiled_functions:
            func_map[func.name] = {
                "name": func.name,
                "signature": func.signature,
                "cpp_code": func.cpp_code,
                "parameters": func.parameters,
                "return_type": func.return_type,
            }

        if ir.blueprint and ir.blueprint.functions:
            for func in ir.blueprint.functions:
                if func.name not in func_map:
                    func_map[func.name] = {
                        "name": func.name,
                        "signature": "",
                        "cpp_code": "",
                        "parameters": [
                            {"name": p["name"], "param_type": p["param_type"], "default_value": p.get("default_value")}
                            for p in func.parameters
                        ],
                        "return_type": func.return_type,
                    }

        if not func_map:
            return

        lines.append("## Functions")
        lines.append("")

        for func_info in func_map.values():
            lines.append(f"### {func_info['name']}")
            lines.append("")

            # 签名
            if func_info["signature"]:
                lines.append(f"**Signature:** `{func_info['signature']}`")
            else:
                params = func_info["parameters"]
                param_strs = []
                for p in params:
                    ptype = p.get("param_type", "")
                    pname = p.get("name", "")
                    default = p.get("default_value")
                    if default is not None:
                        param_strs.append(f"{ptype} {pname} = {default}")
                    else:
                        param_strs.append(f"{ptype} {pname}")
                sig = f"{func_info['return_type']} {func_info['name']}({', '.join(param_strs)})"
                lines.append(f"**Signature:** `{sig}`")
            lines.append("")

            # 参数列表
            params = func_info["parameters"]
            if params:
                lines.append("| Parameter | Type | Default |")
                lines.append("|-----------|------|---------|")
                for p in params:
                    ptype = p.get("param_type", "")
                    pname = p.get("name", "")
                    default = p.get("default_value")
                    default_str = str(default) if default is not None else "-"
                    lines.append(f"| {_escape_md_cell(pname)} | {_escape_md_cell(ptype)} | {_escape_md_cell(default_str)} |")
                lines.append("")

            # C++ 实现代码块
            if func_info["cpp_code"] and func_info["cpp_code"].strip():
                lines.append("```cpp")
                lines.append(func_info["cpp_code"].strip())
                lines.append("```")
                lines.append("")

    def _render_variables(self, lines: list[str], ir: PackageIR) -> None:
        """渲染 Variables 章节 — 变量表格，包含名称、类型、默认值。"""
        if not ir.variables:
            return

        lines.append("## Variables")
        lines.append("")
        lines.append("| Name | Type | Default Value |")
        lines.append("|------|------|---------------|")
        for var in ir.variables:
            default_str = _escape_md_cell(str(var.default_value)) if var.default_value is not None else "-"
            lines.append(f"| {_escape_md_cell(var.name)} | {_escape_md_cell(var.type)} | {default_str} |")
        lines.append("")

    def _find_decompiled(self, ir: PackageIR, name: str):
        """根据函数名查找反编译函数。"""
        for func in ir.decompiled_functions:
            if func.name == name:
                return func
        return None

    def _gen_event_signature(self, event) -> str:
        """从 BlueprintEventIR 生成 C++ override 签名。"""
        params = []
        for p in event.parameters:
            if p.get("is_input"):
                params.append(f"{p.get('param_type', '')} {p.get('name', '')}")
        param_str = ", ".join(params)
        return f"void {event.name}({param_str}) override"

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
