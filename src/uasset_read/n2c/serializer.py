"""N2C 序列化器 — to_n2c_json / from_n2c_json。

将现有图数据转换为 N2CStruct 格式（to_n2c_json），
以及从 N2CStruct dict 重建 dataclass 实例（from_n2c_json）。

Phase 70 Wave 2 输出。
Phase 71: 链提取逻辑迁移到 graph/chain_builder。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from uasset_read.n2c.schema import N2CStruct, N2CGraph, N2CNode, N2CPin
from uasset_read.n2c.id_mapper import N2CIdMapper
from uasset_read.n2c.type_registry import N2CNodeTypeRegistry
from uasset_read.n2c.processors import register_all_processors
from uasset_read.n2c.processor_registry import N2CProcessorRegistry
# Phase 71: 链提取逻辑迁移到 graph/chain_builder
from uasset_read.graph.chain_builder import build_execution_chains_from_flows
from uasset_read.n2c.flow_extractor import extract_data_flow_map


def to_n2c_json(
    graphs: list | None = None,
    result: Any | None = None,
) -> dict:
    """将图数据转换为 N2CStruct 格式 dict。

    参数二选一：graphs 直接传 UEdGraph 列表，或 result 传 ParseResult。

    Args:
        graphs: UEdGraph 列表
        result: ParseResult 对象（用于提取 metadata）

    Returns:
        dict: N2CStruct 兼容 dict（version, metadata, graphs, structs, enums）
    """
    # Ensure registry initialized (idempotent)
    registry = N2CProcessorRegistry.get_instance()
    if not registry._processors or registry._fallback is None:
        register_all_processors()

    # Resolve graph list
    if graphs is None:
        if result is not None and hasattr(result, 'graphs'):
            graphs = result.graphs
        else:
            graphs = []

    # Build ID mapper and node lists
    id_mapper = N2CIdMapper()
    n2c_graphs: list[N2CGraph] = []

    for graph in graphs:
        n2c_nodes: list[N2CNode] = []

        # First pass: register non-Knot nodes
        for idx, node in enumerate(graph.nodes):
            if "Knot" in node.class_name:
                continue  # Knot 穿透：不注册
            if node.node_guid:
                id_mapper.register(node.node_guid)

        # Build name lookup for flow_extractor
        node_name_to_guid: dict[str, str] = {}
        for idx, node in enumerate(graph.nodes):
            if "Knot" in node.class_name:
                continue
            name = _derive_node_name(node, idx)
            node_name_to_guid[name] = node.node_guid

        # Build pin_position_map
        pin_position_map: dict[tuple[str, str], int] = {}
        for node in graph.nodes:
            if "Knot" in node.class_name:
                continue
            for pin_idx, pin in enumerate(node.pins):
                if node.node_guid:
                    pin_position_map[(node.node_guid, pin.pin_name)] = pin_idx

        # Second pass: build N2CNode objects
        for idx, node in enumerate(graph.nodes):
            if "Knot" in node.class_name:
                continue  # Knot 穿透

            short_id = id_mapper.to_short(node.node_guid) if node.node_guid else None
            if short_id is None:
                # Fallback for nodes without GUID
                short_id = f"no-guid-{idx}"

            # Resolve semantic type
            node_type = N2CNodeTypeRegistry.get_instance().resolve(node.class_name)
            semantic_type = node_type.value

            # Derive name
            name = _derive_node_name(node, idx)

            # Check pure (no exec pin)
            has_exec = any(
                p.pin_type and p.pin_type.pin_category == "exec"
                for p in node.pins
            )
            pure = not has_exec

            # Build pins
            input_pins: list[N2CPin] = []
            output_pins: list[N2CPin] = []
            for pin in node.pins:
                n2c_pin = N2CPin(
                    pin_name=pin.pin_name,
                    pin_category=pin.pin_type.pin_category if pin.pin_type else "",
                    pin_subcategory=pin.pin_type.pin_subcategory if pin.pin_type else "",
                    direction="input" if pin.direction == 0 else "output",
                    default_value=pin.default_value,
                )
                if pin.direction == 0:
                    input_pins.append(n2c_pin)
                else:
                    output_pins.append(n2c_pin)

            # Build extra_data via Processor
            extra_data: dict[str, Any] = {}
            if node.node_guid:
                from uasset_read.n2c.definitions import N2CNodeDefinition
                definition = N2CNodeDefinition(
                    node_id=node.node_guid,
                    node_type=node_type,
                    position=(node.node_pos_x, node.node_pos_y),
                    comment=node.node_comment or "",
                )
                N2CProcessorRegistry.get_instance().process_node(
                    node, node_type, definition
                )
                extra_data = dict(definition.extra_data)

                # Ensure member_name for CallFunction
                if node.class_name == "K2Node_CallFunction" and node.node_data:
                    nd = node.node_data
                    fr = None
                    if isinstance(nd, dict):
                        fr = nd.get("function_reference")
                    else:
                        fr = getattr(nd, 'function_reference', None)
                    if fr:
                        if not isinstance(fr, dict):
                            mn = getattr(fr, 'member_name', None)
                            mp = getattr(fr, 'member_parent', None)
                        else:
                            mn = fr.get("member_name")
                            mp = fr.get("member_parent")
                        if mn:
                            extra_data["member_name"] = mn
                        if mp:
                            extra_data["member_parent"] = mp

                # Ensure event_name for Event nodes
                if node.class_name == "K2Node_Event" and node.node_data:
                    nd = node.node_data
                    er = None
                    if isinstance(nd, dict):
                        er = nd.get("event_reference")
                    else:
                        er = getattr(nd, 'event_reference', None)
                    if er:
                        if not isinstance(er, dict):
                            mn = getattr(er, 'member_name', None)
                            mp = getattr(er, 'member_parent', None)
                        else:
                            mn = er.get("member_name")
                            mp = er.get("member_parent")
                        if mn:
                            extra_data["event_name"] = mn
                        if mp:
                            extra_data["event_parent"] = mp

            n2c_node = N2CNode(
                id=short_id,
                type=semantic_type,
                name=name,
                comment=node.node_comment or "",
                pure=pure,
                input_pins=input_pins,
                output_pins=output_pins,
                extra_data=extra_data,
            )
            n2c_nodes.append(n2c_node)

        # Build flows
        from uasset_read.graph.flow_builder import build_execution_flows, build_data_flows
        execution_flows_raw = build_execution_flows(graph)
        data_flows_raw = build_data_flows(graph)

        # Convert execution flows to chains
        exec_chains = build_execution_chains_from_flows(execution_flows_raw, id_mapper, {})

        # Convert data flows to compact map
        data_map = extract_data_flow_map(
            data_flows_raw, id_mapper, node_name_to_guid, pin_position_map
        )

        # Graph type mapping
        from uasset_read.constants import GRAPH_TYPE_MAP
        graph_type = GRAPH_TYPE_MAP.get(graph.graph_class, graph.graph_class)

        n2c_graph = N2CGraph(
            name=graph.graph_name,
            graph_type=graph_type,
            nodes=n2c_nodes,
            flows={
                "execution": exec_chains,
                "data": data_map,
            },
        )
        n2c_graphs.append(n2c_graph)

    # Extract metadata
    metadata: dict[str, str] = {}
    if result is not None:
        if hasattr(result, 'summary') and result.summary:
            summary = result.summary
            if hasattr(summary, 'package_name') and summary.package_name:
                metadata["Name"] = summary.package_name
        if hasattr(result, 'blueprint') and result.blueprint:
            bp = result.blueprint
            if hasattr(bp, 'blueprint_type') and bp.blueprint_type:
                metadata["BlueprintType"] = bp.blueprint_type
            if hasattr(bp, 'parent_class') and bp.parent_class:
                metadata["BlueprintClass"] = bp.parent_class

    struct = N2CStruct(
        metadata=metadata,
        graphs=n2c_graphs,
    )
    return struct.to_dict()


def from_n2c_json(data: dict) -> N2CStruct:
    """从 N2CStruct dict 重建 dataclass 实例。

    与 to_n2c_json() 反向操作。用于验证和消费端使用。

    Args:
        data: N2CStruct 兼容 dict

    Returns:
        N2CStruct: 重建的 dataclass 实例

    Raises:
        ValueError: 如果输入不兼容 N2CStruct schema
    """
    # Validate required fields
    if not isinstance(data, dict):
        raise ValueError("Input must be a dict")
    if "graphs" not in data:
        raise ValueError("Missing required field: graphs")
    if not isinstance(data.get("graphs"), list):
        raise ValueError("'graphs' must be a list")

    # Rebuild graphs
    n2c_graphs: list[N2CGraph] = []
    for graph_data in data.get("graphs", []):
        n2c_nodes: list[N2CNode] = []
        for node_data in graph_data.get("nodes", []):
            if not isinstance(node_data, dict):
                raise ValueError("Each node must be a dict")
            if "id" not in node_data or "type" not in node_data or "name" not in node_data:
                raise ValueError("Node missing required fields: id, type, name")

            # Rebuild pins
            input_pins = [
                _rebuild_pin(p) for p in node_data.get("input_pins", [])
            ]
            output_pins = [
                _rebuild_pin(p) for p in node_data.get("output_pins", [])
            ]

            n2c_node = N2CNode(
                id=node_data["id"],
                type=node_data["type"],
                name=node_data["name"],
                comment=node_data.get("comment", ""),
                pure=node_data.get("pure", False),
                latent=node_data.get("latent", False),
                input_pins=input_pins,
                output_pins=output_pins,
                extra_data=dict(node_data.get("extra_data", {})),
            )
            n2c_nodes.append(n2c_node)

        # Build flows with defaults
        flows_data = graph_data.get("flows", {})
        flows = {
            "execution": flows_data.get("execution", []),
            "data": flows_data.get("data", {}),
        }

        n2c_graph = N2CGraph(
            name=graph_data.get("name", ""),
            graph_type=graph_data.get("graph_type", ""),
            nodes=n2c_nodes,
            flows=flows,
        )
        n2c_graphs.append(n2c_graph)

    return N2CStruct(
        version=data.get("version", "1.0.0"),
        metadata=dict(data.get("metadata", {})),
        graphs=n2c_graphs,
        structs=list(data.get("structs", [])),
        enums=list(data.get("enums", [])),
    )


def _rebuild_pin(pin_data: dict) -> N2CPin:
    """从 dict 重建 N2CPin。"""
    return N2CPin(
        pin_name=pin_data.get("pin_name", ""),
        pin_category=pin_data.get("pin_category", ""),
        pin_subcategory=pin_data.get("pin_subcategory", ""),
        direction=pin_data.get("direction", "input"),
        default_value=pin_data.get("default_value"),
    )


def _derive_node_name(node: Any, idx: int) -> str:
    """从节点派生用户友好的节点名。

    复用 flow_builder.py 中的策略：f"{class_name}_{idx}"。
    """
    return f"{node.class_name}_{idx}"


def _estimate_token_count(data: dict) -> int:
    """粗略估算 JSON 的 token 用量。

    基于 JSON 字符串长度 / 4 的经验公式，与 OpenAI tokenizer 近似。

    Args:
        data: 要估算的 dict

    Returns:
        int: 估算的 token 数量
    """
    if not data:
        return 0
    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # OpenAI tokenizer 约 4 chars/token for JSON
    return max(1, len(json_str) // 4)
