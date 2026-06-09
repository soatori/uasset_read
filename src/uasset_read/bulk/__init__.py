"""Bulk Data 系统（已弃用）

此模块已弃用，将在 v0.5.0 中移除。
BulkData 相关功能将在未来版本中重新设计。
"""
import warnings

warnings.warn(
    "uasset_read.bulk 模块已弃用，将在 v0.5.0 中移除。"
    "BulkData 相关功能将在未来版本中重新设计。",
    DeprecationWarning,
    stacklevel=2,
)

from uasset_read.bulk.structures import FBulkDataHeader, BulkDataFlags

__all__ = ["FBulkDataHeader", "BulkDataFlags"]
