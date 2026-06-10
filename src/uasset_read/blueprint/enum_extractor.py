"""蓝图枚举提取模块 — 从 BlueprintMetadata 提取用户定义的枚举。

导出：
    EnumValueIR: 枚举值 IR
    EnumIR: 枚举 IR
    extract_enums: 从 BlueprintMetadata 提取枚举列表
"""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from uasset_read.models.ir import EnumValueIR, EnumIR

if TYPE_CHECKING:
    from uasset_read.models.blueprint import BlueprintMetadata


def extract_enums(blueprint: Optional["BlueprintMetadata"]) -> List[EnumIR]:
    """从 BlueprintMetadata 提取用户定义的枚举列表。

    枚举信息来源：
    1. BlueprintMetadata.variables 中类型为 byte/enum 的变量
    2. 未来可扩展到独立的枚举定义导出

    Args:
        blueprint: BlueprintMetadata 实例

    Returns:
        EnumIR 列表
    """
    if not blueprint:
        return []

    enums: List[EnumIR] = []
    seen_names: set = set()

    # 从变量中提取枚举类型引用
    for var in blueprint.variables:
        if not hasattr(var, 'var_type') or not var.var_type:
            continue

        pin_type = var.var_type
        # 检查是否为枚举类型（byte 类型 + enum subcategory）
        if pin_type.pin_category in ("byte", "enum"):
            enum_path = pin_type.pin_subcategory or ""
            if enum_path and enum_path != "None" and enum_path not in seen_names:
                seen_names.add(enum_path)
                enum_name = _extract_enum_name(enum_path)
                enums.append(EnumIR(
                    name=enum_name,
                    cpp_type=enum_name,
                    ue_path=enum_path,
                    values=[],  # 枚举值需要从枚举定义中提取，此处仅记录引用
                ))

    return enums


def _extract_enum_name(ue_path: str) -> str:
    """从 UE 路径提取枚举名称。

    Examples:
        "/Script/MyModule.MyEnum" → "EMyEnum"
        "/Game/Enums/EMyEnum" → "EMyEnum"

    UE 枚举在 C++ 中以 E 开头。

    Args:
        ue_path: UE 完整路径

    Returns:
        C++ 枚举名称（E 前缀）
    """
    if not ue_path:
        return ""

    # 提取最后一段（类名部分）
    class_name = ue_path.split('.')[-1] if '.' in ue_path else ue_path.split('/')[-1]

    # UE 枚举在 C++ 中以 E 开头，如果已经是 E 开头则直接使用
    if class_name.startswith('E'):
        return class_name

    # 否则添加 E 前缀
    return f"E{class_name}"


__all__ = ["EnumValueIR", "EnumIR", "extract_enums"]
