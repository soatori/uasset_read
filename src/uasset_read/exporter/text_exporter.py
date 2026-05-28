"""Text 格式导出器 — 包装 format_text_full / format_text_summary。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.exporter.base import ExportOptions, IExporter
from uasset_read.formatters import format_text_full, format_text_summary

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult


class TextExporter(IExporter):
    """YAML 风格文本导出器。"""

    def export(self, result: ParseResult | LinkerParseResult, options: ExportOptions) -> str:
        if options.format == "text_summary":
            return format_text_summary(result)
        return format_text_full(result)

    @property
    def format_name(self) -> str:
        return "text"


# Auto-registration
from uasset_read.exporter.registry import ExporterRegistry
ExporterRegistry.register("text", TextExporter)
ExporterRegistry.register("text_summary", TextExporter)
