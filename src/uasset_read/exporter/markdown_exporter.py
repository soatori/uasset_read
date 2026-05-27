"""Markdown 格式导出器 — 包装 format_markdown。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.exporter.base import ExportOptions, IExporter
from uasset_read.formatters import format_markdown

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult


class MarkdownExporter(IExporter):
    """Markdown 格式导出器（含表格 + Mermaid 流程图）。"""

    def export(self, result: ParseResult | LinkerParseResult, options: ExportOptions) -> str:
        return format_markdown(result)

    @property
    def format_name(self) -> str:
        return "markdown"


# Auto-registration
from uasset_read.exporter.registry import ExporterRegistry
ExporterRegistry.register("markdown", MarkdownExporter)
