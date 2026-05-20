"""
Agent 翻译管线模块。

Phase 66: Agent 翻译管线，将 Blueprint 解析结果转换为 C++ 代码。

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
    # Phase 66-01: 翻译管线
    "AgentTranslationPipeline",
    "translate_blueprint_to_cpp",
    # Phase 66-02: 文件输出
    "CppFileWriter",
    "write_cpp_class_files",
]