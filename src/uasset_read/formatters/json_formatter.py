"""JSON 格式化 — 完整输出、摘要输出、导出列表、属性列表、蓝图字典。

等价迁移 uasset_read_legacy.py L7188-7428, L7251-7357, L7670-7807。
"""
from __future__ import annotations

from typing import Dict, List, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.models.blueprint import BlueprintMetadata, BlueprintVariable, BlueprintFunction, BlueprintEvent, FunctionParameter
    from uasset_read.models.properties import PropertyValue
    from uasset_read.serializers.object_resources import ObjectExport, ObjectImport

from dataclasses import asdict, is_dataclass

from uasset_read.models.properties import StructValue, MapValue, SetValue, EnumValue, TextValue, DelegateValue
from uasset_read.serializers.object_resources import get_asset_class, get_asset_class_with_linker
from .helpers import build_status_info, build_schema_info, resolve_fpackage_index


def format_json_full(result: ParseResult, include_schema: bool = False, include_function_graphs: bool = False) -> Dict:
    """
    完整 JSON 输出（OUT-03）。

    Per D-01: 分层输出（完整详情）
    Per D-02: Package → Exports → Properties 层级结构
    Per D-03: 顶层 errors 字段
    Per D-04: 单一 blueprint 对象结构（D-20-04: graphs 移入 blueprint 内部）
    Per D-05: 未解析的 FPackageIndex 原值保留
    Per D-06: name_map 输出供名称索引和诊断使用
    Per D-20-04: 单一 blueprint 对象结构（graphs 移入 blueprint 内部）
    Per D-20-05: output_version 升级到 "4.0"
    Per D-20-06: blueprint_name 从 package_name 提取
    Per D-02: 移除 imports, soft_references, circular_deps 字段
    output_version 升级到 "5.0" when include_function_graphs=True

    Args:
        result: ParseResult 来自 parse_uasset()
        include_schema: bool，是否包含 _schema 字段（OUT-05）
        include_function_graphs: bool，是否包含顶层 function_graphs 数组

    Returns:
        Dict: 包含 status, output_version, summary, exports, blueprint, errors
        当 include_function_graphs=True 时，额外包含 function_graphs 顶层数组
    """
    summary_dict = {}
    if result.summary:
        summary_dict = {
            "version_ue5": result.summary.file_version_ue5,
            "legacy_version": result.summary.legacy_file_version,
            "package_flags": result.summary.package_flags,  # D-08: raw u32
            "package_name": result.summary.package_name
        }

    # D-20-04: 构建单一 blueprint 对象
    blueprint_obj = None
    if result.blueprint:
        blueprint_obj = _format_blueprint_result(result)

    # output_version 条件化
    output_version = "5.0" if include_function_graphs else "4.0"

    output = {
        "status": asdict(build_status_info(result)),  # D-14-03: 顶层位置（第一个字段）
        "output_version": output_version,  # D-20-05: 反映输出结构重大变化
        "summary": summary_dict,
        "name_map": result.name_map,  # D-06: 名称表供名称索引和诊断
        "exports": format_exports_list(result),
        "blueprint": blueprint_obj,  # D-20-04: 单一 blueprint 对象
        "linker": _format_linker_summary(result),
        "components": _format_components(getattr(result, "components", [])),
        "decompiled_functions": [
            fn.to_dict() if hasattr(fn, "to_dict") else serialize_property_value(fn)
            for fn in getattr(result, "decompiled_functions", [])
        ],
        "resolved_parent_assets": getattr(result, "resolved_parent_assets", []),
        "inherited_blueprint_graphs": getattr(result, "inherited_blueprint_graphs", []),
        "logic_sources": getattr(result, "logic_sources", []),
        # D-02: 移除 imports, soft_references, circular_deps 字段
        # 原因：依赖分析字段不属于格式化模块核心职责
        "errors": result.errors
    }

    # 添加 function_graphs 顶层数组（仅在 include_function_graphs=True）
    if include_function_graphs and result.graphs:
        from uasset_read.graph import build_function_graphs
        blueprint_functions = result.blueprint.functions if result.blueprint else None
        output["function_graphs"] = build_function_graphs(result.graphs, blueprint_functions)

    # OUT-05: 添加 _schema 字段（仅在 include_schema=True）
    if include_schema:
        output["_schema"] = build_schema_info()

    return output


