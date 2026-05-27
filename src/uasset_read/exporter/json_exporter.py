"""JSON 格式导出器 — 包装 format_json_full / format_json_summary。"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from uasset_read.exporter.base import ExportOptions, IExporter
from uasset_read.formatters import format_json_full, format_json_summary

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult


class JsonExporter(IExporter):
    """JSON 格式导出器。

    支持 format_json_full 和 format_json_summary 两种模式。
    """

    def export(self, result: ParseResult | LinkerParseResult, options: ExportOptions) -> str:
        if options.format == "json_summary":
            data = format_json_summary(result, include_schema=options.include_schema)
        else:
            data = format_json_full(
                result,
                include_schema=options.include_schema,
                include_function_graphs=options.include_function_graphs,
            )
        return json.dumps(data, indent=2, ensure_ascii=False)

    @property
    def format_name(self) -> str:
        return "json"

    @property
    def validates_against_schema(self) -> bool:
        return False


# Auto-registration
from uasset_read.exporter.registry import ExporterRegistry
ExporterRegistry.register("json", JsonExporter)
ExporterRegistry.register("json_summary", JsonExporter)
