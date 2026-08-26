"""
C++ header file formatting module — CppClassIR -> UE standard .h text.

Per D-05: Complete UE header file template from JSON IR.
Per T-056-05: Escape comments in string values.
Per T-056-06: Validate class name matches UE naming convention.

Exports:
    format_cpp_header: CppClassIR -> .h text conversion function
"""

from __future__ import annotations

import logging
import re
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.cpp_gen.formatters import CppCallStatement

from uasset_read.cpp_gen.formatters import CppClassIR, CppProperty, CppMethodIR, CppCallStatement
from uasset_read.cpp_gen.sanitizer import (
    sanitize_identifier,
    sanitize_category,
    sanitize_uproperty_marks,
    sanitize_string_literal,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Security-related constants (T-056-05, T-056-06)
# ============================================================================

# Allowed UE class name pattern: alphanumeric and underscore, starting with letter or underscore
UE_CLASS_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# ============================================================================
# Core formatting functions
# ============================================================================


def format_cpp_header(ir: CppClassIR) -> str:
    """Convert CppClassIR to standard UE .h header file text.

    Per D-05: Output format includes:
    1. #pragma once (if header_meta.pragma_once)
    2. #include "CoreMinimal.h" (always added)
    3. #include lines from header_meta.includes (sorted)
    4. #include from header_meta.generated_include (always last)
    5. UCLASS() macro
    6. class declaration and inheritance
    7. GENERATED_BODY()
    8. public: constructor declaration
    9. protected: property declarations

    Args:
        ir: CppClassIR data model

    Returns:
        Standard UE .h header file text
    """
    # T-056-06: validate and sanitize class name
    class_name = _sanitize_class_name(ir.name)
    parent_class = _sanitize_class_name(ir.parent_class)

    # Build output lines
    lines: List[str] = []

    # 1. #pragma once
    if ir.header_meta.pragma_once:
        lines.append("#pragma once")

    # 2. blank line
    lines.append("")

    # 3. #include "CoreMinimal.h" (UE convention, always added)
    lines.append('#include "CoreMinimal.h"')

    # 4. header_meta.includes (deduplicated + sorted)
    includes = sorted(set(ir.header_meta.includes))
    for inc in includes:
        lines.append(f"#include {inc}")

    # 5. generated_include (always the last include)
    if ir.header_meta.generated_include:
        generated_inc = _sanitize_generated_include(class_name)
        lines.append(f"#include {generated_inc}")

    # 6. blank line
    lines.append("")

    # 7. UCLASS macro (Blueprint-generated classes default to Blueprintable)
    lines.append("UCLASS(Blueprintable)")

    # 8. class declaration
    lines.append(f"class {class_name} : public {parent_class}")
    lines.append("{")
    lines.append("    GENERATED_BODY()")

    # 9. blank line
    lines.append("")

    # 10. public: constructor declaration
    lines.append("public:")
    lines.append(f"    {class_name}();")

    # 11. blank line
    lines.append("")

    # 12. protected: property declarations
    lines.append("protected:")

    # Separate component and variable properties (components first)
    components = [p for p in ir.properties if p.category == "component"]
    variables = [p for p in ir.properties if p.category != "component"]

    # Component declarations
    if components:
        lines.append("    // Components")
        for prop in components:
            lines.extend(_format_component_property(prop))

    # Variable declarations
    if variables:
        if components:
            lines.append("")  # blank line between components and variables
        for prop in variables:
            lines.extend(_format_variable_property(prop))

    # 13. Method declarations
    if ir.methods:
        lines.append("")
        lines.append("public:")
        lines.append("    // Blueprint Functions")
        for i, method in enumerate(ir.methods):
            if i > 0:
                lines.append("")
            lines.extend(_format_method_declaration(method))

    # 14. class end
    lines.append("};")

    # 14. trailing newline
    lines.append("")

    return "\n".join(lines)


# ============================================================================
# Helper functions
# ============================================================================


def _sanitize_class_name(name: str) -> str:
    """Sanitize class name to match UE naming convention (T-056-06).

    Only allows alphanumeric characters and underscore, starting with letter or underscore.
    Invalid characters are replaced with underscore.

    Args:
        name: Raw class name

    Returns:
        Sanitized class name
    """
    if not name:
        return "UUnknownClass"

    # Remove invalid characters, replace with underscore
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", name)

    # Ensure starts with letter or underscore
    if sanitized and sanitized[0].isdigit():
        sanitized = f"_{sanitized}"

    if not UE_CLASS_NAME_PATTERN.match(sanitized):
        logger.warning(f"Class name '{name}' could not be sanitized, using default")
        return "UUnknownClass"

    return sanitized


def _sanitize_generated_include(class_name: str) -> str:
    """Sanitize the generated.h include path.

    Args:
        include: Raw include path
        class_name: Sanitized class name

    Returns:
        Sanitized include path (using sanitized class name)
    """
    # Rebuild generated_include using sanitized class name
    # Format: "{ClassName}.generated.h"
    return f'"{class_name}.generated.h"'


def _sanitize_comment(comment: str) -> str:
    """Sanitize comment string to prevent injection (T-056-05).

    Removes sequences that would cause premature block comment closure (*/), preventing C++ injection.

    Args:
        comment: Raw comment text

    Returns:
        Sanitized comment text
    """
    if not comment:
        return ""

    # Remove sequences that could cause premature block comment closure
    sanitized = comment.replace("*/", "* /")

    # Remove other characters that could cause issues
    sanitized = sanitized.replace("\n", " ")
    sanitized = sanitized.replace("\r", "")

    return sanitized


def _format_component_property(prop: CppProperty) -> List[str]:
    """Format component property declaration.

    Per D-04: Components use UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Instanced)
    with Category = "Components" and AllowPrivateAccess.

    Args:
        prop: CppProperty (category="component")

    Returns:
        List of formatted lines
    """
    lines: List[str] = []

    # Build full UPROPERTY arguments
    marks = sanitize_uproperty_marks(prop.uproperty_marks)
    uproperty_args = ", ".join(marks)
    uproperty_args += ', Category = "Components"'
    uproperty_args += ', meta = (AllowPrivateAccess = "true")'

    lines.append(f"    UPROPERTY({uproperty_args})")

    # Property declaration
    safe_name = sanitize_identifier(prop.name)
    decl = f"    {prop.cpp_type} {safe_name};"

    # Add comment (if present)
    if prop.cpp_comment:
        sanitized_comment = _sanitize_comment(prop.cpp_comment)
        decl += f" // {sanitized_comment}"

    lines.append(decl)

    return lines


def _format_variable_property(prop: CppProperty) -> List[str]:
    """Format variable property declaration.

    Per D-04: Variables use UPROPERTY marks list, add Category.
    Default value formatted according to type.

    Args:
        prop: CppProperty (category != "component")

    Returns:
        List of formatted lines
    """
    lines: List[str] = []

    # Build full UPROPERTY arguments
    marks = sanitize_uproperty_marks(prop.uproperty_marks)
    uproperty_args = ", ".join(marks)

    # Add Category (if present)
    if prop.category:
        safe_category = sanitize_category(prop.category)
        uproperty_args += f', Category = "{safe_category}"'

    lines.append(f"    UPROPERTY({uproperty_args})")

    # Property declaration
    safe_name = sanitize_identifier(prop.name)
    decl = f"    {prop.cpp_type} {safe_name}"

    # Add default value (if present and non-empty)
    if prop.default_value is not None:
        default_str = _format_default_value(prop.cpp_type, prop.default_value)
        if default_str:
            decl += f" = {default_str}"

    decl += ";"

    # Add comment (if present)
    if prop.cpp_comment:
        sanitized_comment = _sanitize_comment(prop.cpp_comment)
        decl += f" // {sanitized_comment}"

    lines.append(decl)

    return lines


def _format_default_value(cpp_type: str, value: any) -> str:
    """Format default value string.

    Args:
        cpp_type: C++ type name
        value: Default value

    Returns:
        Formatted default value string
    """
    if value is None:
        return ""

    # Empty string or pure whitespace — no valid default value
    if isinstance(value, str) and not value.strip():
        return ""

    # Handle boolean values
    if cpp_type == "bool":
        return "true" if value else "false"

    # Handle floating-point types
    if cpp_type == "float":
        return f"{float(value)}f"
    if cpp_type == "double":
        return str(float(value))

    # Handle integer types (no suffix)
    if cpp_type in ("int", "int32", "int64", "uint8", "uint16", "uint32", "uint64", "byte"):
        return str(int(value))

    # Handle string types (TEXT wrapper, escape quotes and backslashes)
    if cpp_type in ("FString", "FName"):
        escaped = sanitize_string_literal(str(value))
        return f'TEXT("{escaped}")'

    # FText too complex, skip (currently not supported)
    if cpp_type == "FText":
        return "FText::GetEmpty()"

    # Other types, return directly
    return str(value)


def _format_method_declaration(method: CppMethodIR) -> List[str]:
    """Render CppMethodIR into .h declaration line list.

    Supports is_static, is_virtual, is_pure and other new fields.

    Examples:
        Move -> ["    UFUNCTION(BlueprintCallable)", "    void Move(double LeftRight, double ForwardBackward);"]
        PrimaryThumbstick -> ["    void PrimaryThumbstick(double Axis_X, double Axis_Y) override;"]
        Aim -> ["    UFUNCTION(BlueprintPure)", "    static float GetAimAngle();"]
    """
    lines: List[str] = []

    # UFUNCTION macro
    if method.ufunction_specifiers:
        spec_str = ", ".join(method.ufunction_specifiers)
        lines.append(f"    UFUNCTION({spec_str})")

    # Parameter list
    param_str = ", ".join(f"{p.cpp_type} {p.name}" for p in method.parameters)

    # Modifiers
    modifiers = []
    if method.is_static:
        modifiers.append("static")
    if method.is_virtual and not method.is_override:
        modifiers.append("virtual")
    if method.is_const:
        modifiers.append("const")
    if method.is_override:
        modifiers.append("override")

    # Build declaration
    decl = f"    {method.return_type} {method.cpp_name}({param_str})"

    if modifiers:
        decl += " " + " ".join(modifiers)

    decl += ";"
    lines.append(decl)

    return lines


def format_cpp_call_statements(statements: List["CppCallStatement"]) -> str:
    """Render CppCallStatement list into .cpp reference text.

    Examples:
        CppCallStatement(method_name="Jump", target="this", args=[]) -> "this->Jump();"
    """
    if not statements:
        return ""

    lines = ["// Call Reference"]
    for stmt in statements:
        op = "->"  # UE pointer access operator
        args_str = ", ".join(stmt.args)
        lines.append(f"{stmt.target}{op}{stmt.method_name}({args_str});")

    return "\n".join(lines) + "\n"


# ============================================================================
# Export list
# ============================================================================

__all__ = [
    "format_cpp_header",
    "format_cpp_call_statements",
]
