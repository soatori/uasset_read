"""执行流链式表达构建器。

将 build_execution_flows() 的逐对执行流转换为链式字符串格式（N1->N2->N3），
替代原有 pair 格式，提供更简洁的 LLM 优化输出。
"""
from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional, Set, Tuple

from uasset_read.constants import CONTROL_FLOW_NODES
from uasset_read.models.core import UEdGraph, UEdGraphNode

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


def _derive_short_id(guid: str, index: int) -> str:
    """从 GUID 和 index 派生短 ID。

    格式：N{index}（从 0 开始）
    """
    return f"N{index}"


def build_execution_chains(
    graph: UEdGraph,
    execution_flows: Optional[List[Dict]] = None,
) -> List[Dict]:
    """构建执行流链式表达。

    将逐对执行流转换为链式字符串格式：
    - 线性流: ["N1->N2->N3"]
    - 分支流: ["N1->N2", "N1->N3"]
    - 环检测: has_cycle=True，返回已提取的链

    Args:
        graph: UEdGraph 对象
        execution_flows: 可选的预计算 execution_flows（避免重复计算）

    Returns:
        List[Dict]: 每个 flow entry 包含:
            - start_event: 事件名称
            - chains: 链式字符串列表
            - has_cycle: bool（True 时 chains 可能不完整）
            - chain_metadata: 可选元数据（branch_count 等）
    """
    # 如果未提供 execution_flows，调用 build_execution_flow_entries
    if execution_flows is None:
        from uasset_read.graph.flow_builder import build_execution_flow_entries
        execution_flows = build_execution_flow_entries(graph)

    # 构建 GUID → 短 ID 映射（基于节点顺序）
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

        # Convert to short IDs and collect pin names
        short_ids: List[str] = []
        pin_names: List[str] = []
        for node_info in valid_nodes:
            guid = node_info["node_guid"]
            short_id = guid_to_short.get(guid)
            if short_id is None:
                # Fallback: 使用节点在图中的索引
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
            """构建带引脚名称的链式字符串: N0--exec-->N1--Completed-->N2"""
            parts: List[str] = []
            for i in range(len(ids)):
                parts.append(ids[i])
                if i < len(ids) - 1:
                    pin_name = names[i + 1] if i + 1 < len(names) else ""
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

        result.append(entry)

    return result


__all__ = [
    "build_execution_chains",
]