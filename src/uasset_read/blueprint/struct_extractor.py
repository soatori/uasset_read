"""蓝图结构体提取模块 — 从 BlueprintMetadata 提取用户定义的结构体。

导出：
    StructFieldIR: 结构体字段 IR
    StructIR: 结构体 IR
    extract_structs: 从 BlueprintMetadata 提取结构体列表
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.blueprint import BlueprintMetadata


@dataclass
class StructFieldIR:
    """结构体字段的 IR 表示。

    Attributes:
        name: 字段名称
        cpp_type: C++ 类型名
        default_value: 默认值
    """
    name: str
    cpp_type: str = ""
    default_value: str = ""


@dataclass
class StructIR:
    """蓝图结构体的 IR 表示。

    Attributes:
        name: 结构体名称（如 "FMyStruct"）
        cpp_type: C++ 类型名（带 F 前缀）
        fields: 字段列表
        ue_path: UE 完整路径
    """
    name: str
    cpp_type: str = ""
    fields: List[StructFieldIR] = field(default_factory=list)
    ue_path: str = ""


def extract_structs(blueprint: Optional["BlueprintMetadata"]) -> List[StructIR]:
    """从 BlueprintMetadata 提取用户定义的结构体列表。

    结构体信息来源：
    1. BlueprintMetadata.variables 中类型为 struct 的变量
    2. 未来可扩展到独立的结构体定义导出

    Args:
        blueprint: BlueprintMetadata 实例

    Returns:
        StructIR 列表
    """
    if not blueprint:
        return []

    structs: List[StructIR] = []
    seen_names: set = set()

    # 从变量中提取结构体类型引用
    for var in blueprint.variables:
        if not hasattr(var, 'var_type') or not var.var_type:
            continue

        pin_type = var.var_type
        # 检查是否为结构体类型
        if pin_type.pin_category == "struct":
            struct_path = pin_type.pin_subcategory or ""
            if struct_path and struct_path != "None" and struct_path not in seen_names:
                seen_names.add(struct_path)
                struct_name = _extract_struct_name(struct_path)
                structs.append(StructIR(
                    name=struct_name,
                    cpp_type=struct_name,
                    ue_path=struct_path,
                    fields=[],  # 字段需要从结构体定义中提取，此处仅记录引用
                ))

    return structs


def _extract_struct_name(ue_path: str) -> str:
    """从 UE 路径提取结构体名称。

    Examples:
        "/Script/MyModule.MyStruct" → "FMyStruct"
        "/Game/Structs/FMyStruct" → "FMyStruct"

    UE 结构体在 C++ 中以 F 开头。

    Args:
        ue_path: UE 完整路径

    Returns:
        C++ 结构体名称（F 前缀）
    """
    if not ue_path:
        return ""

    # 提取最后一段（类名部分）
    class_name = ue_path.split('.')[-1] if '.' in ue_path else ue_path.split('/')[-1]

    # UE 结构体在 C++ 中以 F 开头，如果已经是 F 开头则直接使用
    if class_name.startswith('F'):
        return class_name

    # 否则添加 F 前缀
    return f"F{class_name}"


__all__ = ["StructFieldIR", "StructIR", "extract_structs"]
