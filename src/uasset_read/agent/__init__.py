"""Agent 模块导出。

Phase 66: Agent 翻译管线，将 Blueprint 解析结果转换为 C++ 代码。

导出符号：
    CppFileWriter: C++ 文件生成器类
    write_cpp_class_files: 便捷函数，将 CppClassIR 转换为 .h/.cpp 文件
"""
# Note: agent/translator.py (Phase 66-01) will add:
# AgentTranslationPipeline, translate_blueprint_to_cpp

from uasset_read.agent.writer import (
    CppFileWriter,
    write_cpp_class_files,
)

__all__ = [
    # Phase 66-02: 文件输出
    "CppFileWriter",
    "write_cpp_class_files",
    # Phase 66-01: 翻译管线 (to be added)
    # "AgentTranslationPipeline",
    # "translate_blueprint_to_cpp",
]