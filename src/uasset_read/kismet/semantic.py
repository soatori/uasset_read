"""Graph-backed semantic enrichment for Kismet decompilation results."""

import logging
from typing import Any, Dict, List, Optional

from uasset_read.cpp_gen.sanitizer import sanitize_identifier
from uasset_read.models.core import UEdGraph
from uasset_read.kismet.result import KismetDecompiledResult

logger = logging.getLogger(__name__)

# Expression count threshold: function bodies below this are considered "empty", can be supplemented from graph topology
_EMPTY_BODY_THRESHOLD = 3




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
        # When no EventGraph semantic data, still try to enrich empty function bodies from graph topology
        _enrich_empty_functions_from_graphs(functions, graphs)
        return

    by_event = {item["event_name"]: item for item in semantic_calls}
    for result in functions:
        # Parsed results already carry verified current-export bytecode. Graph
        # topology is a distinct inference source and must not replace it.
        if result.bytecode_status == "parsed":
            continue
        if result.function_name.startswith("ExecuteUbergraph_"):
            result.semantic_calls = semantic_calls
            result.cpp_code = _format_ubergraph_semantics(result.function_name, semantic_calls)
            result.logic_source = "graph_topology"
            result.warnings.append("Kismet bytecode semantics enriched from EventGraph pin topology")
            continue

        semantic = by_event.get(result.function_name)
        if semantic:
            result.semantic_calls = [semantic]
            result.cpp_code = _format_event_semantics(result.function_name, semantic)
            result.logic_source = "graph_topology"
            result.warnings.append("Kismet bytecode semantics enriched from EventGraph pin topology")

    # Second pass: enrich empty function bodies with execution flow from graph topology
    _enrich_empty_functions_from_graphs(functions, graphs)


def _enrich_empty_functions_from_graphs(
    functions: List[KismetDecompiledResult],
    graphs: List[UEdGraph],
) -> None:
    """For functions with very few expressions, attempt to supplement execution flow C++ code from UEdGraph topology.

    Some Blueprint functions (e.g. Move, Aim) have Kismet bytecode that is empty or minimal,
    with actual logic entirely defined by K2Node topology. This function scans these "shell"
    functions after the main loop, traces execution chains from the corresponding graph's
    K2Node_FunctionEntry and generates readable C++ pseudocode.
    """
    for result in functions:
        if result.bytecode_status == "parsed":
            continue
        # Skip if already has cpp_code or semantics already enriched
        if result.cpp_code and any("enriched" in w for w in result.warnings):
            continue
        # Functions with expression count above threshold keep original decompilation result
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
    """Find matching K2Node_FunctionEntry and generate C++ code from graph topology.

    Iterates all graphs to find the one whose K2Node_FunctionEntry's
    function_reference.member_name matches function_name, then traces
    execution flow and converts to C++ pseudocode.

    Args:
        function_name: Function name to enrich (e.g. "Move", "Aim")
        graphs: List of all UEdGraph objects

    Returns:
        C++ pseudocode string, or None (no matching graph found)
    """
    from uasset_read.graph import (
        build_execution_flow_entries,
        build_graph_indexes,
        build_normalized_edge_indexes,
        trace_execution_from_event,
    )

    for graph in graphs:
        # Find matching FunctionEntry node
        entry_node = _find_function_entry(graph, function_name)
        if entry_node is None:
            continue

        # Build node_lookup for extracting function names
        _, node_lookup, _ = build_graph_indexes(graph)
        node_name_lookup = {
            n.node_guid: f"{n.class_name}_{idx}"
            for idx, n in enumerate(graph.nodes)
        }

        # Trace execution flow
        execution_flows = build_execution_flow_entries(graph)
        if not execution_flows:
            # Fallback: trace directly from FunctionEntry
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
    """Find K2Node_FunctionEntry node matching the function name in the graph.

    Args:
        graph: UEdGraph object
        function_name: Target function name

    Returns:
        Matching UEdGraphNode, or None
    """
    from uasset_read.graph import node_member_name

    for node in graph.nodes:
        if node.class_name != "K2Node_FunctionEntry":
            continue
        member_name = node_member_name(node)
        # Handle path format "/Game/.../FunctionName"
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
    """Convert execution flow topology to concise C++ pseudocode.

    Iterates CallFunction nodes in the execution flow, generating a chained
    call list. Pure functions are annotated inline as data providers,
    non-pure functions as standalone statements.

    Args:
        function_name: Function name
        execution_flows: List of execution flows from build_execution_flow_entries()
        node_lookup: node_guid → UEdGraphNode lookup table (for extracting function names)

    Returns:
        C++ pseudocode string
    """
    lines: List[str] = [f"void {function_name}() {{"]
    call_count = 0

    for flow_entry in execution_flows:
        nodes = flow_entry.get("nodes", [])
        if not nodes:
            continue

        start_event = flow_entry.get("start_event", "")
        # Only handle FunctionEntry flows
        if start_event and not start_event.startswith("FunctionEntry."):
            continue

        for node_info in nodes:
            node_type = node_info.get("node_type", "")

            # Skip the starting FunctionEntry itself
            if node_type == "K2Node_FunctionEntry":
                continue

            # CallFunction node: extract function name and parameters
            if node_type == "K2Node_CallFunction":
                call_str = _format_call_node(node_info, node_lookup)
                if call_str:
                    lines.append(f"    {call_str};")
                    call_count += 1

            # VariableSet node: variable assignment
            elif node_type == "K2Node_VariableSet":
                var_name = _variable_name_from_node(node_info, node_lookup)
                if var_name:
                    lines.append(f"    {var_name} = <value>;")
                    call_count += 1

            # VariableGet node: variable read
            elif node_type == "K2Node_VariableGet":
                var_name = _variable_name_from_node(node_info, node_lookup)
                if var_name:
                    lines.append(f"    // read {var_name}")
                    call_count += 1

            # Control flow nodes (Branch, etc.)
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

    # No actual calls, do not generate code
    if call_count == 0:
        return ""

    return "\n".join(lines)


