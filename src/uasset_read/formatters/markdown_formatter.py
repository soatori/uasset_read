"""Markdown 格式化 — Markdown 输出 + Mermaid 流程图。

等价迁移 uasset_read_legacy.py L7574-7667。
Phase 32: 输出格式化模块。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Dict

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult

from uasset_read.serializers.object_resources import get_asset_class, get_asset_class_with_linker
from uasset_read.graph import build_graphs_summary
from .helpers import build_status_info


def _escape_md_cell(text: str) -> str:
    """Escape characters that break markdown table formatting."""
    return str(text).replace("|", "\\|").replace("\n", " ")


def format_markdown(result: ParseResult) -> str:
    """
    Markdown 输出（D-14-10~12, OUT-04）。

    三节结构 + 表格优先 + Mermaid 流程图。

    Args:
        result: ParseResult 来自 parse_uasset()

    Returns:
        str: Markdown 格式文本
    """
    lines = []

    # 标题
    asset_name = result.summary.package_name if result.summary else "Unknown"
    asset_name = asset_name.split("/")[-1] if "/" in asset_name else asset_name
    lines.append(f"# Asset: {asset_name}")
    lines.append("")

    # === Asset Overview ===
    lines.append("## Asset Overview")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    if result.summary:
        lines.append(f"| Package | {_escape_md_cell(result.summary.package_name)} |")
        ue_version = result.summary.file_version_ue5 or result.summary.file_version_ue4
        lines.append(f"| Version | UE {_escape_md_cell(str(ue_version))} |")
    # Status
    status_info = build_status_info(result)
    lines.append(f"| Status | {_escape_md_cell(status_info.status)} |")
    if status_info.message:
        lines.append(f"| Message | {_escape_md_cell(status_info.message)} |")
    lines.append("")

    # === Blueprint Details ===
    if result.blueprint and result.blueprint.is_blueprint:
        lines.append("## Blueprint Details")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| Parent Class | {_escape_md_cell(result.blueprint.parent_class or 'Unknown')} |")
        # Variables 统计
        var_count = len(result.blueprint.variables) if result.blueprint.variables else 0
        comp_count = sum(1 for v in result.blueprint.variables if v.is_component) if result.blueprint.variables else 0
        lines.append(f"| Variables | {_escape_md_cell(f'{var_count} ({comp_count} components, {var_count - comp_count} regular)')} |")
        lines.append("")

    # === Graph Summary ===
    graphs_summary = build_graphs_summary(result.graphs)
    if graphs_summary:
        lines.append("## Graph Summary")
        for graph_summary in graphs_summary:
            graph_name = graph_summary.get("graph_name", "Unknown")
            lines.append(f"### {graph_name}")

            # Mermaid 流程图
            flows = graph_summary.get("execution_flows", [])
            if flows:
                mermaid_lines = _build_mermaid_flowchart(flows)
                if mermaid_lines:
                    lines.append("```mermaid")
                    lines.append("graph LR")
                    for mermaid_line in mermaid_lines:
                        lines.append(f"  {mermaid_line}")
                    lines.append("```")
                    lines.append("")
    else:
        lines.append("## Graph Summary")
        lines.append("No graphs in this asset.")
        lines.append("")

    # === Exports ===
    if result.export_map:
        lines.append("## Exports")
        lines.append("| Name | Class | Parent |")
        lines.append("|------|-------|--------|")

        # Extract linker for class resolution (may be None for legacy ParseResult)
        linker = getattr(result, 'linker', None)

        for i, exp in enumerate(result.export_map):
            name = _escape_md_cell(exp.object_name)
            cls = _escape_md_cell(get_asset_class_with_linker(exp, linker) if linker else get_asset_class(exp, result.import_map, result.export_map))
            parent = _escape_md_cell(result.blueprint.parent_class or "") if result.blueprint and i == 0 else ""
            lines.append(f"| {name} | {cls} | {parent} |")
        lines.append("")

    return "\n".join(lines)


def _build_mermaid_flowchart(execution_flows: List[Dict]) -> List[str]:
    """
    从 execution_flows 生成 Mermaid graph LR 代码（D-06, D-07）。

    Args:
        execution_flows: build_execution_flows() 的返回值

    Returns:
        List[str]: Mermaid 行列表（不含 ``` 围栏和 graph LR 头）
    """
    mermaid_lines: List[str] = []

    for flow in execution_flows:
        start_event = flow.get("start_event", "Unknown")
        nodes = flow.get("nodes", [])

        if not nodes:
            continue

        # 从 nodes 提取函数调用链
        # nodes 格式 (新版): [{"node_guid": "...", "node_type": "K2Node_Event", ...}, ...]
        # nodes 格式 (旧版): [{"node_guid": "...", "node_type": "K2Node_CallFunction", "function_name": "FuncName"}, ...]
        calls = []
        for node in nodes:
            node_type = node.get("node_type", "")
            
            # 适配新版格式: 从 node_type 提取节点名（去掉 K2Node_ 前缀）
            if node_type:
                node_name = node_type.replace("K2Node_", "") if node_type.startswith("K2Node_") else node_type
            else:
                node_name = "Unknown"
            
            # 如果有 function_name（旧格式兼容），优先使用
            func_name = node.get("function_name")
            if func_name:
                # 去掉参数部分
                calls.append(func_name)
            else:
                # 新格式: 使用 node_type 显示节点类型
                calls.append(node_name)

        if calls:
            # 如果第一个节点是 Event（与 start_event 重复），跳过它直接连接到后续节点
            if calls[0] == "Event" and len(calls) > 1:
                # start_event --> 第二个节点
                first_func = calls[1]
                mermaid_lines.append(f"{start_event} --> {first_func}")
                # 从第二个节点开始链式连接
                for i in range(1, len(calls) - 1):
                    fn1 = calls[i]
                    fn2 = calls[i + 1]
                    mermaid_lines.append(f"{fn1} --> {fn2}")
            else:
                # 正常连接所有节点
                first_func = calls[0]
                mermaid_lines.append(f"{start_event} --> {first_func}")
                for i in range(len(calls) - 1):
                    fn1 = calls[i]
                    fn2 = calls[i + 1]
                    mermaid_lines.append(f"{fn1} --> {fn2}")

    return mermaid_lines