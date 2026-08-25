"""
C++ code generation formatting sub-module.

Provides C++ class skeleton JSON IR formatting and .h header file generation.

Exports:
    CppProperty: Single C++ UPROPERTY declaration data model
    CppHeaderMeta: Header file metadata model
    CppClassIR: Complete C++ class skeleton IR data model
    format_cpp_class_json: JSON IR formatting function
    format_cpp_header: .h header file text generation function
    kismet_to_cpp_body: Kismet expression -> structured C++ statement list
"""
from uasset_read.cpp_gen.formatters.cpp_json_ir import (
    CppProperty,
    CppHeaderMeta,
    CppClassIR,
    format_cpp_class_json,
    # Method/Call IR
    CppCallParameter,
    CppMethodIR,
    CppCallStatement,
    # Statement IR
    CppStatement,
    CppCallStmt,
    CppAssignmentStmt,
    CppIfStmt,
    CppInlineExprStmt,
    CppReturnStmt,
    CppWhileStmt,
    CppRawStmt,
    # Body builder
    kismet_to_cpp_body,
)
from uasset_read.cpp_gen.formatters.cpp_header_formatter import (
    format_cpp_header,
    format_cpp_call_statements,
)
from uasset_read.cpp_gen.formatters.cpp_function_body_formatter import (
    format_cpp_function_body,
)

__all__ = [
    "CppProperty",
    "CppHeaderMeta",
    "CppClassIR",
    "format_cpp_class_json",
    "format_cpp_header",
    # Method/Call IR
    "CppCallParameter",
    "CppMethodIR",
    "CppCallStatement",
    # Call statement formatting
    "format_cpp_call_statements",
    # Statement IR
    "CppStatement",
    "CppCallStmt",
    "CppAssignmentStmt",
    "CppIfStmt",
    "CppInlineExprStmt",
    "CppReturnStmt",
    "CppWhileStmt",
    "CppRawStmt",
    # Body builder
    "kismet_to_cpp_body",
    "format_cpp_function_body",
]