"""C++ 文件输出模块 — CppClassIR → .h/.cpp 文件文本。

Phase 66-02: 将 CppClassIR 转换为符合 UE C++ 规范的类文件。

类结构：
    CppFileWriter: 文件生成器类
        - _generate_header_text(): 生成 .h 文件内容
        - _generate_cpp_text(): 生成 .cpp 文件内容
        - write_to_files(): 写入文件或返回文本字典

函数：
    write_cpp_class_files(): 便捷函数

文件结构（UE C++ 规范）：
    .h 文件：
        - #pragma once
        - #include "CoreMinimal.h" + parent class include
        - #include "ClassName.generated.h"
        - UCLASS() macro
        - class declaration (class X : public Y)
        - GENERATED_BODY()
        - public/protected/private sections
        - UPROPERTY declarations
        - UFUNCTION declarations + method signatures

    .cpp 文件：
        - #include "ClassName.h"
        - Constructor implementation（从 format_cpp_constructor）
        - Method implementations（从 methods with body）

决策记录：
    D-66-04: 如果 method.body 为空列表，在 .h 中声明，但不生成 .cpp 实现
    D-66-05: 构造函数文本使用 format_cpp_constructor(ir) 生成
    D-66-06: UPROPERTY 标记从 prop.uproperty_marks 提取
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.cpp_gen.formatters import CppClassIR, CppMethodIR, CppProperty

from uasset_read.cpp_gen import (
    format_cpp_header,
    format_cpp_constructor,
)
from uasset_read.cpp_gen.formatters import (
    CppCallStmt,
    CppStatement,
)

logger = logging.getLogger(__name__)

# ============================================================================
# 常量
# ============================================================================

_INDENT = "    "  # 4 空格缩进


# ============================================================================
# CppFileWriter 类
# ============================================================================


class CppFileWriter:
    """C++ 文件生成器，将 CppClassIR 转换为 .h/.cpp 文件文本。

    使用现有的 format_cpp_header 生成 .h 文件，
    组合 format_cpp_constructor + 方法实现生成 .cpp 文件。

    Attributes:
        ir: CppClassIR 数据模型
        _header_text: 缓存的 .h 文件文本
        _cpp_text: 缓存的 .cpp 文件文本
    """

    def __init__(self, ir: "CppClassIR"):
        """初始化文件生成器。

        Args:
            ir: CppClassIR 数据模型（已填充 properties, methods, constructor）
        """
        self.ir = ir
        self._header_text: Optional[str] = None
        self._cpp_text: Optional[str] = None

    def _generate_header_text(self) -> str:
        """生成 .h 头文件文本。

        使用现有的 format_cpp_header 函数，生成符合 UE 规范的 .h 文件。

        Returns:
            .h 文件完整文本
        """
        if self._header_text is None:
            self._header_text = format_cpp_header(self.ir)
        return self._header_text

    def _generate_cpp_text(self) -> str:
        """生成 .cpp 实现文件文本。

        组合：
        1. #include "ClassName.h"
        2. 构造函数实现（format_cpp_constructor）
        3. 方法实现（methods with non-empty body）

        Per D-66-04: 方法 body 为空列表时跳过 .cpp 实现。

        Returns:
            .cpp 文件完整文本
        """
        if self._cpp_text is None:
            self._cpp_text = self._build_cpp_file()
        return self._cpp_text

    def _build_cpp_file(self) -> str:
        """构建 .cpp 文件内容。

        Returns:
            .cpp 文件文本
        """
        lines: List[str] = []

        # 1. 文件头注释
        lines.append(f"// {self.ir.name}.cpp")

        # 2. #include "ClassName.h"
        lines.append(f'#include "{self.ir.name}.h"')

        # 3. 空行
        lines.append("")

        # 4. 构造函数实现
        constructor_text = format_cpp_constructor(self.ir)
        lines.append(constructor_text)

        # 5. 方法实现（仅处理有 body 的方法）
        methods_with_body = [m for m in self.ir.methods if self._has_body(m)]

        for method in methods_with_body:
            # 方法之间空 2 行
            lines.append("")
            lines.append("")
            lines.append(self._format_method_definition(method))

        # 6. 尾随换行
        lines.append("")

        return "\n".join(lines)

    def _has_body(self, method: "CppMethodIR") -> bool:
        """检查方法是否有实现体。

        Per D-66-04: body 为空列表或 None 时返回 False。

        Args:
            method: CppMethodIR

        Returns:
            True 如果有非空 body
        """
        if method.body is None:
            return False
        if isinstance(method.body, list) and len(method.body) == 0:
            return False
        if isinstance(method.body, str) and not method.body.strip():
            return False
        return True

    def _format_method_definition(self, method: "CppMethodIR") -> str:
        """格式化方法实现。

        Args:
            method: CppMethodIR（含 body）

        Returns:
            方法实现的 .cpp 文本
        """
        lines: List[str] = []

        # 函数签名：ReturnType ClassName::MethodName(Params)
        param_str = ", ".join(f"{p.cpp_type} {p.name}" for p in method.parameters)

        # 添加修饰符
        modifiers = []
        if method.is_const:
            modifiers.append("const")
        if method.is_override:
            modifiers.append("override")

        sig = f"{method.return_type} {self.ir.name}::{method.cpp_name}({param_str})"
        if modifiers:
            sig += " " + " ".join(modifiers)

        lines.append(sig)
        lines.append("{")

        # 渲染 body
        if method.body:
            body_lines = self._render_body(method.body)
            lines.extend(body_lines)

        lines.append("}")

        return "\n".join(lines)

    def _render_body(self, body: List[CppStatement] | str) -> List[str]:
        """渲染方法体。

        支持两种 body 类型：
        1. List[CppStatement] — Phase 58 IR 格式
        2. str — Kismet 反编译的文本格式（Phase 66-01）

        Args:
            body: 方法体（IR 或字符串）

        Returns:
            方法体代码行列表
        """
        lines: List[str] = []

        if isinstance(body, str):
            # Kismet 反编译文本 — 直接使用，按行添加缩进
            for line in body.strip().split("\n"):
                lines.append(f"{_INDENT}{line}")
        elif isinstance(body, list):
            # Phase 58 IR 格式 — 渲染语句
            for stmt in body:
                rendered = self._render_statement(stmt)
                if rendered:
                    lines.append(rendered)

        return lines

    def _render_statement(self, stmt: CppStatement) -> str:
        """渲染单个语句。

        Args:
            stmt: CppStatement

        Returns:
            渲染后的代码行（带缩进）
        """
        if isinstance(stmt, CppCallStmt):
            args_str = ", ".join(stmt.args)
            if stmt.target == "Super":
                return f"{_INDENT}Super::{stmt.method_name}({args_str});"
            elif stmt.target == "this":
                return f"{_INDENT}{stmt.method_name}({args_str});"
            else:
                return f"{_INDENT}{stmt.target}->{stmt.method_name}({args_str});"
        else:
            # 其他类型暂时跳过
            return ""

    def _format_property_declaration(self, prop: "CppProperty") -> List[str]:
        """格式化属性声明（供参考，实际由 format_cpp_header 处理）。

        Args:
            prop: CppProperty

        Returns:
            属性声明行列表
        """
        # 此方法已由 format_cpp_header 内部处理
        # 保留为公开 API 以供参考
        lines: List[str] = []
        marks_str = ", ".join(prop.uproperty_marks)
        lines.append(f"    UPROPERTY({marks_str}, Category = \"{prop.category}\")")
        decl = f"    {prop.cpp_type} {prop.name}"
        if prop.default_value is not None:
            decl += f" = {prop.default_value}"
        decl += ";"
        lines.append(decl)
        return lines

    def _format_method_declaration(self, method: "CppMethodIR") -> List[str]:
        """格式化方法声明（供参考，实际由 format_cpp_header 处理）。

        Args:
            method: CppMethodIR

        Returns:
            方法声明行列表
        """
        # 此方法已由 format_cpp_header 内部处理
        # 保留为公开 API 以供参考
        lines: List[str] = []
        if method.ufunction_specifiers:
            spec_str = ", ".join(method.ufunction_specifiers)
            lines.append(f"    UFUNCTION({spec_str})")
        param_str = ", ".join(f"{p.cpp_type} {p.name}" for p in method.parameters)
        decl = f"    {method.return_type} {method.cpp_name}({param_str})"
        if method.is_const:
            decl += " const"
        if method.is_override:
            decl += " override"
        decl += ";"
        lines.append(decl)
        return lines

    def write_to_files(
        self, output_dir: Optional[str] = None
    ) -> Dict[str, str]:
        """写入文件或返回文本字典。

        Args:
            output_dir: 输出目录路径。如果为 None，返回文本字典而不写入文件。

        Returns:
            包含 ".h" 和 ".cpp" 键的字典，值为文件内容字符串

        Raises:
            OSError: 如果目录不存在或写入失败
        """
        header_text = self._generate_header_text()
        cpp_text = self._generate_cpp_text()

        result = {
            ".h": header_text,
            ".cpp": cpp_text,
        }

        if output_dir is not None:
            # 写入文件
            h_path = os.path.join(output_dir, f"{self.ir.name}.h")
            cpp_path = os.path.join(output_dir, f"{self.ir.name}.cpp")

            os.makedirs(output_dir, exist_ok=True)

            with open(h_path, "w", encoding="utf-8") as f:
                f.write(header_text)

            with open(cpp_path, "w", encoding="utf-8") as f:
                f.write(cpp_text)

            logger.info(f"Written: {h_path}, {cpp_path}")

        return result


# ============================================================================
# 便捷函数
# ============================================================================


def write_cpp_class_files(
    ir: "CppClassIR",
    output_dir: Optional[str] = None
) -> Dict[str, str]:
    """便捷函数：将 CppClassIR 转换为 .h/.cpp 文件。

    Args:
        ir: CppClassIR 数据模型
        output_dir: 输出目录路径。如果为 None，返回文本字典而不写入文件。

    Returns:
        包含 ".h" 和 ".cpp" 键的字典，值为文件内容字符串

    Example:
        >>> from uasset_read.agent import write_cpp_class_files
        >>> result = write_cpp_class_files(ir, None)
        >>> print(result[".h"])
        >>> print(result[".cpp"])
    """
    writer = CppFileWriter(ir)
    return writer.write_to_files(output_dir)


# ============================================================================
# 导出列表
# ============================================================================

__all__ = [
    "CppFileWriter",
    "write_cpp_class_files",
]