"""
Kismet Decompilation Pipeline — Standalone decompile_uasset() entry point.

Provides decompile_uasset(path) function that iterates Blueprint
UStruct exports, extracts bytecode, translates to C++ pseudocode, and returns
structured results.

BPGC bytecode fallback with cache reset.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.exceptions import ParseError
from uasset_read.kismet.result import KismetDecompiledResult
from uasset_read.kismet.bytecode_extractor import (
    extract_and_parse,
    USTRUCT_TYPES,
    reset_bpgc_cache,
)
from uasset_read.kismet.body_builder import FunctionBodyBuilder
from uasset_read.kismet.translator import TypeRegistry

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.link.linker import PackageLinker
    from uasset_read.serializers.object_resources import ObjectExport, PackageFileSummary


def decompile_single_function(
    archive: FArchive,
    export: ObjectExport,
    summary: PackageFileSummary,
    name_map: list[str],
    import_map: list,
    export_map: list,
    tolerant: bool = True,
    linker: "PackageLinker | None" = None,
) -> KismetDecompiledResult | None:
    """
    Decompile a single UStruct export to KismetDecompiledResult.

    Internal helper that:
    1. Uses extract_and_parse() to extract and parse bytecode
    2. Translates expressions to C++ pseudocode
    3. Captures local variable types from TypeRegistry
    4. Returns structured result

    Args:
        archive: FArchive instance (file-level archive)
        export: ObjectExport to decompile
        summary: PackageFileSummary for version info
        name_map: Name table for expression resolution
        import_map: Import table for class name resolution
        export_map: Export table for class name resolution
        tolerant: If True, skip unknown tokens instead of raising

    Returns:
        KismetDecompiledResult if bytecode found and parsed successfully,
        None if export has no bytecode or is not a UStruct type.

    On any exception during bytecode extraction/parsing, returns None
    (caller handles error logging via tolerant mode).
    """
    # 复用 extract_and_parse() 提取和解析字节码
    try:
        expressions, error, extraction_reason = extract_and_parse(
            archive, export, summary, name_map, import_map, export_map,
            tolerant=tolerant,
        )
    except (ParseError, ValueError, IndexError, KeyError):
        # Expected failures from corrupted/malformed bytecode
        return None

    if error or not expressions:
        return None

    # 构建退回原因列表
    fallback_reasons: list[str] = []
    if extraction_reason != "function_export":
        fallback_reasons.append(extraction_reason)

    # Build C++ pseudocode using FunctionBodyBuilder
    type_registry = TypeRegistry()
    builder = FunctionBodyBuilder(type_registry, linker=linker)

    # Use export.object_name as function name
    func_name = export.object_name

    # Generate C++ code (use structured flow first, fallback to goto)
    cpp_code = builder.to_function_body_structured(expressions, func_name=func_name)
    warnings = _collect_translation_warnings(cpp_code)

    # 提取函数引用解析统计
    func_ref_stats: dict = {}
    if builder._translator._func_resolver is not None:
        func_ref_stats = builder._translator._func_resolver.get_statistics()
        # 如果有未解析引用，添加警告
        unresolved_report = builder._translator._func_resolver.get_unresolved_report()
        if unresolved_report:
            warnings.append(unresolved_report)

    # Extract signature from generated code (first line)
    # Format: "void FuncName(...) {" or similar
    signature = cpp_code.split("{")[0].strip() if "{" in cpp_code else f"void {func_name}()"

    # Capture local variables from TypeRegistry snapshot
    local_vars: list[dict[str, str]] = []
    for var_name, cpp_type in type_registry._types.items():
        local_vars.append({"name": var_name, "type": cpp_type})

    return KismetDecompiledResult(
        function_name=func_name,
        signature=signature,
        local_variables=local_vars,
        cpp_code=cpp_code,
        expressions=expressions,
        bytecode_source=("function_export" if extraction_reason == "function_export" else "fallback_or_serial_scan"),
        bytecode_status="parsed",
        warnings=warnings,
        fallback_reasons=fallback_reasons,
        function_ref_stats=func_ref_stats,
    )


def _collect_translation_warnings(cpp_code: str) -> list[str]:
    """Report low-confidence bytecode translations instead of staying silent."""
    warnings: list[str] = []
    if "/* unknown:" in cpp_code:
        warnings.append("Kismet translation contains unsupported expression tokens")
    if "Function_" in cpp_code or "LocalFunction_" in cpp_code:
        warnings.append("Kismet translation contains unresolved function references")
    return warnings


def decompile_uasset(path: str, tolerant: bool = True) -> list[KismetDecompiledResult]:
    """
    Decompile all Blueprint functions in a .uasset file.

    Public entry point (D-01, D-07, D-08) that:
    1. Opens FArchive on the .uasset file
    2. Reads summary, name_map, import_map, export_map
    3. Finds Blueprint UStruct exports (Function, UFunction, etc.)
    4. Calls decompile_single_function for each qualifying export
    5. Collects non-None results into list

    Resets BPGC bytecode cache at start (T-72C-04 mitigation).

    Args:
        path: Path to the .uasset file
        tolerant: If True, use tolerant mode for bytecode parsing

    Returns:
        list[KismetDecompiledResult] - may be empty if no bytecode found

    Raises:
        FileNotFoundError: If the file does not exist
        ParseError: If the file is not a valid .uasset package
        Other exceptions: For corrupt package structures
    """
    import os
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import read_package_summary, read_name_table
    from uasset_read.serializers.object_resources import (
        read_import_map,
        read_export_map,
        resolve_class_name,
    )

    # T-72C-04: Reset BPGC cache for fresh extraction per file
    reset_bpgc_cache()

    # Verify file exists
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    # Open archive (NOT tolerant at top level - caller decides)
    archive = FArchive(path, tolerant=False)

    # Read package structures
    summary = read_package_summary(archive)
    archive.seek(summary.name_offset)
    name_map = read_name_table(archive, summary)
    archive.seek(summary.import_offset)
    import_map = read_import_map(archive, summary, name_map)
    archive.seek(summary.export_offset)
    export_map = read_export_map(archive, summary, name_map)

    # Collect UStruct exports
    results: list[KismetDecompiledResult] = []

    for export in export_map:
        # Check if this is a Blueprint UStruct export with bytecode
        class_name = resolve_class_name(export.class_index, import_map, export_map)
        if class_name not in USTRUCT_TYPES:
            continue

        # Skip exports with no script data
        if not export.has_script_serialization:
            continue

        # Attempt decompilation
        result = decompile_single_function(
            archive, export, summary, name_map, import_map, export_map, tolerant=tolerant
        )

        if result is not None:
            results.append(result)

    return results


__all__ = ["decompile_uasset", "decompile_single_function"]
