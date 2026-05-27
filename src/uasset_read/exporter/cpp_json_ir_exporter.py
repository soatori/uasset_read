"""C++ JSON IR 导出器 — 包装 format_cpp_class_json。"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from uasset_read.exporter.base import ExportOptions, IExporter
from uasset_read.cpp_gen import format_cpp_class_json

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult


class CppJsonIrExporter(IExporter):
    """C++ JSON IR 导出器。

    将 CppClassIR 序列化为 JSON 格式。
    """

    def export(self, result: ParseResult | LinkerParseResult, options: ExportOptions) -> str:
        from uasset_read.cpp_gen import extract_cpp_class_skeleton
        ir = extract_cpp_class_skeleton(result)
        data = format_cpp_class_json(ir)
        return json.dumps(data, indent=2, ensure_ascii=False)

    @property
    def format_name(self) -> str:
        return "cpp_json_ir"


# Auto-registration
from uasset_read.exporter.registry import ExporterRegistry
ExporterRegistry.register("cpp_json_ir", CppJsonIrExporter)
