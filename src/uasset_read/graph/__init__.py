"""蓝图图解析模块 — 图入口、执行流/数据流/连接映射构建。

执行流链式表达（build_execution_chains）。
"""

from .parser import extract_blueprint_graphs
from .flow_builder import (
    build_execution_flow_entries,
    build_data_flows,
    build_connections_map,
    format_graphs_json,
    format_pin_ref,
    build_function_graphs,
    # Public API for cross-module consumers (kismet/semantic.py)
    build_graph_indexes,
    build_normalized_edge_indexes,
    trace_execution_from_event,
    node_member_name,
)
from .chain_builder import (
    build_execution_chains,
)

__all__ = [
    "extract_blueprint_graphs",
    "build_execution_flow_entries",
    "build_data_flows",
    "build_connections_map",
    "format_graphs_json",
    "format_pin_ref",
    "build_function_graphs",
    "build_execution_chains",
    # Public API for cross-module consumers
    "build_graph_indexes",
    "build_normalized_edge_indexes",
    "trace_execution_from_event",
    "node_member_name",
]
