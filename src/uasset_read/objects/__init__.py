"""UObject 类型体系（已弃用）

此模块已弃用，将在 v0.5.0 中移除。
请使用 uasset_read.parsers.asset_types 作为替代。
"""
import warnings

warnings.warn(
    "uasset_read.objects 模块已弃用，将在 v0.5.0 中移除。"
    "请使用 uasset_read.parsers.asset_types 作为替代。",
    DeprecationWarning,
    stacklevel=2,
)

from uasset_read.objects.uobject import UObject
from uasset_read.objects.registry import ObjectTypeRegistry

__all__ = ["UObject", "ObjectTypeRegistry"]
