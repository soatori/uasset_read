"""Control flow, data flow, and pose flow emission for Animation Blueprint semantic JSON."""

from __future__ import annotations

from uasset_read.semantic.blueprint.flows import attach_flows as bp_attach_flows


_ENTRY_KINDS = {"event", "custom_event", "function_entry"}


def attach_flows(graphs_json: list[dict], index: dict, reporting) -> None:
    """Attach control_flow, data_flow, and pose_flow to each emitted graph.

    Extends the Blueprint flow attachment with pose flow for animation pose pins.
    """
    # Delegate standard control/data flow to blueprint implementation
    bp_attach_flows(graphs_json, index, reporting)

    # Add pose flow for animation pose connections
    _attach_pose_flows(graphs_json, index, reporting)


def _attach_pose_flows(graphs_json: list[dict], index: dict, reporting) -> None:
    """Attach pose_flow to graphs based on pose pin connections.

    Rules:
    - Only output pose -> input pose edges
    - Reject: output->output, pose->data, cross-graph, orphaned, unresolved GUID
    - Bidirectional LinkedTo produces only one edge
    - Edges ordered by source pin/index for stable ordinals
    """
    seen_edges: set[tuple[str, str]] = set()

    for graph in graphs_json:
        gid = graph["id"]
        pose_entries: list[dict] = []
        pose_edges: list[dict] = []

        # Collect pose pin entries (input pins)
        for node in graph["nodes"]:
            for endpoint, pose_pin in (node.get("pose_pins") or {}).items():
                if pose_pin.get("direction") == "input":
                    pose_entries.append(
                        {
                            "node": node["id"],
                            "pose_pin": endpoint,
                        }
                    )

        # Build pose edges from pin index
        for pin_id, info in index.items():
            if not info.get("is_pose"):
                continue
            if info["graph"] != gid:
                continue
            if info["direction"] != "output":
                continue
            if info.get("orphaned") or info.get("not_connectable"):
                continue

            for target_guid in info.get("linked", []):
                edge_key = (pin_id, target_guid)
                if edge_key in seen_edges or (target_guid, pin_id) in seen_edges:
                    continue
                seen_edges.add(edge_key)

                target = index.get(target_guid)
                if target is None:
                    reporting.diagnostic(
                        "ABP_POSE_LINK_UNRESOLVED",
                        f"graph:{gid}/pose_flow",
                        "warning",
                        "semantic_loss",
                        occurrence={"pin": pin_id, "target": target_guid},
                    )
                    continue
                if target.get("orphaned") or target.get("not_connectable"):
                    reporting.diagnostic(
                        "ABP_POSE_LINK_UNRESOLVED",
                        f"graph:{gid}/pose_flow",
                        "warning",
                        "semantic_loss",
                        occurrence={"pin": pin_id, "target": target_guid},
                    )
                    continue
                if target["graph"] != gid:
                    reporting.diagnostic(
                        "ABP_POSE_LINK_UNRESOLVED",
                        f"graph:{gid}/pose_flow",
                        "warning",
                        "semantic_loss",
                        occurrence={"pin": pin_id, "target": target_guid},
                    )
                    continue
                if not target.get("is_pose"):
                    reporting.diagnostic(
                        "ABP_POSE_LINK_KIND_MISMATCH",
                        f"graph:{gid}/pose_flow",
                        "warning",
                        "semantic_loss",
                        occurrence={"pin": pin_id, "target": target_guid},
                    )
                    continue
                if target["direction"] != "input":
                    reporting.diagnostic(
                        "ABP_POSE_LINK_DIRECTION",
                        f"graph:{gid}/pose_flow",
                        "warning",
                        "semantic_loss",
                        occurrence={"pin": pin_id, "target": target_guid},
                    )
                    continue

                pose_edges.append(
                    {
                        "from": {"node": info["node"], "pose_pin": info["endpoint"]},
                        "to": {"node": target["node"], "pose_pin": target["endpoint"]},
                    }
                )

        # Add ordinal to edges (stable order by source)
        for ordinal, edge in enumerate(pose_edges):
            edge["ordinal"] = ordinal

        if pose_entries or pose_edges:
            pose_flow: dict = {}
            if pose_entries:
                pose_flow["entries"] = pose_entries
            if pose_edges:
                pose_flow["edges"] = pose_edges
            graph["pose_flow"] = pose_flow
