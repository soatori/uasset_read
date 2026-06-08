"""Graph-backed semantic enrichment for Kismet decompilation results."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from uasset_read.models.core import UEdGraph
from uasset_read.kismet.result import KismetDecompiledResult

logger = logging.getLogger(__name__)

# 表达式数量阈值：低于此值的函数体视为"空"，可从图拓扑补充
_EMPTY_BODY_THRESHOLD = 3


def _sanitize_cpp_name(name: str) -> str:
    """将 UE pin 名清理为 C++ 兼容标识符。"""
    cleaned = name.replace(" ", "").replace("/", "").replace("-", "_")
    return cleaned if cleaned else "unnamed"


def enrich_decompiled_functions(
    functions: List[KismetDecompiledResult],
    graphs: List[UEdGraph],
) -> None:
    """Annotate bytecode output with readable EventGraph call semantics.

    Cooked UE5 Blueprint bytecode can be compact enough that the raw token
    stream only produces low-value placeholders. The graph topology still
    carries the event-to-call and parameter mapping, so this pass adds a stable
    semantic view without discarding the original expression tree.
    """
    semantic_calls = extract_eventgraph_semantic_calls(graphs)
    if not semantic_calls:
        # 无 EventGraph 语义数据时，仍尝试为空函数体从图拓扑补充
        _enrich_empty_functions_from_graphs(functions, graphs)
        return

    by_event = {item["event_name"]: item for item in semantic_calls}
    for result in functions:
        if result.function_name == "ExecuteUbergraph_BP_FirstPersonCharacter" or result.function_name.startswith("ExecuteUbergraph_"):
            result.semantic_calls = semantic_calls
            result.cpp_code = _format_ubergraph_semantics(result.function_name, semantic_calls)
            result.warnings.append("Kismet bytecode semantics enriched from EventGraph pin topology")
            continue

        semantic = by_event.get(result.function_name)
        if semantic:
            result.semantic_calls = [semantic]
            result.cpp_code = _format_event_semantics(result.function_name, semantic)
            result.warnings.append("Kismet bytecode semantics enriched from EventGraph pin topology")

    # 第二轮：为空函数体从图拓扑补充执行流
    _enrich_empty_functions_from_graphs(functions, graphs)


def _enrich_empty_functions_from_graphs(
    functions: List[KismetDecompiledResult],
    graphs: List[UEdGraph],
) -> None:
    """对表达式数量极少的函数，尝试从 UEdGraph 拓扑中补充执行流 C++ 代码。

    某些蓝图函数（如 Move、Aim）的 Kismet 字节码本身为空或极简，
    实际逻辑完全由 K2Node 拓扑定义。此函数在主循环之后扫描这些"空壳"函数，
    从对应图的 K2Node_FunctionEntry 追踪执行链并生成可读的 C++ 伪代码。
    """
    for result in functions:
        # 已有 cpp_code 或语义已丰富则跳过
        if result.cpp_code and any("enriched" in w for w in result.warnings):
            continue
        # 表达式数量超过阈值的函数保留原始反编译结果
        if len(result.expressions) > _EMPTY_BODY_THRESHOLD:
            continue

        cpp_code = _enrich_empty_function_from_graph(result.function_name, graphs)
        if cpp_code:
            result.cpp_code = cpp_code
            result.logic_source = "graph_topology"
            result.warnings.append(
                f"Empty bytecode body enriched from UEdGraph K2Node topology "
                f"({len(result.expressions)} expressions)"
            )


def _enrich_empty_function_from_graph(
    function_name: str,
    graphs: List[UEdGraph],
) -> Optional[str]:
    """查找匹配的 K2Node_FunctionEntry 并从图拓扑生成 C++ 代码。

    遍历所有图，找到 K2Node_FunctionEntry 的 function_reference.member_name
    与 function_name 匹配的图，然后追踪执行流并转换为 C++ 伪代码。

    Args:
        function_name: 要补充的函数名（如 "Move", "Aim"）
        graphs: 所有 UEdGraph 列表

    Returns:
        C++ 伪代码字符串，或 None（未找到匹配图）
    """
    from uasset_read.graph import (
        build_execution_flow_entries,
        build_graph_indexes,
        build_normalized_edge_indexes,
        trace_execution_from_event,
    )

    for graph in graphs:
        # 查找匹配的 FunctionEntry 节点
        entry_node = _find_function_entry(graph, function_name)
        if entry_node is None:
            continue

        # 构建 node_lookup 用于提取函数名
        _, node_lookup, _ = build_graph_indexes(graph)
        node_name_lookup = {
            n.node_guid: f"{n.class_name}_{idx}"
            for idx, n in enumerate(graph.nodes)
        }

        # 追踪执行流
        execution_flows = build_execution_flow_entries(graph)
        if not execution_flows:
            # 回退：直接从 FunctionEntry 追踪
            pin_lookup, _, _ = build_graph_indexes(graph)
            edges_by_from_pin, source_edges_by_to_pin = build_normalized_edge_indexes(graph)
            execution_flows = [{
                "start_event": f"FunctionEntry.{function_name}",
                "nodes": trace_execution_from_event(
                    entry_node, pin_lookup, node_lookup, node_name_lookup,
                    edges_by_from_pin, source_edges_by_to_pin,
                ),
            }]

        cpp_code = _flow_to_cpp(function_name, execution_flows, node_lookup)
        if cpp_code:
            return cpp_code

    return None


def _find_function_entry(graph: UEdGraph, function_name: str) -> Optional[Any]:
    """在图中查找匹配函数名的 K2Node_FunctionEntry 节点。

    Args:
        graph: UEdGraph 对象
        function_name: 目标函数名

    Returns:
        匹配的 UEdGraphNode，或 None
    """
    from uasset_read.graph import node_member_name

    for node in graph.nodes:
        if node.class_name != "K2Node_FunctionEntry":
            continue
        member_name = node_member_name(node)
        # 处理路径形式 "/Game/.../FunctionName"
        if '/' in member_name:
            member_name = member_name.split('/')[-1]
        if member_name == function_name:
            return node
    return None


def _flow_to_cpp(
    function_name: str,
    execution_flows: List[Dict[str, Any]],
    node_lookup: Optional[Dict[str, Any]] = None,
) -> str:
    """将执行流拓扑转换为简洁的 C++ 伪代码。

    遍历执行流中的 CallFunction 节点，生成链式调用列表。
    纯函数（Pure）作为数据提供者内联标注，非纯函数作为独立语句。

    Args:
        function_name: 函数名
        execution_flows: build_execution_flow_entries() 返回的执行流列表
        node_lookup: node_guid → UEdGraphNode 查找表（用于提取函数名）

    Returns:
        C++ 伪代码字符串
    """
    lines: List[str] = [f"void {function_name}() {{"]
    call_count = 0

    for flow_entry in execution_flows:
        nodes = flow_entry.get("nodes", [])
        if not nodes:
            continue

        start_event = flow_entry.get("start_event", "")
        # 仅处理 FunctionEntry 流
        if start_event and not start_event.startswith("FunctionEntry."):
            continue

        for node_info in nodes:
            node_type = node_info.get("node_type", "")

            # 跳过起点 FunctionEntry 本身
            if node_type == "K2Node_FunctionEntry":
                continue

            # CallFunction 节点：提取函数名和参数
            if node_type == "K2Node_CallFunction":
                call_str = _format_call_node(node_info, node_lookup)
                if call_str:
                    lines.append(f"    {call_str};")
                    call_count += 1

            # VariableSet 节点：变量赋值
            elif node_type == "K2Node_VariableSet":
                var_name = _variable_name_from_node(node_info, node_lookup)
                if var_name:
                    lines.append(f"    {var_name} = <value>;")
                    call_count += 1

            # VariableGet 节点：变量读取
            elif node_type == "K2Node_VariableGet":
                var_name = _variable_name_from_node(node_info, node_lookup)
                if var_name:
                    lines.append(f"    // read {var_name}")
                    call_count += 1

            # 控制流节点（Branch 等）
            elif node_type == "K2Node_MacroInstance":
                cpp_mapping = node_info.get("cpp_macro_mapping", {})
                macro_expansion = node_info.get("macro_expansion", {})
                macro_name = macro_expansion.get("macro_name", "")
                if cpp_mapping:
                    template = cpp_mapping.get("cpp_template", f"/* {macro_name} */")
                    lines.append(f"    {template}")
                else:
                    lines.append(f"    // {macro_name or node_type}")
                call_count += 1

            elif node_type == "K2Node_IfThenElse":
                branch_type = node_info.get("branch_type", "")
                if branch_type:
                    lines.append(f"    // {node_type} ({branch_type})")

    lines.append("}")

    # 没有实际调用则不生成代码
    if call_count == 0:
        return ""

    return "\n".join(lines)


def _format_call_node(
    node_info: Dict[str, Any],
    node_lookup: Optional[Dict[str, Any]] = None,
) -> str:
    """从执行流节点信息格式化函数调用字符串。

    优先从 node_lookup 中的节点数据提取函数名（function_reference.member_name），
    回退到 data_source 推断。

    Args:
        node_info: 执行流中的节点字典
        node_lookup: node_guid → UEdGraphNode 查找表（可选）

    Returns:
        "FuncName(Arg1, Arg2)" 格式的调用字符串
    """
    from uasset_read.graph import node_member_name

    params = node_info.get("parameters", {})
    input_params = params.get("input_params", []) if isinstance(params, dict) else []

    # 从 node_lookup 提取真实函数名
    func_name = ""
    node_guid = node_info.get("node_guid")
    if node_guid and node_lookup:
        node = node_lookup.get(node_guid)
        if node:
            func_name = node_member_name(node)

    # 回退：从 data_source 推断
    if not func_name:
        for param in input_params:
            if not isinstance(param, dict):
                continue
            ds = param.get("data_source")
            if isinstance(ds, dict):
                for src in ds.get("data_sources", []):
                    if src.get("source_type") == "pure_function" and src.get("function_name"):
                        func_name = src["function_name"]
                        break
            if func_name:
                break

    # 最终回退
    if not func_name:
        func_name = "CallFunction"

    # 从 parameters 中提取有意义的参数名
    args: List[str] = []
    for param in input_params:
        if not isinstance(param, dict):
            continue
        name = param.get("name", "")
        if not name or name.lower() in ("self", "target", "worldcontext"):
            continue
        # 跳过 exec pin
        category = param.get("pin_category", "")
        if category == "exec":
            continue

        # 优先使用 data_source 追踪到的真实参数名
        resolved_name = _resolve_param_name(param)
        final_name = resolved_name if resolved_name else _sanitize_cpp_name(name)
        args.append(final_name)

    return f"{func_name}({', '.join(args)})"


def _variable_name_from_node(
    node_info: Dict[str, Any],
    node_lookup: Optional[Dict[str, Any]] = None,
) -> str:
    """从 VariableSet/VariableGet 节点信息中提取变量名。

    优先从 node_lookup 中的真实节点数据提取（node_data.variable_name），
    回退到 node_info 字典中的 variable_name 字段。

    Args:
        node_info: 执行流中的节点字典
        node_lookup: node_guid → UEdGraphNode 查找表（可选）

    Returns:
        变量名，或空字符串
    """
    # 从 node_lookup 提取真实变量名
    node_guid = node_info.get("node_guid")
    if node_guid and node_lookup:
        node = node_lookup.get(node_guid)
        if node:
            data = node.node_data if isinstance(node.node_data, dict) else {}
            var_name = data.get("variable_name", "")
            if var_name:
                return var_name

    # 回退：直接从 node_info 字典提取
    return node_info.get("variable_name", "")


def _resolve_param_name(param: Dict[str, Any]) -> str:
    """从 data_source 解析参数的真实语义名称。

    优先级：
    1. function_parameter → 使用 FunctionEntry 的 pin 名（如 "Yaw"）
    2. default_value → 使用默认值字面量
    3. pure_function → 使用函数调用表达式
    4. 其他 → 返回空字符串（回退到原始 pin 名）

    Args:
        param: input_params 中的参数字典

    Returns:
        解析后的参数名，或空字符串（表示无法解析）
    """
    ds = param.get("data_source")
    if not isinstance(ds, dict):
        return ""

    sources = ds.get("data_sources", [])
    if not sources:
        return ""

    src = sources[0]
    source_type = src.get("source_type", "")

    if source_type == "function_parameter":
        # FunctionEntry 参数 → 使用 pin 名（如 "Yaw", "Pitch"）
        return _sanitize_cpp_name(src.get("pin", ""))

    if source_type == "default_value":
        # 默认值字面量
        value = src.get("value", "")
        if value:
            return value

    if source_type == "pure_function":
        # Pure 函数输出 → 使用函数调用形式
        func = src.get("function_name", "")
        if func:
            return f"{func}()"

    return ""


def extract_eventgraph_semantic_calls(graphs: List[UEdGraph]) -> List[Dict[str, Any]]:
    """Extract readable event -> function call mappings from EventGraph.

    提取每个事件节点下的所有 CallFunction 节点（不仅第一个）。
    """
    from uasset_read.graph import build_execution_flow_entries, node_member_name

    graph_obj = next((graph for graph in graphs if graph.graph_name == "EventGraph"), None)
    if graph_obj is None:
        return []
    results: List[Dict[str, Any]] = []
    node_by_guid = {node.node_guid: node for node in graph_obj.nodes}

    for flow in build_execution_flow_entries(graph_obj):
        nodes = flow.get("nodes", [])
        event_info = next((node for node in nodes if node.get("node_type") == "K2Node_Event"), None)
        if event_info is None:
            continue

        # 提取该事件下的所有 CallFunction 节点（不仅取第一个）
        call_nodes = [node for node in nodes if node.get("node_type") == "K2Node_CallFunction"]
        if not call_nodes:
            continue

        event_name = event_info.get("event_name") or str(flow.get("start_event", "")).removeprefix("Event.")
        event_parent = _event_parent(node_by_guid.get(event_info.get("node_guid")))

        for call_info in call_nodes:
            # 从 node_by_guid 查找真实节点以提取函数名
            function_name = ""
            node_guid = call_info.get("node_guid")
            if node_guid and node_guid in node_by_guid:
                function_name = node_member_name(node_by_guid[node_guid])

            # 回退：从 flow 节点的 parameters 推断
            if not function_name:
                params = call_info.get("parameters") or {}
                input_params = params.get("input_params") or []
                for param in input_params:
                    if not isinstance(param, dict):
                        continue
                    ds = param.get("data_source")
                    if isinstance(ds, dict):
                        for src in ds.get("data_sources", []):
                            if src.get("source_type") in ("pure_function", "function_output") and src.get("function_name"):
                                function_name = src["function_name"]
                                break
                    if function_name:
                        break

            # 最终回退
            if not function_name:
                function_name = call_info.get("function_name") or ""
            if not function_name:
                continue

            args = _call_args_from_flow(call_info)
            results.append({
                "event_name": event_name,
                "event_parent": event_parent,
                "function_name": function_name,
                "arguments": args,
                "call": f"{function_name}({', '.join(args)})",
                "source": "current_asset",
            })

    return results


def _event_parent(node: Any) -> str | None:
    if node is None:
        return None
    data = node.node_data if isinstance(node.node_data, dict) else {}
    ref = data.get("event_reference") if isinstance(data, dict) else None
    if isinstance(ref, dict):
        return ref.get("member_parent")
    return getattr(ref, "member_parent", None)


def _call_args_from_flow(call_info: Dict[str, Any]) -> List[str]:
    params = call_info.get("parameters") or {}
    input_params = params.get("input_params") or []
    args: List[str] = []
    for param in input_params:
        name = param.get("name") if isinstance(param, dict) else None
        category = param.get("pin_category") if isinstance(param, dict) else None
        if not name or name in ("self", "Target") or category == "exec":
            continue
        args.append(_sanitize_cpp_name(name))
    return args


def _format_event_semantics(function_name: str, semantic: Dict[str, Any]) -> str:
    call = semantic["call"]
    return f"{function_name}() {{\n    {call};\n}}"


def _format_ubergraph_semantics(
    function_name: str,
    semantic_calls: List[Dict[str, Any]],
) -> str:
    lines = [f"{function_name}() {{"]
    for item in semantic_calls:
        lines.append(f"    // {item['event_name']} -> {item['call']}")
        lines.append(f"    {item['call']};")
    lines.append("}")
    return "\n".join(lines)
