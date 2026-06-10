"""蓝图接口提取模块 — 从 BlueprintMetadata 提取实现的接口信息。

导出：
    InterfaceIR: 接口中间表示（name, cpp_type）
    extract_interfaces: 从 BlueprintMetadata 提取接口列表
"""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from uasset_read.models.ir import InterfaceIR

if TYPE_CHECKING:
    from uasset_read.models.blueprint import BlueprintMetadata


def extract_interfaces(blueprint: Optional["BlueprintMetadata"]) -> List[InterfaceIR]:
    """从 BlueprintMetadata 提取实现的接口列表。

    接口信息来源：
    1. BlueprintMetadata.functions 中标记为 interface 的函数
    2. 未来可扩展到 ImplementedInterfaces 属性

    Args:
        blueprint: BlueprintMetadata 实例

    Returns:
        InterfaceIR 列表
    """
    if not blueprint:
        return []

    interfaces: List[InterfaceIR] = []
    seen_names: set = set()

    # 从函数的 interface_class 字段提取接口
    for func in blueprint.functions:
        if hasattr(func, 'is_interface_event') and func.is_interface_event:
            interface_class = getattr(func, 'interface_class', '')
            if interface_class and interface_class not in seen_names:
                seen_names.add(interface_class)
                cpp_name = _extract_interface_name(interface_class)
                interfaces.append(InterfaceIR(
                    name=cpp_name,
                    cpp_type=cpp_name,
                    ue_path=interface_class,
                ))

    # 从 events 中提取接口事件
    for event in blueprint.events:
        if hasattr(event, 'is_interface_event') and event.is_interface_event:
            interface_class = getattr(event, 'interface_class', '')
            if interface_class and interface_class not in seen_names:
                seen_names.add(interface_class)
                cpp_name = _extract_interface_name(interface_class)
                interfaces.append(InterfaceIR(
                    name=cpp_name,
                    cpp_type=cpp_name,
                    ue_path=interface_class,
                ))

    return interfaces


def _extract_interface_name(ue_path: str) -> str:
    """从 UE 路径提取接口名称。

    Examples:
        "/Script/MyModule.BPI_MyInterface" → "IBPI_MyInterface"
        "/Game/Interfaces/BPI_MyInterface" → "IBPI_MyInterface"

    UE 接口类在 C++ 中以 I 开头。

    Args:
        ue_path: UE 完整路径

    Returns:
        C++ 接口名称（I 前缀）
    """
    if not ue_path:
        return ""

    # 提取最后一段（类名部分）
    class_name = ue_path.split('.')[-1] if '.' in ue_path else ue_path.split('/')[-1]

    # UE 接口在 C++ 中以 I 开头，如果已经是 I 开头则直接使用
    if class_name.startswith('I'):
        return class_name

    # 否则添加 I 前缀
    return f"I{class_name}"


__all__ = ["InterfaceIR", "extract_interfaces"]
