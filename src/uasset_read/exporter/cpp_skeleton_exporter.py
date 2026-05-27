"""C++ 骨架导出器 — 包装 extract_cpp_class_skeleton + format_cpp_header。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.exporter.base import ExportOptions, IExporter

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult


class CppSkeletonExporter(IExporter):
    """C++ 类骨架导出器（.h 头文件）。

    需要 parse_uasset_with_linker 返回的 LinkerParseResult。
    对普通 ParseResult 会尝试提取但可能结果有限。
    """

    def export(self, result: ParseResult | LinkerParseResult, options: ExportOptions) -> str:
        from uasset_read.cpp_gen import extract_cpp_class_skeleton, format_cpp_header
        ir = extract_cpp_class_skeleton(result)
        return format_cpp_header(ir)

    @property
    def format_name(self) -> str:
        return "cpp_skeleton"


# Auto-registration
from uasset_read.exporter.registry import ExporterRegistry
ExporterRegistry.register("cpp_skeleton", CppSkeletonExporter)
