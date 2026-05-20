"""
Kismet Expression → C++ Function Body Builder.

Phase 63 Wave 4: Assembles a list of KismetExpression into a complete
C++ function body with proper indentation, semicolons, braces, and labels.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.kismet.expressions.base import KismetExpression
    from uasset_read.kismet.translator import TypeRegistry


# Statements that already end with ';' internally or shouldn't get one added.
_STATEMENT_TERMINATED = {
    "goto ", "if ", "return;", "}", "{", "switch ", "case ", "default:",
    "assert(", "/*",
}


def _needs_semicolon(line: str) -> bool:
    """Check if a C++ line needs a semicolon appended."""
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.endswith(";"):
        return False
    if stripped.endswith("{") or stripped.endswith("}"):
        return False
    for prefix in _STATEMENT_TERMINATED:
        if stripped.startswith(prefix):
            return False
    return True


class FunctionBodyBuilder:
    """
    Assembles KismetExpression list into a readable C++ function body.

    Usage:
        builder = FunctionBodyBuilder(type_registry)
        cpp = builder.to_function_body(expressions, func_name="MyFunction")
    """

    def __init__(self, type_registry: "TypeRegistry | None" = None) -> None:
        from uasset_read.kismet.translator import KismetTranslator, TypeRegistry
        self.type_registry = type_registry or TypeRegistry()
        self._translator = KismetTranslator(self.type_registry)

    def to_function_body(
        self,
        expressions: list["KismetExpression"],
        func_name: str | None = None,
    ) -> str:
        """
        Translate a list of KismetExpression into a C++ function body.

        Args:
            expressions: List of expressions from Phase 62 bytecode parsing.
            func_name: Optional function name for the output wrapper.

        Returns:
            Formatted C++ function body string.
        """
        # Build byte_offset → expression index map for label generation
        offset_to_index: dict[int, int] = {}
        for idx, expr in enumerate(expressions):
            byte_offset = getattr(expr, "byte_offset", None)
            if byte_offset is not None:
                offset_to_index[byte_offset] = idx
            # Also track CodeOffset attributes for jump targets
            if hasattr(expr, "CodeOffset"):
                offset_to_index[expr.CodeOffset] = idx

        # Collect pending labels (offsets that are jump targets)
        jump_targets: set[int] = set()
        for expr in expressions:
            if hasattr(expr, "CodeOffset"):
                jump_targets.add(expr.CodeOffset)

        # Translate each expression
        lines: list[str] = []
        label_set: set[int] = set()

        for idx, expr in enumerate(expressions):
            cpp_line = self._translator.line_cpp(expr)

            # Skip empty lines (EX_EndOfScript, EX_PushExecutionFlow, etc.)
            if not cpp_line or cpp_line.strip() == "":
                continue

            # Check if this index is a jump target — emit label
            for target in sorted(jump_targets):
                if offset_to_index.get(target) == idx and target not in label_set:
                    lines.append(f"Label_{target}:")
                    label_set.add(target)

            # Handle multi-line output (e.g., BreakVector)
            for sub_line in cpp_line.split("\n"):
                sub_line = sub_line.strip()
                if not sub_line:
                    continue
                if _needs_semicolon(sub_line):
                    sub_line += ";"
                lines.append(sub_line)

        # Wrap in function signature
        signature = func_name if func_name else "void UnknownFunction"
        if "(" not in signature:
            signature += "()"

        body = "\n".join(f"    {line}" for line in lines)
        return f"{signature} {{\n{body}\n}}"

    def to_function_body_structured(
        self,
        expressions: list["KismetExpression"],
        func_name: str | None = None,
    ) -> str:
        """
        Translate expressions using structured control flow reconstruction.

        Tries StructuredControlFlow first; falls back to goto-based output
        if no structured patterns are detected.

        Args:
            expressions: List of KismetExpression from Phase 62.
            func_name: Optional function name for the wrapper.

        Returns:
            Formatted C++ function body string.
        """
        from uasset_read.kismet.structured_flow import StructuredControlFlow

        flow = StructuredControlFlow()
        structured_lines = flow.reconstruct(expressions)

        if not structured_lines:
            # No patterns detected, use goto fallback
            return self.to_function_body(expressions, func_name)

        # Add semicolons and indentation to structured lines
        processed: list[str] = []
        for line in structured_lines:
            stripped = line.strip()
            if not stripped:
                continue
            if _needs_semicolon(stripped):
                stripped += ";"
            processed.append(stripped)

        signature = func_name if func_name else "void UnknownFunction"
        if "(" not in signature:
            signature += "()"

        body = "\n".join(f"    {line}" for line in processed)
        return f"{signature} {{\n{body}\n}}"