def _format_call_node(
    node_info: Dict[str, Any],
    node_lookup: Optional[Dict[str, Any]] = None,
) -> str:
    """Format function call string from execution flow node information.

    Prefers extracting function name from node_lookup's node data
    (function_reference.member_name), falls back to data_source inference.

    Args:
        node_info: Node dict from execution flow
        node_lookup: node_guid → UEdGraphNode lookup table (optional)

    Returns:
        Call string in "FuncName(Arg1, Arg2)" format
    """
    from uasset_read.graph import node_member_name

    params = node_info.get("parameters", {})
    input_params = params.get("input_params", []) if isinstance(params, dict) else []

    # Extract real function name from node_lookup
    func_name = ""
    node_guid = node_info.get("node_guid")
    if node_guid and node_lookup:
        node = node_lookup.get(node_guid)
        if node:
            func_name = node_member_name(node)

    # Fallback: infer from data_source
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

    # Final fallback
    if not func_name:
        func_name = "CallFunction"

    # Extract meaningful parameter names from parameters
    args: List[str] = []
    for param in input_params:
        if not isinstance(param, dict):
            continue
        name = param.get("name", "")
        if not name or name.lower() in ("self", "target", "worldcontext"):
            continue
        # Skip exec pin
        category = param.get("pin_category", "")
        if category == "exec":
            continue

        # Prefer real parameter name traced from data_source
        resolved_name = _resolve_param_name(param)
        final_name = resolved_name if resolved_name else sanitize_identifier(name)
        args.append(final_name)

    return f"{func_name}({', '.join(args)})"


def _variable_name_from_node(
    node_info: Dict[str, Any],
    node_lookup: Optional[Dict[str, Any]] = None,
) -> str:
    """Extract variable name from VariableSet/VariableGet node information.

    Prefers extracting from node_lookup's real node data (node_data.variable_name),
    falls back to variable_name field in node_info dict.

    Args:
        node_info: Node dict from execution flow
        node_lookup: node_guid → UEdGraphNode lookup table (optional)

    Returns:
        Variable name, or empty string
    """
    # Extract real variable name from node_lookup
    node_guid = node_info.get("node_guid")
    if node_guid and node_lookup:
        node = node_lookup.get(node_guid)
        if node:
            data = node.node_data if isinstance(node.node_data, dict) else {}
            var_name = data.get("variable_name", "")
            if var_name:
                return var_name

    # Fallback: extract directly from node_info dict
    return node_info.get("variable_name", "")


def _resolve_param_name(param: Dict[str, Any]) -> str:
    """Resolve the true semantic name of a parameter from data_source.

    Priority:
    1. function_parameter → use FunctionEntry's pin name (e.g. "Yaw")
    2. default_value → use default value literal
    3. pure_function → use function call expression
    4. other → return empty string (fallback to original pin name)

    Args:
        param: Parameter dict from input_params

    Returns:
        Resolved parameter name, or empty string (unresolvable)
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
        # FunctionEntry parameter → use pin name (e.g. "Yaw", "Pitch")
        return sanitize_identifier(src.get("pin", ""))

    if source_type == "default_value":
        # Default value literal
        value = src.get("value", "")
        if value:
            return value

    if source_type == "pure_function":
        # Pure function output → use function call form
        func = src.get("function_name", "")
        if func:
            return f"{func}()"

    return ""


def extract_eventgraph_semantic_calls(graphs: List[UEdGraph]) -> List[Dict[str, Any]]:
    """Extract readable event -> function call mappings from EventGraph.

    Extracts all CallFunction nodes under each event node (not just the first).
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

        # Extract all CallFunction nodes under this event (not just the first)
        call_nodes = [node for node in nodes if node.get("node_type") == "K2Node_CallFunction"]
        if not call_nodes:
            continue

        event_name = event_info.get("event_name") or str(flow.get("start_event", "")).removeprefix("Event.")
        event_parent = _event_parent(node_by_guid.get(event_info.get("node_guid")))

        for call_info in call_nodes:
            # Look up real node from node_by_guid to extract function name
            function_name = ""
            node_guid = call_info.get("node_guid")
            if node_guid and node_guid in node_by_guid:
                function_name = node_member_name(node_by_guid[node_guid])

            # Fallback: infer from flow node's parameters
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

            # Final fallback
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
        args.append(sanitize_identifier(name))
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
