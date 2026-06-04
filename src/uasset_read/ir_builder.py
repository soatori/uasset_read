"""IR 构建层 — 将 ParseResult 转换为 PackageIR。

构建阶段处理所有 FPackageIndex 跨引用解析和 GUID 标准化。
渲染器只接收 PackageIR，不访问 ParseResult。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    PropertyIR,
    ExportIR,
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


# Blueprint 元数据键列表 — 与 cpp_constructor_ir_builder.py 保持一致
_BLUEPRINT_METADATA_KEYS = frozenset({
    "BlueprintSystemVersion",
    "GeneratedClass",
    "SimpleConstructionScript",
    "bCanEverTick",
    "bCanEverRender",
    "bStartWithTickEnabled",
    "bReplicates",
    "NetUpdateFrequency",
    "MinNetUpdateFrequency",
    "NetPriority",
})


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

    return PackageIR(
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
    )


def _build_header(result: ParseResult) -> PackageHeaderIR:
    summary = result.summary
    version = _get_version_string(result)

    return PackageHeaderIR(
        package_name=_safe_str(getattr(summary, "package_name", None)),
        package_class=_safe_str(getattr(summary, "package_class", None)),
        package_flags=getattr(summary, "package_flags", 0) or 0,
        total_export_count=getattr(summary, "total_export_count", 0) or 0,
        total_import_count=getattr(summary, "total_import_count", 0) or 0,
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
    )


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
    """从 ParseResult.blueprint 构建 BlueprintIR。"""
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


def _extract_parameters(func) -> list[dict]:
    """从 KismetDecompiledResult 中提取参数信息。

    优先使用 semantic_calls 中的参数信息，回退到 signature 解析。
    """
    # 如果 semantic_calls 包含参数信息
    if func.semantic_calls:
        for call in func.semantic_calls:
            params = call.get("parameters")
            if params:
                return params

    # 从 local_variables 回退
    if func.local_variables:
        return [{"name": v.get("name", ""), "param_type": v.get("type", "")} for v in func.local_variables]

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
    """从 ParseResult.blueprint.variables 构建 VariableIR 列表。"""
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
        ))
    return variables


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
