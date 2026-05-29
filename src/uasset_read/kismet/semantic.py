"""Graph-backed semantic enrichment for Kismet decompilation results."""
from __future__ import annotations

from typing import Any, Dict, List

from uasset_read.models.core import UEdGraph
from uasset_read.kismet.result import KismetDecompiledResult


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


def extract_eventgraph_semantic_calls(graphs: List[UEdGraph]) -> List[Dict[str, Any]]:
    """Extract readable event -> function call mappings from EventGraph."""
    from uasset_read.graph import build_execution_flows

    graph_obj = next((graph for graph in graphs if graph.graph_name == "EventGraph"), None)
    if graph_obj is None:
        return []
    results: List[Dict[str, Any]] = []
    node_by_guid = {node.node_guid: node for node in graph_obj.nodes}

    for flow in build_execution_flows(graph_obj):
        nodes = flow.get("nodes", [])
        event_info = next((node for node in nodes if node.get("node_type") == "K2Node_Event"), None)
        call_info = next((node for node in nodes if node.get("node_type") == "K2Node_CallFunction"), None)
        if event_info is None or call_info is None:
            continue
        event_name = event_info.get("event_name") or str(flow.get("start_event", "")).removeprefix("Event.")
        event_parent = _event_parent(node_by_guid.get(event_info.get("node_guid")))
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
        args.append(name)
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
