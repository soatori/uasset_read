"""
C++ 代码生成模块。

提供 UE 蓝图数据到 C++ 骨架代码的映射和生成功能。

模块：
    cpp_type_mapper: UE 类型路径 → C++ 类型名映射
    cpp_uproperty_mapper: CPF 标志 → UPROPERTY 标记映射
    extract_cpp_skeleton: C++ 类骨架提取
    formatters: C++ JSON IR 格式化和 .h 头文件生成

导出符号：
    类型映射：
        UE_TO_CPP_TYPE_MAP: UE 类型路径 → C++ 类型名字典
        ENGINE_CLASS_PATHS: Engine 类路径 → C++ 类名字典
        ue_path_to_cpp_type: UE 类型路径 → C++ 类型名转换函数
        ue_package_path_to_cpp_class: 包路径 → C++ 类名转换函数
        infer_class_prefix: 父类名 → C++ 前缀推断函数
        resolve_ue_type: 完整 UE 路径 → C++ 类型名解析函数

    属性映射：
        CPF_TO_UPROPERTY_MAP: CPF 标志 → UPROPERTY 标记映射规则
        cpf_flags_to_uproperty_marks: CPF 标志 → UPROPERTY 标记列表转换函数

    骨架提取：
        extract_cpp_class_skeleton: LinkerParseResult → CppClassIR 提取函数

    JSON IR 格式化（从 formatters 子模块）：
        CppProperty: 单个 C++ UPROPERTY 声明数据模型
        CppHeaderMeta: 头文件元数据模型
        CppClassIR: 完整 C++ 类骨架 IR 数据模型
        format_cpp_class_json: JSON IR 格式化函数

    .h 头文件生成：
        format_cpp_header: CppClassIR → .h 文本转换函数
"""
from uasset_read.cpp_gen.cpp_type_mapper import (
    UE_TO_CPP_TYPE_MAP,
    ENGINE_CLASS_PATHS,
    ue_path_to_cpp_type,
    ue_package_path_to_cpp_class,
    infer_class_prefix,
    resolve_ue_type,
)
from uasset_read.cpp_gen.cpp_uproperty_mapper import (
    CPF_TO_UPROPERTY_MAP,
    cpf_flags_to_uproperty_marks,
)
from uasset_read.cpp_gen.extract_cpp_skeleton import (
    extract_cpp_class_skeleton,
)
from uasset_read.cpp_gen.formatters import (
    CppProperty,
    CppHeaderMeta,
    CppClassIR,
    format_cpp_class_json,
    format_cpp_header,
    format_cpp_call_statements,
    # Method/Call IR
    CppCallParameter,
    CppMethodIR,
    CppCallStatement,
    # Statement IR
    CppStatement,
    CppCallStmt,
    CppAssignmentStmt,
    CppIfStmt,
    CppInlineExprStmt,
    CppReturnStmt,
    CppWhileStmt,
    CppRawStmt,
    # Body builder
    kismet_to_cpp_body,
)
from uasset_read.cpp_gen.cpp_default_value_formatter import (
    format_cpp_default_value,
    format_cpp_transform,
    format_cpp_component_init,
    format_cpp_input_action_load,
)
from uasset_read.cpp_gen.cpp_constructor_formatter import (
    build_constructor_sections,
    format_cpp_constructor,
)
from uasset_read.cpp_gen.extract_cpp_skeleton import (
    extract_cpp_constructor,
)
from uasset_read.cpp_gen.sanitizer import (
    sanitize_identifier,
)

__all__ = [
    # 类型映射
    "UE_TO_CPP_TYPE_MAP",
    "ENGINE_CLASS_PATHS",
    "ue_path_to_cpp_type",
    "ue_package_path_to_cpp_class",
    "infer_class_prefix",
    "resolve_ue_type",
    # 属性映射
    "CPF_TO_UPROPERTY_MAP",
    "cpf_flags_to_uproperty_marks",
    # 骨架提取
    "extract_cpp_class_skeleton",
    # JSON IR 格式化
    "CppProperty",
    "CppHeaderMeta",
    "CppClassIR",
    "format_cpp_class_json",
    # .h 头文件生成
    "format_cpp_header",
    # Call statement formatting
    "format_cpp_call_statements",
    # Method/Call IR
    "CppCallParameter",
    "CppMethodIR",
    "CppCallStatement",
    # Statement IR
    "CppStatement",
    "CppCallStmt",
    "CppAssignmentStmt",
    "CppIfStmt",
    "CppInlineExprStmt",
    "CppReturnStmt",
    "CppWhileStmt",
    "CppRawStmt",
    # Body builder
    "kismet_to_cpp_body",
    # C++ 默认值格式化
    "format_cpp_default_value",
    "format_cpp_transform",
    "format_cpp_component_init",
    "format_cpp_input_action_load",
    # C++ 构造函数格式化
    "build_constructor_sections",
    "format_cpp_constructor",
    "extract_cpp_constructor",
    # C++ 标识符清理
    "sanitize_identifier",
]