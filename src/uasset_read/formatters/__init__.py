"""输出格式化模块 — JSON/Markdown 输出。

模块组织（D-01）:
- json_formatter: format_json_full, format_exports_list,
                  format_properties_list, format_blueprint_dict
- markdown_formatter: format_markdown, _build_mermaid_flowchart
- helpers: build_status_info, build_schema_info, resolve_fpackage_index
- schemas: 预留目录（D-09）
"""

# JSON 格式化（Wave 1）
from .json_formatter import (
    format_json_full,
    format_exports_list,
    format_properties_list,
    format_blueprint_dict,
)

# Markdown 格式化（Wave 2 placeholder）
from .markdown_formatter import (
    format_markdown,
)

# 辅助函数
from .helpers import (
    build_status_info,
    build_schema_info,
    resolve_fpackage_index,
)

__all__ = [
    # JSON 格式化
    "format_json_full",
    "format_exports_list",
    "format_properties_list",
    "format_blueprint_dict",
    # Markdown 格式化
    "format_markdown",
    # 辅助函数
    "build_status_info",
    "build_schema_info",
    "resolve_fpackage_index",
]
