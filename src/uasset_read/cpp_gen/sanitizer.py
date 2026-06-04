"""
C++ 标识符清理模块。

提供将 UE 蓝图名称（可含空格、特殊字符）转换为合法 C++ 标识符的功能。

导出：
    sanitize_identifier: 清理 C++ 标识符函数
"""
from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)


def sanitize_identifier(name: str) -> str:
    """将 UE 引脚名/变量名转换为有效 C++ 标识符。

    规则：
    1. 空格 → 下划线（"Target Touch UI" → "Target_Touch_UI"）
    2. 移除非法字符（只保留字母、数字、下划线）
    3. 数字开头 → 前缀 _（"123Var" → "_123Var"）
    4. 空字符串 → "_unnamed"

    Args:
        name: 原始名称（可能包含空格、特殊字符）

    Returns:
        合法的 C++ 标识符

    Examples:
        >>> sanitize_identifier("Target Touch UI")
        'Target_Touch_UI'
        >>> sanitize_identifier("MyVar@#$")
        'MyVar'
        >>> sanitize_identifier("123Var")
        '_123Var'
        >>> sanitize_identifier("")
        '_unnamed'
        >>> sanitize_identifier("Left / Right")
        'Left__Right'
        >>> sanitize_identifier("Primary Thumbstick")
        'Primary_Thumbstick'
    """
    if not name:
        return "_unnamed"

    # 1. 空格 → 下划线
    cleaned = name.replace(' ', '_')

    # 2. 移除非法字符（只保留字母、数字、下划线）
    cleaned = re.sub(r'[^A-Za-z0-9_]', '', cleaned)

    # 3. 数字开头 → 前缀 _
    if cleaned and cleaned[0].isdigit():
        cleaned = '_' + cleaned

    # 4. 空字符串 → 默认名
    if not cleaned:
        return "_unnamed"

    return cleaned


__all__ = [
    "sanitize_identifier",
]