def _format_blueprint_result(result: ParseResult) -> Dict[str, Any]:
    """Build the standard Blueprint DTO result."""
    from uasset_read.graph import build_blueprint_node_index

    package_name = result.summary.package_name if result.summary else ""
    metadata = format_blueprint_dict(result.blueprint, blueprint_name=package_name)
    node_index = build_blueprint_node_index(result.graphs)
    warnings = _collect_blueprint_warnings(result)

    return {
        "PackageName": package_name,
        "BlueprintClass": _resolve_blueprint_class(result),
        "Graphs": node_index["Graphs"],
        "NodeCount": node_index["NodeCount"],
        "Nodes": node_index["Nodes"],
        "Warnings": warnings,
        "Extensions": {
            "Metadata": metadata,
        },
    }


def _resolve_blueprint_class(result: ParseResult) -> str | None:
    blueprint = getattr(result, "blueprint", None)
    parent_class = getattr(blueprint, "parent_class", None) if blueprint else None
    return parent_class or None


def _collect_blueprint_warnings(result: ParseResult) -> List[str]:
    from uasset_read.graph import build_connections_map

    warnings: List[str] = []
    blueprint = getattr(result, "blueprint", None)
    if blueprint and getattr(blueprint, "detection_warning", None):
        warnings.append(str(blueprint.detection_warning))
    if blueprint and not getattr(blueprint, "parent_class", None):
        warnings.append("BlueprintClass could not be resolved from parsed metadata")

    for graph in result.graphs:
        _, graph_warnings = build_connections_map(graph)
        warnings.extend(graph_warnings)
        for node in graph.nodes:
            if not node.node_guid:
                warnings.append(f"{graph.graph_name}: node {node.class_name} is missing NodeGuid")
            if not node.class_name:
                warnings.append(f"{graph.graph_name}: graph node is missing Type")

    return list(dict.fromkeys(warnings))


def format_exports_list(result: ParseResult) -> List[Dict]:
    """
    格式化导出列表用于 JSON 输出。

    Per D-11/D-12: ParentClass, SuperIndex 在解析阶段提取
    Per D-13: 解析失败时添加 Warning 字段
    Per D-15: Soft object paths 输出原始路径字符串

    Args:
        result: ParseResult 包含 export_map

    Returns:
        List[Dict]: 每个元素包含 index, name, class, serial_size, properties,
                    outer_index, super_index, parent_class
    """
    exports_list = []

    # Extract linker for class resolution (may be None for legacy ParseResult)
    linker = getattr(result, 'linker', None)

    for i, exp in enumerate(result.export_map or []):
        # Resolve ParentClass from blueprint extraction
        parent_class = None
        parent_warning = None
        if result.blueprint and result.blueprint.is_blueprint:
            parent_class = result.blueprint.parent_class
            parent_warning = result.blueprint.detection_warning

        export_dict = {
            "index": i,
            "name": exp.object_name,
            "class": (get_asset_class_with_linker(exp, linker) if linker else get_asset_class(exp, result.import_map, result.export_map or [])),
            "serial_size": exp.serial_size,
            "properties": format_properties_list(exp.properties) if exp.properties else [],
            # Per D-12: resolved references
            "outer_index": resolve_fpackage_index(exp.outer_index, result),
            "super_index": resolve_fpackage_index(exp.super_index, result),
            "parent_class": parent_class,  # from blueprint or resolution
        }

        # Per D-13: include warning if resolution failed
        if parent_warning:
            export_dict["parent_warning"] = parent_warning

        exports_list.append(export_dict)

    return exports_list


