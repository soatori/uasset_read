"""IR 构建层 — 将 ParseResult 转换为 PackageIR。

构建阶段处理所有 FPackageIndex 跨引用解析和 GUID 标准化。
渲染器只接收 PackageIR，不访问 ParseResult。
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    PropertyIR,
    ExportIR,
    ExportRawIR,
    GraphIR,
    NodeIR,
    PinIR,
    LinkerSummaryIR,
    BlueprintIR,
    BlueprintFunctionIR,
    BlueprintEventIR,
    DecompiledFunctionIR,
    ExecutionChainIR,
    VariableIR,
)

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult


from uasset_read.constants import BLUEPRINT_METADATA_KEYS as _BLUEPRINT_METADATA_KEYS
from uasset_read.serializers.object_resources import PackageIndex


def _classify_variable(var) -> str:
    """分类蓝图变量。"""
    name = getattr(var, "var_name", "") or ""
    if name in _BLUEPRINT_METADATA_KEYS:
        return "metadata"
    if getattr(var, "is_component", False):
        return "component"
    if "InputAction" in name or "InputAxis" in name:
        return "input_action"
    return "user"


def build_package_ir(result: "ParseResult | LinkerParseResult") -> PackageIR:
    """将 ParseResult 转换为 PackageIR。

    构建阶段：
    1. 从 summary 提取 header
    2. 逐条转换 export_map 为 ExportIR
    3. 通过 linker 解析 import/export 路径
    4. GUID 标准化为 32 位小写 hex

    tolerant 模式：单个 Export 解析失败时跳过该项继续。
    """
    header = _build_header(result)
    exports = _build_exports(result)
    linker = _build_linker(result)

    # 构建 function_graphs（从 result.graphs）
    function_graphs = []
    fallback_graphs = getattr(result, "metadata", {}).get("function_graphs_fallback")
    if fallback_graphs:
        function_graphs = list(fallback_graphs)
    elif hasattr(result, 'graphs') and result.graphs:
        try:
            function_graphs = _build_function_graphs_safe(result)
        except Exception as e:
            if hasattr(result, "warnings"):
                result.warnings.append(f"function_graphs generation skipped: {e}")

    status = _result_status(result)
    metadata = getattr(result, "metadata", None) or {}
    errors = list(getattr(result, "errors", None) or [])

    if errors:
        status_code = "PARSE_ERROR"
        status_message = errors[0]
    elif metadata.get("lightweight_tolerant_parse"):
        status_code = "LIGHTWEIGHT_TOLERANT_PARSE"
        status_message = (
            f"轻量容错解析：导出数量过多"
            f"({getattr(result.summary, 'export_count', '?')})，已降级处理"
        )
    else:
        status_code = None
        status_message = None

    ir = PackageIR(
        header=header,
        name_map=list(result.name_map) if result.name_map else [],
        imports=_build_imports(result),
        exports=exports,
        linker=linker,
        blueprint=_build_blueprint_ir(result),
        decompiled_functions=_build_decompiled_functions_ir(result),
        execution_chains=_build_execution_chains_ir(result),
        variables=_build_variables_ir(result),
        diagnostics=result.diagnostics or [],
        function_graphs=function_graphs,
        resolved_parent_assets=list(getattr(result, "resolved_parent_assets", None) or []),
        inherited_blueprint_graphs=list(getattr(result, "inherited_blueprint_graphs", None) or []),
        logic_sources=list(getattr(result, "logic_sources", None) or []),
        soft_object_paths=list(getattr(result, "soft_references", None) or []),
        soft_package_references=list(getattr(result, "soft_package_references", None) or []),
        depends_map=list(getattr(result.summary, "depends_map", None) or []) if result.summary else [],
        resolved_depends_map=_build_resolved_depends_map(result),
        asset_registry_data_offset=_safe_int(getattr(result.summary, "asset_registry_data_offset", 0)) if result.summary else 0,
        errors=errors,
        status=status,
        status_message=status_message,
        status_code=status_code,
    )

    # 绑定函数/事件实现关联
    if ir.blueprint is not None:
        _bind_implementations(ir.blueprint, ir.decompiled_functions, ir.function_graphs)

    return ir


def _result_status(result: "ParseResult | LinkerParseResult") -> str:
    # 非成功分支
    if not getattr(result, "is_success", False):
        if (
            getattr(result, "summary", None) is not None
            or getattr(result, "name_map", None)
            or getattr(result, "import_map", None)
            or getattr(result, "export_map", None)
        ):
            return "partial"
        return "failed"

    # is_success=True 分支：综合检查 export 级 parse_status
    if getattr(result, "errors", None):
        return "partial"
    metadata = getattr(result, "metadata", None) or {}
    if metadata.get("lightweight_tolerant_parse"):
        return "partial"

    # 检查 export 级状态
    export_map = getattr(result, "export_map", None) or []
    if export_map and isinstance(export_map, list):
        _PARTIAL_STATUSES = {"opaque", "skipped", "partial_metadata", "opaque_unversioned", "fallback"}
        _FAILED_STATUSES = {"failed"}
        failed_count = 0
        partial_count = 0
        for exp in export_map:
            status = getattr(exp, "parse_status", None)
            if status in _FAILED_STATUSES:
                failed_count += 1
            elif status in _PARTIAL_STATUSES:
                partial_count += 1
        if failed_count == len(export_map):
            return "failed"
        if failed_count > 0 or partial_count > 0:
            return "partial"

    return "success"


def _build_function_graphs_safe(result: "ParseResult | LinkerParseResult") -> list[dict]:
    """Build function_graphs with a simple complexity guard for large graphs."""
    graphs = getattr(result, "graphs", None) or []
    total_nodes = sum(len(getattr(graph, "nodes", None) or []) for graph in graphs)
    total_pins = sum(
        len(getattr(node, "pins", None) or [])
        for graph in graphs
        for node in (getattr(graph, "nodes", None) or [])
    )
    max_nodes = 900
    max_pins = 12000
    if total_nodes > max_nodes or total_pins > max_pins:
        if hasattr(result, "warnings"):
            result.warnings.append(
                "function_graphs generation skipped due to graph complexity "
                f"(nodes={total_nodes}, pins={total_pins})"
            )
        return _build_function_graph_summaries(result)

    from uasset_read.graph import build_function_graphs
    blueprint_functions = None
    if hasattr(result, 'blueprint') and result.blueprint:
        blueprint_functions = getattr(result.blueprint, 'functions', None)
    return build_function_graphs(graphs, blueprint_functions)


def _build_function_graph_summaries(result: "ParseResult | LinkerParseResult") -> list[dict]:
    entries = []
    for graph in getattr(result, "graphs", None) or []:
        for node in getattr(graph, "nodes", None) or []:
            if getattr(node, "class_name", "") != "K2Node_FunctionEntry":
                continue
            function_name = "Unknown"
            node_data = getattr(node, "node_data", None)
            ref = None
            if isinstance(node_data, dict):
                ref = node_data.get("function_reference")
            elif node_data is not None:
                ref = getattr(node_data, "function_reference", None)
            raw_name = getattr(ref, "member_name", None) if ref is not None else None
            if raw_name and raw_name != "None":
                function_name = raw_name.split("/")[-1]
            entries.append({
                "function_name": function_name,
                "graph_source": getattr(graph, "graph_name", ""),
                "entry_node_guid": getattr(node, "node_guid", ""),
                "signature": {"return_type": "", "parameters": []},
                "execution_flows": [],
                "fallback_reason": "graph_complexity_limit",
            })
    return entries


def _build_header(result: ParseResult) -> PackageHeaderIR:
    summary = result.summary
    version = _get_version_string(result)

    return PackageHeaderIR(
        package_name=_safe_str(getattr(summary, "package_name", None)),
        package_class=_safe_str(getattr(summary, "package_class", None)),
        package_flags=_safe_int(getattr(summary, "package_flags", 0)),
        total_export_count=_safe_int(getattr(summary, "export_count", 0)),
        total_import_count=_safe_int(getattr(summary, "import_count", 0)),
        ue_version=version,
    )


def _get_version_string(result: ParseResult) -> str:
    """从 version_container 提取 UE 版本字符串。"""
    vc = result.version_container
    if vc is None:
        return "unknown"

    # 优先尝试 get_ue_version_string（如果存在且可调用）
    method = getattr(vc, "get_ue_version_string", None)
    if callable(method):
        try:
            return method()
        except Exception:
            pass

    # 回退：基于 is_ue5 判断
    if getattr(vc, "is_ue5", False):
        return "5.x"
    return "4.x"


def _build_imports(result: ParseResult) -> list[dict]:
    imports = []
    for imp in result.import_map or []:
        imports.append({
            "class_package": _safe_str(getattr(imp, "class_package", None)),
            "class_name": _safe_str(getattr(imp, "class_name", None)),
            "object_name": _safe_str(getattr(imp, "object_name", None)),
        })
    return imports


def _build_exports(result: ParseResult) -> list[ExportIR]:
    exports = []
    for idx, export in enumerate(result.export_map or []):
        try:
            export_ir = _build_export_ir(idx, export, result)
            exports.append(export_ir)
        except Exception:
            # tolerant 模式：跳过失败的 export
            pass
    return exports


def _build_export_ir(idx: int, export, result: ParseResult) -> ExportIR:
    outer_resolved = _resolve_package_index(result, getattr(export, "outer_index", None))
    super_resolved = _resolve_package_index(result, getattr(export, "super_index", None))

    parent_class = None
    if result.blueprint and getattr(result.blueprint, "parent_class", None):
        parent_class = result.blueprint.parent_class

    properties = []
    for prop in getattr(export, "properties", None) or []:
        properties.append(_build_property_ir(prop))

    graphs = []
    for graph in getattr(export, "graphs", None) or []:
        graphs.append(_build_graph_ir(graph))

    bulk_data = getattr(export, "bulk_data_header", None)
    asset_type_data = getattr(export, "_asset_type_data", None)

    # 构建 UE 原始导出表字段
    raw = _build_export_raw_ir(export)

    return ExportIR(
        index=idx,
        object_name=_safe_str(getattr(export, "object_name", None)),
        object_class=_safe_str(getattr(export, "object_class", None)),
        serial_size=getattr(export, "serial_size", 0) or 0,
        outer_index_resolved=outer_resolved,
        super_index_resolved=super_resolved,
        parent_class=parent_class,
        properties=properties,
        graphs=graphs,
        bulk_data=bulk_data,
        asset_type_data=asset_type_data,
        parse_status=_safe_str(getattr(export, "parse_status", "success")) or "success",
        fallback_reason=(
            _safe_str(getattr(export, "fallback_reason", None))
            if getattr(export, "fallback_reason", None) is not None else None
        ),
        error_message=(
            _safe_str(getattr(export, "error_message", None))
            if getattr(export, "error_message", None) is not None else None
        ),
        ue_export_raw=raw,
        diagnostics=_build_export_diagnostics(export),
    )


def _build_export_raw_ir(export) -> ExportRawIR:
    """从 ObjectExport 构建 UE 原始导出表字段。"""

    def _pkg_index_raw(pi) -> int:
        """提取 PackageIndex 原始整数值。"""
        if pi is None:
            return 0
        return getattr(pi, "index", 0)

    return ExportRawIR(
        class_index=_pkg_index_raw(getattr(export, "class_index", None)),
        super_index=_pkg_index_raw(getattr(export, "super_index", None)),
        outer_index=_pkg_index_raw(getattr(export, "outer_index", None)),
        template_index=_pkg_index_raw(getattr(export, "template_index", None)),
        object_flags=getattr(export, "object_flags", 0) or 0,
        serial_offset=getattr(export, "serial_offset", 0) or 0,
        package_flags=getattr(export, "package_flags", 0) or 0,
        b_forced_export=bool(getattr(export, "b_forced_export", False)),
        b_not_for_client=bool(getattr(export, "b_not_for_client", False)),
        b_not_for_server=bool(getattr(export, "b_not_for_server", False)),
        b_is_inherited_instance=bool(getattr(export, "b_is_inherited_instance", False)),
        b_not_always_loaded_for_editor_game=bool(getattr(export, "b_not_always_loaded_for_editor_game", True)),
        b_is_asset=bool(getattr(export, "b_is_asset", False)),
        b_generate_public_hash=bool(getattr(export, "b_generate_public_hash", False)),
        script_serialization_start_offset=getattr(export, "script_serialization_start_offset", 0) or 0,
        script_serialization_end_offset=getattr(export, "script_serialization_end_offset", 0) or 0,
        guid=_safe_str(getattr(export, "guid", "")) or "",
    )


def _build_export_diagnostics(export) -> dict | None:
    """从 ObjectExport.transforms 构建诊断信息。"""
    transforms = getattr(export, "transforms", None) or {}
    if not transforms:
        return None
    return dict(transforms)


def _build_property_ir(prop) -> PropertyIR:
    return PropertyIR(
        name=_safe_str(getattr(prop, "name", None)),
        type=_safe_str(getattr(prop, "type", None)),
        value=getattr(prop, "value", None),
        array_index=getattr(prop, "array_index", -1) or -1,
        guid=_normalize_guid(getattr(prop, "guid", None)),
    )


def _build_graph_ir(graph) -> GraphIR:
    nodes = []
    for node in getattr(graph, "nodes", None) or []:
        nodes.append(_build_node_ir(node))

    return GraphIR(
        graph_guid=_normalize_guid(getattr(graph, "graph_guid", None)),
        graph_name=_safe_str(getattr(graph, "graph_name", None)),
        graph_class=_safe_str(getattr(graph, "graph_class", None)),
        nodes=nodes,
        execution_chains=getattr(graph, "execution_chains", None) or [],
    )


def _build_node_ir(node) -> NodeIR:
    pins = []
    for pin in getattr(node, "pins", None) or []:
        pins.append(_build_pin_ir(pin))

    return NodeIR(
        node_guid=_normalize_guid(getattr(node, "node_guid", None)),
        node_class=_safe_str(getattr(node, "class_name", None)),
        node_comment=getattr(node, "node_comment", None),
        pins=pins,
        execution_flow=getattr(node, "execution_flow", None) or [],
        macro_expansion=getattr(node, "macro_expansion", None),
    )


def _build_pin_ir(pin) -> PinIR:
    linked_to = []
    for ref in getattr(pin, "linked_to_raw", None) or []:
        guid = _extract_pin_guid(ref)
        if guid:
            linked_to.append(guid)

    direction = "EGPD_Input"
    if getattr(pin, "direction", 0) == 1:
        direction = "EGPD_Output"

    return PinIR(
        pin_name=_safe_str(getattr(pin, "pin_name", None)),
        pin_type=_safe_str(getattr(pin, "pin_type", None)),
        pin_type_value=getattr(pin, "pin_type_value", None),
        linked_to=linked_to,
        direction=direction,
        default_value=getattr(pin, "default_value", None),
    )


def _resolve_package_index(result: ParseResult, pkg_index) -> str | None:
    """将 PackageIndex 解析为可读路径字符串。"""
    if pkg_index is None or result.linker is None:
        return None
    try:
        obj_ref = result.linker.resolve_package_index(pkg_index)
        if obj_ref is None:
            return None
        # UObjectInstance 有 get_full_name() 方法
        if hasattr(obj_ref, "get_full_name"):
            return obj_ref.get_full_name()
        return str(obj_ref)
    except Exception:
        return None


def _build_resolved_depends_map(result: "ParseResult") -> list[list[dict]]:
    """将 DependsMap 的原始 PackageIndex 解析为可读路径。

    Returns:
        二维列表：外层按 export 索引，内层为 [{index, path}] 列表。
    """
    if not result.summary:
        return []
    raw_map = getattr(result.summary, "depends_map", None) or []
    if not raw_map:
        return []

    resolved: list[list[dict]] = []
    for dep_indices in raw_map:
        row: list[dict] = []
        for idx in dep_indices:
            pkg_idx = PackageIndex(idx)
            path = _resolve_package_index(result, pkg_idx)
            row.append({"index": idx, "path": path})
        resolved.append(row)
    return resolved


def _build_linker(result: ParseResult) -> LinkerSummaryIR | None:
    linker = result.linker
    if linker is None:
        return None

    import_paths = []
    for imp in result.import_map or []:
        path = f"{_safe_str(getattr(imp, 'class_package', None))}.{_safe_str(getattr(imp, 'class_name', None))}"
        if path.strip("."):
            import_paths.append(path)

    export_paths = []
    for exp in result.export_map or []:
        name = getattr(exp, "object_name", "")
        if name:
            export_paths.append(name)

    return LinkerSummaryIR(
        has_linker=True,
        import_paths=import_paths,
        export_paths=export_paths,
    )


def _build_blueprint_ir(result: ParseResult) -> BlueprintIR | None:
    """从 ParseResult.blueprint 构建 BlueprintIR（完整元数据）。"""
    bp = result.blueprint
    if bp is None:
        return None

    functions = []
    for func in bp.functions:
        functions.append(BlueprintFunctionIR(
            name=func.name,
            return_type=func.return_type,
            parameters=[{
                "name": p.name,
                "param_type": p.param_type,
                "default_value": p.default_value,
                "is_input": p.is_input,
                "is_output": p.is_output,
            } for p in func.parameters],
            function_flags=getattr(func, "function_flags", 0) or 0,
            is_pure=getattr(func, "is_pure", False),
            is_blueprint_callable=getattr(func, "is_blueprint_callable", False),
            is_const=getattr(func, "is_const", False),
            is_static=getattr(func, "is_static", False),
            is_net=getattr(func, "is_net", False),
            is_net_reliable=getattr(func, "is_net_reliable", False),
            is_blueprint_private=getattr(func, "is_blueprint_private", False),
            access_specifier=getattr(func, "access_specifier", "Public") or "Public",
            meta_data=dict(getattr(func, "meta_data", None) or {}),
        ))

    events = []
    for evt in bp.events:
        events.append(BlueprintEventIR(
            name=evt.name,
            event_type=evt.event_type,
            parameters=[{
                "name": p.name,
                "param_type": p.param_type,
                "default_value": p.default_value,
                "is_input": p.is_input,
                "is_output": p.is_output,
            } for p in evt.parameters],
            function_flags=getattr(evt, "function_flags", 0) or 0,
            is_override=getattr(evt, "is_override", False),
            override_parent_class=_safe_str(getattr(evt, "override_parent_class", None)),
            override_parent_event=_safe_str(getattr(evt, "override_parent_event", None)),
            is_interface_event=getattr(evt, "is_interface_event", False),
            interface_class=_safe_str(getattr(evt, "interface_class", None)),
            is_net=getattr(evt, "is_net", False),
            is_net_multicast=getattr(evt, "is_net_multicast", False),
            is_replicated=getattr(evt, "is_replicated", False),
            is_cosmetic=getattr(evt, "is_cosmetic", False),
            is_static=getattr(evt, "is_static", False),
            meta_data=dict(getattr(evt, "meta_data", None) or {}),
        ))

    components = list(result.components) if result.components else []

    return BlueprintIR(
        parent_class=bp.parent_class,
        functions=functions,
        events=events,
        components=components,
    )


def _build_decompiled_functions_ir(result: ParseResult) -> list[DecompiledFunctionIR]:
    """从 ParseResult.decompiled_functions 构建 DecompiledFunctionIR 列表。"""
    decompiled = []
    for func in result.decompiled_functions or []:
        # 从 signature 解析 return_type（签名格式："ReturnType FuncName(params)"）
        return_type = _extract_return_type(func.signature)
        parameters = _extract_parameters(func)
        decompiled.append(DecompiledFunctionIR(
            name=func.function_name,
            signature=func.signature,
            cpp_code=func.cpp_code,
            parameters=parameters,
            return_type=return_type,
            fallback_reasons=func.fallback_reasons,
        ))
    return decompiled


def _extract_return_type(signature: str) -> str:
    """从 C++ 函数签名中提取返回类型。

    签名格式："ReturnType FuncName(params)"
    """
    if not signature:
        return "void"
    # 查找第一个空格（返回类型和函数名之间的分隔）
    space_idx = signature.find(" ")
    if space_idx > 0:
        return signature[:space_idx]
    return "void"


def _extract_parameters_from_signature(signature: str) -> list[dict]:
    """从 C++ 函数签名中解析参数列表。

    签名格式: "ReturnType FuncName(param1, param2, ...)"
    返回: [{"name": "param1", "type": "int32"}, ...]
    """
    if not signature:
        return []

    # 提取括号内的参数部分
    match = re.search(r'\(([^)]*)\)', signature)
    if not match:
        return []

    params_str = match.group(1).strip()
    if not params_str:
        return []

    params = []
    for param in params_str.split(','):
        param = param.strip()
        if not param:
            continue
        # 分离类型和名称: "int32 EntryPoint" → ("int32", "EntryPoint")
        parts = param.rsplit(None, 1)
        if len(parts) == 2:
            params.append({"name": parts[1], "type": parts[0]})
        elif len(parts) == 1:
            # 只有类型没有名称
            params.append({"name": "", "type": parts[0]})
    return params


def _extract_parameters(func) -> list[dict]:
    """从 KismetDecompiledResult 中提取参数信息。

    优先级: semantic_calls → local_variables → signature 解析
    """
    # 1) semantic_calls 中的 arguments
    if func.semantic_calls:
        for call in func.semantic_calls:
            args = call.get("arguments")
            if args:
                return [{"name": a, "type": ""} for a in args]

    # 2) local_variables
    if func.local_variables:
        return [{"name": v.get("name", ""), "type": v.get("type", "")} for v in func.local_variables]

    # 3) 从 signature 字符串解析
    if func.signature:
        return _extract_parameters_from_signature(func.signature)

    return []


def _build_execution_chains_ir(result: ParseResult) -> list[ExecutionChainIR]:
    """从所有图的执行链构建 ExecutionChainIR 列表。"""
    chains = []
    for graph in result.graphs or []:
        for node in graph.nodes or []:
            # 查找事件节点作为链的起始
            class_name = getattr(node, "class_name", "") or ""
            if "Event" not in class_name:
                continue
            # 从事件节点的引脚获取事件名
            event_name = _get_event_name_from_node(node)
            # 构建从该事件开始的执行链
            chain = _trace_execution_from_node(node, graph)
            if chain:
                chains.append(ExecutionChainIR(event=event_name, chain=chain))
    return chains


def _build_variables_ir(result: ParseResult) -> list[VariableIR]:
    """从 ParseResult.blueprint.variables 构建 VariableIR 列表（完整元数据）。"""
    variables = []
    bp = result.blueprint
    if bp is None:
        return variables
    for var in bp.variables or []:
        kind = _classify_variable(var)
        if kind == "metadata":
            continue  # 跳过元数据变量
        var_type = _format_var_type(var)
        default_value = _safe_str(getattr(var, "default_value", None)) or None
        variables.append(VariableIR(
            name=_safe_str(getattr(var, "var_name", None)),
            type=var_type,
            default_value=default_value,
            kind=kind,
            guid=_normalize_guid(getattr(var, "var_guid", None)),
            category=_safe_str(getattr(var, "category", None)),
            property_flags=getattr(var, "property_flags", 0) or 0,
            replication_condition=getattr(var, "replication_condition", 0) or 0,
            rep_notify_func=_safe_str(getattr(var, "rep_notify_func", None)),
            friendly_name=_safe_str(getattr(var, "friendly_name", None)),
            metadata=dict(getattr(var, "metadata", None) or {}),
            flags_labels=list(getattr(var, "flags_labels", None) or []),
            edit_condition=_safe_str(getattr(var, "edit_condition", None)),
            is_edit_anywhere=getattr(var, "is_edit_anywhere", False),
            is_visible_anywhere=getattr(var, "is_visible_anywhere", False),
            is_blueprint_read_only=getattr(var, "is_blueprint_read_only", False),
            is_transient=getattr(var, "is_transient", False),
            is_replicated=getattr(var, "is_replicated", False),
            is_rep_notify=getattr(var, "is_rep_notify", False),
            is_expose_on_spawn=getattr(var, "is_expose_on_spawn", False),
            is_save_game=getattr(var, "is_save_game", False),
        ))
    return variables


# 事件别名映射：Blueprint 事件名 → 常见 C++/蓝图实现函数名
_EVENT_ALIASES: dict[str, list[str]] = {
    "ReceiveBeginPlay": ["BeginPlay"],
    "ReceiveTick": ["Tick"],
    "ReceiveEndPlay": ["EndPlay"],
    "ReceiveAnyDamage": ["AnyDamage"],
    "ReceivePointDamage": ["PointDamage"],
    "ReceiveRadialDamage": ["RadialDamage"],
    "ReceiveActorBeginOverlap": ["ActorBeginOverlap"],
    "ReceiveActorEndOverlap": ["ActorEndOverlap"],
    "ReceiveActorBeginCursorOver": ["ActorBeginCursorOver"],
    "ReceiveActorEndCursorOver": ["ActorEndCursorOver"],
    "ReceiveHit": ["Hit"],
    "ReceiveDestroyed": ["Destroyed"],
}


def _bind_implementations(
    blueprint: BlueprintIR,
    decompiled: list[DecompiledFunctionIR],
    function_graphs: list[dict],
) -> None:
    """将 decompiled_functions 和 function_graphs 关联到 blueprint 的函数/事件。

    匹配优先级：
    1. 精确函数名匹配 decompiled_functions.name
    2. 事件别名匹配（如 ReceiveBeginPlay → BeginPlay）
    3. function_graphs[].function_name 匹配
    4. 均未匹配 → implementation_status 保持 "missing"
    """
    # 构建查找索引
    decompiled_by_name: dict[str, DecompiledFunctionIR] = {}
    for f in decompiled:
        if f.name not in decompiled_by_name:
            decompiled_by_name[f.name] = f

    graph_by_name: dict[str, dict] = {}
    for g in function_graphs:
        fn = g.get("function_name", "")
        if fn and fn not in graph_by_name:
            graph_by_name[fn] = g

    for func in blueprint.functions:
        _bind_single_implementation(func, decompiled_by_name, graph_by_name, [func.name])

    for evt in blueprint.events:
        candidates = [evt.name]
        aliases = _EVENT_ALIASES.get(evt.name)
        if aliases:
            candidates.extend(aliases)
        _bind_single_implementation(evt, decompiled_by_name, graph_by_name, candidates)


def _bind_single_implementation(
    item,
    decompiled_by_name: dict[str, DecompiledFunctionIR],
    graph_by_name: dict[str, dict],
    candidate_names: list[str],
) -> None:
    """绑定单个函数/事件的实现。"""
    matched_decompiled = None
    match_count = 0

    for name in candidate_names:
        df = decompiled_by_name.get(name)
        if df:
            matched_decompiled = df
            match_count += 1

    if matched_decompiled:
        item.implementation = {
            "name": matched_decompiled.name,
            "signature": matched_decompiled.signature,
            "cpp_code": matched_decompiled.cpp_code,
            "parameters": matched_decompiled.parameters,
            "return_type": matched_decompiled.return_type,
        }
        if matched_decompiled.fallback_reasons:
            item.implementation["fallback_reasons"] = matched_decompiled.fallback_reasons
        item.implementation_status = "decompiled"
        if match_count > 1:
            item.implementation["ambiguous_match"] = True
        return

    # 尝试 function_graphs
    for name in candidate_names:
        fg = graph_by_name.get(name)
        if fg:
            item.function_graph = {
                "function_name": fg.get("function_name", ""),
                "graph_source": fg.get("graph_source", ""),
                "entry_node_guid": fg.get("entry_node_guid", ""),
            }
            item.implementation_status = "graph_only"
            return

    # 无匹配，保持 "missing"


def _format_var_type(var) -> str:
    """将 BlueprintVariable 的 var_type 格式化为可读字符串。"""
    pin_type = getattr(var, "var_type", None)
    if pin_type is None:
        return "Unknown"
    category = getattr(pin_type, "pin_category", "") or ""
    subcategory = getattr(pin_type, "pin_subcategory", "") or ""
    object_name = getattr(pin_type, "pin_subcategory_object_name", None) or ""
    container = getattr(pin_type, "container_type", 0)

    # 容器类型前缀
    container_map = {1: "TArray", 2: "TMap", 3: "TSet"}
    prefix = container_map.get(container, "")

    # 基础类型
    if category == "struct" and object_name:
        base = object_name
    elif category == "class" and object_name:
        base = object_name
    elif category == "enum" and subcategory:
        base = subcategory
    elif subcategory:
        base = subcategory
    elif category:
        base = category
    else:
        base = "Unknown"

    if prefix:
        return f"{prefix}<{base}>"
    return base


def _get_event_name_from_node(node) -> str:
    """从事件节点提取事件名称。"""
    # 优先使用 node_comment（事件节点的注释通常是事件名）
    comment = getattr(node, "node_comment", None)
    if comment:
        return comment
    # 回退到类名
    return getattr(node, "class_name", "Unknown") or "Unknown"


def _trace_execution_from_node(start_node, graph) -> list[str]:
    """从起始节点追踪执行流链。"""
    visited = set()
    chain = []
    current = start_node
    while current:
        guid = getattr(current, "node_guid", None)
        if not guid or guid in visited:
            break
        visited.add(guid)
        class_name = getattr(current, "class_name", "") or "Unknown"
        chain.append(class_name)
        # 找到下一个执行节点
        next_node = _find_next_exec_node(current, graph, visited)
        current = next_node
    return chain


def _find_next_exec_node(node, graph, visited) -> object | None:
    """从节点的执行输出引脚找到下一个节点。"""
    for pin in node.pins or []:
        # 执行输出引脚（direction=1 表示输出）
        direction = getattr(pin, "direction", 0)
        if direction != 1:
            continue
        pin_type = getattr(pin, "pin_type", None)
        pin_category = ""
        if pin_type:
            pin_category = getattr(pin_type, "pin_category", "") or ""
        if pin_category != "exec":
            continue
        # 遍历 linked_to_raw 找到下一个节点
        for ref in pin.linked_to_raw or []:
            target_pin_id = None
            if isinstance(ref, dict):
                target_pin_id = ref.get("pin_guid") or ref.get("pin_id")
            elif isinstance(ref, str):
                target_pin_id = ref
            else:
                target_pin_id = getattr(ref, "pin_guid", None) or getattr(ref, "pin_id", None)
            if not target_pin_id:
                continue
            # 查找目标引脚所在的节点
            target_node = _find_node_by_pin_id(target_pin_id, graph, visited)
            if target_node:
                return target_node
    return None


def _find_node_by_pin_id(pin_id: str, graph, visited) -> object | None:
    """根据引脚 ID 查找对应的节点（未访问过的）。"""
    for node in graph.nodes or []:
        node_guid = getattr(node, "node_guid", None)
        if node_guid in visited:
            continue
        for pin in node.pins or []:
            pin_guid = getattr(pin, "pin_id", None)
            if pin_guid == pin_id:
                return node
    return None


def _safe_str(value) -> str:
    """安全地将值转为字符串，None 返回空字符串。"""
    if value is None:
        return ""
    return str(value)


def _safe_int(value, default: int = 0) -> int:
    """安全地将值转为 int，仅接受真实 int 和明确数字字符串，其他类型返回 default。

    MagicMock 对象实现了 __int__ 返回 1，因此必须显式排除非 int 对象。
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _normalize_guid(guid: str | None) -> str | None:
    """将 GUID 标准化为 32 位小写 hex（无横杠）。"""
    if not guid:
        return None
    cleaned = str(guid).replace("-", "").lower()
    if len(cleaned) == 32 and all(c in "0123456789abcdef" for c in cleaned):
        return cleaned
    return None


def _extract_pin_guid(ref) -> str | None:
    """从 Pin 引用中提取并标准化 GUID。"""
    if isinstance(ref, dict):
        raw = ref.get("pin_guid") or ref.get("pin_id")
        return _normalize_guid(raw) if raw else None
    if isinstance(ref, str):
        return _normalize_guid(ref)
    raw = getattr(ref, "pin_guid", None) or getattr(ref, "pin_id", None)
    return _normalize_guid(raw) if raw else None
