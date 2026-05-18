"""
C++ 代码生成格式化子模块。

提供 C++ 类骨架 JSON IR 格式化功能。

导出符号：
    CppProperty: 单个 C++ UPROPERTY 声明数据模型
    CppHeaderMeta: 头文件元数据模型
    CppClassIR: 完整 C++ 类骨架 IR 数据模型
    format_cpp_class_json: JSON IR 格式化函数
"""
from uasset_read.cpp_gen.formatters.cpp_json_ir import (
    CppProperty,
    CppHeaderMeta,
    CppClassIR,
    format_cpp_class_json,
)

__all__ = [
    "CppProperty",
    "CppHeaderMeta",
    "CppClassIR",
    "format_cpp_class_json",
]