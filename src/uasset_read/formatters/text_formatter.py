"""Text 格式化 — YAML 风格完整输出、精简输出。

等价迁移 uasset_read_legacy.py L7431-7571。
Phase 32: 输出格式化模块（Wave 2 实现）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult


def format_text_full(result: ParseResult) -> str:
    """
    YAML 风格完整文本输出（OUT-02, OUT2-03）。

    Per D-17: YAML 风格层级，2 空格缩进
    Per D-19: ERRORS 区块在末尾
    Per D-21: Blueprint 元数据嵌入
    Per D-22: 嵌套 YAML 缩进
    Phase 8: Graphs section with summary（OUT2-03）

    Args:
        result: ParseResult 来自 parse_uasset()

    Returns:
        str: YAML 风格文本输出
    """
    # Wave 2 实现
    raise NotImplementedError("format_text_full: Wave 2 实现")


def format_text_summary(result: ParseResult) -> str:
    """
    精简 YAML 风格摘要（OUT-02）。

    Per D-18: 每个 export 一行: "Name (Type)"
    Per D-22: YAML 缩进

    Args:
        result: ParseResult 来自 parse_uasset()

    Returns:
        str: 精简 YAML 风格摘要
    """
    # Wave 2 实现
    raise NotImplementedError("format_text_summary: Wave 2 实现")