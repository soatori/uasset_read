"""属性类型解析器的共享辅助函数（lazy import helpers 等）。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
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
