"""蓝图图解析模块 — 图入口、执行流/数据流/连接映射构建。

Phase 31: 蓝图图解析模块。
Phase 71: 执行流链式表达（build_execution_chains）。
"""

from .parser import extract_blueprint_graphs
from .flow_builder import (
    build_execution_flows,
    build_data_flows,
    build_connections_map,
    build_graphs_summary,
    format_graphs_json,
    is_function_graph,
    build_function_graphs,  # Phase 55
)
from .chain_builder import (
    build_execution_chains,  # Phase 71
    build_execution_chains_from_flows,  # Phase 71 (N2C compat)
)
from .pin_trace import write_pin_trace_report, write_phase75_diagnostic

__all__ = [
    "extract_blueprint_graphs",
    "build_execution_flows",
    "build_data_flows",
    "build_connections_map",
    "build_graphs_summary",
    "format_graphs_json",
    "is_function_graph",
    "build_function_graphs",
    "build_execution_chains",
    "build_execution_chains_from_flows",
    "write_pin_trace_report",
    "write_phase75_diagnostic",
]
