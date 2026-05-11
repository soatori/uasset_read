"""Markdown 格式化 — Markdown 输出 + Mermaid 流程图。

等价迁移 uasset_read_legacy.py L7574-7667。
Phase 32: 输出格式化模块（Wave 2 实现）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Dict

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult


def format_markdown(result: ParseResult) -> str:
    """
    Markdown 输出（D-14-10~12, OUT-04）。

    三节结构 + 表格优先 + Mermaid 流程图。

    Args:
        result: ParseResult 来自 parse_uasset()

    Returns:
        str: Markdown 格式文本
    """
    # Wave 2 实现
    raise NotImplementedError("format_markdown: Wave 2 实现")


def _build_mermaid_flowchart(execution_flows: List[Dict]) -> List[str]:
    """
    从 execution_flows 生成 Mermaid graph LR 代码（D-06, D-07）。

    Args:
        execution_flows: build_execution_flows() 的返回值

    Returns:
        List[str]: Mermaid 行列表（不含 ``` 围栏）
    """
    # Wave 2 实现
    raise NotImplementedError("_build_mermaid_flowchart: Wave 2 实现")