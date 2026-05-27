"""Blueprint 翻译参考文本导出器 — 包装 format_blueprint_translation_text。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.exporter.base import ExportOptions, IExporter
from uasset_read.formatters import format_blueprint_translation_text

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult


class BlueprintTextExporter(IExporter):
    """蓝图翻译参考文本导出器（紧凑格式，用于 C++ 转换辅助）。"""

    def export(self, result: ParseResult | LinkerParseResult, options: ExportOptions) -> str:
        return format_blueprint_translation_text(result)

    @property
    def format_name(self) -> str:
        return "blueprint_text"


# Auto-registration
from uasset_read.exporter.registry import ExporterRegistry
ExporterRegistry.register("blueprint_text", BlueprintTextExporter)