def serialize_property_value(value: Any, depth: int = 0, max_depth: int = 10) -> Any:
    """将高级属性值 dataclass 转换为 JSON 兼容 dict。

    处理 StructValue, MapValue, SetValue, EnumValue, TextValue, DelegateValue。
    原始 dict/str/int/float/None 等 JSON 原生类型直接返回。

    Args:
        value: 属性值（任意类型）
        depth: 当前递归深度（内部使用）
        max_depth: 最大递归深度，超过此值返回截断标记

    Returns:
        JSON 兼容的 dict 或原始值
    """
    if depth > max_depth:
        return "[deep nesting truncated]"

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {k: serialize_property_value(v, depth + 1, max_depth) for k, v in value.items()}

    if isinstance(value, list):
        return [serialize_property_value(item, depth + 1, max_depth) for item in value]

    if isinstance(value, StructValue):
        payload = {
            "struct_type": value.struct_type,
            "fields": {k: serialize_property_value(v, depth + 1, max_depth) for k, v in value.fields.items()}
        }
        if value.raw_size is not None:
            payload["raw_size"] = value.raw_size
        if value.parse_status != "parsed":
            payload["parse_status"] = value.parse_status
        return payload
    if isinstance(value, MapValue):
        return {
            "key_type": value.key_type,
            "value_type": value.value_type,
            "entries": [
                {
                    "key": serialize_property_value(entry.get("key"), depth + 1, max_depth),
                    "value": serialize_property_value(entry.get("value"), depth + 1, max_depth),
                }
                for entry in value.entries
            ]
        }
    if isinstance(value, SetValue):
        return {
            "element_type": value.element_type,
            "elements": [serialize_property_value(elem, depth + 1, max_depth) for elem in value.elements]
        }
    if isinstance(value, EnumValue):
        return {
            "enum_type": value.enum_type,
            "value": value.value_name
        }
    if isinstance(value, TextValue):
        return {
            "namespace": value.namespace,
            "key": value.key,
            "source_string": value.source_string
        }
    if isinstance(value, DelegateValue):
        return {
            "object_ref": value.object_ref,
            "function_name": value.function_name
        }

    # Fallback: 尝试 asdict 或 str
    if is_dataclass(value):
        return asdict(value)
    return str(value)


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
            "value": serialize_property_value(prop.value),  # None → JSON null automatically
            "array_index": prop.array_index
        }
        props_list.append(prop_dict)

    return props_list


def format_blueprint_dict(blueprint: BlueprintMetadata, blueprint_name: str = None) -> Dict:
    """
    格式化 BlueprintMetadata 用于 JSON 输出（D-04, D-20-06）。

    Per D-20-06: blueprint_name 从 package_name 或导出名提取

    Args:
        blueprint: BlueprintMetadata 对象
        blueprint_name: 资产名称（可选）

    Returns:
        Dict: 包含 blueprint_name, parent_class, variables, functions, events, detection_warning
    """
    # 增强的变量输出
    variables_list = [_format_variable_enhanced(var) for var in blueprint.variables]

    # 增强的函数输出
    functions_list = [_format_function_enhanced(func) for func in blueprint.functions]

    # 增强的事件输出
    events_list = [_format_event_enhanced(event) for event in blueprint.events]

    return {
        "blueprint_name": blueprint_name,  # D-20-06
        "parent_class": blueprint.parent_class,  # None if not resolved
        "variables": variables_list,  # 增强格式
        "functions": functions_list,
        "events": events_list,
        "detection_warning": blueprint.detection_warning  # None if no warning
    }


# ============================================================================
# 增强的 JSON 格式化辅助函数 (META-04)
# ============================================================================

def _format_variable_enhanced(variable: BlueprintVariable) -> dict:
    """格式化增强的变量元数据（META-04）"""
    result = {
        "name": variable.var_name,
        "type": {
            "pin_category": variable.var_type.pin_category,
            "pin_sub_category": variable.var_type.pin_subcategory,
            "container_type": variable.var_type.container_type,
            "is_reference": getattr(variable.var_type, 'is_reference', False),
            "is_const": getattr(variable.var_type, 'is_const', False)
        },
        "category": variable.category,
        "default_value": serialize_property_value(variable.default_value),
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
        "meta_data": variable.metadata
    }
    return result


def _format_parameter(parameter: FunctionParameter) -> dict:
    """格式化函数参数（META-04）"""
    return {
        "name": parameter.name,
        "type": parameter.param_type,
        "default_value": serialize_property_value(parameter.default_value),
        "is_input": parameter.is_input,
        "is_output": parameter.is_output,
        "is_optional": parameter.is_optional,
        "property_flags": parameter.property_flags,
        "meta_data": parameter.meta_data
    }


def _format_function_enhanced(function: BlueprintFunction) -> dict:
    """格式化增强的函数元数据（META-04）"""
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
    """格式化增强的事件元数据（META-04）"""
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


