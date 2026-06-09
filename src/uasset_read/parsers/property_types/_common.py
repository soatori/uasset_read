"""属性类型解析器的共享辅助函数（lazy import helpers 等）。"""
from __future__ import annotations

import re
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.core import FEdGraphPinType
    from uasset_read.versioning import VersionContainer


# ============================================================================
# Lazy import helpers (avoid circular dependency with property_parser.py)
# ============================================================================

def _get_parse_property_value():
    """Lazy import to avoid circular dependency (parsers <-> property_types)."""
    from uasset_read.parsers.property_parser import parse_property_value
    return parse_property_value


def _get_read_property_tag():
    """Lazy import to avoid circular dependency."""
    from uasset_read.serializers.property_tags import read_property_tag
    return read_property_tag


def _get_read_tag_value_bounded():
    """Lazy import to avoid circular dependency."""
    from uasset_read.serializers.property_tags import read_tag_value_bounded
    return read_tag_value_bounded


def _build_version_container_from_summary(summary: Any) -> Optional["VersionContainer"]:
    """从 summary 构建 VersionContainer（Lazy，避免循环导入）。"""
    if summary is None:
        return None
    # 已缓存则直接返回
    cached = getattr(summary, "_version_container", None)
    if cached is not None:
        return cached
    try:
        from uasset_read.versioning import build_version_container
        vc = build_version_container(summary)
        # 缓存到 summary 上，避免重复构建
        try:
            summary._version_container = vc
        except AttributeError:
            pass
        return vc
    except Exception:
        return None


# ============================================================================
# 默认值解析（从 property_types.py 迁移）
# ============================================================================

def parse_default_value(value_str: str, var_type: "FEdGraphPinType") -> Any:
    """
    解析 DefaultValue 字符串到 Python 原生类型（BLUE-03）。

    Per D-13: 解析为 int, float, bool, str。
    Per D-14: 解析失败时回退到原始字符串。
    Per D-15: 仅基本类型 — 无数组、向量、对象。
    Per D-16: Vector 类型保持为字符串 "(X=...,Y=...,Z=...)"。
    """
    if not value_str:
        return None

    # 检查向量格式，保持为字符串
    if value_str.startswith("(") and value_str.endswith(")"):
        return value_str

    # 使用 PinCategory 进行类型检测
    category = var_type.pin_category.lower()

    # 布尔解析
    if category in ("bool", "boolean"):
        if value_str.lower() in ("true", "1"):
            return True
        elif value_str.lower() in ("false", "0"):
            return False
        return value_str

    # 整数解析
    if category in ("int", "integer"):
        if re.match(r'^-?\d+$', value_str):
            return int(value_str)
        return value_str

    # 浮点/实数解析
    if category in ("float", "real", "double"):
        if re.match(r'^-?\d+\.?\d*$', value_str):
            return float(value_str)
        return value_str

    # 字符串/名称：保持原样
    if category in ("string", "name", "text"):
        return value_str

    # 未知类别：回退到原始字符串
    return value_str
