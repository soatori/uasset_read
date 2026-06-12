"""Package Summary 序列化 — PackageFileSummary 及相关读取函数。

从 uasset_read.py 提取（第 901-2543 行）。
UE5.7 专用版本 — 已移除 UE4 兼容代码。
"""
from __future__ import annotations

from .models import (
    GenerationInfo,
    EngineVersion,
    CustomVersion,
    PackageFileSummary,
)
from .reader import (
    read_package_summary,
    validate_export_data_range,
)
from .tables import (
    read_name_table,
    read_depends_map,
    read_soft_package_references,
    read_preload_dependencies,
)

__all__ = [
    # 数据模型
    "GenerationInfo",
    "EngineVersion",
    "CustomVersion",
    "PackageFileSummary",
    # 主读取函数
    "read_package_summary",
    "validate_export_data_range",
    # 辅助表读取
    "read_name_table",
    "read_depends_map",
    "read_soft_package_references",
    "read_preload_dependencies",
]
