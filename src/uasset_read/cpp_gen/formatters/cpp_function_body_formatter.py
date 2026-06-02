"""C++ 函数体格式化模块 — CppStatement 树 → .cpp 文本。

将函数体 IR 渲染为可读的 UE .cpp 实现文件。
"""
from __future__ import annotations

from typing import List

from uasset_read.cpp_gen.formatters import (
    CppAssignmentStmt,
    CppCallStmt,
    CppClassIR,
    CppIfStmt,
    CppInlineExprStmt,
    CppMethodIR,
    CppStatement,
)


# ============================================================================
# 核心格式化函数
# ============================================================================

def format_cpp_function_body(method_ir: CppMethodIR) -> str:
    """将单个 CppMethodIR 渲染为 .cpp 函数实现文本。

    输出格式：
    ```
    ReturnType ClassName::MethodName(Params)
    {
        // body statements
    }
    ```

    Args:
        method_ir: 方法 IR（含 body 字段）

    Returns:
        .cpp 函数实现文本
    """
    lines: List[str] = []

    # 函数签名行
    param_str = ", ".join(f"{p.cpp_type} {p.name}" for p in method_ir.parameters)
    sig = f"{method_ir.return_type} {method_ir.cpp_name}({param_str})"

    lines.append(sig)
    lines.append("{")

    # 渲染 body 语句
    if method_ir.body:
        body_lines = _render_statements(method_ir.body, indent=1)
        lines.extend(body_lines)

    lines.append("}")

    return "\n".join(lines)


def format_full_cpp_implementation(ir: CppClassIR) -> str:
    """将完整 CppClassIR 渲染为 .cpp 实现文件文本。

    输出结构：
    1. // ClassName.cpp 注释
    2. #include "ClassName.h"
    3. 空行
    4. 每个 method 的函数实现（方法之间空 2 行）
    5. 尾随换行

    Args:
        ir: CppClassIR 数据模型

    Returns:
        完整 .cpp 文件文本
    """
    lines: List[str] = []

    # 文件头注释
    lines.append(f"// {ir.name}.cpp")

    # include
    lines.append(f'#include "{ir.name}.h"')

    # 空行
    lines.append("")

    # 方法实现
    methods_with_body = [m for m in ir.methods if m.body]

    for i, method in enumerate(methods_with_body):
        if i > 0:
            lines.append("")  # 方法之间空 2 行
            lines.append("")
        lines.append(format_cpp_function_body(method))

    # 尾随换行
    lines.append("")

    return "\n".join(lines)


# ============================================================================
# 语句渲染辅助函数
# ============================================================================

_INDENT = "    "  # 4 空格


def _render_statements(statements: List[CppStatement], indent: int = 1) -> List[str]:
    """递归渲染 CppStatement 列表为 .cpp 行。"""
    lines: List[str] = []
    prefix = _INDENT * indent

    for stmt in statements:
        if isinstance(stmt, CppCallStmt):
            lines.append(_render_call_stmt(stmt, prefix))
        elif isinstance(stmt, CppAssignmentStmt):
            lines.append(_render_assignment_stmt(stmt, prefix))
        elif isinstance(stmt, CppIfStmt):
            lines.extend(_render_if_stmt(stmt, indent))
        elif isinstance(stmt, CppInlineExprStmt):
            # InlineExprStmt 不独立成行，跳过
            pass
        else:
            pass  # 未知类型跳过

    return lines


def _render_call_stmt(stmt: CppCallStmt, prefix: str) -> str:
    """渲染 CppCallStmt 为 .cpp 行。"""
    args_str = ", ".join(stmt.args)

    if stmt.target == "Super":
        return f"{prefix}Super::{stmt.method_name}({args_str});"
    elif stmt.target == "this":
        return f"{prefix}{stmt.method_name}({args_str});"
    else:
        return f"{prefix}{stmt.target}->{stmt.method_name}({args_str});"


def _render_assignment_stmt(stmt: CppAssignmentStmt, prefix: str) -> str:
    """渲染 CppAssignmentStmt 为 .cpp 行。"""
    return f"{prefix}{stmt.lhs} = {stmt.rhs};"


def _render_if_stmt(stmt: CppIfStmt, indent: int) -> List[str]:
    """递归渲染 CppIfStmt 为 .cpp 行列表。"""
    lines: List[str] = []
    prefix = _INDENT * indent
    inner_prefix = _INDENT * (indent + 1)

    # if (condition) {
    lines.append(f"{prefix}if ({stmt.condition}) {{")

    # then_body
    if stmt.then_body:
        then_lines = _render_statements(stmt.then_body, indent + 1)
        lines.extend(then_lines)

    # }
    if stmt.else_body:
        lines.append(f"{prefix}}} else {{")
        else_lines = _render_statements(stmt.else_body, indent + 1)
        lines.extend(else_lines)
        lines.append(f"{prefix}}}")
    else:
        lines.append(f"{prefix}}}")

    return lines


# ============================================================================
# 导出列表
# ============================================================================

__all__ = [
    "format_cpp_function_body",
    "format_full_cpp_implementation",
]
