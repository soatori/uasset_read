"""C++ 函数体格式化模块 — CppStatement 树 → .cpp 文本。

将函数体 IR 渲染为可读的 UE .cpp 实现文件。
"""
from __future__ import annotations

import re
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

    优先使用结构化 body（CppStatement 列表），回退到 body_text（原始文本）。

    Args:
        method_ir: 方法 IR（含 body 或 body_text 字段）

    Returns:
        .cpp 函数实现文本
    """
    lines: List[str] = []

    # 函数签名行 — .cpp 实现必须使用 ClassName::MethodName 格式
    param_str = ", ".join(f"{p.cpp_type} {p.name}" for p in method_ir.parameters)
    if method_ir.class_name:
        sig = f"{method_ir.return_type} {method_ir.class_name}::{method_ir.cpp_name}({param_str})"
    else:
        sig = f"{method_ir.return_type} {method_ir.cpp_name}({param_str})"

    lines.append(sig)
    lines.append("{")

    # 优先渲染结构化 body 语句
    if method_ir.body:
        body_lines = _render_statements(method_ir.body, indent=1)
        lines.extend(body_lines)
    elif method_ir.body_text:
        # 回退：直接使用 Kismet 反编译的原始文本
        # 先检测并剥离多余的函数签名包裹，避免嵌套
        stripped = _strip_function_wrapper(method_ir.body_text)
        for raw_line in stripped.split("\n"):
            raw_line = raw_line.strip()
            if raw_line:
                lines.append(f"    {raw_line}")

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

    # 方法实现（优先结构化 body，回退到 body_text）
    methods_with_body = [m for m in ir.methods if m.body or m.body_text]

    for i, method in enumerate(methods_with_body):
        # 确保方法设置了 class_name，用于 ClassName::Method 前缀
        if not method.class_name:
            method.class_name = ir.name
        if i > 0:
            lines.append("")  # 方法之间空 2 行
            lines.append("")
        lines.append(format_cpp_function_body(method))

    # 尾随换行
    lines.append("")

    return "\n".join(lines)


# ============================================================================
# body_text 包裹剥离
# ============================================================================

# 函数签名正则：匹配 ReturnType FuncName(...) 形式的行
# 例如：void UMyClass::ExecuteUbergraph(int32 EntryPoint)
# 策略：首行以标识符开头、含 '('、且 '(' 前最后一词不是控制流关键字

# 匹配 C++ 标识符（含 ::、*、& 等修饰符）直到 '('
_FUNC_SIG_RE = re.compile(
    r'^[A-Za-z_]\w*'            # 返回类型（至少一个标识符）
    r'[\s\w:*&]*'               # 后续修饰符（类型指针、const、命名空间等）
    r'\('                       # 左括号
)

# 控制流关键字集合，用于排除误判
_CONTROL_KEYWORDS = frozenset({
    'if', 'else', 'for', 'while', 'switch', 'do', 'try', 'catch',
})


def _strip_function_wrapper(text: str) -> str:
    """检测并剥离 body_text 外层的函数签名 + 花括号包裹。

    有些 Kismet 反编译器输出的 body_text 已包含完整函数定义：
    ```
    void UMyClass::ExecuteUbergraph(int32 EntryPoint)
    {
        // 实际语句
    }
    ```
    这种情况如果不处理，format_cpp_function_body() 会再次包裹签名和花括号，
    导致嵌套。本函数检测这种情况并剥离外层，返回纯函数体内容。

    剥离逻辑：
    1. 首行匹配函数签名正则
    2. 第二行（忽略空行）为 '{'
    3. 最后一个非空行为 '}'
    4. 满足以上条件时，提取中间内容并去掉一层缩进

    Args:
        text: body_text 原始文本

    Returns:
        剥离后的纯函数体文本；如果不是包裹格式则原样返回
    """
    if not text or not text.strip():
        return text

    lines = text.split("\n")

    # 过滤出非空行索引，用于定位首行、花括号位置
    non_empty = [(i, line.strip()) for i, line in enumerate(lines) if line.strip()]

    if len(non_empty) < 3:
        # 不足 3 行非空行（签名、{、}），不可能是包裹格式
        return text

    first_idx, first_text = non_empty[0]
    last_idx, last_text = non_empty[-1]

    # 条件 1：首行是函数签名（含 '(' 且匹配正则）
    if '(' not in first_text or not _FUNC_SIG_RE.match(first_text):
        return text

    # 条件 2：'{ 位置' — 支持两种格式：
    #   格式 A: 签名独占一行，第二非空行为 '{'
    #   格式 B: 签名行以 '{' 结尾（如 "void Func() {"）
    brace_on_first_line = first_text.endswith('{')
    if not brace_on_first_line:
        if len(non_empty) < 3:
            return text
        second_idx, second_text = non_empty[1]
        if second_text != '{':
            return text
        body_start = second_idx + 1
    else:
        if len(non_empty) < 2:
            return text
        body_start = first_idx + 1

    # 条件 3：最后非空行是 '}'
    if last_text != '}':
        return text

    # 条件 4：排除控制流语句（if/for/while 等）
    before_paren = first_text[:first_text.index('(')].split()[-1].lower() if '(' in first_text else ''
    if before_paren in _CONTROL_KEYWORDS:
        return text

    # 满足所有条件，剥离外层
    body_end = last_idx
    body_lines = lines[body_start:body_end]

    # 去掉一层缩进（如果存在的话）
    dedented = []
    for line in body_lines:
        if line.startswith("    "):
            dedented.append(line[4:])
        elif line.startswith("\t"):
            dedented.append(line[1:])
        else:
            dedented.append(line)

    return "\n".join(dedented)


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
