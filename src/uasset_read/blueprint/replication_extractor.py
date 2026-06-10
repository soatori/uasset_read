"""蓝图复制提取模块 — 从 BlueprintMetadata 提取复制变量和 OnRep 函数。

导出：
    ReplicatedVarIR: 复制变量 IR
    ReplicationIR: 复制 IR
    extract_replication: 从 BlueprintMetadata 提取复制信息
"""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from uasset_read.models.ir import ReplicatedVarIR, ReplicationIR

if TYPE_CHECKING:
    from uasset_read.models.blueprint import BlueprintMetadata


def extract_replication(blueprint: Optional["BlueprintMetadata"]) -> ReplicationIR:
    """从 BlueprintMetadata 提取复制信息。

    复制信息来源：
    1. BlueprintMetadata.variables 中标记为 replicated 的变量
    2. 变量的 rep_notify_func 字段（OnRep 函数名）

    Args:
        blueprint: BlueprintMetadata 实例

    Returns:
        ReplicationIR 实例
    """
    if not blueprint:
        return ReplicationIR()

    replicated_vars: List[ReplicatedVarIR] = []
    on_rep_functions: List[str] = []
    seen_on_reps: set = set()

    # 从变量中提取复制信息
    for var in blueprint.variables:
        is_replicated = getattr(var, 'is_replicated', False)
        is_net = getattr(var, 'is_net', False)

        if is_replicated or is_net:
            var_name = var.var_name if hasattr(var, 'var_name') else ""
            if not var_name:
                continue

            # 提取 C++ 类型
            cpp_type = ""
            if hasattr(var, 'var_type') and var.var_type:
                cpp_type = _pin_type_to_cpp(var.var_type)

            # 提取 OnRep 函数
            on_rep_func = getattr(var, 'rep_notify_func', '') or ""
            rep_condition = getattr(var, 'replication_condition', 0) or 0

            replicated_vars.append(ReplicatedVarIR(
                name=var_name,
                cpp_type=cpp_type,
                on_rep_function=on_rep_func,
                replication_condition=rep_condition,
            ))

            # 收集 OnRep 函数
            if on_rep_func and on_rep_func not in seen_on_reps:
                seen_on_reps.add(on_rep_func)
                on_rep_functions.append(on_rep_func)

    return ReplicationIR(
        replicated_vars=replicated_vars,
        on_rep_functions=on_rep_functions,
    )


def _pin_type_to_cpp(pin_type) -> str:
    """将 FEdGraphPinType 转换为 C++ 类型名。

    Args:
        pin_type: FEdGraphPinType 实例

    Returns:
        C++ 类型名
    """
    if not pin_type:
        return "void"

    category = getattr(pin_type, 'pin_category', '')
    subcategory = getattr(pin_type, 'pin_subcategory', '')

    # 基础类型映射
    type_map = {
        "real": "float",
        "double": "double",
        "float": "float",
        "int": "int32",
        "int32": "int32",
        "int64": "int64",
        "byte": "uint8",
        "bool": "bool",
        "string": "FString",
        "name": "FName",
        "text": "FText",
        "struct": subcategory or "FStruct",
        "object": "UObject*",
        "class": "UClass*",
    }

    cpp_type = type_map.get(category, category)

    # 如果是 struct 类型，使用 subcategory
    if category == "struct" and subcategory:
        # 提取结构体名称
        struct_name = subcategory.split('.')[-1] if '.' in subcategory else subcategory.split('/')[-1]
        if not struct_name.startswith('F'):
            struct_name = f"F{struct_name}"
        cpp_type = struct_name

    return cpp_type


__all__ = ["ReplicatedVarIR", "ReplicationIR", "extract_replication"]
