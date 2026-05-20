"""
Agent 翻译管线模块。

Phase 66: 提供 Agent 可调用的翻译入口，整合 Phase 64-65 输出到 CppClassIR。

模块：
    translator: AgentTranslationPipeline 整合类

导出符号：
    AgentTranslationPipeline: 翻译管线整合类
    translate_blueprint_to_cpp: 便捷翻译函数
"""
from uasset_read.agent.translator import (
    AgentTranslationPipeline,
    translate_blueprint_to_cpp,
)

__all__ = [
    "AgentTranslationPipeline",
    "translate_blueprint_to_cpp",
]