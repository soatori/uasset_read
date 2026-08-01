"""Execution chain expression builder.

Converts per-pair execution flows from build_execution_flows() to chain string format (N1->N2->N3),
replacing the original pair format to provide a more concise LLM-optimized output.
"""

from typing import Dict, List, Optional

from uasset_read.models.core import UEdGraph



def _detect_cycle(adjacency: dict[str, list[str]]) -> bool:
    """DFS cycle detection.

    Args:
        adjacency: {node_id: [successor_ids]} adjacency list

    Returns:
        True if a cycle is detected
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    # Collect all nodes appearing in the adjacency list (including nodes that only appear as targets),
    # ensuring DFS does not miss nodes that only appear as neighbors.
    all_nodes: set[str] = set(adjacency.keys())
    for neighbors in adjacency.values():
        all_nodes.update(neighbors)
    color: dict[str, int] = {node: WHITE for node in all_nodes}

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for neighbor in adjacency.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                return True  # Back edge = cycle
            if color[neighbor] == WHITE and dfs(neighbor):
                return True
        color[node] = BLACK
        return False

    for node in list(color.keys()):
        if color[node] == WHITE:
            if dfs(node):
                return True
    return False


def _derive_short_id(guid: str, index: int) -> str:
    """Derive a short ID from GUID and index.

    Format: N{index} (starting from 0)
    """
    return f"N{index}"


def build_execution_chains(
    graph: UEdGraph,
    execution_flows: Optional[List[Dict]] = None,
) -> List[Dict]:
    """Build execution chain expressions.

    Converts per-pair execution flows to chain string format:
    - Linear flow: ["N1->N2->N3"]
    - Branch flow: ["N1->N2", "N1->N3"]
    - Cycle detection: has_cycle=True, returns extracted chains

    Args:
        graph: UEdGraph object
        execution_flows: optional precomputed execution_flows (avoids redundant computation)

    Returns:
        List[Dict]: each flow entry contains:
            - start_event: event name
            - chains: list of chain strings
            - has_cycle: bool (chains may be incomplete when True)
            - chain_metadata: optional metadata (branch_count, etc.)
    """
    from uasset_read.graph.flow_builder import build_normalized_edge_indexes

    exec_edges_by_source: Dict[str, List[Dict]] = {}
    seen_exec_edges: set[tuple[str, str, str]] = set()
    edges_by_from_pin, _ = build_normalized_edge_indexes(graph)
    for edges in edges_by_from_pin.values():
        for edge in edges:
            from_node_guid = edge.get("from_node_guid")
            from_pin = edge.get("from_pin")
            to_node_guid = edge.get("to_node_guid")
            if not (
                edge.get("is_exec")
                and from_node_guid
                and from_pin
                and to_node_guid
            ):
                continue
            edge_key = (from_node_guid, from_pin, to_node_guid)
            if edge_key in seen_exec_edges:
                continue
            seen_exec_edges.add(edge_key)
            exec_edges_by_source.setdefault(from_node_guid, []).append(edge)
    for edges in exec_edges_by_source.values():
        edges.sort(key=lambda edge: (edge["from_pin"], edge["to_node_guid"]))

    # If execution_flows not provided, call build_execution_flow_entries
    if execution_flows is None:
        from uasset_read.graph.flow_builder import build_execution_flow_entries
        execution_flows = build_execution_flow_entries(graph)

    # Build GUID -> short ID mapping (based on node order)
    guid_to_short: Dict[str, str] = {}
    for idx, node in enumerate(graph.nodes):
        if node.node_guid:
            guid_to_short[node.node_guid] = _derive_short_id(node.node_guid, idx)

    result: List[Dict] = []

    for flow_entry in execution_flows:
        nodes = flow_entry.get("nodes", [])
        if not nodes:
            continue

        start_event = flow_entry.get("start_event", "Unknown")

        # Filter out nodes without GUID and Knots
        valid_nodes: List[Dict] = []
        for node_info in nodes:
            # Skip nodes with warning about missing guid
            if node_info.get("warning") == "missing node_guid":
                continue
            guid = node_info.get("node_guid")
            if not guid:
                continue
            # Skip Knots (reroute nodes)
            node_type = node_info.get("node_type", "")
            if "Knot" in node_type:
                continue
            valid_nodes.append(node_info)

        if not valid_nodes:
            continue

        branch_node_guids = [
            node_info["node_guid"]
            for node_info in valid_nodes
            if node_info.get("branch_type")
        ]

        # Convert to short IDs and collect pin names
        short_ids: List[str] = []
        pin_names: List[str] = []
        for node_info in valid_nodes:
            guid = node_info["node_guid"]
            short_id = guid_to_short.get(guid)
            if short_id is None:
                # Fallback: use node index in graph
                short_id = f"N{len(guid_to_short)}"
                guid_to_short[guid] = short_id
            short_ids.append(short_id)
            pin_names.append(node_info.get("used_exec_pin_name", ""))

        if not short_ids:
            continue

        # Build adjacency for cycle detection
        adjacency: Dict[str, List[str]] = {}
        for i in range(len(short_ids) - 1):
            src = short_ids[i]
            dst = short_ids[i + 1]
            if src not in adjacency:
                adjacency[src] = []
            adjacency[src].append(dst)

        # Cycle detection
        has_cycle = _detect_cycle(adjacency)

        # Check for ControlFlow termination (stopped_at / branch_type)
        branch_count = 0
        chains: List[str] = []

        # Find branch points
        branch_indices: List[int] = []
        for i, node_info in enumerate(valid_nodes):
            if node_info.get("branch_type"):
                branch_indices.append(i)
                branch_count += 1
            elif node_info.get("stopped_at"):
                branch_indices.append(i)

        def _build_chain_segment(ids: List[str], names: List[str]) -> str:
            """Build a chain string with pin names: N0--exec-->N1--Completed-->N2"""
            parts: List[str] = []
            for i in range(len(ids)):
                parts.append(ids[i])
                if i < len(ids) - 1:
                    # pin name comes from the source node (names[i]), not the target node (names[i+1])
                    # used_exec_pin_name is set on the source node, its exec output pin connects forward
                    pin_name = names[i] if i < len(names) else ""
                    if pin_name:
                        parts.append(f"--{pin_name}-->")
                    else:
                        parts.append("->")
            return "".join(parts)

        if branch_indices:
            # Split chains at branch points
            last_end = -1
            for branch_idx in branch_indices:
                if branch_idx > last_end:
                    chain = _build_chain_segment(
                        short_ids[last_end + 1:branch_idx + 1],
                        pin_names[last_end + 1:branch_idx + 1],
                    )
                    if chain:
                        chains.append(chain)
                last_end = branch_idx
            # Add remaining chain after last branch (if any nodes remain)
            if len(short_ids) > last_end + 1:
                remaining_chain = _build_chain_segment(
                    short_ids[last_end + 1:],
                    pin_names[last_end + 1:],
                )
                if remaining_chain:
                    chains.append(remaining_chain)
        else:
            # Linear chain
            chain = _build_chain_segment(short_ids, pin_names)
            chains.append(chain)

        entry: Dict = {
            "start_event": start_event,
            "chains": chains,
            "has_cycle": has_cycle,
        }

        # Optional metadata
        if branch_count > 0:
            entry["chain_metadata"] = {"branch_count": branch_count}

        branch_paths: List[Dict] = []
        for source_guid in branch_node_guids:
            for edge in exec_edges_by_source.get(source_guid, []):
                branch_paths.append({
                    "from_node_guid": source_guid,
                    "output_pin": edge["from_pin"],
                    "to_node_guid": edge["to_node_guid"],
                })
        if branch_paths:
            entry["branch_paths"] = branch_paths

        result.append(entry)

    return result


__all__ = [
    "build_execution_chains",
]
