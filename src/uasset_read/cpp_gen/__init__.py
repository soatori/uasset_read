"""C++ code generation module.

Provides mapping and generation from UE blueprint data to C++ skeleton code.

Submodules:
    cpp_type_mapper: UE type path -> C++ type name mapping
    cpp_uproperty_mapper: CPF flag -> UPROPERTY specifier mapping
    extract_cpp_skeleton: C++ class skeleton extraction
    cpp_default_value_formatter: Default value formatting for C++ output
    cpp_constructor_formatter: Constructor section formatting
    sanitizer: Identifier and string literal sanitization
    math_simplifier: KismetMathLibrary function -> operator simplification
    formatters: C++ JSON IR formatting, .h header generation, function body formatting
    extractors: C++ function body extraction

All symbols are available from their respective submodules.
Import directly from submodules, e.g.:
    from uasset_read.cpp_gen.cpp_type_mapper import ue_path_to_cpp_type
"""
