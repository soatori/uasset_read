"""蓝图图解析模块 — 图入口、执行流/数据流/连接映射构建。

执行流链式表达（build_execution_chains）。
"""

from .parser import extract_blueprint_graphs
from .flow_builder import (
    build_execution_flow_entries,
    build_execution_flows,
    build_data_flows,
    build_connections_map,
    build_graphs_summary,
    format_graphs_json,
    format_pin_ref,
    _derive_node_name,
    is_function_graph,
    build_function_graphs,
    build_blueprint_node_index,
    # Public API for cross-module consumers (kismet/semantic.py)
    build_graph_indexes,
    build_normalized_edge_indexes,
    trace_execution_from_event,
    node_member_name,
)
from .chain_builder import (
    build_execution_chains,
)
from .pin_trace import write_pin_trace_report, write_phase75_diagnostic

__all__ = [
    "extract_blueprint_graphs",
    "build_execution_flow_entries",
    "build_execution_flows",
    "build_data_flows",
    "build_connections_map",
    "build_graphs_summary",
    "format_graphs_json",
    "format_pin_ref",
    "_derive_node_name",
    "is_function_graph",
    "build_function_graphs",
    "build_blueprint_node_index",
    "build_execution_chains",
    "write_pin_trace_report",
    "write_phase75_diagnostic",
]
