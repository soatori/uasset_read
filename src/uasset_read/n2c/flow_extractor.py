"""N2C 执行流链提取器。

将 build_execution_flows() 的逐对执行流转换为链式表达（N1->N2->N3），
将 build_data_flows() 的输出转换为紧凑映射（N1.P0 -> N2.P1）。

Phase 70 Wave 2 输出。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from uasset_read.constants import CONTROL_FLOW_NODES

MAX_CHAIN_DEPTH = 1000


def _detect_cycle(adjacency: dict[str, list[str]]) -> bool:
    """DFS 环检测。

    Args:
        adjacency: {node_id: [successor_ids]} 邻接表

    Returns:
        True 如果检测到环
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node: WHITE for node in adjacency}

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for neighbor in adjacency.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                return True  # 后向边 = 环
            if color[neighbor] == WHITE and dfs(neighbor):
                return True
        color[node] = BLACK
        return False

    for node in list(color.keys()):
        if color[node] == WHITE:
            if dfs(node):
                return True
    return False


def extract_chains(
    execution_flows: list[dict],
    id_mapper: Any,  # N2CIdMapper
    node_lookup: dict,
) -> list:
    """将 build_execution_flows() 的输出转换为 N2C 链式字符串。

    Args:
        execution_flows: build_execution_flows() 返回的列表
            [{"start_event": "...", "nodes": [{"node_guid": "...", ...}, ...]}]
        id_mapper: N2CIdMapper 实例，用于 GUID -> 短 ID 转换
        node_lookup: 节点查找表（保留接口兼容）

    Returns:
        list: 链式字符串列表，或环检测时的 pair format 列表
            - 线性流: ["N1->N2->N3"]
            - 分支流: ["N1->N2", "N1->N3"]（ControlFlow 拆分）
            - 环检测: [{"from": "N1", "to": "N2"}, ...] + {"_format": "pairs"}
    """
    all_chains: list[str] = []
    has_cycle = False

    for flow_entry in execution_flows:
        nodes = flow_entry.get("nodes", [])
        if not nodes:
            continue

        # Filter out nodes without GUID and Knots
        valid_nodes = []
        for node_info in nodes:
            # Skip nodes with warning about missing guid
            if node_info.get("warning") == "missing node_guid":
                continue
            guid = node_info.get("node_guid")
            if not guid:
                continue
            # Skip Knots (shouldn't appear but safety check)
            node_type = node_info.get("node_type", "")
            if "Knot" in node_type:
                continue
            valid_nodes.append(node_info)

        if not valid_nodes:
            continue

        # Convert to short IDs
        short_ids: list[str] = []
        for node_info in valid_nodes:
            guid = node_info["node_guid"]
            short_id = id_mapper.to_short(guid)
            if short_id is None:
                short_id = id_mapper.register(guid)
            if short_id is not None:
                short_ids.append(short_id)

        if not short_ids:
            continue

        # Build adjacency for cycle detection
        adjacency: dict[str, list[str]] = {}
        for i in range(len(short_ids) - 1):
            src = short_ids[i]
            dst = short_ids[i + 1]
            if src not in adjacency:
                adjacency[src] = []
            adjacency[src].append(dst)

        # Cycle detection
        if _detect_cycle(adjacency):
            has_cycle = True
            continue  # Will fall back to pair format

        # Check for ControlFlow termination (stopped_at)
        is_branch = False
        for i, node_info in enumerate(valid_nodes):
            if node_info.get("stopped_at") or node_info.get("branch_type"):
                # ControlFlow node terminates this chain
                if node_info.get("branch_type") == "Branch":
                    # Branch: split into True/False chains
                    # In the linear flow, the Branch is the end point
                    is_branch = True
                break

        if is_branch:
            # For Branch, the chain ends at the branch node
            # Find branch position
            branch_idx = len(short_ids) - 1
            for i, node_info in enumerate(valid_nodes):
                if node_info.get("branch_type") == "Branch":
                    branch_idx = i
                    break

            # Chain up to branch
            if branch_idx > 0:
                chain = "->".join(short_ids[:branch_idx + 1])
                all_chains.append(chain)

                # For Branch, also add individual branch chains
                # (True/False branches would be separate execution_flows in a full graph)
                # Here we just mark the branch as end point
        else:
            # Linear chain
            chain = "->".join(short_ids)
            all_chains.append(chain)

    # Cycle fallback: return pair format
    if has_cycle and not all_chains:
        pairs: list[dict] = []
        for flow_entry in execution_flows:
            nodes = flow_entry.get("nodes", [])
            for i in range(len(nodes) - 1):
                src_guid = nodes[i].get("node_guid")
                dst_guid = nodes[i + 1].get("node_guid")
                if not src_guid or not dst_guid:
                    continue
                src_id = id_mapper.to_short(src_guid)
                if src_id is None:
                    src_id = id_mapper.register(src_guid)
                dst_id = id_mapper.to_short(dst_guid)
                if dst_id is None:
                    dst_id = id_mapper.register(dst_guid)
                if src_id and dst_id:
                    pairs.append({"from": src_id, "to": dst_id})
        return pairs + [{"_format": "pairs"}]

    return all_chains


def extract_data_flow_map(
    data_flows: list[dict],
    id_mapper: Any,  # N2CIdMapper
    node_name_to_guid: dict[str, str],
    pin_position_map: dict[tuple[str, str], int],
) -> dict[str, str]:
    """将 build_data_flows() 的输出转换为紧凑映射。

    Args:
        data_flows: build_data_flows() 返回的列表
            [{"source": {"node": "K2Node_Event_0", "pin": "ReturnValue"},
              "target": {"node": "K2Node_CallFunction_3", "pin": "InString"}}]
        id_mapper: N2CIdMapper 实例
        node_name_to_guid: {node_name: node_guid} 反向映射
        pin_position_map: {(node_guid, pin_name): pin_index}

    Returns:
        dict[str, str]: {"N1.P0": "N2.P1"} 紧凑映射
    """
    result: dict[str, str] = {}

    for flow in data_flows:
        source = flow.get("source", {})
        target = flow.get("target", {})

        source_node_name = source.get("node")
        source_pin_name = source.get("pin")
        target_node_name = target.get("node")
        target_pin_name = target.get("pin")

        if not source_node_name or not target_node_name:
            continue

        # Look up GUIDs
        source_guid = node_name_to_guid.get(source_node_name)
        target_guid = node_name_to_guid.get(target_node_name)

        if not source_guid or not target_guid:
            # Try GUID fallback (if format_pin_ref returned node_guid directly)
            source_guid = source.get("node_guid")
            target_guid = target.get("node_guid")
            if not source_guid or not target_guid:
                continue  # Skip if lookup fails

        # Convert to short IDs
        source_short = id_mapper.to_short(source_guid)
        target_short = id_mapper.to_short(target_guid)

        if source_short is None:
            source_short = id_mapper.register(source_guid)
        if target_short is None:
            target_short = id_mapper.register(target_guid)

        if source_short is None or target_short is None:
            continue

        # Get pin indices
        source_pin_idx = pin_position_map.get((source_guid, source_pin_name), 0)
        target_pin_idx = pin_position_map.get((target_guid, target_pin_name), 0)

        # Build compact key
        source_key = f"{source_short}.P{source_pin_idx}"
        target_key = f"{target_short}.P{target_pin_idx}"

        result[source_key] = target_key

    return result
