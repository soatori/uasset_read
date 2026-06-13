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


def _format_transforms(transforms) -> str:
    """格式化 Transform 字典为紧凑字符串。"""
    if not transforms:
        return "Identity"
    parts = []
    loc = transforms.get("relative_location") if isinstance(transforms, dict) else getattr(transforms, "relative_location", None)
    rot = transforms.get("relative_rotation") if isinstance(transforms, dict) else getattr(transforms, "relative_rotation", None)
    scale = transforms.get("relative_scale") if isinstance(transforms, dict) else getattr(transforms, "relative_scale", None)
    if loc:
        x = getattr(loc, "x", 0) if not isinstance(loc, dict) else loc.get("x", 0)
        y = getattr(loc, "y", 0) if not isinstance(loc, dict) else loc.get("y", 0)
        z = getattr(loc, "z", 0) if not isinstance(loc, dict) else loc.get("z", 0)
        parts.append(f"Loc({x:.1f},{y:.1f},{z:.1f})")
    if rot:
        p = getattr(rot, "pitch", 0) if not isinstance(rot, dict) else rot.get("pitch", 0)
        y = getattr(rot, "yaw", 0) if not isinstance(rot, dict) else rot.get("yaw", 0)
        r = getattr(rot, "roll", 0) if not isinstance(rot, dict) else rot.get("roll", 0)
        parts.append(f"Rot({p:.1f},{y:.1f},{r:.1f})")
    if scale:
        x = getattr(scale, "x", 1) if not isinstance(scale, dict) else scale.get("x", 1)
        y = getattr(scale, "y", 1) if not isinstance(scale, dict) else scale.get("y", 1)
        z = getattr(scale, "z", 1) if not isinstance(scale, dict) else scale.get("z", 1)
        parts.append(f"Scale({x:.1f},{y:.1f},{z:.1f})")
    return " ".join(parts) if parts else "Identity"


def _collect_input_actions(ir) -> list[tuple[str, dict]]:
    """从 PackageIR 收集 Enhanced Input Action 绑定。

    支持两种来源：
    1. graphs 中的 K2Node_EnhancedInputAction 节点（当前未使用，graphs 通常为空）
    2. decompiled_functions 中的 InpActEvt_*_K2Node_EnhancedInputActionEvent_* 函数名
    """
    import re
    input_actions: list[tuple[str, dict]] = []
    seen_actions: set[str] = set()

    # 来源1: graphs 中的节点（保留兼容）
    for export in ir.exports:
        for graph in export.graphs:
            for node in graph.nodes:
                if node.node_class == "K2Node_EnhancedInputAction":
                    data = node.node_data
                    if isinstance(data, dict):
                        path = data.get("input_action_path", "?")
                        triggers = data.get("trigger_events", {})
                        input_actions.append((path, triggers))

    # 来源2: decompiled_functions 中的函数名
    # 格式: InpActEvt_IA_Jump_K2Node_EnhancedInputActionEvent_2
    pattern = re.compile(r'^InpActEvt_(.+)_K2Node_EnhancedInputActionEvent')
    for func in (ir.decompiled_functions or []):
        match = pattern.match(func.name)
        if match:
            action_name = match.group(1)
            if action_name not in seen_actions:
                seen_actions.add(action_name)
                # 从函数名解析 action path（简化处理）
                input_actions.append((action_name, {}))

    return input_actions


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

        # === Blueprint Details（仅蓝图资产） ===
        if ir.blueprint:
            lines.append("## Blueprint Details")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            if ir.blueprint.parent_class:
                lines.append(f"| Parent Class | {_escape_md_cell(ir.blueprint.parent_class)} |")
            var_count = len(ir.variables) if ir.variables else 0
            comp_count = sum(1 for c in ir.blueprint.components) if ir.blueprint.components else 0
            lines.append(f"| Variables | {var_count} ({comp_count} components, {var_count - comp_count} regular) |")
            lines.append("")

            # === Component Hierarchy Mermaid 图 ===
            if ir.blueprint.components:
                lines.append("### Component Hierarchy")
                lines.append("")
                lines.append("```mermaid")
                lines.append("graph TD")
                root_name = asset_name.replace(" ", "_")
                lines.append(f"  {root_name}[\"{asset_name}\"]")
                for comp in ir.blueprint.components:
                    comp_name = comp.get("name", "Unknown") if isinstance(comp, dict) else getattr(comp, "name", "Unknown")
                    comp_class = comp.get("class", "Unknown") if isinstance(comp, dict) else getattr(comp, "class_name", "Unknown")
                    safe_name = "".join(c if c.isalnum() or c == "_" else "_" for c in comp_name)
                    lines.append(f"  {root_name} --> {safe_name}[\"{comp_name}<br/><i>{comp_class}</i>\"]")
                lines.append("```")
                lines.append("")

                # 组件详情表
                lines.append("| Component | Class | Transform |")
                lines.append("|-----------|-------|-----------|")
                for comp in ir.blueprint.components:
                    if isinstance(comp, dict):
                        comp_name = comp.get("name", "Unknown")
                        comp_class = comp.get("class", "Unknown")
                        transforms = comp.get("transforms", {})
                    else:
                        comp_name = getattr(comp, "name", "Unknown")
                        comp_class = getattr(comp, "class_name", "Unknown")
                        transforms = getattr(comp, "transforms", {}) or {}
                    transform_str = _format_transforms(transforms)
                    lines.append(f"| {_escape_md_cell(comp_name)} | {_escape_md_cell(comp_class)} | {transform_str} |")
                lines.append("")

            # === Input Action Bindings ===
            input_actions = _collect_input_actions(ir)
            if input_actions:
                lines.append("### Input Action Bindings")
                lines.append("")
                lines.append("| Input Action | Trigger | Event Type |")
                lines.append("|--------------|---------|------------|")
                for path, triggers in input_actions:
                    action_name = _escape_md_cell(path)
                    if triggers:
                        first_trigger = True
                        for trigger_name, event_type in triggers.items():
                            if first_trigger:
                                lines.append(f"| {action_name} | {trigger_name} | {event_type} |")
                                first_trigger = False
                            else:
                                lines.append(f"| | {trigger_name} | {event_type} |")
                    else:
                        lines.append(f"| {action_name} | — | — |")
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

        # === 诊断信息 ===
        self._render_diagnostics(lines, ir)

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

    def _render_diagnostics(self, lines: list[str], ir: PackageIR) -> None:
        """渲染诊断信息章节 — 偏移范围诊断表格。"""
        if not ir.diagnostics:
            return

        lines.append("## 诊断信息")
        lines.append("")
        lines.append("| 类型 | 模块 | 对象名 | 字段 | 错误信息 |")
        lines.append("|------|------|--------|------|----------|")
        for diag in ir.diagnostics:
            d = diag.to_dict() if hasattr(diag, "to_dict") else {}
            kind = _escape_md_cell(d.get("kind", ""))
            module = _escape_md_cell(d.get("module", ""))
            object_name = _escape_md_cell(d.get("object_name", ""))
            field_name = _escape_md_cell(d.get("field", ""))
            error = _escape_md_cell(d.get("error", ""))
            lines.append(f"| {kind} | {module} | {object_name} | {field_name} | {error} |")
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
