"""输出格式化模块 — 辅助函数。

模块组织（D-01）:
- helpers: build_status_info, build_schema_info, resolve_fpackage_index
- schemas: 预留目录（D-09）

注：JSON/Text/Markdown/Blueprint 格式化函数已移除（deprecated 0.4.5），
推荐使用 parse_single(format=...) 统一入口 + renderers 系统。
"""

# 辅助函数
from .helpers import (
    build_status_info,
    build_schema_info,
    resolve_fpackage_index,
)

__all__ = [
    # 辅助函数
    "build_status_info",
    "build_schema_info",
    "resolve_fpackage_index",
]
