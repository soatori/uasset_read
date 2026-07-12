from __future__ import annotations

"""文本摘要渲染器 — 人类可读的结构化摘要，适合 Git textconv。

字段排序稳定（sorted），确保同一资产不同版本的输出行号对齐，提升 diff 可读性。

只注册 text 格式。
"""

from typing import IO, TYPE_CHECKING

from uasset_read.renderers.base import IRenderer, RenderOptions, EDITOR_VARIABLE_NAMES, EDITOR_NODE_CLASSES
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


class TextRenderer(IRenderer):
    """文本摘要渲染器。生成人类可读、行稳定的文本摘要。"""

    @property
    def format_name(self) -> str:
        return "text"

    def _build_lines(self, ir: PackageIR, options: RenderOptions) -> list[str]:
        lines: list[str] = []
        h = ir.header
        is_debug = options.output_level == "debug"

        # === 标题行 ===
        lines.append(f"=== {h.package_name} ===")
        lines.append(f"Type: {h.package_class}")
        lines.append(f"Version: {h.ue_version}")
        if h.package_flags:
            lines.append(f"Flags: 0x{h.package_flags:08X}")
        lines.append(f"Exports: {h.total_export_count}")
        lines.append(f"Imports: {h.total_import_count}")
        if h.folder_name:
            lines.append(f"Folder: {h.folder_name}")
        lines.append("")

        # === Import 表 ===
        if ir.imports:
            lines.append("[Imports]")
            for imp in sorted(ir.imports, key=lambda x: getattr(x, "object_name", "") or (x.get("object_name", "") if isinstance(x, dict) else "")):
                name = getattr(imp, "object_name", None) or (imp.get("object_name", "?") if isinstance(imp, dict) else "?")
                cls = getattr(imp, "class_name", None) or (imp.get("object_class", "?") if isinstance(imp, dict) else "?")
                lines.append(f"  {name} ({cls})")
            lines.append("")

        # === Export 表 ===
        if ir.exports:
            lines.append("[Exports]")
            for exp in sorted(ir.exports, key=lambda e: e.index):
                size_str = f" {exp.serial_size} bytes" if exp.serial_size else ""
                lines.append(
                    f"  [{exp.index}] {exp.object_name} ({exp.object_class}){size_str}"
                )
                if exp.parent_class:
                    lines.append(f"      Parent: {exp.parent_class}")
                if exp.parse_status != "success":
                    lines.append(f"      Status: {exp.parse_status}")
            lines.append("")

        # === Linker ===
        if ir.linker:
            lk = ir.linker
            lines.append("[Linker]")
            lines.append(f"  Imports: {len(lk.import_paths)}")
            lines.append(f"  Exports: {len(lk.export_paths)}")
            lines.append("")

        # === Blueprint ===
        if ir.blueprint:
            bp = ir.blueprint
            lines.append("[Blueprint]")
            if bp.parent_class:
                lines.append(f"  Parent Class: {bp.parent_class}")
            if bp.description:
                desc = bp.description.strip()
                if len(desc) > 200:
                    desc = desc[:197] + "..."
                lines.append(f"  Description: {desc}")
            if bp.interfaces:
                lines.append(f"  Interfaces: {len(bp.interfaces)}")
            if bp.functions:
                lines.append("  Functions:")
                for fn in sorted(bp.functions, key=lambda f: f.name):
                    lines.append(f"    - {fn.name}")
                    if fn.parameters:
                        params = ", ".join(
                            p.get("name", "?") for p in sorted(
                                fn.parameters,
                                key=lambda p: p.get("name", ""),
                            )
                        )
                        lines.append(f"      Params: {params}")
            if bp.events:
                lines.append("  Events:")
                for ev in sorted(bp.events, key=lambda e: e.name):
                    lines.append(f"    - {ev.name}")
            if bp.components:
                lines.append(f"  Components: {len(bp.components)}")
            lines.append("")

        # === Variables ===
        if ir.variables:
            # standard 模式下过滤编辑器内部变量
            if is_debug:
                filtered_variables = ir.variables
            else:
                filtered_variables = [
                    v for v in ir.variables
                    if v.name not in EDITOR_VARIABLE_NAMES
                ]
            if filtered_variables:
                lines.append("[Variables]")
                for var in sorted(filtered_variables, key=lambda v: v.name):
                    default = ""
                    if var.default_value:
                        dv = var.default_value
                        if len(dv) > 100:
                            dv = dv[:97] + "..."
                        default = f" = {dv}"
                    lines.append(f"  {var.name}: {var.type}{default}")
                lines.append("")

        # === Decompiled Functions ===
        if ir.decompiled_functions:
            lines.append("[Decompiled Functions]")
            for fn in sorted(ir.decompiled_functions, key=lambda f: f.name):
                sig = fn.signature if fn.signature else fn.name
                lines.append(f"  {sig}")
            lines.append("")

        # === Execution Chains ===
        if ir.execution_chains:
            lines.append("[Execution Chains]")
            for chain in ir.execution_chains:
                nodes = " -> ".join(chain.chain[:5])
                if len(chain.chain) > 5:
                    nodes += f" -> ... ({len(chain.chain)} total)"
                lines.append(f"  {chain.event}: {nodes}")
            lines.append("")

        # === Graphs (per export) ===
        for exp in ir.exports:
            if exp.graphs:
                for g in exp.graphs:
                    # standard 模式下过滤编辑器节点
                    if is_debug:
                        filtered_nodes = g.nodes
                    else:
                        filtered_nodes = [
                            n for n in g.nodes
                            if n.node_class not in EDITOR_NODE_CLASSES
                        ]
                    # 过滤后无节点的图不显示
                    if not filtered_nodes and not is_debug:
                        continue
                    lines.append(f"[Graph: {g.graph_name}]")
                    lines.append(f"  Nodes: {len(filtered_nodes)}")
                    if g.execution_chains:
                        for ec in g.execution_chains[:3]:
                            lines.append(f"  Chain: {' -> '.join(ec)}")
                        if len(g.execution_chains) > 3:
                            lines.append(
                                f"  ... +{len(g.execution_chains) - 3} more chains"
                            )
                    lines.append("")

        # === Animation ===
        if ir.anim_blueprint:
            abp = ir.anim_blueprint
            lines.append("[AnimBlueprint]")
            if abp.baked_state_machines:
                lines.append(f"  State Machines: {len(abp.baked_state_machines)}")
                for sm in abp.baked_state_machines:
                    lines.append(f"    - {sm.machine_name}")
            lines.append("")

        if ir.anim_sequence:
            ans = ir.anim_sequence
            lines.append("[AnimSequence]")
            if ans.notifies:
                lines.append(f"  Notifies: {len(ans.notifies)}")
            lines.append("")

        if ir.anim_montage:
            amt = ir.anim_montage
            lines.append("[AnimMontage]")
            if amt.composite_sections:
                lines.append(f"  Composite Sections: {len(amt.composite_sections)}")
            lines.append("")

        # === Diagnostics ===
        if ir.diagnostics:
            lines.append("[Diagnostics]")
            for diag in ir.diagnostics[:10]:
                if isinstance(diag, dict):
                    lines.append(f"  {diag.get('message', diag)}")
                else:
                    lines.append(f"  {diag}")
            if len(ir.diagnostics) > 10:
                lines.append(f"  ... +{len(ir.diagnostics) - 10} more")
            lines.append("")

        # === Status ===
        if ir.status != "success":
            lines.append(f"Status: {ir.status}")
            if ir.status_message:
                lines.append(f"  Message: {ir.status_message}")
            lines.append("")

        return lines

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        return "\n".join(self._build_lines(ir, options))

    def render_to(self, ir: PackageIR, writer: IO[str], options: RenderOptions | None = None) -> None:
        if options is None:
            options = RenderOptions()
        writer.write("\n".join(self._build_lines(ir, options)))


# 注册
register_renderer("text", TextRenderer)
