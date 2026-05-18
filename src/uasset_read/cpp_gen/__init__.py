"""
C++ 代码生成模块（Phase 56）。

提供 UE 蓝图数据到 C++ 骨架代码的映射和生成功能。

模块：
    cpp_type_mapper: UE 类型路径 → C++ 类型名映射
    cpp_uproperty_mapper: CPF 标志 → UPROPERTY 标记映射

导出符号：
    类型映射：
        UE_TO_CPP_TYPE_MAP: UE 类型路径 → C++ 类型名字典
        ENGINE_CLASS_PATHS: Engine 类路径 → C++ 类名字典
        ue_path_to_cpp_type: UE 类型路径 → C++ 类型名转换函数
        ue_package_path_to_cpp_class: 包路径 → C++ 类名转换函数

    属性映射：
        CPF_TO_UPROPERTY_MAP: CPF 标志 → UPROPERTY 标记映射规则
        cpf_flags_to_uproperty_marks: CPF 标志 → UPROPERTY 标记列表转换函数
"""
from uasset_read.cpp_gen.cpp_type_mapper import (
    UE_TO_CPP_TYPE_MAP,
    ENGINE_CLASS_PATHS,
    ue_path_to_cpp_type,
    ue_package_path_to_cpp_class,
)
from uasset_read.cpp_gen.cpp_uproperty_mapper import (
    CPF_TO_UPROPERTY_MAP,
    cpf_flags_to_uproperty_marks,
)

__all__ = [
    # 类型映射
    "UE_TO_CPP_TYPE_MAP",
    "ENGINE_CLASS_PATHS",
    "ue_path_to_cpp_type",
    "ue_package_path_to_cpp_class",
    # 属性映射
    "CPF_TO_UPROPERTY_MAP",
    "cpf_flags_to_uproperty_marks",
]