def _extract_call_function_parameters(
    node: Any,
    pin_lookup: Optional[Dict] = None,
    node_lookup: Optional[Dict] = None,
    node_name_lookup: Optional[Dict] = None
) -> Dict[str, List[Dict]]:
    """从 K2Node_CallFunction 节点的 pins 中提取函数参数。

    过滤 exec pins，将输入/输出参数分离为结构化数组。
    增强 input_params 的 data_source 字段（数据来源追踪）。

    Args:
        node: K2Node_CallFunction 节点
        pin_lookup: pin_id → (node_guid, pin_name) 查找表（可选，用于 data_source）
        node_lookup: node_guid → node 查找表（可选，用于 data_source）
        node_name_lookup: node_guid → node_name 查找表（可选，用于 data_source）

    Returns:
        Dict: {"input_params": [...], "output_params": [...]}
    """
    input_params: List[Dict] = []
    output_params: List[Dict] = []

    for pin in node.pins:
        if pin.pin_type and pin.pin_type.pin_category == "exec":
            continue

        param: Dict[str, Any] = {
            "name": pin.pin_name,
            "pin_category": pin.pin_type.pin_category if pin.pin_type else "",
        }
        if pin.pin_type:
            if pin.pin_type.pin_subcategory:
                param["pin_subcategory"] = pin.pin_type.pin_subcategory
            if pin.pin_type.is_reference:
                param["is_reference"] = True
        if pin.default_value is not None and pin.default_value != "":
            param["default_value"] = pin.default_value

        if pin.direction == 0:  # Input
            # 添加 data_source 字段（仅当 lookup 可用时）
            if pin_lookup and node_lookup and node_name_lookup:
                from uasset_read.graph.flow_builder import _trace_data_source
                try:
                    data_source = _trace_data_source(pin, pin_lookup, node_lookup, node_name_lookup)
                    if data_source:
                        param["data_source"] = data_source
                except Exception:
                    pass  # 追踪失败时不影响基本参数提取

            input_params.append(param)
        else:  # Output
            output_params.append(param)

    return {"input_params": input_params, "output_params": output_params}


def _format_components(components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """格式化组件列表用于 JSON 输出（D-06）。"""
    result = []
    for comp in components:
        comp_dict = {
            "name": comp.get("name", ""),
            "class": comp.get("class", ""),
            "properties": comp.get("properties", {}),
            "transforms": {},
        }
        transforms = comp.get("transforms", {})
        for key, value in transforms.items():
            if is_dataclass(value) and not isinstance(value, type):
                comp_dict["transforms"][key] = asdict(value)
            else:
                comp_dict["transforms"][key] = value
        result.append(comp_dict)
    return result


def _format_linker_summary(result: ParseResult) -> Dict[str, Any]:
    """序列化 PackageLinker 对象图为 JSON 可输出的摘要。

    包含对象计数、根对象列表和完整导出/导入对象列表。
    避免序列化循环引用（outer、linker 等），仅输出名称和类信息。
    当 linker 为 None 时，返回基于 import_map/export_map 的基础信息。
    """
    linker = result.linker

    def _instance_summary(inst) -> Dict[str, Any]:
        """将 UObjectInstance 转换为可序列化的摘要字典。"""
        return {
            "name": inst.object_name,
            "class": inst.object_class,
            "is_import": inst.is_import,
            "outer": inst.outer.object_name if inst.outer else None,
        }

    if linker is None:
        # Linker 未创建时，基于 import_map/export_map 返回基础信息
        export_objects = []
        import_objects = []
        for exp in (result.export_map or []):
            import_objects.append({
                "name": exp.object_name if isinstance(exp.object_name, str) else f"<name_id_{exp.object_name}>",
                "class": "",
                "is_import": False,
                "outer": None,
            })
        for imp in (result.import_map or []):
            import_objects.append({
                "name": imp.object_name if isinstance(imp.object_name, str) else f"<name_id_{imp.object_name}>",
                "class": "",
                "is_import": True,
                "outer": None,
            })

        return {
            "import_count": len(import_objects),
            "export_count": len(export_objects),
            "root_count": 0,
            "root_objects": [],
            "exports": export_objects,
            "imports": import_objects,
            "status": "not_available",
        }

    export_objects = [
        _instance_summary(inst)
        for inst in getattr(linker, '_export_objects', [])
    ]
    import_objects = [
        _instance_summary(inst)
        for inst in getattr(linker, '_import_objects', [])
    ]
    root_objects = [
        _instance_summary(inst)
        for inst in getattr(linker, '_root_objects', [])
    ]

    return {
        "import_count": len(import_objects),
        "export_count": len(export_objects),
        "root_count": len(root_objects),
        "root_objects": root_objects,
        "exports": export_objects,
        "imports": import_objects,
        "status": "ok",
    }
