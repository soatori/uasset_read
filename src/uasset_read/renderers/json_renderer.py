"""JSON 渲染器 — 递归序列化 PackageIR 为 JSON。

提供两种注册格式：
- json: 完整分析格式，字段最全
- json_summary: 机器可读摘要，精简 exports、省略大体积字段
"""
from __future__ import annotations

import json
import dataclasses
from typing import TYPE_CHECKING, Any

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR

# 输出格式版本号
_OUTPUT_VERSION_FULL = "5.0"
_OUTPUT_VERSION_SUMMARY = "4.0"


class _JSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理 dataclass 等非原生类型。"""

    def default(self, o):
        to_dict = getattr(o, "to_dict", None)
        if callable(to_dict):
            return to_dict()
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, bytes):
            return o.hex()
        return super().default(o)


class JSONRenderer(IRenderer):
    """JSON 渲染器 — 完整分析格式。递归序列化 IR 为 JSON。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        data = {
            "status": {
                "status": ir.status,
                "message": ir.status_message,
                "code": ir.status_code,
            },
            "output_version": _OUTPUT_VERSION_FULL,
            "summary": {
                "package_name": ir.header.package_name,
                "package_class": ir.header.package_class,
                "package_flags": ir.header.package_flags,
                "total_export_count": ir.header.total_export_count,
                "total_import_count": ir.header.total_import_count,
                "ue_version": ir.header.ue_version,
            },
            "name_map": ir.name_map,
            "imports": ir.imports,
            "exports": [self._export_to_dict(e, options) for e in ir.exports],
        }
        if ir.linker is not None:
            data["linker"] = {
                "has_linker": ir.linker.has_linker,
                "import_paths": ir.linker.import_paths,
                "export_paths": ir.linker.export_paths,
            }
        if ir.blueprint is not None:
            data["blueprint"] = self._blueprint_to_dict(ir.blueprint)
        if ir.decompiled_functions:
            data["decompiled_functions"] = [self._decompiled_function_to_dict(f) for f in ir.decompiled_functions]
        if ir.execution_chains:
            data["execution_chains"] = [{"event": c.event, "chain": c.chain} for c in ir.execution_chains]
        if ir.variables:
            data["variables"] = [self._variable_to_dict(v) for v in ir.variables]
        if ir.diagnostics:
            data["diagnostics"] = [d.to_dict() for d in ir.diagnostics]
        if ir.resolved_parent_assets:
            data["resolved_parent_assets"] = ir.resolved_parent_assets
        if ir.logic_sources:
            data["logic_sources"] = ir.logic_sources
        if ir.inherited_blueprint_graphs:
            data["inherited_blueprint_graphs"] = ir.inherited_blueprint_graphs
        if ir.soft_object_paths:
            data["soft_object_paths"] = ir.soft_object_paths
        if ir.soft_package_references:
            data["soft_package_references"] = ir.soft_package_references
        if ir.depends_map:
            data["depends_map"] = ir.depends_map
        if ir.resolved_depends_map:
            data["resolved_depends_map"] = ir.resolved_depends_map
        if ir.asset_registry_data_offset > 0:
            data["asset_registry_data_offset"] = ir.asset_registry_data_offset
        if ir.errors:
            data["errors"] = ir.errors
        if options.include_function_graphs:
            data["function_graphs"] = self._build_function_graphs(ir)
        return json.dumps(data, indent=options.indent, ensure_ascii=False, cls=_JSONEncoder)

    def _export_to_dict(self, export, options: RenderOptions) -> dict[str, Any]:
        d = {
            "index": export.index,
            "object_name": export.object_name,
            "object_class": export.object_class,
            "serial_size": export.serial_size,
            "outer_index_resolved": export.outer_index_resolved,
            "super_index_resolved": export.super_index_resolved,
            "parent_class": export.parent_class,
            "properties": [self._property_to_dict(p) for p in export.properties],
            "graphs": [self._graph_to_dict(g, options) for g in export.graphs],
        }
        if export.bulk_data is not None:
            d["bulk_data"] = export.bulk_data
        if export.asset_type_data is not None:
            d["asset_type_data"] = export.asset_type_data
        if export.parse_status != "success":
            d["parse_status"] = export.parse_status
        if export.fallback_reason:
            d["fallback_reason"] = export.fallback_reason
        if export.error_message:
            d["error_message"] = export.error_message
        if export.ue_export_raw is not None:
            raw = export.ue_export_raw
            d["ue_export_raw"] = {
                "class_index": raw.class_index,
                "super_index": raw.super_index,
                "outer_index": raw.outer_index,
                "template_index": raw.template_index,
                "object_flags": raw.object_flags,
                "serial_offset": raw.serial_offset,
                "package_flags": raw.package_flags,
                "b_forced_export": raw.b_forced_export,
                "b_not_for_client": raw.b_not_for_client,
                "b_not_for_server": raw.b_not_for_server,
                "b_is_inherited_instance": raw.b_is_inherited_instance,
                "b_not_always_loaded_for_editor_game": raw.b_not_always_loaded_for_editor_game,
                "b_is_asset": raw.b_is_asset,
                "b_generate_public_hash": raw.b_generate_public_hash,
                "script_serialization_start_offset": raw.script_serialization_start_offset,
                "script_serialization_end_offset": raw.script_serialization_end_offset,
            }
            if raw.guid:
                d["ue_export_raw"]["guid"] = raw.guid
        if export.diagnostics:
            d["diagnostics"] = export.diagnostics
        return d

    def _property_to_dict(self, prop) -> dict[str, Any]:
        return {"name": prop.name, "type": prop.type, "value": prop.value, "array_index": prop.array_index, "guid": prop.guid}

    def _graph_to_dict(self, graph, options: RenderOptions) -> dict[str, Any]:
        return {"graph_name": graph.graph_name, "graph_guid": graph.graph_guid, "nodes": [self._node_to_dict(n) for n in graph.nodes], "execution_chains": graph.execution_chains}

    def _node_to_dict(self, node) -> dict[str, Any]:
        d = {"node_guid": node.node_guid, "node_class": node.node_class, "node_comment": node.node_comment, "pins": [self._pin_to_dict(p) for p in node.pins], "execution_flow": node.execution_flow}
        if node.macro_expansion is not None:
            d["macro_expansion"] = node.macro_expansion
        return d

    def _pin_to_dict(self, pin) -> dict[str, Any]:
        return {"pin_name": pin.pin_name, "pin_type": pin.pin_type, "pin_type_value": pin.pin_type_value, "linked_to": pin.linked_to, "direction": pin.direction, "default_value": pin.default_value}

    def _blueprint_to_dict(self, blueprint) -> dict[str, Any]:
        """序列化 BlueprintIR 为字典（完整元数据）。"""
        d: dict[str, Any] = {"parent_class": blueprint.parent_class}
        if blueprint.functions:
            d["functions"] = [self._function_to_dict(f) for f in blueprint.functions]
        if blueprint.events:
            d["events"] = [self._event_to_dict(e) for e in blueprint.events]
        if blueprint.components:
            d["components"] = blueprint.components
        return d

    def _variable_to_dict(self, var) -> dict[str, Any]:
        """序列化 VariableIR 为字典（完整元数据，省略默认值字段）。"""
        d: dict[str, Any] = {"name": var.name, "type": var.type, "kind": var.kind}
        if var.default_value is not None:
            d["default_value"] = var.default_value
        if var.guid:
            d["guid"] = var.guid
        if var.category:
            d["category"] = var.category
        if var.property_flags:
            d["property_flags"] = var.property_flags
        if var.replication_condition:
            d["replication_condition"] = var.replication_condition
        if var.rep_notify_func:
            d["rep_notify_func"] = var.rep_notify_func
        if var.friendly_name:
            d["friendly_name"] = var.friendly_name
        if var.metadata:
            d["metadata"] = var.metadata
        if var.flags_labels:
            d["flags_labels"] = var.flags_labels
        if var.edit_condition:
            d["edit_condition"] = var.edit_condition
        # 布尔 flags 只在 True 时输出，减少噪音
        for flag in (
            "is_edit_anywhere", "is_visible_anywhere", "is_blueprint_read_only",
            "is_transient", "is_replicated", "is_rep_notify",
            "is_expose_on_spawn", "is_save_game",
        ):
            if getattr(var, flag, False):
                d[flag] = True
        return d

    def _function_to_dict(self, func) -> dict[str, Any]:
        """序列化 BlueprintFunctionIR 为字典（完整元数据 + 实现关联）。"""
        d: dict[str, Any] = {
            "name": func.name,
            "return_type": func.return_type,
            "parameters": func.parameters,
        }
        if func.function_flags:
            d["function_flags"] = func.function_flags
        for flag in (
            "is_pure", "is_blueprint_callable", "is_const", "is_static",
            "is_net", "is_net_reliable", "is_blueprint_private",
        ):
            if getattr(func, flag, False):
                d[flag] = True
        if func.access_specifier and func.access_specifier != "Public":
            d["access_specifier"] = func.access_specifier
        if func.meta_data:
            d["meta_data"] = func.meta_data
        # 实现关联
        if func.implementation:
            d["implementation"] = func.implementation
        if func.function_graph:
            d["function_graph"] = func.function_graph
        d["implementation_status"] = func.implementation_status
        return d

    def _event_to_dict(self, evt) -> dict[str, Any]:
        """序列化 BlueprintEventIR 为字典（完整元数据 + 实现关联）。"""
        d: dict[str, Any] = {
            "name": evt.name,
            "event_type": evt.event_type,
            "parameters": evt.parameters,
        }
        if evt.function_flags:
            d["function_flags"] = evt.function_flags
        if evt.is_override:
            d["is_override"] = True
        if evt.override_parent_class:
            d["override_parent_class"] = evt.override_parent_class
        if evt.override_parent_event:
            d["override_parent_event"] = evt.override_parent_event
        if evt.is_interface_event:
            d["is_interface_event"] = True
        if evt.interface_class:
            d["interface_class"] = evt.interface_class
        for flag in (
            "is_net", "is_net_multicast", "is_replicated",
            "is_cosmetic", "is_static",
        ):
            if getattr(evt, flag, False):
                d[flag] = True
        if evt.meta_data:
            d["meta_data"] = evt.meta_data
        # 实现关联
        if evt.implementation:
            d["implementation"] = evt.implementation
        if evt.function_graph:
            d["function_graph"] = evt.function_graph
        d["implementation_status"] = evt.implementation_status
        return d

    def _decompiled_function_to_dict(self, func) -> dict[str, Any]:
        """序列化 DecompiledFunctionIR 为字典。"""
        d = {"name": func.name, "signature": func.signature, "cpp_code": func.cpp_code, "parameters": func.parameters, "return_type": func.return_type}
        if func.fallback_reasons:
            d["fallback_reasons"] = func.fallback_reasons
        return d

    def _build_function_graphs(self, ir: PackageIR) -> list[dict]:
        """直接返回 IR 中已构建的 function_graphs 数据。"""
        return ir.function_graphs

    @property
    def format_name(self) -> str:
        return "json"


