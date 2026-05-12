"""JSON 格式化 — 完整输出、摘要输出、导出列表、属性列表、蓝图字典。

等价迁移 uasset_read_legacy.py L7188-7428, L7251-7357, L7670-7807。
Phase 32: 输出格式化模块。
"""
from __future__ import annotations

from typing import Dict, List, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.models.blueprint import BlueprintMetadata, BlueprintVariable, BlueprintFunction, BlueprintEvent, FunctionParameter
    from uasset_read.models.properties import PropertyValue
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport

from dataclasses import asdict

from uasset_read.serializers.object_resources import get_asset_class
from .helpers import build_status_info, build_schema_info, resolve_fpackage_index


def format_json_full(result: ParseResult, include_schema: bool = False) -> Dict:
    """
    完整 JSON 输出（OUT-03）。

    Per D-01: 分层输出（完整详情）
    Per D-02: Package → Exports → Properties 层级结构
    Per D-03: 顶层 errors 字段
    Per D-04: 单一 blueprint 对象结构（D-20-04: graphs 移入 blueprint 内部）
    Per D-05: 未解析的 FPackageIndex 原值保留
    Per D-06: name_map 不输出（已解析为对象名）
    Per D-20-04: 单一 blueprint 对象结构（graphs 移入 blueprint 内部）
    Per D-20-05: output_version 升级到 "4.0"
    Per D-20-06: blueprint_name 从 package_name 提取
    Per D-02（Phase 32）: 移除 imports, soft_references, circular_deps 字段

    Args:
        result: ParseResult 来自 parse_uasset()
        include_schema: bool，是否包含 _schema 字段（OUT-05）

    Returns:
        Dict: 包含 status, output_version, summary, exports, blueprint, graphs_summary, errors
    """
    summary_dict = {}
    if result.summary:
        summary_dict = {
            "version_ue4": result.summary.file_version_ue4,
            "version_ue5": result.summary.file_version_ue5,
            "legacy_version": result.summary.legacy_file_version,
            "package_flags": result.summary.package_flags,  # D-08: raw u32
            "package_name": result.summary.package_name
        }

    # D-20-04: 构建单一 blueprint 对象（包含 graphs）
    blueprint_obj = None
    if result.blueprint:
        blueprint_obj = format_blueprint_dict(
            result.blueprint,
            blueprint_name=result.summary.package_name if result.summary else None
        )
        # graphs 移入 blueprint（使用 Phase 31 的 format_graphs_json）
        from uasset_read.graph import format_graphs_json
        blueprint_obj["graphs"] = format_graphs_json(result.graphs)

    # Phase 31 的 build_graphs_summary 用于顶层 graphs_summary
    from uasset_read.graph import build_graphs_summary

    output = {
        "status": asdict(build_status_info(result)),  # D-14-03: 顶层位置（第一个字段）
        "output_version": "4.0",  # D-20-05: 反映输出结构重大变化
        "summary": summary_dict,
        "exports": format_exports_list(result),
        "blueprint": blueprint_obj,  # D-20-04: 单一 blueprint 对象
        "graphs_summary": build_graphs_summary(result.graphs),  # D-14-04: 顶层化（OUT-02）
        # D-02（Phase 32）: 移除 imports, soft_references, circular_deps 字段
        # 原因：依赖分析字段不属于格式化模块核心职责
        "errors": result.errors
    }

    # OUT-05: 添加 _schema 字段（仅在 include_schema=True）
    if include_schema:
        output["_schema"] = build_schema_info()

    return output


def format_exports_list(result: ParseResult) -> List[Dict]:
    """
    格式化导出列表用于 JSON 输出。

    Per D-11/D-12: ParentClass, SuperIndex 在 Phase 3 解析
    Per D-13: 解析失败时添加 Warning 字段
    Per D-15: Soft object paths 输出原始路径字符串

    Args:
        result: ParseResult 包含 export_map

    Returns:
        List[Dict]: 每个元素包含 index, name, class, serial_size, properties,
                    outer_index, super_index, parent_class
    """
    exports_list = []

    for i, exp in enumerate(result.export_map):
        # Resolve ParentClass from Phase 3 extraction
        parent_class = None
        parent_warning = None
        if result.blueprint and result.blueprint.is_blueprint:
            parent_class = result.blueprint.parent_class
            parent_warning = result.blueprint.detection_warning

        export_dict = {
            "index": i,
            "name": exp.object_name,
            "class": get_asset_class(exp, result.import_map, result.export_map),
            "serial_size": exp.serial_size,
            "properties": format_properties_list(exp.properties) if exp.properties else [],
            # Per D-12: resolved references
            "outer_index": resolve_fpackage_index(exp.outer_index, result),
            "super_index": resolve_fpackage_index(exp.super_index, result),
            "parent_class": parent_class,  # from Phase 3 or resolution
        }

        # Per D-13: include warning if resolution failed
        if parent_warning:
            export_dict["parent_warning"] = parent_warning

        exports_list.append(export_dict)

    return exports_list


