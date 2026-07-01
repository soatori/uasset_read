"""JSON 渲染器 — 递归序列化 PackageIR 为 JSON。

仅注册 json 格式：完整分析格式，字段最全。
"""
from __future__ import annotations

import json
import dataclasses
from typing import TYPE_CHECKING, Any

from uasset_read.renderers.base import IRenderer, RenderOptions
from uasset_read.renderers import register_renderer
from uasset_read.constants import decode_package_flags

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

    # 编辑器布局属性（不影响运行时和 C++ 翻译）
    _EDITOR_PROPERTY_NAMES = frozenset({
        # 节点布局
        "NodePosX", "NodePosY", "NodeWidth", "NodeHeight",
        "NodeGuid", "NodeComment", "bIsCommentBubbleVisible",
        # 注释相关
        "CommentColor", "FontSize",
        "bCommentBubbleVisible_InDetailsPanel",
        "bCommentBubblePinned", "bCommentBubbleVisible",
        # 图相关
        "Schema", "GraphGuid", "ErrorType",
        "AdvancedPinDisplay", "MoveMode",
        # 事件/函数引用（已提取到其他字段）
        "EventReference", "bOverrideFunction",
    })

    # 编辑器内部变量（不影响运行时和 C++ 翻译）
    _EDITOR_VARIABLE_NAMES = frozenset({
        "UbergraphPages",  # 图页面索引列表
        "FunctionGraphs",  # 函数图索引列表
        "CategorySorting",  # 编辑器分类排序
        "ImplementedInterfaces",  # 已实现接口（已在 blueprint.interfaces 中）
        "LastEditedDocuments",  # 最后编辑文档
        "ThumbnailInfo",  # 缩略图信息
        "bLegacyNeedToPurgeSkelRefs",  # 骨骼引用清理标记
    })

    # 编辑器内部节点类（不影响运行时，UE 编译时移除）
    _EDITOR_NODE_CLASSES = frozenset({
        "K2Node_Knot",  # 重定向节点，仅编辑器布局用途
    })

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        all_exports = ir.exports
        is_debug = options.output_level == "debug"

        data: dict[str, Any] = {}
        if options.include_schema:
            data["$schema"] = "package.schema.json"
        data["status"] = {
            "status": ir.status,
            "message": ir.status_message,
            "code": ir.status_code,
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
        data["exports"] = [
            self._export_to_dict(e, options, is_debug)
            for e in all_exports
            if is_debug or e.object_class not in self._EDITOR_NODE_CLASSES
        ]
        if ir.blueprint is not None:
            data["blueprint"] = self._blueprint_to_dict(ir.blueprint)
        if ir.decompiled_functions:
            data["decompiled_functions"] = [self._decompiled_function_to_dict(f) for f in ir.decompiled_functions]
        # execution_chains: 过滤空的 chains
        if ir.execution_chains:
            chains = [{"event": c.event, "chain": c.chain} for c in ir.execution_chains]
            if is_debug:
                data["execution_chains"] = chains
            else:
                # standard 模式下只保留有内容的 chains
                chains_with_content = [c for c in chains if c.get("chain")]
                if chains_with_content:
                    data["execution_chains"] = chains_with_content
        if ir.variables:
            # standard 模式下过滤编辑器内部变量
            if is_debug:
                data["variables"] = [self._variable_to_dict(v) for v in ir.variables]
            else:
                variables = [
                    self._variable_to_dict(v) for v in ir.variables
                    if v.name not in self._EDITOR_VARIABLE_NAMES
                ]
                if variables:
                    data["variables"] = variables
        if ir.resolved_parent_assets:
            data["resolved_parent_assets"] = ir.resolved_parent_assets
        if ir.inherited_blueprint_graphs:
            data["inherited_blueprint_graphs"] = ir.inherited_blueprint_graphs
        if ir.logic_sources:
            data["logic_sources"] = ir.logic_sources
        if ir.errors:
            data["errors"] = ir.errors
        # diagnostics: 去重
        if ir.diagnostics:
            if is_debug:
                data["diagnostics"] = [d.to_dict() for d in ir.diagnostics]
            else:
                # standard 模式下去重
                seen = set()
                unique_diags = []
                for d in ir.diagnostics:
                    d_dict = d.to_dict()
                    key = (d_dict.get("field"), d_dict.get("error"))
                    if key not in seen:
                        seen.add(key)
                        unique_diags.append(d_dict)
                if unique_diags:
                    data["diagnostics"] = unique_diags
        if ir.asset_registry_data:
            data["asset_registry_data"] = ir.asset_registry_data
        if ir.anim_blueprint:
            data["anim_blueprint"] = self._anim_blueprint_to_dict(ir.anim_blueprint)
        if ir.anim_sequence:
            data["anim_sequence"] = self._anim_sequence_to_dict(ir.anim_sequence)
        if ir.anim_montage:
            data["anim_montage"] = self._anim_montage_to_dict(ir.anim_montage)
        if options.include_function_graphs:
            data["function_graphs"] = self._build_function_graphs(ir)
        return json.dumps(data, indent=options.indent, ensure_ascii=False, cls=_JSONEncoder)

    def _export_to_dict(self, export, options: RenderOptions, is_debug: bool = False) -> dict[str, Any]:
        # standard 模式下过滤编辑器布局属性
        if is_debug:
            properties = [self._property_to_dict(p) for p in export.properties]
        else:
            properties = [
                self._property_to_dict(p) for p in export.properties
                if p.name not in self._EDITOR_PROPERTY_NAMES
            ]

        # graphs: standard 模式下只保留有内容的
        graphs = [self._graph_to_dict(g, options) for g in export.graphs]
        if not is_debug:
            graphs = [g for g in graphs if g.get("nodes")]

        d = {
            "object_name": export.object_name,
            "object_class": export.object_class,
            "serial_size": export.serial_size,
            "parent_class": export.parent_class,
        }
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

    def _property_to_dict(self, prop) -> dict[str, Any]:
        return {"name": prop.name, "type": prop.type, "value": prop.value, "array_index": prop.array_index, "guid": prop.guid}

    def _graph_to_dict(self, graph, options: RenderOptions) -> dict[str, Any]:
        result = {
            "graph_name": graph.graph_name,
            "graph_guid": graph.graph_guid,
            "nodes": [self._node_to_dict(n) for n in graph.nodes],
            "execution_chains": graph.execution_chains,
        }
        if graph.graph_type:
            result["graph_type"] = graph.graph_type
        if graph.subgraphs:
            result["subgraphs"] = [self._graph_to_dict(sg, options) for sg in graph.subgraphs]
        return result

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
        return d

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


register_renderer("json", JSONRenderer)
