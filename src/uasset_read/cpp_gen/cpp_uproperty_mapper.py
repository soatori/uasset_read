"""
CPF 属性标志 → UPROPERTY 标记映射模块。

提供 CPF 标志位到 UPROPERTY 宏标记的转换。
Per D-04: CPF 标志直接映射到 UPROPERTY 标记。

导出：
    CPF_TO_UPROPERTY_MAP: CPF 标志到 UPROPERTY 标记的映射
    cpf_flags_to_uproperty_marks: CPF 标志 → UPROPERTY 标记列表转换函数
"""
from __future__ import annotations

import logging
from typing import List, Tuple

from uasset_read.constants import (
    CPF_Edit,
    CPF_BlueprintVisible,
    CPF_BlueprintReadOnly,
    CPF_BlueprintReadWrite,
    CPF_EditAnywhere,
    CPF_EditInstanceOnly,
    CPF_InstancedReference,
    CPF_BlueprintAssignable,
    CPF_BlueprintCallable,
    CPF_Replicated,
    CPF_Net,
    CPF_Transient,
    CPF_DuplicateTransient,
    CPF_Config,
    CPF_SaveGame,
    CPF_NoClear,
    CPF_ExposeOnSpawn,
    CPF_Interp,
    CPF_RepNotify,
    CPF_ReferenceOnly,
    CPF_Deprecated,
    CPF_AdvancedDisplay,
    CPF_Protected,
)

logger = logging.getLogger(__name__)

# ============================================================================
# CPF 标志 → UPROPERTY 标记映射
# D-04: 按优先级排序的组合检查映射
# ============================================================================

# 映射格式: (check_flags, result_marks, is_combined_check)
# - is_combined_check=True: 所有 check_flags 必须设置才触发
# - is_combined_check=False: 任一 check_flags 设置即触发
# 顺序很重要：更具体的组合检查在前

_CPF_UPROPERTY_RULES: List[Tuple[int, List[str], bool]] = [
    # 组合检查：EditAnywhere + BlueprintReadWrite（常见组合）
    (CPF_Edit | CPF_BlueprintVisible, ["EditAnywhere", "BlueprintReadWrite"], True),

    # 单标志检查（按 UE UPROPERTY 文档顺序）
    (CPF_EditAnywhere, ["EditAnywhere"], False),
    (CPF_EditInstanceOnly, ["EditInstanceOnly"], False),
    (CPF_BlueprintReadOnly, ["BlueprintReadOnly"], False),
    (CPF_BlueprintReadWrite, ["BlueprintReadWrite"], False),
    (CPF_InstancedReference, ["Instanced"], False),
    (CPF_BlueprintAssignable, ["BlueprintAssignable"], False),
    (CPF_BlueprintCallable, ["BlueprintCallable"], False),
    (CPF_Replicated, ["Replicated"], False),
    (CPF_Transient, ["Transient"], False),
    (CPF_DuplicateTransient, ["DuplicateTransient"], False),
    (CPF_Config, ["Config"], False),
    (CPF_SaveGame, ["SaveGame"], False),
    (CPF_NoClear, ["NoClear"], False),
    (CPF_ExposeOnSpawn, ["ExposeOnSpawn"], False),
    (CPF_Interp, ["Interp"], False),
    (CPF_RepNotify, ["RepNotify"], False),
    (CPF_ReferenceOnly, ["ReferenceOnly"], False),
    (CPF_Deprecated, ["Deprecated"], False),
    (CPF_AdvancedDisplay, ["AdvancedDisplay"], False),
    (CPF_Protected, ["Protected"], False),
]

# CPF_Net 单独处理：只有当 CPF_Replicated 未设置时才添加
# CPF_Replicated 隐含 CPF_Net，所以 CPF_Net 通常不需要单独显示


