"""输出格式化模块 — JSON/Text/Markdown 输出。

Phase 32: 输出格式化模块。

模块组织（D-01）:
- json_formatter: format_json_full, format_json_summary, format_exports_list,
                  format_properties_list, format_blueprint_dict
- text_formatter: format_text_full, format_text_summary
- markdown_formatter: format_markdown, _build_mermaid_flowchart
- helpers: build_status_info, build_schema_info, resolve_fpackage_index
- schemas: 预留目录（D-09）

Re-export Phase 31 函数（D-01b）:
- build_graphs_summary, format_graphs_json, format_pin_ref, _derive_node_name
"""

# Phase 31 re-export（D-01b）
from uasset_read.graph.flow_builder import (
    build_graphs_summary,
    format_graphs_json,
    format_pin_ref,
    _derive_node_name,
)

# JSON 格式化（Wave 1）
from .json_formatter import (
    format_json_full,
    format_json_summary,
    format_exports_list,
    format_properties_list,
    format_blueprint_dict,
)

# Text 格式化（Wave 2 placeholder）
from .text_formatter import (
    format_text_full,
    format_text_summary,
)

# Markdown 格式化（Wave 2 placeholder）
from .markdown_formatter import (
    format_markdown,
    _build_mermaid_flowchart,
)

# Blueprint 翻译参考文本（Phase 74）
from .blueprint_text_formatter import (
    format_blueprint_translation_text,
)
from .blueprint_ue_text_formatter import (
    format_blueprint_ue_text,
)

# 辅助函数
from .helpers import (
    build_status_info,
    build_schema_info,
    resolve_fpackage_index,
)

# Phase 56: C++ JSON IR 格式化
from uasset_read.cpp_gen.formatters import (
    CppProperty,
    CppHeaderMeta,
    CppClassIR,
    format_cpp_class_json,
)

__all__ = [
    # Phase 31 re-export
    "build_graphs_summary",
    "format_graphs_json",
    "format_pin_ref",
    "_derive_node_name",
    # JSON 格式化
    "format_json_full",
    "format_json_summary",
    "format_exports_list",
    "format_properties_list",
    "format_blueprint_dict",
    # Text 格式化
    "format_text_full",
    "format_text_summary",
    # Markdown 格式化
    "format_markdown",
    "_build_mermaid_flowchart",
    # Blueprint 翻译参考文本
    "format_blueprint_translation_text",
    "format_blueprint_ue_text",
    # 辅助函数
    "build_status_info",
    "build_schema_info",
    "resolve_fpackage_index",
    # Phase 56: C++ JSON IR
    "CppProperty",
    "CppHeaderMeta",
    "CppClassIR",
    "format_cpp_class_json",
]
