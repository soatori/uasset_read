"""IR 构建层 — 将 ParseResult 转换为 PackageIR。

构建阶段处理所有 FPackageIndex 跨引用解析和 GUID 标准化。
渲染器只接收 PackageIR，不访问 ParseResult。
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from uasset_read.models.ir import (
    PackageIR, PackageHeaderIR, PropertyIR, ExportIR, ExportRawIR,
    GraphIR, NodeIR, PinIR, LinkerSummaryIR, BlueprintIR,
    BlueprintFunctionIR, BlueprintEventIR, DecompiledFunctionIR,
    ExecutionChainIR, VariableIR,
)

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult

from uasset_read.ir_builder._utils import (
    _safe_str,
    _safe_int,
    _normalize_guid,
    _extract_pin_guid,
    _classify_variable,
)
from uasset_read.ir_builder._exports import (
    _build_exports,
    _build_export_ir,
    _build_export_raw_ir,
    _build_export_diagnostics,
    _build_property_ir,
    _resolve_package_index,
    _build_resolved_depends_map,
)
from uasset_read.ir_builder._graphs import (
    _build_graph_ir,
    _build_node_ir,
    _build_pin_ir,
)
from uasset_read.ir_builder._blueprint import (
    _build_blueprint_ir,
    _build_decompiled_functions_ir,
    _build_execution_chains_ir,
    _build_variables_ir,
    _bind_implementations,
    _extract_parameters_from_signature,
)
from uasset_read.ir_builder._linker import _build_linker
from uasset_read.constants import BLUEPRINT_METADATA_KEYS as _BLUEPRINT_METADATA_KEYS


def build_package_ir(result: "ParseResult | LinkerParseResult") -> PackageIR:
    """将 ParseResult 转换为 PackageIR。

    构建阶段：
    1. 从 summary 提取 header
    2. 逐条转换 export_map 为 ExportIR
    3. 通过 linker 解析 import/export 路径
    4. GUID 标准化为 32 位小写 hex

    tolerant 模式：单个 Export 解析失败时跳过该项继续。
    """
    header = _build_header(result)
    exports = _build_exports(result)
    linker = _build_linker(result)

    # 构建 function_graphs（从 result.graphs）
    function_graphs = []
    fallback_graphs = getattr(result, "metadata", {}).get("function_graphs_fallback")
    if fallback_graphs:
        function_graphs = list(fallback_graphs)
    elif hasattr(result, 'graphs') and result.graphs:
        try:
            function_graphs = _build_function_graphs_safe(result)
        except Exception as e:
            if hasattr(result, "warnings"):
                result.warnings.append(f"function_graphs generation skipped: {e}")

    status = _result_status(result)
    metadata = getattr(result, "metadata", None) or {}
    errors = list(getattr(result, "errors", None) or [])

    if errors:
        status_code = "PARSE_ERROR"
        status_message = errors[0]
    elif metadata.get("lightweight_tolerant_parse"):
        status_code = "LIGHTWEIGHT_TOLERANT_PARSE"
        status_message = (
            f"轻量容错解析：导出数量过多"
            f"({getattr(result.summary, 'export_count', '?')})，已降级处理"
        )
    else:
        status_code = None
        status_message = None

    ir = PackageIR(
        header=header,
        name_map=list(result.name_map) if result.name_map else [],
        imports=_build_imports(result),
        exports=exports,
        linker=linker,
        blueprint=_build_blueprint_ir(result),
        decompiled_functions=_build_decompiled_functions_ir(result),
        execution_chains=_build_execution_chains_ir(result),
        variables=_build_variables_ir(result),
        diagnostics=result.diagnostics or [],
        function_graphs=function_graphs,
        resolved_parent_assets=list(getattr(result, "resolved_parent_assets", None) or []),
        inherited_blueprint_graphs=list(getattr(result, "inherited_blueprint_graphs", None) or []),
        logic_sources=list(getattr(result, "logic_sources", None) or []),
        soft_object_paths=list(getattr(result, "soft_references", None) or []),
        soft_package_references=list(getattr(result, "soft_package_references", None) or []),
        depends_map=list(getattr(result.summary, "depends_map", None) or []) if result.summary else [],
        resolved_depends_map=_build_resolved_depends_map(result),
        asset_registry_data_offset=_safe_int(getattr(result.summary, "asset_registry_data_offset", 0)) if result.summary else 0,
        errors=errors,
        status=status,
        status_message=status_message,
        status_code=status_code,
    )

    # 绑定函数/事件实现关联
    if ir.blueprint is not None:
        _bind_implementations(ir.blueprint, ir.decompiled_functions, ir.function_graphs)

    return ir


def _result_status(result: "ParseResult | LinkerParseResult") -> str:
    # 非成功分支
    if not getattr(result, "is_success", False):
        if (
            getattr(result, "summary", None) is not None
            or getattr(result, "name_map", None)
            or getattr(result, "import_map", None)
            or getattr(result, "export_map", None)
        ):
            return "partial"
        return "failed"

    # is_success=True 分支：综合检查 export 级 parse_status
    if getattr(result, "errors", None):
        return "partial"
    metadata = getattr(result, "metadata", None) or {}
    if metadata.get("lightweight_tolerant_parse"):
        return "partial"

    # 检查 export 级状态
    export_map = getattr(result, "export_map", None) or []
    if export_map and isinstance(export_map, list):
        _PARTIAL_STATUSES = {"opaque", "skipped", "partial_metadata", "opaque_unversioned", "fallback"}
        _FAILED_STATUSES = {"failed"}
        failed_count = 0
        partial_count = 0
        for exp in export_map:
            status = getattr(exp, "parse_status", None)
            if status in _FAILED_STATUSES:
                failed_count += 1
            elif status in _PARTIAL_STATUSES:
                partial_count += 1
        if failed_count == len(export_map):
            return "failed"
        if failed_count > 0 or partial_count > 0:
            return "partial"

    return "success"


def _build_function_graphs_safe(result: "ParseResult | LinkerParseResult") -> list[dict]:
    """Build function_graphs with a simple complexity guard for large graphs."""
    graphs = getattr(result, "graphs", None) or []
    total_nodes = sum(len(getattr(graph, "nodes", None) or []) for graph in graphs)
    total_pins = sum(
        len(getattr(node, "pins", None) or [])
        for graph in graphs
        for node in (getattr(graph, "nodes", None) or [])
    )
    max_nodes = 900
    max_pins = 12000
    if total_nodes > max_nodes or total_pins > max_pins:
        if hasattr(result, "warnings"):
            result.warnings.append(
                "function_graphs generation skipped due to graph complexity "
                f"(nodes={total_nodes}, pins={total_pins})"
            )
        return _build_function_graph_summaries(result)

    from uasset_read.graph import build_function_graphs
    blueprint_functions = None
    if hasattr(result, 'blueprint') and result.blueprint:
        blueprint_functions = getattr(result.blueprint, 'functions', None)
    return build_function_graphs(graphs, blueprint_functions)


def _build_function_graph_summaries(result: "ParseResult | LinkerParseResult") -> list[dict]:
    entries = []
    for graph in getattr(result, "graphs", None) or []:
        for node in getattr(graph, "nodes", None) or []:
            if getattr(node, "class_name", "") != "K2Node_FunctionEntry":
                continue
            function_name = "Unknown"
            node_data = getattr(node, "node_data", None)
            ref = None
            if isinstance(node_data, dict):
                ref = node_data.get("function_reference")
            elif node_data is not None:
                ref = getattr(node_data, "function_reference", None)
            raw_name = getattr(ref, "member_name", None) if ref is not None else None
            if raw_name and raw_name != "None":
                function_name = raw_name.split("/")[-1]
            entries.append({
                "function_name": function_name,
                "graph_source": getattr(graph, "graph_name", ""),
                "entry_node_guid": getattr(node, "node_guid", ""),
                "signature": {"return_type": "", "parameters": []},
                "execution_flows": [],
                "fallback_reason": "graph_complexity_limit",
            })
    return entries


def _build_header(result: ParseResult) -> PackageHeaderIR:
    summary = result.summary
    version = _get_version_string(result)

    return PackageHeaderIR(
        package_name=_safe_str(getattr(summary, "package_name", None)),
        package_class=_safe_str(getattr(summary, "package_class", None)),
        package_flags=_safe_int(getattr(summary, "package_flags", 0)),
        total_export_count=_safe_int(getattr(summary, "export_count", 0)),
        total_import_count=_safe_int(getattr(summary, "import_count", 0)),
        ue_version=version,
    )


def _get_version_string(result: ParseResult) -> str:
    """从 version_container 提取 UE 版本字符串。"""
    vc = result.version_container
    if vc is None:
        return "unknown"

    # 优先尝试 get_ue_version_string（如果存在且可调用）
    method = getattr(vc, "get_ue_version_string", None)
    if callable(method):
        try:
            return method()
        except Exception:
            pass

    # 回退：基于 is_ue5 判断
    if getattr(vc, "is_ue5", False):
        return "5.x"
    return "4.x"


def _build_imports(result: ParseResult) -> list[dict]:
    imports = []
    for imp in result.import_map or []:
        imports.append({
            "class_package": _safe_str(getattr(imp, "class_package", None)),
            "class_name": _safe_str(getattr(imp, "class_name", None)),
            "object_name": _safe_str(getattr(imp, "object_name", None)),
        })
    return imports
