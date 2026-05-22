"""执行流链式表达构建器。

将 build_execution_flows() 的逐对执行流转换为链式字符串格式（N1->N2->N3），
替代原有 pair 格式，提供更简洁的 LLM 优化输出。

Phase 71 Wave 1 输出。
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
    # 如果未提供 execution_flows，调用 build_execution_flows
    if execution_flows is None:
        from uasset_read.graph.flow_builder import build_execution_flows
        execution_flows = build_execution_flows(graph)

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

        # Convert to short IDs
        short_ids: List[str] = []
        for node_info in valid_nodes:
            guid = node_info["node_guid"]
            short_id = guid_to_short.get(guid)
            if short_id is None:
                # Fallback: 使用节点在图中的索引
                short_id = f"N{len(guid_to_short)}"
                guid_to_short[guid] = short_id
            short_ids.append(short_id)

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

        if branch_indices:
            # Split chains at branch points
            # For each branch, create a chain up to that point
            last_end = -1
            for branch_idx in branch_indices:
                # Chain from start to branch node
                if branch_idx > last_end:
                    chain = "->".join(short_ids[last_end + 1:branch_idx + 1])
                    if chain:
                        chains.append(chain)
                last_end = branch_idx
            # Add remaining chain after last branch (if any nodes remain)
            if len(short_ids) > last_end + 1:
                remaining_chain = "->".join(short_ids[last_end + 1:])
                if remaining_chain:
                    chains.append(remaining_chain)
        else:
            # Linear chain
            chain = "->".join(short_ids)
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


def build_execution_chains_from_flows(
    execution_flows: List[Dict],
    id_mapper: Any,
    node_lookup: Dict,
) -> List:
    """将 execution_flows 转换为链式表达（兼容 N2CIdMapper）。

    内部使用 N2CIdMapper 进行 GUID → 短 ID 映射，
    保持与 n2c/flow_extractor.extract_chains 的兼容性。

    Args:
        execution_flows: build_execution_flows() 返回的列表
        id_mapper: N2CIdMapper 实例
        node_lookup: 节点查找表（保留接口兼容）

    Returns:
        list: 链式字符串列表，或环检测时的 pair format 列表
    """
    all_chains: List[str] = []
    has_cycle = False

    for flow_entry in execution_flows:
        nodes = flow_entry.get("nodes", [])
        if not nodes:
            continue

        # Filter out nodes without GUID and Knots
        valid_nodes: List[Dict] = []
        for node_info in nodes:
            if node_info.get("warning") == "missing node_guid":
                continue
            guid = node_info.get("node_guid")
            if not guid:
                continue
            node_type = node_info.get("node_type", "")
            if "Knot" in node_type:
                continue
            valid_nodes.append(node_info)

        if not valid_nodes:
            continue

        # Convert to short IDs using id_mapper
        short_ids: List[str] = []
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
        adjacency: Dict[str, List[str]] = {}
        for i in range(len(short_ids) - 1):
            src = short_ids[i]
            dst = short_ids[i + 1]
            if src not in adjacency:
                adjacency[src] = []
            adjacency[src].append(dst)

        # Cycle detection
        if _detect_cycle(adjacency):
            has_cycle = True
            continue

        # Check for ControlFlow termination
        is_branch = False
        branch_idx = len(short_ids) - 1
        for i, node_info in enumerate(valid_nodes):
            if node_info.get("stopped_at") or node_info.get("branch_type"):
                if node_info.get("branch_type") == "Branch":
                    is_branch = True
                    branch_idx = i
                break

        if is_branch:
            # Chain up to branch
            if branch_idx > 0:
                chain = "->".join(short_ids[:branch_idx + 1])
                all_chains.append(chain)
        else:
            # Linear chain
            chain = "->".join(short_ids)
            all_chains.append(chain)

    # Cycle fallback: return pair format
    if has_cycle and not all_chains:
        pairs: List[Dict] = []
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


__all__ = [
    "build_execution_chains",
    "build_execution_chains_from_flows",
]