def cpf_flags_to_uproperty_marks(cpf_flags: int, is_component: bool = False) -> List[str]:
    """
    将 CPF 标志位转换为 UPROPERTY 标记列表。

    按照映射规则将 CPF 标志转换为 UPROPERTY 宏中的标记。
    对于组件，如果未设置明确的可见性标志，自动添加默认标记。

    Args:
        cpf_flags: CPF 属性标志位掩码（来自 .uasset 解析）
        is_component: 是否为组件属性（影响默认标记）

    Returns:
        UPROPERTY 标记字符串列表

    Examples:
        >>> from uasset_read.constants import CPF_Edit, CPF_BlueprintVisible
        >>> cpf_flags_to_uproperty_marks(CPF_Edit | CPF_BlueprintVisible)
        ['EditAnywhere', 'BlueprintReadWrite']
        >>> cpf_flags_to_uproperty_marks(0)
        []
        >>> cpf_flags_to_uproperty_marks(CPF_InstancedReference)
        ['Instanced']
    """
    # T-056-02: 验证标志范围
    if cpf_flags < 0:
        logger.warning(f"Invalid CPF flags (negative): {cpf_flags}")
        return []

    # CPF 标志是 64 位无符号整数
    if cpf_flags >= (1 << 64):
        logger.warning(f"CPF flags out of 64-bit range: {cpf_flags}")
        cpf_flags = cpf_flags & ((1 << 64) - 1)

    marks: List[str] = []

    # 遍历映射规则
    for check_flags, result_marks, is_combined in _CPF_UPROPERTY_RULES:
        if is_combined:
            # 组合检查：所有标志都必须设置
            if (cpf_flags & check_flags) == check_flags:
                for mark in result_marks:
                    if mark not in marks:
                        marks.append(mark)
        else:
            # 单标志检查
            if cpf_flags & check_flags:
                for mark in result_marks:
                    if mark not in marks:
                        marks.append(mark)

    # CPF_Net 特殊处理：只有当 CPF_Replicated 未设置时才添加
    if (cpf_flags & CPF_Net) and not (cpf_flags & CPF_Replicated):
        if "Net" not in marks:
            marks.append("Net")

    # 组件默认标记：UE SCS 组件默认行为
    # 如果是组件且没有明确的可见性/编辑标志，添加 VisibleAnywhere + BlueprintReadOnly
    if is_component:
        has_edit_flag = any(
            m in marks
            for m in ["EditAnywhere", "EditInstanceOnly", "EditDefaultsOnly"]
        )
        has_visible_flag = any(
            m in marks
            for m in ["VisibleAnywhere", "VisibleInstanceOnly", "VisibleDefaultsOnly"]
        )

        # 如果没有编辑或可见标志，添加默认的 VisibleAnywhere + BlueprintReadOnly
        if not has_edit_flag and not has_visible_flag:
            marks.insert(0, "VisibleAnywhere")

        # 组件通常是只读的（由蓝图管理）
        has_blueprint_access = any(
            m in marks
            for m in ["BlueprintReadWrite", "BlueprintReadOnly", "BlueprintCallable"]
        )
        if not has_blueprint_access:
            marks.append("BlueprintReadOnly")

    return marks


# ============================================================================
# 反向映射：UPROPERTY 标记 → CPF 标志（用于测试和调试）
# ============================================================================

_UPROPERTY_TO_CPF: dict[str, int] = {
    "EditAnywhere": CPF_EditAnywhere,
    "EditInstanceOnly": CPF_EditInstanceOnly,
    "EditDefaultsOnly": CPF_Edit,
    "BlueprintReadOnly": CPF_BlueprintReadOnly,
    "BlueprintReadWrite": CPF_BlueprintReadWrite,
    "Instanced": CPF_InstancedReference,
    "BlueprintAssignable": CPF_BlueprintAssignable,
    "BlueprintCallable": CPF_BlueprintCallable,
    "Replicated": CPF_Replicated,
    "Net": CPF_Net,
    "Transient": CPF_Transient,
    "DuplicateTransient": CPF_DuplicateTransient,
    "Config": CPF_Config,
    "SaveGame": CPF_SaveGame,
    "NoClear": CPF_NoClear,
    "ExposeOnSpawn": CPF_ExposeOnSpawn,
    "Interp": CPF_Interp,
    "RepNotify": CPF_RepNotify,
    "ReferenceOnly": CPF_ReferenceOnly,
    "Deprecated": CPF_Deprecated,
    "AdvancedDisplay": CPF_AdvancedDisplay,
    "Protected": CPF_Protected,
}


def uproperty_mark_to_cpf(mark: str) -> int:
    """
    将单个 UPROPERTY 标记转换为对应的 CPF 标志。

    用于测试和调试目的。

    Args:
        mark: UPROPERTY 标记字符串

    Returns:
        对应的 CPF 标志值，如果未知则返回 0
    """
    return _UPROPERTY_TO_CPF.get(mark, 0)


# ============================================================================
# 导出列表
# ============================================================================

# 暴露规则列表供外部使用（只读）
CPF_TO_UPROPERTY_MAP = _CPF_UPROPERTY_RULES

__all__ = [
    "CPF_TO_UPROPERTY_MAP",
    "cpf_flags_to_uproperty_marks",
    "uproperty_mark_to_cpf",
]