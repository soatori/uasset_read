"""UE 原样风格蓝图节点文本导出器。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.exporter.base import ExportOptions, IExporter
from uasset_read.formatters import format_blueprint_ue_text

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult


class BlueprintUETextExporter(IExporter):
    """输出接近 UE 文本导出的蓝图节点文本。"""

    def export(self, result: ParseResult | LinkerParseResult, options: ExportOptions) -> str:
        return format_blueprint_ue_text(result)

    @property
    def format_name(self) -> str:
        return "blueprint_ue_text"


from uasset_read.exporter.registry import ExporterRegistry

ExporterRegistry.register("blueprint_ue_text", BlueprintUETextExporter)
