"""
C++ code generation module.

Provides mapping and generation from UE blueprint data to C++ skeleton code.

Modules:
    cpp_type_mapper: UE type path -> C++ type name mapping
    cpp_uproperty_mapper: CPF flag -> UPROPERTY specifier mapping
    extract_cpp_skeleton: C++ class skeleton extraction
    formatters: C++ JSON IR formatting and .h header file generation
    math_simplifier: KismetMathLibrary function -> operator simplification

Exported symbols:
    Type mapping:
        UE_TO_CPP_TYPE_MAP: UE type path -> C++ type name dictionary
        ENGINE_CLASS_PATHS: Engine class path -> C++ class name dictionary
        ue_path_to_cpp_type: UE type path -> C++ type name conversion function
        ue_package_path_to_cpp_class: Package path -> C++ class name conversion function
        infer_class_prefix: Parent class name -> C++ prefix inference function
        resolve_ue_type: Full UE path -> C++ type name resolution function

    Property mapping:
        CPF_TO_UPROPERTY_MAP: CPF flag -> UPROPERTY specifier mapping rules
        cpf_flags_to_uproperty_marks: CPF flag -> UPROPERTY specifier list conversion function

    Skeleton extraction:
        extract_cpp_class_skeleton: PackageIR -> CppClassIR extraction function

    JSON IR formatting (from formatters sub-module):
        CppProperty: Single C++ UPROPERTY declaration data model
        CppHeaderMeta: Header file metadata model
        CppClassIR: Full C++ class skeleton IR data model
        format_cpp_class_json: JSON IR formatting function

    .h header file generation:
        format_cpp_header: CppClassIR -> .h text conversion function

    Math function simplification:
        MathSimplifier: KismetMathLibrary function -> operator simplifier
"""

from uasset_read.cpp_gen.cpp_type_mapper import (
    UE_TO_CPP_TYPE_MAP,
    ENGINE_CLASS_PATHS,
    ue_path_to_cpp_type,
    ue_package_path_to_cpp_class,
    infer_class_prefix,
    resolve_ue_type,
)
from uasset_read.cpp_gen.cpp_uproperty_mapper import (
    CPF_TO_UPROPERTY_MAP,
    cpf_flags_to_uproperty_marks,
)
from uasset_read.cpp_gen.extract_cpp_skeleton import (
    extract_cpp_class_skeleton,
)
from uasset_read.cpp_gen.formatters import (
    CppProperty,
    CppHeaderMeta,
    CppClassIR,
    format_cpp_class_json,
    format_cpp_header,
    format_cpp_call_statements,
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
from uasset_read.cpp_gen.cpp_default_value_formatter import (
    format_cpp_default_value,
    format_cpp_transform,
    format_cpp_component_init,
    format_cpp_input_action_load,
)
from uasset_read.cpp_gen.cpp_constructor_formatter import (
    build_constructor_sections,
    format_cpp_constructor,
)
from uasset_read.cpp_gen.extract_cpp_skeleton import (
    extract_cpp_constructor,
)
from uasset_read.cpp_gen.sanitizer import (
    sanitize_identifier,
    sanitize_string_literal,
    sanitize_uproperty_marks,
    sanitize_category,
)
from uasset_read.cpp_gen.math_simplifier import (
    MathSimplifier,
)

__all__ = [
    # Type mapping
    "UE_TO_CPP_TYPE_MAP",
    "ENGINE_CLASS_PATHS",
    "ue_path_to_cpp_type",
    "ue_package_path_to_cpp_class",
    "infer_class_prefix",
    "resolve_ue_type",
    # Property mapping
    "CPF_TO_UPROPERTY_MAP",
    "cpf_flags_to_uproperty_marks",
    # Skeleton extraction
    "extract_cpp_class_skeleton",
    # JSON IR formatting
    "CppProperty",
    "CppHeaderMeta",
    "CppClassIR",
    "format_cpp_class_json",
    # .h header file generation
    "format_cpp_header",
    # Call statement formatting
    "format_cpp_call_statements",
    # Method/Call IR
    "CppCallParameter",
    "CppMethodIR",
    "CppCallStatement",
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
    # C++ default value formatting
    "format_cpp_default_value",
    "format_cpp_transform",
    "format_cpp_component_init",
    "format_cpp_input_action_load",
    # C++ constructor formatting
    "build_constructor_sections",
    "format_cpp_constructor",
    "extract_cpp_constructor",
    # C++ identifier sanitization
    "sanitize_identifier",
    "sanitize_string_literal",
    "sanitize_uproperty_marks",
    "sanitize_category",
    # Math function simplification
    "MathSimplifier",
]
