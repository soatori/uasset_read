"""蓝图委托提取模块 — 从 BlueprintMetadata 提取委托和多播委托。

导出：
    DelegateIR: 委托 IR
    extract_delegates: 从 BlueprintMetadata 提取委托列表
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.blueprint import BlueprintMetadata


@dataclass
class DelegateIR:
    """蓝图委托的 IR 表示。

    Attributes:
        name: 委托名称（如 "FMyDelegate"）
        cpp_type: C++ 类型名（带 F 前缀）
        signature: 签名字符串（参数和返回类型）
        is_multicast: 是否为多播委托
        ue_path: UE 完整路径
    """
    name: str
    cpp_type: str = ""
    signature: str = ""
    is_multicast: bool = False
    ue_path: str = ""


def extract_delegates(blueprint: Optional["BlueprintMetadata"]) -> List[DelegateIR]:
    """从 BlueprintMetadata 提取委托和多播委托列表。

    委托信息来源：
    1. BlueprintMetadata.functions 中标记为 delegate 或 multicast_delegate 的函数
    2. BlueprintMetadata.events 中关联的 multicast_delegate

    Args:
        blueprint: BlueprintMetadata 实例

    Returns:
        DelegateIR 列表
    """
    if not blueprint:
        return []

    delegates: List[DelegateIR] = []
    seen_names: set = set()

    # 从函数中提取委托
    for func in blueprint.functions:
        is_delegate = getattr(func, 'is_delegate', False)
        is_multicast = getattr(func, 'is_multicast_delegate', False)

        if is_delegate or is_multicast:
            delegate_name = func.name
            if delegate_name and delegate_name not in seen_names:
                seen_names.add(delegate_name)
                cpp_name = _extract_delegate_name(delegate_name)
                signature = _build_signature(func)
                delegates.append(DelegateIR(
                    name=cpp_name,
                    cpp_type=cpp_name,
                    signature=signature,
                    is_multicast=is_multicast,
                    ue_path="",  # 委托通常没有完整的 UE 路径
                ))

    # 从事件中提取多播委托
    for event in blueprint.events:
        multicast_delegate = getattr(event, 'multicast_delegate', None)
        if multicast_delegate and hasattr(multicast_delegate, 'delegate_name'):
            delegate_name = multicast_delegate.delegate_name
            if delegate_name and delegate_name not in seen_names:
                seen_names.add(delegate_name)
                cpp_name = _extract_delegate_name(delegate_name)
                delegates.append(DelegateIR(
                    name=cpp_name,
                    cpp_type=cpp_name,
                    signature="",
                    is_multicast=True,
                    ue_path="",
                ))

    return delegates


def _extract_delegate_name(name: str) -> str:
    """从委托名称提取 C++ 类型名。

    Examples:
        "MyDelegate" → "FMyDelegate"
        "OnMyEvent" → "FOnMyEvent"

    UE 委托在 C++ 中以 F 开头。

    Args:
        name: 委托名称

    Returns:
        C++ 委托名称（F 前缀）
    """
    if not name:
        return ""

    # 如果已经是 F 开头则直接使用
    if name.startswith('F'):
        return name

    # 否则添加 F 前缀
    return f"F{name}"


def _build_signature(func) -> str:
    """从 BlueprintFunction 构建委托签名。

    Args:
        func: BlueprintFunction 实例

    Returns:
        签名字符串（如 "void(int32, float)"）
    """
    params = []
    if hasattr(func, 'parameters'):
        for param in func.parameters:
            if hasattr(param, 'param_type') and param.param_type:
                params.append(param.param_type)

    return_type = getattr(func, 'return_type', 'void') or 'void'
    param_str = ", ".join(params)
    return f"{return_type}({param_str})"


__all__ = ["DelegateIR", "extract_delegates"]