def format_properties_list(properties: List[PropertyValue]) -> List[Dict]:
    """
    格式化属性列表用于 JSON 输出。

    Per OUT-05: None → null in JSON（Python None 保留）

    Args:
        properties: List[PropertyValue] 对象列表

    Returns:
        List[Dict]: 每个元素包含 name, type, value, array_index
    """
    props_list = []

    for prop in properties:
        prop_dict = {
            "name": prop.name,
            "type": prop.type,
            "value": prop.value,  # None → JSON null automatically
            "array_index": prop.array_index
        }
        props_list.append(prop_dict)

    return props_list


def format_json_summary(result: ParseResult, include_schema: bool = False) -> Dict:
    """
    精简 JSON 摘要 — 70%+ token 减少（D-14-07~09, OUT-03）。

    精简策略:
    - 移除: imports, soft_references, circular_deps, errors
    - 精简 exports: 仅 name, class, parent_class
    - 移除 properties 数组
    - 保留: status, output_version, graphs_summary

    Per D-07: 移除依赖字段
    Per D-08: 精简 exports
    Per D-09: 移除 properties 数组

    Args:
        result: ParseResult 来自 parse_uasset()
        include_schema: bool，是否包含 _schema 字段（OUT-05）

    Returns:
        Dict: 精简摘要
    """
    version_dict = {}
    if result.summary:
        version_dict = {
            "ue4": result.summary.file_version_ue4,
            "ue5": result.summary.file_version_ue5 or result.summary.legacy_file_version,
            "legacy": result.summary.legacy_file_version
        }

    # D-14-08: 精简 exports（仅 name, class, parent_class）
    exports_summary = []
    for i, exp in enumerate(result.export_map):
        # 获取 parent_class（仅在蓝图主对象的第一个 export）
        parent_class = ""
        if result.blueprint and result.blueprint.is_blueprint and i == 0:
            parent_class = result.blueprint.parent_class or ""

        exports_summary.append({
            "name": exp.object_name,
            "class": get_asset_class(exp, result.import_map, result.export_map),
            "parent_class": parent_class
        })

    # Phase 31 的 build_graphs_summary
    from uasset_read.graph import build_graphs_summary

    output = {
        "status": asdict(build_status_info(result)),  # D-14-03: 顶层位置
        "output_version": "4.0",  # D-20-05: API 版本标识
        "version": version_dict,
        "package_name": result.summary.package_name if result.summary else "",
        "exports": exports_summary,  # D-14-08: 精简版本
        "graphs_summary": build_graphs_summary(result.graphs),  # D-14-04: 顶层化
    }

    # D-14-07: 移除 imports/soft_references/circular_deps/errors
    # errors 数组已移除（status 字段已包含状态信息）

    # D-20-04: blueprint 精简（仅保留核心字段）
    if result.blueprint and result.blueprint.is_blueprint:
        output["blueprint"] = {
            "blueprint_name": result.summary.package_name if result.summary else None,
            "parent_class": result.blueprint.parent_class,
        }

    # OUT-05: 添加 _schema 字段（仅在 include_schema=True）
    if include_schema:
        output["_schema"] = build_schema_info()

    return output


def format_blueprint_dict(blueprint: BlueprintMetadata, blueprint_name: str = None) -> Dict:
    """
    格式化 BlueprintMetadata 用于 JSON 输出（D-04, D-20-06）。

    Per D-20-06: blueprint_name 从 package_name 或导出名提取
    Phase 26: 增强元数据输出（META-04）

    Args:
        blueprint: BlueprintMetadata 对象
        blueprint_name: 资产名称（可选）

    Returns:
        Dict: 包含 blueprint_name, parent_class, variables, functions, events, detection_warning
    """
    # 增强的变量输出（Phase 26）
    variables_list = [_format_variable_enhanced(var) for var in blueprint.variables]

    # 增强的函数输出（Phase 26）
    functions_list = [_format_function_enhanced(func) for func in blueprint.functions]

    # 增强的事件输出（Phase 26）
    events_list = [_format_event_enhanced(event) for event in blueprint.events]

    return {
        "blueprint_name": blueprint_name,  # D-20-06
        "parent_class": blueprint.parent_class,  # None if not resolved
        "variables": variables_list,  # Phase 26: 增强格式
        "functions": functions_list,  # Phase 26: 新增
        "events": events_list,  # Phase 26: 新增
        "detection_warning": blueprint.detection_warning  # None if no warning
    }


# ============================================================================
# Phase 26: 增强的 JSON 格式化辅助函数 (META-04)
# ============================================================================

