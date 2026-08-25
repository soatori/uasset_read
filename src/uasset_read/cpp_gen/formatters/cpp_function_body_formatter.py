"""C++ function body formatting module — CppStatement tree -> .cpp text.

Renders function body IR into readable UE .cpp implementation files.
"""

import re
from typing import List

from uasset_read.cpp_gen.formatters import (
    CppAssignmentStmt,
    CppCallStmt,
    CppIfStmt,
    CppInlineExprStmt,
    CppMethodIR,
    CppStatement,
)


# ============================================================================
# Core formatting functions
# ============================================================================


def format_cpp_function_body(method_ir: CppMethodIR) -> str:
    """Render a single CppMethodIR into .cpp function implementation text.

    Output format:
    ```
    ReturnType ClassName::MethodName(Params)
    {
        // body statements
    }
    ```

    Prefers structured body (CppStatement list), falls back to body_text (raw text).

    Args:
        method_ir: Method IR (with body or body_text field)

    Returns:
        .cpp function implementation text
    """
    lines: List[str] = []

    # Function signature line — .cpp implementation must use ClassName::MethodName format
    param_str = ", ".join(f"{p.cpp_type} {p.name}" for p in method_ir.parameters)
    if method_ir.class_name:
        sig = f"{method_ir.return_type} {method_ir.class_name}::{method_ir.cpp_name}({param_str})"
    else:
        sig = f"{method_ir.return_type} {method_ir.cpp_name}({param_str})"

    lines.append(sig)
    lines.append("{")

    # Prefer rendering structured body statements
    if method_ir.body:
        body_lines = _render_statements(method_ir.body, indent=1)
        lines.extend(body_lines)
    elif method_ir.body_text:
        # Fallback: use Kismet decompiled raw text directly
        # First detect and strip extra function signature wrapper to avoid nesting
        stripped = _strip_function_wrapper(method_ir.body_text)
        for raw_line in stripped.split("\n"):
            raw_line = raw_line.strip()
            if raw_line:
                lines.append(f"    {raw_line}")

    lines.append("}")

    return "\n".join(lines)


# ============================================================================
# body_text wrapper stripping
# ============================================================================

# Function signature regex: matches lines in the form ReturnType FuncName(...)
# Example: void UMyClass::ExecuteUbergraph(int32 EntryPoint)
# Strategy: first line starts with identifier, contains '(', and the last word
# before '(' is not a control flow keyword

# Match C++ identifiers (with ::, *, & etc. modifiers) up to '('
_FUNC_SIG_RE = re.compile(
    r"^[A-Za-z_]\w*"  # return type (at least one identifier)
    r"[\s\w:*&]*"  # subsequent modifiers (type pointers, const, namespace, etc.)
    r"\("  # opening parenthesis
)

# Control flow keyword set, used to exclude false positives
_CONTROL_KEYWORDS = frozenset(
    {
        "if",
        "else",
        "for",
        "while",
        "switch",
        "do",
        "try",
        "catch",
    }
)


def _strip_function_wrapper(text: str) -> str:
    """Detect and strip function signature + brace wrapper from body_text.

    Some Kismet decompilers output body_text that already contains the full function definition:
    ```
    void UMyClass::ExecuteUbergraph(int32 EntryPoint)
    {
        // actual statements
    }
    ```
    If not handled, format_cpp_function_body() would wrap the signature and braces again,
    causing nesting. This function detects this case and strips the outer layer,
    returning pure function body content.

    Stripping logic:
    1. First line matches function signature regex
    2. Second line (skipping blank lines) is '{'
    3. Last non-empty line is '}'
    4. When all conditions are met, extract middle content and remove one level of indentation

    Args:
        text: body_text raw text

    Returns:
        Stripped pure function body text; returned as-is if not in wrapper format
    """
    if not text or not text.strip():
        return text

    lines = text.split("\n")

    # Filter non-empty line indices to locate first line and brace positions
    non_empty = [(i, line.strip()) for i, line in enumerate(lines) if line.strip()]

    if len(non_empty) < 3:
        # Less than 3 non-empty lines (signature, {, }), cannot be wrapper format
        return text

    first_idx, first_text = non_empty[0]
    last_idx, last_text = non_empty[-1]

    # Condition 1: first line is function signature (contains '(' and matches regex)
    if "(" not in first_text or not _FUNC_SIG_RE.match(first_text):
        return text

    # Condition 2: '{ position' — supports two formats:
    #   Format A: signature on its own line, second non-empty line is '{'
    #   Format B: signature line ends with '{' (e.g., "void Func() {")
    brace_on_first_line = first_text.endswith("{")
    if not brace_on_first_line:
        if len(non_empty) < 3:
            return text
        second_idx, second_text = non_empty[1]
        if second_text != "{":
            return text
        body_start = second_idx + 1
    else:
        if len(non_empty) < 2:
            return text
        body_start = first_idx + 1

    # Condition 3: last non-empty line is '}'
    if last_text != "}":
        return text

    # Condition 4: exclude control flow statements (if/for/while etc.)
    before_paren = first_text[: first_text.index("(")].split()[-1].lower() if "(" in first_text else ""
    if before_paren in _CONTROL_KEYWORDS:
        return text

    # All conditions met, strip outer layer
    body_end = last_idx
    body_lines = lines[body_start:body_end]

    # Remove one level of indentation (if present)
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
# Statement rendering helpers
# ============================================================================

_INDENT = "    "  # 4 spaces


def _render_statements(statements: List[CppStatement], indent: int = 1) -> List[str]:
    """Recursively render CppStatement list into .cpp lines."""
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
            # InlineExprStmt does not stand alone as a line, skip
            pass
        else:
            pass  # unknown type, skip

    return lines


def _render_call_stmt(stmt: CppCallStmt, prefix: str) -> str:
    """Render CppCallStmt into a .cpp line."""
    args_str = ", ".join(stmt.args)

    if stmt.target == "Super":
        return f"{prefix}Super::{stmt.method_name}({args_str});"
    elif stmt.target == "this":
        return f"{prefix}{stmt.method_name}({args_str});"
    else:
        return f"{prefix}{stmt.target}->{stmt.method_name}({args_str});"


def _render_assignment_stmt(stmt: CppAssignmentStmt, prefix: str) -> str:
    """Render CppAssignmentStmt into a .cpp line."""
    return f"{prefix}{stmt.lhs} = {stmt.rhs};"


def _render_if_stmt(stmt: CppIfStmt, indent: int) -> List[str]:
    """Recursively render CppIfStmt into .cpp line list."""
    lines: List[str] = []
    prefix = _INDENT * indent
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
# Export list
# ============================================================================

__all__ = [
    "format_cpp_function_body",
    "format_full_cpp_implementation",
]