class JsonSummaryRenderer(IRenderer):
    """JSON 摘要渲染器 — 机器可读精简格式。

    精简策略（对齐旧 format_json_summary）：
    - exports 仅保留 name/class/parent_class
    - 省略 imports, decompiled_functions, execution_chains, variables
    - 省略 function_graphs, resolved_parent_assets, inherited_blueprint_graphs, logic_sources
    - 保留 status, output_version, summary, name_map, linker, blueprint (精简)
    - 保留 diagnostics（容错模式诊断需要）和 errors
    """

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        data: dict[str, Any] = {
            "status": {
                "status": ir.status,
                "message": ir.status_message,
                "code": ir.status_code,
            },
            "output_version": _OUTPUT_VERSION_SUMMARY,
            "summary": {
                "package_name": ir.header.package_name,
                "package_class": ir.header.package_class,
                "package_flags": ir.header.package_flags,
                "total_export_count": ir.header.total_export_count,
                "total_import_count": ir.header.total_import_count,
                "ue_version": ir.header.ue_version,
            },
            "name_map": ir.name_map,
            "exports": [self._export_summary(e) for e in ir.exports],
        }
        if ir.linker is not None:
            data["linker"] = {
                "has_linker": ir.linker.has_linker,
                "import_paths": ir.linker.import_paths,
                "export_paths": ir.linker.export_paths,
            }
        if ir.blueprint is not None:
            data["blueprint"] = {
                "parent_class": ir.blueprint.parent_class,
                "function_count": len(ir.blueprint.functions),
                "event_count": len(ir.blueprint.events),
                "component_count": len(ir.blueprint.components),
            }
        if ir.errors:
            data["errors"] = ir.errors
        if ir.diagnostics:
            data["diagnostics"] = [d.to_dict() for d in ir.diagnostics]
        return json.dumps(data, indent=options.indent, ensure_ascii=False, cls=_JSONEncoder)

    def _export_summary(self, export) -> dict[str, Any]:
        """精简 export — 仅 name/class/parent_class。"""
        return {
            "name": export.object_name,
            "class": export.object_class,
            "parent_class": export.parent_class,
        }

    @property
    def format_name(self) -> str:
        return "json_summary"


register_renderer("json", JSONRenderer)
register_renderer("json_summary", JsonSummaryRenderer)
