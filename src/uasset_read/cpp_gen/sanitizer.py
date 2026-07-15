"""
C++ 标识符与内容净化模块。

提供将 UE 资产派生字段转换为安全 C++ 代码的功能，防止注入。
所有 C++ 生成代码中的用户派生内容必须经过此模块净化。

导出：
    sanitize_identifier: 清理 C++ 标识符函数
    sanitize_string_literal: 清理 C++ 字符串字面量 / TEXT() 内容
    sanitize_uproperty_marks: 清理 UPROPERTY specifier 列表
    sanitize_category: 清理 UPROPERTY Category 字符串
"""

import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# UPROPERTY specifier 白名单
# ============================================================================

_UPROPERTY_SPECIFIER_WHITELIST = frozenset({
    # 可见性 / 编辑
    "EditAnywhere",
    "EditInstanceOnly",
    "EditDefaultsOnly",
    "VisibleAnywhere",
    "VisibleInstanceOnly",
    "VisibleDefaultsOnly",
    # Blueprint 访问
    "BlueprintReadWrite",
    "BlueprintReadOnly",
    "BlueprintCallable",
    "BlueprintAssignable",
    "BlueprintPure",
    "BlueprintType",
    "NotBlueprintType",
    # 实例
    "Instanced",
    "DuplicateTransient",
    "Transient",
    # 网络
    "Replicated",
    "ReplicatedUsing",
    # 配置
    "Config",
    "GlobalConfig",
    # 其他
    "SaveGame",
    "NoClear",
    "NoExport",
    "Interp",
    "NonTransactional",
    "ExposeOnSpawn",
    "AllowPrivateAccess",
    "Deprecated",
    "AdvancedDisplay",
    "Protected",
    "Meta",
    "Category",
    "Ref",
    "SubobjectReference",
})


def sanitize_identifier(name: str, fallback: str = "_unnamed") -> str:
    """将 UE 引脚名/变量名转换为有效 C++ 标识符。

    规则：
    1. 空格 → 下划线（"Target Touch UI" → "Target_Touch_UI"）
    2. 移除非法字符（只保留字母、数字、下划线）
    3. 数字开头 → 前缀 _（"123Var" → "_123Var"）
    4. 空字符串 / None → fallback

    Args:
        name: 原始名称（可能包含空格、特殊字符）
        fallback: 净化后为空时的回退值

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
        >>> sanitize_identifier(None, "_fallback")
        '_fallback'
        >>> sanitize_identifier("Left / Right")
        'Left__Right'
        >>> sanitize_identifier("Primary Thumbstick")
        'Primary_Thumbstick'
    """
    if not name:
        return fallback

    # 1. 空格 → 下划线
    cleaned = name.replace(' ', '_')

    # 2. 移除非法字符（只保留字母、数字、下划线）
    cleaned = re.sub(r'[^A-Za-z0-9_]', '', cleaned)

    # 3. 数字开头 → 前缀 _
    if cleaned and cleaned[0].isdigit():
        cleaned = '_' + cleaned

    # 4. 空字符串 → 默认名
    if not cleaned:
        return fallback

    return cleaned


def sanitize_string_literal(value: str) -> str:
    """净化用于 C++ 字符串字面量 / TEXT() 的值。

    转义反斜杠、双引号、换行、回车、制表符，防止注入。
    输出内容可直接嵌入 TEXT("...") 或 "..." 中。

    Args:
        value: 原始字符串值

    Returns:
        转义后的字符串，可安全嵌入 C++ 字符串字面量

    Examples:
        >>> sanitize_string_literal('Hello "World"')
        'Hello \\\\"World\\\\"'
        >>> sanitize_string_literal('C:\\\\path')
        'C:\\\\\\\\path'
        >>> sanitize_string_literal('line1\\nline2')
        'line1\\\\nline2'
        >>> sanitize_string_literal('tab\\there')
        'tab\\\\there'
        >>> sanitize_string_literal('cr\\rhere')
        'cr\\\\rhere'
        >>> sanitize_string_literal('null\\x00byte')
        'null\\\\0byte'
    """
    if value is None:
        return ""

    result = value
    # 反斜杠必须最先转义（否则后续转义的反斜杠会被二次转义）
    result = result.replace('\\', '\\\\')
    # 双引号
    result = result.replace('"', '\\"')
    # null 字节
    result = result.replace('\x00', '\\0')
    # 换行符
    result = result.replace('\n', '\\n')
    # 回车符
    result = result.replace('\r', '\\r')
    # 制表符
    result = result.replace('\t', '\\t')

    return result


def sanitize_uproperty_marks(marks: Optional[List[str]]) -> List[str]:
    """净化 UPROPERTY specifier 列表。

    只保留白名单中的合法 specifier，过滤危险内容。
    空值或 None 返回空列表。

    Args:
        marks: UPROPERTY specifier 字符串列表

    Returns:
        过滤后的合法 specifier 列表

    Examples:
        >>> sanitize_uproperty_marks(["EditAnywhere", "BlueprintReadWrite"])
        ['EditAnywhere', 'BlueprintReadWrite']
        >>> sanitize_uproperty_marks(["EditAnywhere", "INJECTED_CODE", "Transient"])
        ['EditAnywhere', 'Transient']
        >>> sanitize_uproperty_marks(None)
        []
        >>> sanitize_uproperty_marks([])
        []
        >>> sanitize_uproperty_marks(["EditAnywhere", "EditAnywhere"])
        ['EditAnywhere']
    """
    if not marks:
        return []

    result: List[str] = []
    for mark in marks:
        if not mark or not isinstance(mark, str):
            continue
        # 精确匹配白名单（区分大小写，UE specifier 为 PascalCase）
        if mark in _UPROPERTY_SPECIFIER_WHITELIST:
            if mark not in result:
                result.append(mark)
        else:
            logger.debug(f"Filtered invalid UPROPERTY specifier: {mark!r}")

    return result


def sanitize_category(category: str) -> str:
    """净化 UPROPERTY Category 字符串。

    移除引号、反斜杠、换行等危险字符，只保留字母数字、空格和下划线。
    输出可直接嵌入 Category = "..." 中。

    Args:
        category: 原始 Category 字符串

    Returns:
        净化后的 Category 字符串

    Examples:
        >>> sanitize_category('My "Category"')
        'My Category'
        >>> sanitize_category('C:\\\\path/to')
        'Cpathto'
        >>> sanitize_category("line\\nbreak")
        'linebreak'
        >>> sanitize_category('  Trimmed  ')
        'Trimmed'
        >>> sanitize_category('Valid_Category 123')
        'Valid_Category 123'
    """
    if not category:
        return ""

    # 移除引号（防止逃逸出 Category = "..."）
    result = category.replace('"', '').replace("'", "")
    # 移除反斜杠
    result = result.replace('\\', '')
    # 移除换行和回车
    result = result.replace('\n', '').replace('\r', '')
    # 移除制表符
    result = result.replace('\t', ' ')
    # 只保留字母数字空格下划线
    result = re.sub(r'[^A-Za-z0-9 _]', '', result)
    # 压缩连续空格
    result = re.sub(r' +', ' ', result)
    # 去除首尾空格
    result = result.strip()

    return result


__all__ = [
    "sanitize_identifier",
    "sanitize_string_literal",
    "sanitize_uproperty_marks",
    "sanitize_category",
]
