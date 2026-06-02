"""
Agent 翻译管线模块。

模块：
    translator: AgentTranslationPipeline 整合类
    writer: CppFileWriter 文件生成器

导出符号：
    AgentTranslationPipeline: 翻译管线整合类
    translate_blueprint_to_cpp: 便捷翻译函数
    CppFileWriter: C++ 文件生成器类
    write_cpp_class_files: 便捷函数，将 CppClassIR 转换为 .h/.cpp 文件
"""
from uasset_read.agent.translator import (
    AgentTranslationPipeline,
    translate_blueprint_to_cpp,
)
from uasset_read.agent.writer import (
    CppFileWriter,
    write_cpp_class_files,
)

__all__ = [
    "AgentTranslationPipeline",
    "translate_blueprint_to_cpp",
    "CppFileWriter",
    "write_cpp_class_files",
]