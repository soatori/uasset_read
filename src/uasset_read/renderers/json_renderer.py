"""JSON 渲染器 — 递归序列化 PackageIR 为 JSON。"""
from __future__ import annotations

import json
import dataclasses
from typing import TYPE_CHECKING, Any

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


class _JSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理 dataclass 等非原生类型。"""

    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, bytes):
            return o.hex()
        return super().default(o)


class JSONRenderer(IRenderer):
    """JSON 渲染器。递归序列化 IR 为 JSON，包含 status 字段。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        data = {
            "status": {"status": "success", "message": None, "code": None},
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
        if ir.diagnostics:
            data["diagnostics"] = [d.to_dict() for d in ir.diagnostics]
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
        """序列化 BlueprintIR 为字典。"""
        d: dict[str, Any] = {"parent_class": blueprint.parent_class}
        if blueprint.functions:
            d["functions"] = [{"name": f.name, "return_type": f.return_type, "parameters": f.parameters} for f in blueprint.functions]
        if blueprint.events:
            d["events"] = [{"name": e.name, "event_type": e.event_type, "parameters": e.parameters} for e in blueprint.events]
        if blueprint.components:
            d["components"] = blueprint.components
        return d

    def _decompiled_function_to_dict(self, func) -> dict[str, Any]:
        """序列化 DecompiledFunctionIR 为字典。"""
        d = {"name": func.name, "signature": func.signature, "cpp_code": func.cpp_code, "parameters": func.parameters, "return_type": func.return_type}
        if func.fallback_reasons:
            d["fallback_reasons"] = func.fallback_reasons
        return d

    def _build_function_graphs(self, ir: PackageIR) -> list[dict]:
        graphs = []
        for export in ir.exports:
            for graph in export.graphs:
                graphs.append({"export_name": export.object_name, "graph_name": graph.graph_name, "graph_guid": graph.graph_guid, "node_count": len(graph.nodes), "execution_chains": graph.execution_chains})
        return graphs

    @property
    def format_name(self) -> str:
        return "json"


register_renderer("json", JSONRenderer)
register_renderer("json_summary", JSONRenderer)