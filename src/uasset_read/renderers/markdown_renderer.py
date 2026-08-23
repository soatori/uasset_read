from __future__ import annotations

"""Markdown + Mermaid flow chart renderer."""

from typing import TYPE_CHECKING

from uasset_read.renderers.base import (
    IRenderer,
    RenderOptions,
    is_blueprint_export,
    EDITOR_PROPERTY_NAMES,
    filter_editor_items,
    filter_variables,
)
from uasset_read.renderers import register_renderer
from uasset_read.constants import decode_package_flags

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


def _escape_md_cell(text: str) -> str:
    """Escape characters that would break Markdown table formatting."""
    return str(text).replace("|", "\\|").replace("\n", " ")


def _escape_mermaid_label(text: str) -> str:
    """Escape special characters in Mermaid labels to prevent graph parsing failures."""
    s = str(text)
    for ch in ('"', "[", "]", "{", "}"):
        s = s.replace(ch, f"#{ord(ch)};")
    return s


def _format_transforms(transforms) -> str:
    """Format Transform dict into a compact string."""
    if not transforms:
        return "Identity"
    parts = []
    loc = (
        transforms.get("relative_location")
        if isinstance(transforms, dict)
        else getattr(transforms, "relative_location", None)
    )
    rot = (
        transforms.get("relative_rotation")
        if isinstance(transforms, dict)
        else getattr(transforms, "relative_rotation", None)
    )
    scale = (
        transforms.get("relative_scale")
        if isinstance(transforms, dict)
        else getattr(transforms, "relative_scale", None)
    )
    if loc:
        x = getattr(loc, "x", 0) if not isinstance(loc, dict) else loc.get("x", 0)
        y = getattr(loc, "y", 0) if not isinstance(loc, dict) else loc.get("y", 0)
        z = getattr(loc, "z", 0) if not isinstance(loc, dict) else loc.get("z", 0)
        parts.append(f"Loc({x:.1f},{y:.1f},{z:.1f})")
    if rot:
        p = (
            getattr(rot, "pitch", 0)
            if not isinstance(rot, dict)
            else rot.get("pitch", 0)
        )
        y = getattr(rot, "yaw", 0) if not isinstance(rot, dict) else rot.get("yaw", 0)
        r = getattr(rot, "roll", 0) if not isinstance(rot, dict) else rot.get("roll", 0)
        parts.append(f"Rot({p:.1f},{y:.1f},{r:.1f})")
    if scale:
        x = getattr(scale, "x", 1) if not isinstance(scale, dict) else scale.get("x", 1)
        y = getattr(scale, "y", 1) if not isinstance(scale, dict) else scale.get("y", 1)
        z = getattr(scale, "z", 1) if not isinstance(scale, dict) else scale.get("z", 1)
        parts.append(f"Scale({x:.1f},{y:.1f},{z:.1f})")
    return " ".join(parts) if parts else "Identity"


def _collect_input_actions(ir) -> list[tuple[str, list[dict]]]:
    """Collect Enhanced Input Action bindings from PackageIR.

    Supports two sources:
    1. K2Node_EnhancedInputAction nodes in graphs (prefer new fields)
    2. InpActEvt_*_K2Node_EnhancedInputActionEvent_* function names in decompiled_functions (fallback)
    """
    import re
    input_actions: list[tuple[str, list[dict]]] = []
    seen_actions: set[str] = set()

    # Source 1: nodes in graphs (prefer new fields)
    for export in ir.exports:
        for graph in export.graphs:
            for node in graph.nodes:
                if node.node_class == "K2Node_EnhancedInputAction":
                    # Use new fields
                    path = node.input_action_path or "?"
                    triggers = node.trigger_events or []

                    if path not in seen_actions:
                        seen_actions.add(path)
                        input_actions.append((path, triggers))

    # Source 2: function names in decompiled_functions (fallback path)
    # Format: InpActEvt_IA_Jump_K2Node_EnhancedInputActionEvent_2
    pattern = re.compile(r'^InpActEvt_(.+)_K2Node_EnhancedInputActionEvent')
    for func in (ir.decompiled_functions or []):
        match = pattern.match(func.name)
        if match:
            action_name = match.group(1)
            if action_name not in seen_actions:
                seen_actions.add(action_name)
                # Fallback: parse from function name, no detailed info available
                input_actions.append((action_name, []))

    return input_actions


