"""字符串/字典清理工具 — 移除二进制字符，确保 JSON 安全输出。"""
from __future__ import annotations


def _sanitize_string(value: str) -> str:
    """清理字符串中的二进制/null 字符，确保 JSON 安全输出。

    保留 \n \r \t 等常用控制字符，移除 null 和其他控制字符。
    """
    if not value:
        return value
    # 移除 null 字符
    value = value.replace('\x00', '')
    # 移除其他控制字符（保留 \n \r \t）
    value = ''.join(c for c in value if c >= ' ' or c in '\n\r\t')
    return value


def _sanitize_pin_dict(pin_dict: dict) -> dict:
    """清理 pin dict 中所有字符串字段。"""
    sanitized = {}
    for key, val in pin_dict.items():
        if isinstance(val, str):
            sanitized[key] = _sanitize_string(val)
        elif isinstance(val, (list, dict)):
            sanitized[key] = _sanitize_recursive(val)
        else:
            sanitized[key] = val
    return sanitized


def _sanitize_recursive(obj, visited=None):
    """递归清理列表/字典中的字符串。

    Args:
        obj: 要清理的对象
        visited: 已访问对象的 id 集合，用于防止循环引用导致的无限递归
    """
    # 初始化 visited 集合（仅在顶层调用时）
    if visited is None:
        visited = set()

    # 对可变对象检查循环引用
    if isinstance(obj, (list, dict)):
        obj_id = id(obj)
        if obj_id in visited:
            # 检测到循环引用，返回安全的替代值
            if isinstance(obj, dict):
                return {}
            return []
        visited.add(obj_id)

    if isinstance(obj, str):
        return _sanitize_string(obj)
    elif isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    elif isinstance(obj, list):
        return [_sanitize_recursive(item, visited) for item in obj]
    elif isinstance(obj, dict):
        return {k: _sanitize_recursive(v, visited) for k, v in obj.items()}
    elif hasattr(obj, "get_full_name"):
        try:
            return obj.get_full_name()
        except Exception:
            return str(obj)
    elif hasattr(obj, "object_name"):
        return getattr(obj, "object_name", str(obj))
    return str(obj)
