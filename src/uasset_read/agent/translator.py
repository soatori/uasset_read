"""
Agent 翻译管线整合模块 — AgentTranslationPipeline。

整合 cpp_gen + Kismet 反编译输出，提供 Agent 可调用的翻译入口。

Per D-66-01: 如果 blueprint 为 None，raise ValueError。
Per D-66-02: 如果 graphs 为空，从 blueprint_functions 回退。
Per D-66-03: CppMethodIR 添加 body_text 字段用于存储函数体文本。

导出：
    AgentTranslationPipeline: 翻译管线整合类
    translate_blueprint_to_cpp: 便捷翻译函数
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Dict, Any

if TYPE_CHECKING:
    from uasset_read.link.result import LinkerParseResult
    from uasset_read.kismet.result import KismetDecompiledResult
    from uasset_read.cpp_gen.formatters import CppClassIR, CppMethodIR

logger = logging.getLogger(__name__)


class AgentTranslationPipeline:
    """Agent 翻译管线整合类。

    连接 cpp_gen + Kismet 反编译输出，
    将 LinkerParseResult 转换为完整的 CppClassIR。

    Usage:
        result = parse_uasset_with_linker("file.uasset", tolerant=True)
        pipeline = AgentTranslationPipeline(result)
        ir = pipeline.translate()

    或使用便捷函数：
        ir = translate_blueprint_to_cpp(result)
    """

    def __init__(self, result: "LinkerParseResult"):
        """初始化翻译管线。

        Args:
            result: LinkerParseResult（来自 parse_uasset_with_linker）

        Raises:
            ValueError: 如果 result 为 None 或 result.blueprint 为 None 或不是蓝图（Per D-66-01）
        """
        # 输入验证（Per T-66-01）
        if result is None:
            raise ValueError(
                "LinkerParseResult is None — cannot translate to C++"
            )
        if not hasattr(result, 'blueprint'):
            raise ValueError(
                "Input is not a LinkerParseResult — missing blueprint attribute"
            )
        if result.blueprint is None:
            raise ValueError(
                "LinkerParseResult.blueprint is None — cannot translate to C++"
            )
        if not result.blueprint.is_blueprint:
            raise ValueError(
                "LinkerParseResult.blueprint.is_blueprint is False — not a blueprint, cannot translate"
            )

        self.result = result
        self._warnings: List[str] = []

    def translate(self) -> "CppClassIR":
        """执行翻译，返回 CppClassIR。

        流程：
        1. extract_cpp_class_skeleton() → 类骨架（properties + header_meta）
        2. extract_cpp_functions() → 方法签名（from graphs）
        3. _inject_kismet_functions() → 注入 Kismet 反编译函数体

        Returns:
            CppClassIR: 完整的 C++ 类中间表示
        """
        # Step 1: 提取类骨架
        from uasset_read.cpp_gen import extract_cpp_class_skeleton

        ir = extract_cpp_class_skeleton(self.result)

        # Step 2: 提取方法签名
        from uasset_read.cpp_gen.extract_cpp_skeleton import extract_cpp_functions

        # Per D-66-02: 如果 graphs 为空，尝试从 blueprint_functions 回退
        graphs = self.result.graphs or []
        blueprint_functions = getattr(self.result.blueprint, 'functions', None)

        methods = extract_cpp_functions(
            graphs=graphs,
            blueprint_functions=blueprint_functions,
            linker=self.result.linker
        )

        ir.methods = methods

        # Step 3: 注入 Kismet 反编译函数体
        self._inject_kismet_functions(ir)

        # 记录警告到 IR（Per T-66-03）
        if hasattr(ir, 'warnings'):
            ir.warnings = self._warnings
        else:
            # CppClassIR 没有 warnings 字段，但可以记录到 header_meta 的注释中
            pass

        return ir

    def _inject_kismet_functions(self, ir: "CppClassIR") -> None:
        """注入 Kismet 反编译函数体到 CppMethodIR。

        遍历 decompiled_functions，匹配到对应的 CppMethodIR，
        将 cpp_code 注入到 method.body_text 字段（Per D-66-03）。

        匹配逻辑：按 function_name 匹配 CppMethodIR.cpp_name
        Fallback：如果 decompiled_functions 为空，methods 保持原状（骨架模式）

        Args:
            ir: CppClassIR（methods 已填充）
        """
        decompiled = self.result.decompiled_functions or []

        if not decompiled:
            logger.debug("No decompiled_functions available — skeleton mode")
            self._warnings.append("No Kismet decompiled functions — methods have no body")
            return

        # 建立方法名索引
        method_index: Dict[str, "CppMethodIR"] = {}
        for method in ir.methods:
            method_index[method.cpp_name] = method

        # 匹配并注入
        matched_count = 0
        for decompiled_func in decompiled:
            method = self._match_decompiled_to_method(decompiled_func, method_index)
            if method:
                method.body_text = decompiled_func.cpp_code
                matched_count += 1
                logger.debug(
                    f"Injected body_text for method '{method.cpp_name}' "
                    f"from Kismet '{decompiled_func.function_name}'"
                )
            else:
                self._warnings.append(
                    f"Kismet decompiled '{decompiled_func.function_name}' "
                    f"not matched to any CppMethodIR"
                )
                logger.warning(
                    f"Kismet decompiled '{decompiled_func.function_name}' "
                    f"not found in method_index"
                )

        logger.info(
            f"Injected {matched_count}/{len(decompiled)} Kismet functions into CppMethodIR"
        )

    def _match_decompiled_to_method(
        self,
        decompiled: "KismetDecompiledResult",
        method_index: Dict[str, "CppMethodIR"]
    ) -> Optional["CppMethodIR"]:
        """匹配 KismetDecompiledResult 到 CppMethodIR。

        匹配逻辑：
        1. 精确匹配：function_name == cpp_name
        2. 清理后匹配：function_name 清理后 == cpp_name（处理大小写差异）
        3. 部分匹配：function_name 包含 cpp_name 或反之

        Args:
            decompiled: KismetDecompiledResult
            method_index: 方法名索引

        Returns:
            匹配的 CppMethodIR 或 None
        """
        func_name = decompiled.function_name

        # 精确匹配
        if func_name in method_index:
            return method_index[func_name]

        # 清理后匹配（处理大小写、下划线差异）
        from uasset_read.cpp_gen.extract_cpp_skeleton import _sanitize_identifier
        sanitized_name = _sanitize_identifier(func_name)
        if sanitized_name in method_index:
            return method_index[sanitized_name]

        # 部分匹配（function_name 可能包含前缀/后缀）
        for cpp_name, method in method_index.items():
            if func_name.lower() == cpp_name.lower():
                return method
            if cpp_name.lower() in func_name.lower() or func_name.lower() in cpp_name.lower():
                # 宽松匹配（可能需要进一步验证）
                logger.debug(
                    f"Loose match: '{func_name}' ≈ '{cpp_name}'"
                )
                return method

        return None


def translate_blueprint_to_cpp(
    result: "LinkerParseResult",
    output_dir: Optional[str] = None
) -> "CppClassIR":
    """便捷翻译函数。

    将 LinkerParseResult 翻译为 CppClassIR。

    Args:
        result: LinkerParseResult（来自 parse_uasset_with_linker）
        output_dir: 可选输出目录（未来用于写入 .h/.cpp 文件）

    Returns:
        CppClassIR: 完整的 C++ 类中间表示

    Raises:
        ValueError: 如果 result.blueprint 为 None 或不是蓝图

    Example:
        from uasset_read import parse_uasset_with_linker
        from uasset_read.agent import translate_blueprint_to_cpp

        result = parse_uasset_with_linker("BP.uasset", tolerant=True)
        ir = translate_blueprint_to_cpp(result)

        print(f"Class: {ir.name} extends {ir.parent_class}")
        print(f"Properties: {len(ir.properties)}")
        print(f"Methods: {len(ir.methods)}")
    """
    pipeline = AgentTranslationPipeline(result)
    return pipeline.translate()


__all__ = [
    "AgentTranslationPipeline",
    "translate_blueprint_to_cpp",
]