def _format_variable_enhanced(variable: BlueprintVariable) -> dict:
    """格式化增强的变量元数据（Phase 26: META-04）"""
    result = {
        "name": variable.var_name,
        "type": {
            "pin_category": variable.var_type.pin_category,
            "pin_sub_category": variable.var_type.pin_sub_category,
            "container_type": variable.var_type.container_type,
            "is_reference": variable.var_type.is_reference,
            "is_const": variable.var_type.is_const
        },
        "category": variable.category,
        "default_value": variable.default_value,
        "friendly_name": variable.friendly_name,
        "property_flags": variable.property_flags,
        "edit_condition": variable.edit_condition,
        "edit_category": variable.edit_category,
        "edit_widget": variable.edit_widget,
        "is_edit_anywhere": variable.is_edit_anywhere,
        "is_edit_instance_only": variable.is_edit_instance_only,
        "is_visible_anywhere": variable.is_visible_anywhere,
        "is_blueprint_read_only": variable.is_blueprint_read_only,
        "is_blueprint_readable": variable.is_blueprint_readable,
        "is_blueprint_writable": variable.is_blueprint_writable,
        "is_blueprint_assignable": variable.is_blueprint_assignable,
        "is_blueprint_callable": variable.is_blueprint_callable,
        "is_transient": variable.is_transient,
        "is_duplicate_transient": variable.is_duplicate_transient,
        "is_text_export_transient": variable.is_text_export_transient,
        "is_non_transient": variable.is_non_transient,
        "is_export_object": variable.is_export_object,
        "is_save_game": variable.is_save_game,
        "is_no_clear": variable.is_no_clear,
        "is_reference_only": variable.is_reference_only,
        "is_rep_notify": variable.is_rep_notify,
        "is_interp": variable.is_interp,
        "is_expose_on_spawn": variable.is_expose_on_spawn,
        "is_net": variable.is_net,
        "is_replicated": variable.is_replicated,
        "is_non_pi_ed_duplicate_transient": variable.is_non_pi_ed_duplicate_transient,
        "is_component": variable.is_component,
        "meta_data": variable.meta_data
    }
    return result


def _format_parameter(parameter: FunctionParameter) -> dict:
    """格式化函数参数（Phase 26: META-04）"""
    return {
        "name": parameter.name,
        "type": parameter.param_type,
        "default_value": parameter.default_value,
        "is_input": parameter.is_input,
        "is_output": parameter.is_output,
        "is_optional": parameter.is_optional,
        "property_flags": parameter.property_flags,
        "meta_data": parameter.meta_data
    }


def _format_function_enhanced(function: BlueprintFunction) -> dict:
    """格式化增强的函数元数据（Phase 26: META-04）"""
    result = {
        "name": function.name,
        "return_type": function.return_type,
        "function_flags": function.function_flags,
        "is_pure": function.is_pure,
        "is_blueprint_callable": function.is_blueprint_callable,
        "is_blueprint_event": function.is_blueprint_event,
        "is_blueprint_implementable_event": function.is_blueprint_implementable_event,
        "is_native": function.is_native,
        "is_const": function.is_const,
        "is_static": function.is_static,
        "is_virtual": function.is_virtual,
        "is_exec": function.is_exec,
        "is_net": function.is_net,
        "is_net_reliable": function.is_net_reliable,
        "is_net_server": function.is_net_server,
        "is_net_client": function.is_net_client,
        "is_net_multicast": function.is_net_multicast,
        "is_blueprint_private": function.is_blueprint_private,
        "is_blueprint_protected": function.is_blueprint_protected,
        "is_blueprint_public": function.is_blueprint_public,
        "is_blueprint_pure": function.is_blueprint_pure,
        "is_blueprint_cosmetic": function.is_blueprint_cosmetic,
        "is_editor_only": function.is_editor_only,
        "is_final": function.is_final,
        "is_delegate": function.is_delegate,
        "is_multicast_delegate": function.is_multicast_delegate,
        "is_has_out_parms": function.is_has_out_parms,
        "is_has_defaults": function.is_has_defaults,
        "access_specifier": function.access_specifier,
        "parameters": [_format_parameter(param) for param in function.parameters],
        "meta_data": function.meta_data
    }
    return result


def _format_event_enhanced(event: BlueprintEvent) -> dict:
    """格式化增强的事件元数据（Phase 26: META-04）"""
    result = {
        "name": event.name,
        "event_type": event.event_type,
        "function_flags": event.function_flags,
        "is_blueprint_event": event.is_blueprint_event,
        "is_blueprint_implementable_event": event.is_blueprint_implementable_event,
        "is_net": event.is_net,
        "is_net_multicast": event.is_net_multicast,
        "is_net_reliable": event.is_net_reliable,
        "is_net_client": event.is_net_client,
        "is_net_server": event.is_net_server,
        "is_replicated": event.is_replicated,
        "is_cosmetic": event.is_cosmetic,
        "is_static": event.is_static,
        "is_multicast": event.is_multicast,
        "is_override": event.is_override,
        "override_parent_class": event.override_parent_class,
        "override_parent_event": event.override_parent_event,
        "is_interface_event": event.is_interface_event,
        "interface_class": event.interface_class,
        "parameters": [_format_parameter(param) for param in event.parameters],
        "meta_data": event.meta_data
    }

    # 添加多播委托信息
    if event.multicast_delegate:
        result["multicast_delegate"] = {
            "delegate_name": event.multicast_delegate.delegate_name,
            "signature_function": event.multicast_delegate.signature_function,
            "is_callable_in_blueprint": event.multicast_delegate.is_callable_in_blueprint
        }

    return result