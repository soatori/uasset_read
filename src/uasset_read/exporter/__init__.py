"""导出系统 — 统一接口、注册表、批量导出。

借鉴 CUE4Parse 的 IExporter + ExporterOptions 模式，
将分散的 formatter 函数封装为统一的导出管线。

使用示例:
    from uasset_read.exporter import export, ExportOptions, ExporterRegistry

    # 便捷方式
    output = export(result, format="json")

    # 完整方式
    options = ExportOptions(format="json", include_schema=True)
    exporter = ExporterRegistry.get("json")
    output = exporter.export(result, options)
"""

# 必须先导入 registry（导出器模块会在 import 时自动注册）
from .base import ExportOptions, IExporter, ExportValidationError
from .registry import ExporterRegistry, export

# 触发所有导出器的自动注册（导入即注册）
from . import json_exporter      # noqa: F401
from . import text_exporter      # noqa: F401
from . import markdown_exporter  # noqa: F401
from . import blueprint_text_exporter  # noqa: F401
from . import blueprint_ue_text_exporter  # noqa: F401
from . import n2c_exporter       # noqa: F401
from . import cpp_skeleton_exporter  # noqa: F401
from . import cpp_json_ir_exporter   # noqa: F401

from .batch import BatchExporter, BatchExportResult

__all__ = [
    "ExportOptions",
    "IExporter",
    "ExportValidationError",
    "ExporterRegistry",
    "export",
    "BatchExporter",
    "BatchExportResult",
    # 具体导出器类
    "JsonExporter",
    "TextExporter",
    "MarkdownExporter",
    "BlueprintTextExporter",
    "BlueprintUETextExporter",
    "N2CExporter",
    "CppSkeletonExporter",
    "CppJsonIrExporter",
]

# 延迟导入具体类到 __all__（避免循环依赖）
def __getattr__(name: str):
    if name == "JsonExporter":
        from .json_exporter import JsonExporter
        return JsonExporter
    elif name == "TextExporter":
        from .text_exporter import TextExporter
        return TextExporter
    elif name == "MarkdownExporter":
        from .markdown_exporter import MarkdownExporter
        return MarkdownExporter
    elif name == "BlueprintTextExporter":
        from .blueprint_text_exporter import BlueprintTextExporter
        return BlueprintTextExporter
    elif name == "BlueprintUETextExporter":
        from .blueprint_ue_text_exporter import BlueprintUETextExporter
        return BlueprintUETextExporter
    elif name == "N2CExporter":
        from .n2c_exporter import N2CExporter
        return N2CExporter
    elif name == "CppSkeletonExporter":
        from .cpp_skeleton_exporter import CppSkeletonExporter
        return CppSkeletonExporter
    elif name == "CppJsonIrExporter":
        from .cpp_json_ir_exporter import CppJsonIrExporter
        return CppJsonIrExporter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
