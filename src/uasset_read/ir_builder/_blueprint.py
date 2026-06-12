"""IR 构建层 — 蓝图、反编译函数、执行链、变量。"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from uasset_read.ir_builder._utils import _safe_str, _normalize_guid, _classify_variable
from uasset_read.models.ir import (
    BlueprintIR,
    BlueprintFunctionIR,
    BlueprintEventIR,
    DecompiledFunctionIR,
    ExecutionChainIR,
    VariableIR,
)
from uasset_read.serializers.object_resources import PackageIndex

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult


def _build_blueprint_ir(result: "ParseResult") -> BlueprintIR | None:
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


def _build_decompiled_functions_ir(result: "ParseResult") -> list[DecompiledFunctionIR]:
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


def _build_execution_chains_ir(result: "ParseResult") -> list[ExecutionChainIR]:
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


def _build_variables_ir(result: "ParseResult") -> list[VariableIR]:
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
