from __future__ import annotations

"""JSON 渲染器 — 递归序列化 PackageIR 为 JSON。

仅注册 json 格式：完整分析格式，字段最全。
"""

import json
import re
import dataclasses
from typing import IO, TYPE_CHECKING, Any

from uasset_read.renderers.base import (
    IRenderer, RenderOptions,
    EDITOR_PROPERTY_NAMES,
    filter_editor_items, filter_variables,
)
from uasset_read.renderers import register_renderer
from uasset_read.constants import decode_package_flags
from uasset_read.models.ir import HexViewEntryIR

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


class _JSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理 dataclass 等非原生类型。"""

    def default(self, o):
        to_dict = getattr(type(o), "to_dict", None)
        if callable(to_dict):
            return to_dict(o)
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, bytes):
            return o.hex()
        return super().default(o)


class JSONRenderer(IRenderer):
    """JSON 渲染器 — 完整分析格式。递归序列化 IR 为 JSON。"""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        data = self._build_data(ir, options)
        return json.dumps(data, indent=options.indent, ensure_ascii=False, cls=_JSONEncoder)

    def render_to(self, ir: PackageIR, writer: IO[str], options: RenderOptions | None = None) -> None:
        """流式渲染 IR 到 writer，避免构建完整 JSON 字符串。

        输出格式与 render() 一致，直接使用 json.dump 写入 writer。
        适用于大文件或管道输出场景（不占用中间字符串内存）。

        Args:
            ir: PackageIR 实例
            writer: 可写文本流（StringIO、文件对象等）
            options: 渲染选项，None 时使用默认值
        """
        if options is None:
            options = RenderOptions()
        data = self._build_data(ir, options)
        json.dump(data, writer, indent=options.indent, ensure_ascii=False, cls=_JSONEncoder)
        writer.write("\n")

    def _build_data(self, ir: PackageIR, options: RenderOptions) -> dict[str, Any]:
        """构建渲染数据字典（render() 和 render_to() 共用）。"""
        is_debug = options.output_level == "debug"

        data: dict[str, Any] = {}
        if options.include_schema:
            data["$schema"] = "package.schema.json"
        data["status"] = {
            "status": ir.diagnostics_data.status if ir.diagnostics_data else "success",
            "message": ir.diagnostics_data.status_message if ir.diagnostics_data else None,
            "code": ir.diagnostics_data.status_code if ir.diagnostics_data else None,
        }
        data["summary"] = {
            "package_name": ir.header.package_name,
            "package_class": ir.header.package_class,
            "package_flags": ir.header.package_flags,
            "package_flags_decoded": decode_package_flags(ir.header.package_flags),
            "total_export_count": ir.header.total_export_count,
            "total_import_count": ir.header.total_import_count,
            "ue_version": ir.header.ue_version,
            "saved_hash": ir.header.saved_hash.hex() if ir.header.saved_hash else None,
        }
        all_exports = ir.exports if is_debug else filter_editor_items(ir.exports)
        data["exports"] = [
            self._export_to_dict(e, options, is_debug)
            for e in all_exports
        ]
        if ir.blueprint is not None:
            data["blueprint"] = self._blueprint_to_dict(ir.blueprint)
        if ir.decompiled_functions:
            data["decompiled_functions"] = [self._decompiled_function_to_dict(f) for f in ir.decompiled_functions]
        if ir.execution_chains:
            chains = [{"event": c.event, "chain": c.chain} for c in ir.execution_chains]
            if is_debug:
                data["execution_chains"] = chains
            else:
                chains_with_content = [c for c in chains if c.get("chain")]
                if chains_with_content:
                    data["execution_chains"] = chains_with_content
        if ir.variables:
            if is_debug:
                data["variables"] = [self._variable_to_dict(v) for v in ir.variables]
            else:
                variables = [
                    self._variable_to_dict(v) for v in filter_variables(ir.variables)
                ]
                if variables:
                    data["variables"] = variables
        if ir.dependencies and ir.dependencies.resolved_parent_assets:
            data["resolved_parent_assets"] = ir.dependencies.resolved_parent_assets
        if ir.dependencies and ir.dependencies.inherited_blueprint_graphs:
            data["inherited_blueprint_graphs"] = ir.dependencies.inherited_blueprint_graphs
        if ir.logic_sources:
            data["logic_sources"] = ir.logic_sources
        if ir.diagnostics_data and ir.diagnostics_data.errors:
            data["errors"] = ir.diagnostics_data.errors
        if ir.diagnostics_data and ir.diagnostics_data.warnings:
            data["warnings"] = ir.diagnostics_data.warnings
        if ir.diagnostics:
            if is_debug:
                data["diagnostics"] = [d.to_dict() for d in ir.diagnostics]
            else:
                all_diags = [d.to_dict() for d in ir.diagnostics]
                folded = self._fold_diagnostics(all_diags)
                if folded:
                    data["diagnostics"] = folded
        if ir.dependencies and ir.dependencies.asset_registry_data:
            data["asset_registry_data"] = ir.dependencies.asset_registry_data
        if ir.animation and ir.animation.anim_blueprint:
            data["anim_blueprint"] = self._anim_blueprint_to_dict(ir.animation.anim_blueprint)
        if ir.animation and ir.animation.anim_sequence:
            data["anim_sequence"] = self._anim_sequence_to_dict(ir.animation.anim_sequence)
        if ir.animation and ir.animation.anim_montage:
            data["anim_montage"] = self._anim_montage_to_dict(ir.animation.anim_montage)
        if (options.hex_view or options.output_level == "debug") and ir.debug and ir.debug.hex_view:
            data["debug"] = {
                "hex_view": [self._hex_view_entry_to_dict(e) for e in ir.debug.hex_view]
            }
        if options.include_function_graphs:
            data["function_graphs"] = self._build_function_graphs(ir)
        data["statistics"] = self._calculate_statistics(ir)
        return data

    def _export_to_dict(self, export, options: RenderOptions, is_debug: bool = False) -> dict[str, Any]:
        # standard 模式下过滤编辑器布局属性
        if is_debug:
            properties = [self._property_to_dict(p, is_debug=True) for p in export.properties]
        else:
            properties = [
                self._property_to_dict(p, is_debug=False) for p in export.properties
                if p.name not in EDITOR_PROPERTY_NAMES
            ]

        # graphs: standard 模式下只保留有内容的
        graphs = [self._graph_to_dict(g, options) for g in export.graphs]
        if not is_debug:
            graphs = [g for g in graphs if g.get("nodes")]

        d = {
            "object_name": export.object_name,
            "object_class": export.object_class,
            "serial_size": export.serial_size,
        }
        # parent_class: debug 模式下始终包含，standard 模式下仅非 None 时包含
        if is_debug or export.parent_class is not None:
            d["parent_class"] = export.parent_class
        # standard 模式下只添加非空字段
        if properties or is_debug:
            d["properties"] = properties
        if graphs or is_debug:
            d["graphs"] = graphs
        if export.parse_status != "success":
            d["parse_status"] = export.parse_status
        if export.fallback_reason:
            d["fallback_reason"] = export.fallback_reason
        if export.error_message:
            d["error_message"] = export.error_message
        return d

    def _property_to_dict(self, prop, is_debug: bool = False) -> dict[str, Any]:
        d: dict[str, Any] = {"name": prop.name, "type": prop.type, "value": prop.value}
        # standard 模式下省略默认值字段
        if is_debug or prop.array_index != -1:
            d["array_index"] = prop.array_index
        if is_debug or prop.guid is not None:
            d["guid"] = prop.guid
        # StructValue 元数据精简（standard 模式）
        if not is_debug and hasattr(prop.value, "__dataclass_fields__"):
            value_dict = dataclasses.asdict(prop.value)
            for field_name, default in [
                ("parse_status", "success"),
                ("property_type", "StructProperty"),
                ("kind", "struct_binary_decoded"),
            ]:
                if value_dict.get(field_name) == default:
                    value_dict.pop(field_name, None)
            d["value"] = value_dict
        # ObjectProperty full_name 省略（standard 模式）
        if not is_debug and d.get("type") == "ObjectProperty" and isinstance(d.get("value"), dict):
            val = d["value"]
            if "full_name" in val and "object_name" in val:
                d["value"] = {k: v for k, v in val.items() if k != "full_name"}
        return d

    def _graph_to_dict(self, graph, options: RenderOptions) -> dict[str, Any]:
        result = {
            "graph_name": graph.graph_name,
            "graph_guid": graph.graph_guid,
            "nodes": [self._node_to_dict(n, options.output_level) for n in graph.nodes],
            "execution_chains": graph.execution_chains,
        }
        if graph.graph_type:
            result["graph_type"] = graph.graph_type
        if graph.subgraphs:
            result["subgraphs"] = [self._graph_to_dict(sg, options) for sg in graph.subgraphs]
        return result

    def _node_to_dict(self, node, output_level: str = "standard") -> dict[str, Any]:
        d = {"node_guid": node.node_guid, "node_class": node.node_class, "node_comment": node.node_comment, "pins": [self._pin_to_dict(p, output_level) for p in node.pins], "execution_flow": node.execution_flow}
        if node.macro_expansion is not None:
            d["macro_expansion"] = node.macro_expansion
        return d

    def _pin_to_dict(self, pin, output_level: str = "standard") -> dict[str, Any]:
        is_debug = output_level == "debug"
        d: dict[str, Any] = {
            "pin_name": pin.pin_name,
            "linked_to": pin.linked_to,
            "direction": pin.direction,
            "pin_category": pin.pin_category,
            "container_type": pin.container_type,
        }
        if is_debug:
            # debug 模式：保留所有字段
            d["pin_type"] = pin.pin_type
            d["default_value"] = pin.default_value
            d["pin_subcategory"] = pin.pin_subcategory
            d["is_reference"] = pin.is_reference
            d["is_const"] = pin.is_const
            d["is_weak_pointer"] = pin.is_weak_pointer
            d["is_uobject_wrapper"] = pin.is_uobject_wrapper
        else:
            # standard 模式：只输出非默认值
            if pin.default_value:
                d["default_value"] = pin.default_value
            if pin.pin_subcategory:
                d["pin_subcategory"] = pin.pin_subcategory
            if pin.is_reference:
                d["is_reference"] = True
            if pin.is_const:
                d["is_const"] = True
            if pin.is_weak_pointer:
                d["is_weak_pointer"] = True
            if pin.is_uobject_wrapper:
                d["is_uobject_wrapper"] = True
        # 条件字段（两种模式都适用）
        if pin.pin_subcategory_object_name is not None:
            d["pin_subcategory_object"] = pin.pin_subcategory_object_name
        if pin.is_map_key:
            d["is_map_key"] = True
        if pin.is_map_value:
            d["is_map_value"] = True
        # Map terminal 类型
        if pin.container_type == "Map":
            if pin.map_key_pin_category:
                d["map_key_pin_category"] = pin.map_key_pin_category
            if pin.map_key_pin_subcategory:
                d["map_key_pin_subcategory"] = pin.map_key_pin_subcategory
            if pin.map_key_pin_subcategory_object_name is not None:
                d["map_key_pin_subcategory_object"] = pin.map_key_pin_subcategory_object_name
        return d

    def _extract_error_pattern(self, error: str) -> str:
        """提取 error 模式，替换数字为 {n} 占位符。"""
        return re.sub(r'\d+', '{n}', error)

    def _extract_position(self, diag: dict) -> int | None:
        """从 diagnostic 字典中提取位置（使用 current_pos 字段）。"""
        return diag.get("current_pos")

    def _fold_diagnostics(self, diagnostics: list) -> list:
        """折叠相同 (kind, field) 模式的 diagnostics。

        单条不折叠，多条折叠为一条含 count 和 pos_range 的记录。
        """
        if not diagnostics:
            return diagnostics

        # 按 (kind, field) 分组
        groups: dict[tuple[str, str], list] = {}
        for diag in diagnostics:
            key = (diag.get("kind", ""), diag.get("field", ""))
            if key not in groups:
                groups[key] = []
            groups[key].append(diag)

        folded = []
        for (kind, field), items in groups.items():
            if len(items) == 1:
                folded.append(items[0])
            else:
                first_error = items[0].get("error", "")
                error_pattern = self._extract_error_pattern(first_error)
                positions = []
                for item in items:
                    pos = self._extract_position(item)
                    if pos is not None:
                        positions.append(pos)
                folded_item: dict[str, Any] = {
                    "kind": kind,
                    "field": field,
                    "error": first_error,
                    "error_pattern": error_pattern,
                    "count": len(items),
                }
                if positions:
                    folded_item["pos_range"] = {
                        "min": min(positions),
                        "max": max(positions),
                    }
                folded.append(folded_item)

        return folded

    def _blueprint_to_dict(self, blueprint) -> dict[str, Any]:
        """序列化 BlueprintIR 为字典（完整元数据）。"""
        d: dict[str, Any] = {"parent_class": blueprint.parent_class}
        if getattr(blueprint, "description", ""):
            d["description"] = blueprint.description
        if getattr(blueprint, "interfaces", []):
            # interfaces 已经是 dict 列表（来自 IR builder）
            d["interfaces"] = blueprint.interfaces
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
        if not getattr(func, "is_implemented", True):
            d["is_implemented"] = False
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
        if func.bytecode_confidence != "verified":
            d["bytecode_confidence"] = func.bytecode_confidence
        return d

    def _calculate_statistics(self, ir: PackageIR) -> dict:
        """计算导出统计信息，包括 opaque 类分布。"""
        stats = {
            "total_exports": len(ir.exports),
            "success_count": 0,
            "partial_count": 0,
            "opaque_count": 0,
            "failed_count": 0,
            "opaque_classes": {},
        }

        for export in ir.exports:
            status = getattr(export, 'parse_status', 'success')
            if status == 'success':
                stats["success_count"] += 1
            elif status in ('partial', 'partial_metadata'):
                stats["partial_count"] += 1
            elif status == 'opaque':
                stats["opaque_count"] += 1
                cls = getattr(export, 'object_class', 'unknown')
                stats["opaque_classes"][cls] = stats["opaque_classes"].get(cls, 0) + 1
            elif status == 'failed':
                stats["failed_count"] += 1

        return stats

    def _build_function_graphs(self, ir: PackageIR) -> list[dict]:
        """直接返回 IR 中已构建的 function_graphs 数据。"""
        return ir.function_graphs

    @property
    def format_name(self) -> str:
        return "json"

    def _anim_blueprint_to_dict(self, anim_ir) -> dict[str, Any]:
        """序列化 AnimBlueprintIR 为字典。"""
        d: dict[str, Any] = {}
        if anim_ir.target_skeleton:
            d["target_skeleton"] = anim_ir.target_skeleton
        if anim_ir.baked_state_machines:
            d["baked_state_machines"] = [
                self._baked_state_machine_to_dict(sm) for sm in anim_ir.baked_state_machines
            ]
        if anim_ir.anim_notifies:
            d["anim_notifies"] = [
                self._anim_notify_to_dict(n) for n in anim_ir.anim_notifies
            ]
        if anim_ir.sync_group_names:
            d["sync_group_names"] = anim_ir.sync_group_names
        if anim_ir.graph_asset_player_info:
            d["graph_asset_player_info"] = anim_ir.graph_asset_player_info
        if anim_ir.graph_blend_options:
            d["graph_blend_options"] = anim_ir.graph_blend_options
        if anim_ir.anim_node_data:
            d["anim_node_data"] = anim_ir.anim_node_data
        return d

    def _baked_state_machine_to_dict(self, sm) -> dict[str, Any]:
        """序列化 BakedStateMachineIR 为字典。"""
        return {
            "machine_name": sm.machine_name,
            "initial_state": sm.initial_state,
            "states": [
                {
                    "state_name": s.state_name,
                    "state_root_node_index": s.state_root_node_index,
                    "b_is_a_conduit": s.b_is_a_conduit,
                }
                for s in sm.states
            ],
            "transitions": [
                {
                    "previous_state": t.previous_state,
                    "next_state": t.next_state,
                    "crossfade_duration": t.crossfade_duration,
                    "blend_mode": t.blend_mode,
                }
                for t in sm.transitions
            ],
        }

    def _anim_notify_to_dict(self, notify) -> dict[str, Any]:
        """序列化 AnimNotifyIR 为字典。"""
        return {
            "notify_name": notify.notify_name,
            "trigger_time_offset": notify.trigger_time_offset,
            "duration": notify.duration,
            "notify_class": notify.notify_class,
            "track_index": notify.track_index,
        }

    def _anim_sequence_to_dict(self, anim_ir) -> dict[str, Any]:
        """序列化 AnimSequenceIR 为字典。"""
        d: dict[str, Any] = {}
        if anim_ir.target_skeleton:
            d["target_skeleton"] = anim_ir.target_skeleton
        if anim_ir.additive_anim_type:
            d["additive_anim_type"] = anim_ir.additive_anim_type
        if anim_ir.sequence_length:
            d["sequence_length"] = anim_ir.sequence_length
        if anim_ir.rate_scale:
            d["rate_scale"] = anim_ir.rate_scale
        if anim_ir.notifies:
            d["notifies"] = [self._anim_notify_to_dict(n) for n in anim_ir.notifies]
        if anim_ir.float_curve_names:
            d["float_curve_names"] = anim_ir.float_curve_names
        d["has_compressed_data"] = anim_ir.has_compressed_data
        return d

    def _anim_montage_to_dict(self, anim_ir) -> dict[str, Any]:
        """序列化 AnimMontageIR 为字典。"""
        d: dict[str, Any] = {}
        if anim_ir.blend_mode_in:
            d["blend_mode_in"] = anim_ir.blend_mode_in
        if anim_ir.blend_mode_out:
            d["blend_mode_out"] = anim_ir.blend_mode_out
        if anim_ir.blend_in_option:
            d["blend_in_option"] = anim_ir.blend_in_option
        if anim_ir.blend_out_option:
            d["blend_out_option"] = anim_ir.blend_out_option
        if anim_ir.sync_group:
            d["sync_group"] = anim_ir.sync_group
        if anim_ir.rate_scale:
            d["rate_scale"] = anim_ir.rate_scale
        if anim_ir.composite_sections:
            d["composite_sections"] = anim_ir.composite_sections
        if anim_ir.slot_anim_tracks:
            d["slot_anim_tracks"] = anim_ir.slot_anim_tracks
        if anim_ir.branching_point_markers:
            d["branching_point_markers"] = anim_ir.branching_point_markers
        if anim_ir.notifies:
            d["notifies"] = [self._anim_notify_to_dict(n) for n in anim_ir.notifies]
        if anim_ir.float_curve_names:
            d["float_curve_names"] = anim_ir.float_curve_names
        return d

    def _hex_view_entry_to_dict(self, entry: "HexViewEntryIR") -> dict[str, Any]:
        """序列化 HexViewEntryIR 为字典。"""
        d: dict[str, Any] = {
            "key": entry.key,
            "type": entry.type,
            "start": entry.start,
            "stop": entry.stop,
            "size": entry.size,
        }
        if entry.field_path is not None:
            d["field_path"] = entry.field_path
        if entry.semantic_type is not None:
            d["semantic_type"] = entry.semantic_type
        if isinstance(entry.value, bytes):
            d["value_hex"] = entry.value.hex()
            d["value_size"] = len(entry.value)
        elif isinstance(entry.value, str):
            d["value"] = entry.value
        else:
            d["value"] = entry.value
        return d


register_renderer("json", JSONRenderer)
