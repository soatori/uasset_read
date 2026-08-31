"""Control flow and data flow emission (BP-9, BP-10)."""

from __future__ import annotations

_ENTRY_KINDS = {"event", "custom_event", "function_entry"}


def attach_flows(graphs_json: list[dict], index: dict, reporting) -> None:
    """Attach control_flow/data_flow to each emitted graph, in place.

    Canonical edges are emitted from the output side only (LinkedTo is
    bidirectional). Exec and data edges never mix. Orphaned, not-connectable,
    cross-graph, and unresolved endpoints never produce edges -- they produce
    diagnostics (BP-10: no guessed edges).
    """
    node_graph: dict[str, str] = {}
    for graph in graphs_json:
        for node in graph["nodes"]:
            node_graph[node["id"]] = graph["id"]

    exec_edges: dict[str, list[dict]] = {g["id"]: [] for g in graphs_json}
    data_edges: dict[str, list[dict]] = {g["id"]: [] for g in graphs_json}
    entries: dict[str, list[dict]] = {g["id"]: [] for g in graphs_json}
    seen_edges: set[tuple[str, str]] = set()

    for graph in graphs_json:
        for node in graph["nodes"]:
            if node.get("kind") in _ENTRY_KINDS:
                for endpoint, port in (node.get("control_ports") or {}).items():
                    if port.get("direction") == "output":
                        entries[graph["id"]].append({"node": node["id"], "port": endpoint})

    for pin_id, info in index.items():
        if info["direction"] != "output" or info["orphaned"] or info["not_connectable"]:
            continue
        gid = info["graph"]
        for target_guid in info.get("linked", []):
            edge_key = (pin_id, target_guid)
            if edge_key in seen_edges or (target_guid, pin_id) in seen_edges:
                continue
            seen_edges.add(edge_key)
            target = index.get(target_guid)
            if target is None or target["orphaned"] or target["not_connectable"] or target["graph"] != gid:
                reporting.diagnostic(
                    "BP_LINK_UNRESOLVED",
                    f"graph:{gid}/data_flow",
                    "warning",
                    "semantic_loss",
                    occurrence={"pin": pin_id, "target": target_guid},
                )
                continue
            if target["direction"] != "input":
                reporting.diagnostic(
                    "BP_LINK_DIRECTION",
                    f"graph:{gid}/data_flow",
                    "warning",
                    "semantic_loss",
                    occurrence={"pin": pin_id, "target": target_guid},
                )
                continue
            if info["is_exec"] != target["is_exec"]:
                reporting.diagnostic(
                    "BP_LINK_KIND_MISMATCH",
                    f"graph:{gid}/data_flow",
                    "warning",
                    "semantic_loss",
                    occurrence={"pin": pin_id, "target": target_guid},
                )
                continue
            endpoint_key = "port" if info["is_exec"] else "pin"
            edge = {
                "from": {"node": info["node"], endpoint_key: info["endpoint"]},
                "to": {"node": target["node"], endpoint_key: target["endpoint"]},
            }
            (exec_edges[gid] if info["is_exec"] else data_edges[gid]).append(edge)

    for graph in graphs_json:
        gid = graph["id"]
        exec_list = exec_edges[gid]
        for ordinal, edge in enumerate(exec_list):
            edge["ordinal"] = ordinal
        control: dict = {"entries": entries[gid]}
        if exec_list:
            control["edges"] = exec_list
        graph["control_flow"] = control
        if data_edges[gid]:
            graph["data_flow"] = {"edges": data_edges[gid]}
