"""IR 构建层 — 公共工具函数。

被 __init__.py 和各子模块共同使用，避免循环导入。
"""
from __future__ import annotations

import re


def _safe_str(value) -> str:
    """安全地将值转为字符串，None 返回空字符串。"""
    if value is None:
        return ""
    return str(value)


def _safe_int(value, default: int = 0) -> int:
    """安全地将值转为 int，仅接受真实 int 和明确数字字符串，其他类型返回 default。

    MagicMock 对象实现了 __int__ 返回 1，因此必须显式排除非 int 对象。
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _normalize_guid(guid: str | None) -> str | None:
    """将 GUID 标准化为 32 位小写 hex（无横杠）。"""
    if not guid:
        return None
    cleaned = str(guid).replace("-", "").lower()
    if len(cleaned) == 32 and all(c in "0123456789abcdef" for c in cleaned):
        return cleaned
    return None


def _extract_pin_guid(ref) -> str | None:
    """从 Pin 引用中提取并标准化 GUID。"""
    if isinstance(ref, dict):
        raw = ref.get("pin_guid") or ref.get("pin_id")
        return _normalize_guid(raw) if raw else None
    if isinstance(ref, str):
        return _normalize_guid(ref)
    raw = getattr(ref, "pin_guid", None) or getattr(ref, "pin_id", None)
    return _normalize_guid(raw) if raw else None


def _classify_variable(var) -> str:
    """分类蓝图变量。"""
    from uasset_read.constants import BLUEPRINT_METADATA_KEYS as _BLUEPRINT_METADATA_KEYS

    name = getattr(var, "var_name", "") or ""
    if name in _BLUEPRINT_METADATA_KEYS:
        return "metadata"
    if getattr(var, "is_component", False):
        return "component"
    if "InputAction" in name or "InputAxis" in name:
        return "input_action"
    return "user"