class MarkdownRenderer(IRenderer):
    """Markdown + Mermaid flow chart renderer."""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        # If hex_view is enabled and IR has hex_view data, return hex view format
        if options.hex_view and ir.debug and ir.debug.hex_view:
            from uasset_read.debug.hex_view import format_hex_view
            result = format_hex_view(ir.debug.hex_view)
            if ir.debug.hex_view_truncated_count > 0:
                result += (
                    f"\n\n> **Note**: {ir.debug.hex_view_truncated_count} hex view entries "
                    f"dropped due to buffer size limit."
                )
            return result

        lines: list[str] = []

        # Title
        asset_name = ir.header.package_name.split("/")[-1] if "/" in ir.header.package_name else ir.header.package_name
        lines.append(f"# {asset_name}")
        lines.append("")

        # Overview table
        lines.append("## Asset Overview")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| Package | {_escape_md_cell(ir.header.package_name)} |")
        lines.append(f"| Class | {_escape_md_cell(ir.header.package_class)} |")
        flag_names = ", ".join(decode_package_flags(ir.header.package_flags))
        lines.append(f"| Flags | {ir.header.package_flags} ({flag_names}) |")
        lines.append(f"| Exports | {ir.header.total_export_count} |")
        lines.append(f"| Imports | {ir.header.total_import_count} |")
        lines.append(f"| UE Version | {_escape_md_cell(ir.header.ue_version)} |")
        lines.append("")

        # === Status / Errors / Warnings ===
        self._render_status_section(lines, ir)

        # === Opaque Classes ===
        opaque_count = sum(
            1 for e in ir.exports if getattr(e, "parse_status", None) == "opaque"
        )
        if opaque_count > 0:
            lines.append(f"\n### Opaque Classes ({opaque_count})\n")
            opaque_classes = {}
            for export in ir.exports:
                if getattr(export, "parse_status", None) == "opaque":
                    cls = getattr(export, "object_class", "unknown")
                    opaque_classes[cls] = opaque_classes.get(cls, 0) + 1
            for cls, count in sorted(opaque_classes.items(), key=lambda x: -x[1]):
                lines.append(f"- {cls}: {count}")

        # === Blueprint Details (blueprint assets only) ===
        if ir.blueprint:
            lines.append("## Blueprint Details")
            lines.append("| Field | Value |")
            lines.append("|-------|-------|")
            if ir.blueprint.parent_class:
                lines.append(
                    f"| Parent Class | {_escape_md_cell(ir.blueprint.parent_class)} |"
                )
            if ir.blueprint.description:
                lines.append(
                    f"| Description | {_escape_md_cell(ir.blueprint.description)} |"
                )
            if ir.blueprint.interfaces:
                ifaces = ", ".join(i.get("name", "") for i in ir.blueprint.interfaces)
                lines.append(f"| Interfaces | {_escape_md_cell(ifaces)} |")
            var_count = len(ir.variables) if ir.variables else 0
            comp_count = (
                sum(1 for c in ir.blueprint.components)
                if ir.blueprint.components
                else 0
            )
            lines.append(
                f"| Variables | {var_count} ({comp_count} components, {max(0, var_count - comp_count)} regular) |"
            )
            lines.append("")

            # === Component Hierarchy Mermaid Diagram ===
            if ir.blueprint.components:
                lines.append("### Component Hierarchy")
                lines.append("")
                lines.append("```mermaid")
                lines.append("graph TD")
                root_name = asset_name.replace(" ", "_")
                lines.append(f'  {root_name}["{asset_name}"]')
                for comp in ir.blueprint.components:
                    comp_name = (
                        comp.get("name", "Unknown")
                        if isinstance(comp, dict)
                        else getattr(comp, "name", "Unknown")
                    )
                    comp_class = (
                        comp.get("class", "Unknown")
                        if isinstance(comp, dict)
                        else getattr(comp, "class_name", "Unknown")
                    )
                    safe_name = "".join(
                        c if c.isalnum() or c == "_" else "_" for c in comp_name
                    )
                    safe_label = _escape_mermaid_label(
                        f"{comp_name}<br/><i>{comp_class}</i>"
                    )
                    lines.append(f'  {root_name} --> {safe_name}["{safe_label}"]')
                lines.append("```")
                lines.append("")

                # Component details table
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
                    lines.append(
                        f"| {_escape_md_cell(comp_name)} | {_escape_md_cell(comp_class)} | {transform_str} |"
                    )
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
                        for trigger in triggers:
                            trigger_name = trigger.get("trigger_name", "?")
                            event_type = trigger.get("event_type", "?")
                            if first_trigger:
                                lines.append(
                                    f"| {action_name} | {trigger_name} | {event_type} |"
                                )
                                first_trigger = False
                            else:
                                lines.append(f"| | {trigger_name} | {event_type} |")
                    else:
                        lines.append(f"| {action_name} | — | — |")
                lines.append("")

        # Exports — only show blueprint exports, filter editor node class exports (consistent with JSON renderer)
        blueprint_exports = [
            e for e in filter_editor_items(ir.exports) if is_blueprint_export(e)
        ]
        if blueprint_exports:
            lines.append("## Exports")
            lines.append("| Name | Class | Size | Properties |")
            lines.append("|------|-------|------|------------|")
            for export in blueprint_exports:
                prop_count = len(export.properties) if export.properties else 0
                lines.append(
                    f"| {_escape_md_cell(export.object_name)} "
                    f"| {_escape_md_cell(export.object_class)} "
                    f"| {export.serial_size} "
                    f"| {prop_count} |"
                )
            lines.append("")

        # Graph + Mermaid
        for export in blueprint_exports:
            for graph in export.graphs:
                lines.append(f"## Graph: {graph.graph_name}")
                lines.append(f"- **Nodes**: {len(graph.nodes)}")
                if graph.execution_chains:
                    lines.append(
                        f"- **Execution Chains**: {len(graph.execution_chains)}"
                    )
                if graph.subgraphs:
                    lines.append(f"- **Subgraphs**: {len(graph.subgraphs)}")
                if graph.graph_type:
                    lines.append(f"- **Type**: {graph.graph_type}")
                lines.append("")

                if graph.nodes or graph.subgraphs:
                    lines.append("```mermaid")
                    lines.append("graph TD")
                    self._render_mermaid_nodes(lines, graph)
                    lines.append("```")
                    lines.append("")

            # Property details (filter editor layout properties, consistent with JSON renderer)
            self._render_export_properties(lines, export)

            # asset_type_data: SoundWave, SoundCue, DataTable 等 handler 提取的语义数据
            atd = getattr(export, "asset_type_data", None)
            if atd:
                self._render_asset_type_data(lines, atd)

        # === Event Graph ===
        self._render_event_graph(lines, ir)

        # === Functions ===
        self._render_functions(lines, ir)

        # === Variables ===
        self._render_variables(lines, ir)

        # === Asset Registry Data ===
        self._render_asset_registry(lines, ir)

        # === Animation Data ===
        self._render_anim_data(lines, ir)

        # === Material Data ===
        self._render_material_section(ir, lines)

        # === Diagnostics ===
        self._render_diagnostics(lines, ir)

        return "\n".join(lines)

    def _render_status_section(self, lines: list[str], ir: PackageIR) -> None:
        """Render Status / Errors / Warnings section."""
        dd = ir.diagnostics_data
        if not dd or dd.status == "success":
            return

        # Status
        lines.append("## Status")
        lines.append("")
        status_label = dd.status.upper()
        if dd.status_message:
            lines.append(f"**{status_label}**: {_escape_md_cell(dd.status_message)}")
        else:
            lines.append(f"**{status_label}**")
        lines.append("")

        # Errors
        if dd.errors:
            lines.append("### Errors")
            lines.append("")
            for err in dd.errors:
                lines.append(f"- {_escape_md_cell(err)}")
            lines.append("")

        # Warnings
        if dd.warnings:
            lines.append("### Warnings")
            lines.append("")
            for warn in dd.warnings:
                lines.append(f"- {_escape_md_cell(warn)}")
            lines.append("")

    def _render_event_graph(self, lines: list[str], ir: PackageIR) -> None:
        """Render Event Graph section — one subsection per event function, including C++ code blocks."""
        events = ir.blueprint.events if ir.blueprint and ir.blueprint.events else []
        if not events and not ir.execution_chains:
            return

        lines.append("## Event Graph")
        lines.append("")

        # Use event info from execution_chains
        chains_by_event: dict[str, list[str]] = {}
        for chain in ir.execution_chains:
            chains_by_event.setdefault(chain.event, []).extend(chain.chain)

        # Deduplicated event names
        seen_events: set[str] = set()
        for event in events:
            if event.name in seen_events:
                continue
            seen_events.add(event.name)

            lines.append(f"### {event.name}")
            lines.append("")

            # Find matching decompiled function
            decompiled = self._find_decompiled(ir, event.name)
            if decompiled:
                warn = self._provenance_warning(decompiled)
                if warn:
                    lines.append(warn)
                    lines.append("")
                lines.append("```cpp")
                lines.append(decompiled.signature)
                lines.append("{")
                if decompiled.cpp_code.strip():
                    for code_line in decompiled.cpp_code.strip().splitlines():
                        lines.append(f"    {code_line}")
                lines.append("}")
                lines.append("```")
            else:
                # Generate event override signature
                lines.append("```cpp")
                lines.append(self._gen_event_signature(event))
                lines.append("{")
                lines.append("    // Event handler")
                lines.append("}")
                lines.append("```")
            lines.append("")

            # Execution chain
            chain = chains_by_event.get(event.name, [])
            if chain:
                lines.append("**Execution Chain:**")
                lines.append("")
                lines.append(" -> ".join(chain))
                lines.append("")

        # Handle events in execution_chains not listed in events
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
        """Render Functions section — one subsection per blueprint function with signature, parameters, C++ code."""
        # Decompiled functions are authoritative when available.  Blueprint
        # metadata is a fallback for assets with no decompiled functions.
        func_map: dict[str, dict] = {}

        for func in ir.decompiled_functions:
            func_map[func.name] = {
                "name": func.name,
                "signature": func.signature,
                "cpp_code": func.cpp_code,
                "parameters": func.parameters,
                "return_type": func.return_type,
                "local_variables": func.local_variables,
                "bytecode_confidence": func.bytecode_confidence,
                "bytecode_status": func.bytecode_status,
                "translation_status": func.translation_status,
                "bytecode_source": func.bytecode_source,
                "logic_source": func.logic_source,
                "warnings": func.warnings,
                "fallback_reasons": func.fallback_reasons,
                "error_code": getattr(func, "error_code", None),
                "error_message": getattr(func, "error_message", None),
                "script_metrics": getattr(func, "script_metrics", None),
            }

        if not func_map and ir.blueprint and ir.blueprint.functions:
            for func in ir.blueprint.functions:
                if func.name not in func_map:
                    func_map[func.name] = {
                        "name": func.name,
                        "signature": "",
                        "cpp_code": "",
                        "parameters": [
                            {
                                "name": p["name"],
                                "param_type": p["param_type"],
                                "default_value": p.get("default_value"),
                            }
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

            # Signature
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

            # Status line
            bs = func_info.get("bytecode_status", "unknown")
            ts = func_info.get("translation_status", "not_applicable")
            lines.append(f"**Status:** bytecode={bs}, translation={ts}")
            lines.append("")

            # Parameter list
            params = func_info["parameters"]
            if params:
                lines.append("| Parameter | Type | Default |")
                lines.append("|-----------|------|---------|")
                for p in params:
                    ptype = p.get("param_type", "")
                    pname = p.get("name", "")
                    default = p.get("default_value")
                    default_str = str(default) if default is not None else "-"
                    lines.append(
                        f"| {_escape_md_cell(pname)} | {_escape_md_cell(ptype)} | {_escape_md_cell(default_str)} |"
                    )
                lines.append("")

            # Local variables are function-scoped and optional: only render
            # data actually recovered from this function's bytecode.
            local_variables = func_info.get("local_variables", [])
            if local_variables:
                lines.append("**Local Variables:**")
                lines.append("")
                lines.append("| Local | Type |")
                lines.append("|-------|------|")
                for local in local_variables:
                    lines.append(
                        f"| {_escape_md_cell(local.get('name', ''))} | "
                        f"{_escape_md_cell(local.get('type', ''))} |"
                    )
                lines.append("")

            warn = self._provenance_warning(func_info)
            if warn:
                lines.append(warn)
                lines.append("")

            # Script metrics
            script_metrics = func_info.get("script_metrics")
            if script_metrics is not None:
                lines.append("**Script Metrics:**")
                lines.append("")
                lines.append("| Metric | Value |")
                lines.append("|--------|-------|")
                lines.append(f"| bytecode_buffer_size | {script_metrics.bytecode_buffer_size} |")
                lines.append(f"| serialized_script_size | {script_metrics.serialized_script_size} |")
                lines.append(f"| serialized_bytes_consumed | {script_metrics.serialized_bytes_consumed} |")
                lines.append(f"| bytecode_bytes_consumed | {script_metrics.bytecode_bytes_consumed} |")
                lines.append("")

            # C++ implementation code block
            if func_info["cpp_code"] and func_info["cpp_code"].strip():
                lines.append("```cpp")
                lines.append(func_info["cpp_code"].strip())
                lines.append("```")
                lines.append("")

    def _render_variables(self, lines: list[str], ir: PackageIR) -> None:
        """Render Variables section — variable table with name, type, default value."""
        if not ir.variables:
            return

        # Filter editor-internal variables (consistent with JSON renderer)
        filtered_variables = filter_variables(ir.variables)
        if not filtered_variables:
            return

        lines.append("## Variables")
        lines.append("")
        lines.append("| Name | Type | Default Value |")
        lines.append("|------|------|---------------|")
        for var in filtered_variables:
            default_str = (
                _escape_md_cell(str(var.default_value))
                if var.default_value is not None
                else "-"
            )
            lines.append(
                f"| {_escape_md_cell(var.name)} | {_escape_md_cell(var.type)} | {default_str} |"
            )
        lines.append("")

    def _render_asset_registry(self, lines: list[str], ir: PackageIR) -> None:
        """Render Asset Registry Data section — asset metadata tags."""
        data = ir.dependencies.asset_registry_data if ir.dependencies else None
        if not data:
            return

        objects = data.get("objects", [])
        if not objects:
            return

        lines.append("## Asset Registry Data")
        lines.append("")

        for obj in objects:
            obj_path = obj.get("object_path", "")
            obj_class = obj.get("object_class_name", "")
            tags = obj.get("tags", {})

            lines.append(f"### {_escape_md_cell(obj_path)}")
            lines.append("")
            lines.append(f"**Class:** `{_escape_md_cell(obj_class)}`")
            lines.append("")

            if tags:
                lines.append("| Tag | Value |")
                lines.append("|-----|-------|")
                for key, value in tags.items():
                    lines.append(
                        f"| {_escape_md_cell(key)} | {_escape_md_cell(value)} |"
                    )
                lines.append("")

    def _render_anim_data(self, lines: list[str], ir: PackageIR) -> None:
        """Render animation data section — AnimBlueprint, AnimSequence, AnimMontage."""
        anim = ir.animation
        if not anim:
            return

        # AnimBlueprint
        if anim.anim_blueprint:
            lines.append("## Animation Blueprint")
            lines.append("")
            if anim.anim_blueprint.target_skeleton:
                lines.append(
                    f"**Target Skeleton**: `{anim.anim_blueprint.target_skeleton}`"
                )
                lines.append("")
            if anim.anim_blueprint.sync_group_names:
                lines.append(
                    f"**Sync Groups**: {', '.join(anim.anim_blueprint.sync_group_names)}"
                )
                lines.append("")
            if anim.anim_blueprint.graph_asset_player_info:
                lines.append("### Graph Asset Player Info")
                lines.append("")
                lines.append("| Key | Value |")
                lines.append("|-----|-------|")
                for key, value in anim.anim_blueprint.graph_asset_player_info.items():
                    lines.append(
                        f"| {_escape_md_cell(key)} | {_escape_md_cell(value)} |"
                    )
                lines.append("")
            if anim.anim_blueprint.graph_blend_options:
                lines.append("### Graph Blend Options")
                lines.append("")
                lines.append("| Key | Value |")
                lines.append("|-----|-------|")
                for key, value in anim.anim_blueprint.graph_blend_options.items():
                    lines.append(
                        f"| {_escape_md_cell(key)} | {_escape_md_cell(value)} |"
                    )
                lines.append("")
            if anim.anim_blueprint.anim_node_data:
                lines.append("### Anim Node Data")
                lines.append("")
                for idx, node_data in enumerate(anim.anim_blueprint.anim_node_data):
                    lines.append(f"**Node {idx}**:")
                    lines.append("")
                    if isinstance(node_data, dict):
                        for key, value in node_data.items():
                            lines.append(f"- **{key}**: {value}")
                    else:
                        lines.append(f"- {node_data}")
                    lines.append("")
            for sm in anim.anim_blueprint.baked_state_machines:
                lines.append(f"### State Machine: {sm.machine_name}")
                lines.append("")
                lines.append("| State | Root Node | Conduit |")
                lines.append("|-------|-----------|---------|")
                for state in sm.states:
                    conduit = "Yes" if state.b_is_a_conduit else "No"
                    lines.append(
                        f"| {state.state_name} | #{state.state_root_node_index} | {conduit} |"
                    )
                lines.append("")
            if anim.anim_blueprint.anim_notifies:
                lines.append("### Anim Notifies")
                lines.append("")
                lines.append("| Name | Class | Trigger Offset | Duration |")
                lines.append("|------|-------|---------------|----------|")
                for notify in anim.anim_blueprint.anim_notifies:
                    lines.append(
                        f"| {notify.notify_name} | {notify.notify_class or '-'} | {notify.trigger_time_offset} | {notify.duration} |"
                    )
                lines.append("")

        # AnimSequence
        if anim.anim_sequence:
            lines.append("## Animation Sequence")
            lines.append("")
            if anim.anim_sequence.target_skeleton:
                lines.append(
                    f"**Target Skeleton**: `{anim.anim_sequence.target_skeleton}`"
                )
            if anim.anim_sequence.sequence_length:
                lines.append(
                    f"**Sequence Length**: {anim.anim_sequence.sequence_length:.2f}s"
                )
            if anim.anim_sequence.rate_scale != 1.0:
                lines.append(f"**Rate Scale**: {anim.anim_sequence.rate_scale}")
            if anim.anim_sequence.additive_anim_type:
                lines.append(
                    f"**Additive Type**: {anim.anim_sequence.additive_anim_type}"
                )
            if anim.anim_sequence.notifies:
                lines.append("")
                lines.append("### Anim Notifies")
                lines.append("")
                lines.append("| Name | Class | Trigger Offset | Duration |")
                lines.append("|------|-------|---------------|----------|")
                for notify in anim.anim_sequence.notifies:
                    lines.append(
                        f"| {notify.notify_name} | {notify.notify_class or '-'} | {notify.trigger_time_offset} | {notify.duration} |"
                    )
            if anim.anim_sequence.float_curve_names:
                lines.append("")
                lines.append(
                    f"**Float Curves**: {', '.join(anim.anim_sequence.float_curve_names)}"
                )
            lines.append(
                f"**Has Compressed Data**: {anim.anim_sequence.has_compressed_data}"
            )
            lines.append("")

        # AnimMontage
        if anim.anim_montage:
            lines.append("## Animation Montage")
            lines.append("")
            if anim.anim_montage.blend_mode_in:
                lines.append(f"**Blend In Mode**: {anim.anim_montage.blend_mode_in}")
            if anim.anim_montage.blend_mode_out:
                lines.append(f"**Blend Out Mode**: {anim.anim_montage.blend_mode_out}")
            if anim.anim_montage.blend_in_option:
                lines.append(
                    f"**Blend In Option**: {anim.anim_montage.blend_in_option}"
                )
            if anim.anim_montage.blend_out_option:
                lines.append(
                    f"**Blend Out Option**: {anim.anim_montage.blend_out_option}"
                )
            if anim.anim_montage.sync_group:
                lines.append(f"**Sync Group**: {anim.anim_montage.sync_group}")
            if anim.anim_montage.rate_scale != 1.0:
                lines.append(f"**Rate Scale**: {anim.anim_montage.rate_scale}")
            if anim.anim_montage.composite_sections:
                lines.append("")
                lines.append("### Composite Sections")
                lines.append("")
                for i, section in enumerate(anim.anim_montage.composite_sections):
                    lines.append(f"{i}. {section}")
            if anim.anim_montage.slot_anim_tracks:
                lines.append("")
                lines.append("### Slot Anim Tracks")
                lines.append("")
                for i, track in enumerate(anim.anim_montage.slot_anim_tracks):
                    lines.append(f"{i}. {track}")
            if anim.anim_montage.branching_point_markers:
                lines.append("")
                lines.append("### Branching Point Markers")
                lines.append("")
                for marker in anim.anim_montage.branching_point_markers:
                    lines.append(f"- {marker}")
            if anim.anim_montage.notifies:
                lines.append("")
                lines.append("### Anim Notifies")
                lines.append("")
                lines.append("| Name | Class | Trigger Offset | Duration |")
                lines.append("|------|-------|---------------|----------|")
                for notify in anim.anim_montage.notifies:
                    lines.append(
                        f"| {notify.notify_name} | {notify.notify_class or '-'} | {notify.trigger_time_offset} | {notify.duration} |"
                    )
            if anim.anim_montage.float_curve_names:
                lines.append("")
                lines.append(
                    f"**Float Curves**: {', '.join(anim.anim_montage.float_curve_names)}"
                )
            lines.append("")

    def _render_diagnostics(self, lines: list[str], ir: PackageIR) -> None:
        """Render diagnostics section — grouped by severity with icons."""
        # Show section header if there are diagnostics or truncation to report
        dd = ir.diagnostics_data
        has_truncation = dd and dd.diagnostics_truncated_count > 0
        if not ir.diagnostics and not has_truncation:
            return

        severity_icons = {
            "critical": "🔴",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
        }

        # Group by severity
        by_severity: dict[str, list] = {}
        for diag in ir.diagnostics:
            d = diag.to_dict() if hasattr(diag, "to_dict") else {}
            severity = d.get("severity", "info")
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(d)

        lines.append("## Diagnostics")
        lines.append("")

        # Show truncation notice if any diagnostics were dropped
        if has_truncation:
            lines.append(
                f"> **Note**: {dd.diagnostics_truncated_count} diagnostics "
                f"dropped due to buffer size limit."
            )
            lines.append("")

        for severity in ["critical", "error", "warning", "info"]:
            if severity not in by_severity:
                continue
            diagnostics = by_severity[severity]
            icon = severity_icons.get(severity, "")
            lines.append(f"### {icon} {severity.upper()} ({len(diagnostics)})")
            lines.append("")
            lines.append("| Type | Module | Object | Field | Error |")
            lines.append("|------|------|--------|------|----------|")
            for d in diagnostics:
                kind = _escape_md_cell(d.get("kind", ""))
                module = _escape_md_cell(d.get("module", ""))
                object_name = _escape_md_cell(d.get("object_name", ""))
                field_name = _escape_md_cell(d.get("field", ""))
                error = _escape_md_cell(d.get("error", ""))
                lines.append(
                    f"| {kind} | {module} | {object_name} | {field_name} | {error} |"
                )
            lines.append("")

    def _render_asset_type_data(self, lines: list[str], data: dict) -> None:
        """渲染 asset type handler 提取的语义数据（如 sound 块）。"""
        if not data:
            return
        lines.append("### Asset Type Data")
        lines.append("")
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"**{key}:**")
                lines.append("")
                for k, v in value.items():
                    lines.append(f"- **{k}:** `{v}`")
            else:
                lines.append(f"- **{key}:** `{value}`")
        lines.append("")

    def _render_export_properties(self, lines: list[str], export) -> None:
        """Render export property table."""
        # Filter editor properties (standard output level)
        filtered_props = [
            p for p in (export.properties or []) if p.name not in EDITOR_PROPERTY_NAMES
        ]
        if not filtered_props:
            return

        lines.append("### Properties")
        lines.append("")
        lines.append("| Name | Type | Value |")
        lines.append("|------|------|-------|")
        for prop in filtered_props:
            name = _escape_md_cell(prop.name)
            prop_type = _escape_md_cell(prop.type)
            value = prop.value if prop.value is not None else "null"

            # Truncate long values
            value_str = str(value)
            if len(value_str) > 50:
                value_str = value_str[:50]
            value_str = _escape_md_cell(value_str)

            lines.append(f"| {name} | {prop_type} | {value_str} |")
        lines.append("")

    def _find_decompiled(self, ir: PackageIR, name: str):
        """Find decompiled function by function name."""
        for func in ir.decompiled_functions:
            if func.name == name:
                return func
        return None

    def _provenance_warning(self, func) -> str | None:
        """Generate a Markdown warning block for non-verified decompiled functions.

        Shows status, source, confidence, and degradation reasons.
        Returns None for normal verified bytecode (no warning needed).

        Accepts both DecompiledFunctionIR objects and plain dicts.
        """
        def _get(obj, key, default):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        confidence = _get(func, "bytecode_confidence", "verified")
        if confidence == "verified":
            return None

        status = _get(func, "bytecode_status", "unknown")
        translation = _get(func, "translation_status", "not_applicable")
        source = _get(func, "bytecode_source", "unknown")
        logic = _get(func, "logic_source", "current_asset")
        reasons = _get(func, "fallback_reasons", [])
        error_code = _get(func, "error_code", None)

        parts = [f"status={status}", f"translation={translation}", f"source={source}", f"logic={logic}"]
        if confidence != "verified":
            parts.append(f"confidence={confidence}")
        if error_code:
            parts.append(f"error={error_code}")
        if reasons:
            parts.append(f"reasons={'; '.join(reasons)}")

        lines = ["> [!WARNING]", f"> Function body provenance: {', '.join(parts)}"]
        return "\n".join(lines)

    def _gen_event_signature(self, event) -> str:
        """Generate C++ override signature from BlueprintEventIR."""
        params = []
        for p in event.parameters:
            if p.get("is_input"):
                params.append(f"{p.get('param_type', '')} {p.get('name', '')}")
        param_str = ", ".join(params)
        return f"void {event.name}({param_str}) override"

    def _build_pin_to_node_index(self, graph) -> dict[str, str]:
        """Build Pin GUID -> Node GUID mapping index."""
        pin_to_node: dict[str, str] = {}
        for node in graph.nodes:
            node_guid = node.node_guid
            if not node_guid:
                continue
            for pin in node.pins:
                if pin.pin_guid:
                    pin_to_node[pin.pin_guid] = node_guid
        return pin_to_node

    def _render_mermaid_edges(self, graph, pin_to_node: dict[str, str], indent: int = 0) -> list[str]:
        """Render Mermaid edges, using Node GUID instead of Pin GUID."""
        prefix = "    " * indent
        edge_lines: list[str] = []
        seen_edges: set[tuple[str, str]] = set()

        for node in graph.nodes:
            source_guid = (node.node_guid or "")[:8]
            for pin in node.pins:
                for linked_pin_guid in (pin.linked_to or []):
                    # Convert Pin GUID to Node GUID
                    target_node_guid = pin_to_node.get(linked_pin_guid)

                    # Skip unresolvable Pin references
                    if target_node_guid is None:
                        continue

                    target_guid = target_node_guid[:8]

                    # Skip self-loops
                    if source_guid == target_guid:
                        continue

                    # Deduplicate
                    edge_key = (source_guid, target_guid)
                    if edge_key in seen_edges:
                        continue
                    seen_edges.add(edge_key)

                    edge_lines.append(f"{prefix}    {source_guid} --> {target_guid}")

        return edge_lines

    def _render_mermaid_nodes(self, lines: list[str], graph, indent: int = 0) -> None:
        """Render Mermaid nodes and connections (recursive support for nested subgraphs)."""
        prefix = "    " * indent

        # Define nodes
        for node in graph.nodes:
            label = _escape_mermaid_label(node.node_comment or node.node_class)
            safe_guid = node.node_guid[:8] if node.node_guid else "unknown"
            lines.append(f'{prefix}    {safe_guid}["{label}"]')

        # Define connections (using index to convert Pin GUID -> Node GUID)
        pin_to_node = self._build_pin_to_node_index(graph)
        edge_lines = self._render_mermaid_edges(graph, pin_to_node, indent)
        lines.extend(edge_lines)

        # Recursively render nested subgraphs
        for subgraph in graph.subgraphs or []:
            sg_name = subgraph.graph_name or "subgraph"
            safe_sg_name = sg_name.replace(" ", "_").replace(".", "_")[:20]
            lines.append(f"{prefix}    subgraph {safe_sg_name}")
            self._render_mermaid_nodes(lines, subgraph, indent + 1)
            lines.append(f"{prefix}    end")

    @property
    def format_name(self) -> str:
        return "markdown"

    def _render_material_section(self, ir: PackageIR, lines: list[str]) -> None:
        """Render Material section in Markdown."""
        if ir.material is None:
            return
        mat = ir.material
        lines.append(f"\n## Material ({mat.material_type})\n")
        if mat.properties:
            lines.append("| Property | Value |")
            lines.append("|----------|-------|")
            for key, val in sorted(mat.properties.items()):
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                lines.append(f"| {key} | {val} |")
            lines.append("")
        if mat.parent:
            lines.append(f"**Parent:** {mat.parent}\n")
        if mat.expressions:
            lines.append("### Expressions\n")
            lines.append("| GUID | Class | Type |")
            lines.append("|------|-------|------|")
            for expr in mat.expressions:
                lines.append(
                    f"| {expr.expression_guid[:8]}... | {expr.expression_class} | {expr.expression_type or ''} |"
                )
            lines.append("")
        if mat.parameters:
            lines.append("### Parameters\n")
            for ptype, params in mat.parameters.items():
                if params:
                    lines.append(f"**{ptype}:** {', '.join(sorted(params.keys()))}\n")
        if mat.data_flow:
            lines.append(f"**Data flow connections:** {len(mat.data_flow)}\n")


register_renderer("markdown", MarkdownRenderer)
