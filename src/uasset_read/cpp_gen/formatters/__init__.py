"""
C++ 代码生成格式化子模块。

提供 C++ 类骨架 JSON IR 格式化功能和 .h 头文件生成功能。

导出符号：
    CppProperty: 单个 C++ UPROPERTY 声明数据模型
    CppHeaderMeta: 头文件元数据模型
    CppClassIR: 完整 C++ 类骨架 IR 数据模型
    format_cpp_class_json: JSON IR 格式化函数
    format_cpp_header: .h 头文件文本生成函数
"""
from uasset_read.cpp_gen.formatters.cpp_json_ir import (
    CppProperty,
    CppHeaderMeta,
    CppClassIR,
    format_cpp_class_json,
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
)
from uasset_read.cpp_gen.formatters.cpp_header_formatter import (
    format_cpp_header,
    format_cpp_call_statements,
)
from uasset_read.cpp_gen.formatters.cpp_function_body_formatter import (
    format_cpp_function_body,
    format_full_cpp_implementation,
)

__all__ = [
    "CppProperty",
    "CppHeaderMeta",
    "CppClassIR",
    "format_cpp_class_json",
    "format_cpp_header",
    # Method/Call IR
    "CppCallParameter",
    "CppMethodIR",
    "CppCallStatement",
    # Call statement formatting
    "format_cpp_call_statements",
    # Statement IR
    "CppStatement",
    "CppCallStmt",
    "CppAssignmentStmt",
    "CppIfStmt",
    "CppInlineExprStmt",
    # Function body formatting
    "format_cpp_function_body",
    "format_full_cpp_implementation",
]