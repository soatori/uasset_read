from __future__ import annotations

"""
Kismet Decompilation Pipeline — Standalone decompile_uasset() entry point.

Provides decompile_uasset(path) function that iterates Function/UFunction
exports, extracts bytecode, translates to C++ pseudocode, and returns
structured results.
"""

from typing import TYPE_CHECKING

from uasset_read.exceptions import ParseError
from uasset_read.kismet.result import KismetDecompiledResult
from uasset_read.kismet.bytecode_extractor import (
    parse_bytecode_stream,
    FUNCTION_EXPORT_CLASSES,
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
    native_fields: list | None = None,
) -> KismetDecompiledResult | None:
    """
    Decompile a single UStruct export to KismetDecompiledResult.

    Internal helper that:
    1. Uses read_ufunction_script() to extract script bytes, then parse_bytecode_stream()
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
        native_fields: Optional list of NativeFieldDeclaration from
            FunctionScriptReadResult. When provided, used to derive the
            function signature, parameters, and return type.

    Returns:
        KismetDecompiledResult if bytecode found and parsed successfully.
        In tolerant mode, returns a result with bytecode_status="failed" and
        error details in fallback_reasons when decompilation fails.
        Returns None only if export is not a UStruct type (no bytecode at all).
    """
    func_name = export.object_name

    def _failed_result(reason: str) -> KismetDecompiledResult:
        """Build failure result, preserving per-function failure signal."""
        return KismetDecompiledResult(
            function_name=func_name,
            signature=f"void {func_name}()",
            local_variables=[],
            cpp_code="",
            bytecode_source="unknown",
            bytecode_status="failed",
            warnings=[],
            fallback_reasons=[reason],
        )

    # Use read_ufunction_script() to extract script bytes, then parse
    from uasset_read.kismet.ufunction_reader import read_ufunction_script

    try:
        script_result = read_ufunction_script(
            archive, export, summary, name_map, import_map, export_map,
        )
    except (ParseError, ValueError, IndexError, KeyError) as exc:
        if tolerant:
            return _failed_result(f"bytecode extraction error: {exc}")
        raise

    if script_result.status == "no_script":
        return KismetDecompiledResult(
            function_name=func_name,
            signature=f"void {func_name}()",
            local_variables=[],
            cpp_code="",
            bytecode_source="unknown",
            bytecode_status="no_script",
            translation_status="not_applicable",
            error_code="confirmed_no_script",
            error_message="UFunction Script header declares no bytecode",
            error_context={
                "function_name": func_name,
                "package_offset": export.serial_offset,
                "export_offset": export.serial_offset,
            },
            script_metrics={
                "bytecode_buffer_size": 0,
                "serialized_script_size": 0,
                "serialized_bytes_consumed": 0,
                "bytecode_bytes_consumed": 0,
            },
        )
    if script_result.status == "failed":
        reason = script_result.failure.error_message if script_result.failure else "unknown"
        return _failed_result(f"UFunction script read failed: {reason}")

    # Parse the bytecode from the serialized script
    expressions = []
    error = None
    if script_result.serialized_script:
        try:
            expressions = parse_bytecode_stream(
                script_result.serialized_script, name_map, summary,
                bytecode_buffer_size=script_result.bytecode_buffer_size,
                tolerant=tolerant,
            )
        except (ParseError, ValueError) as exc:
            error = str(exc)

    if error or not expressions:
        if tolerant:
            reason = error if error else "no bytecode expressions extracted"
            return KismetDecompiledResult(
                function_name=func_name,
                signature=f"void {func_name}()",
                local_variables=[],
                cpp_code="",
                bytecode_source="function_export",
                bytecode_status="failed",
                translation_status="not_applicable",
                error_code="bytecode_decode_error",
                error_message=reason,
                error_context={
                    "function_name": func_name,
                    "package_offset": export.serial_offset,
                    "export_offset": export.serial_offset,
                },
                script_metrics={
                    "bytecode_buffer_size": script_result.bytecode_buffer_size,
                    "serialized_script_size": script_result.serialized_script_size,
                    "serialized_bytes_consumed": len(script_result.serialized_script),
                    "bytecode_bytes_consumed": 0,
                },
                warnings=[],
                fallback_reasons=[f"bytecode decode error: {reason}"],
            )
        return None

    # Build fallback reason list
    fallback_reasons: list[str] = []

    # Build C++ pseudocode using FunctionBodyBuilder
    type_registry = TypeRegistry()
    builder = FunctionBodyBuilder(type_registry, linker=linker)

    # Generate C++ code (use structured flow first, fallback to goto)
    cpp_code = builder.to_function_body_structured(expressions, func_name=func_name)
    warnings = _collect_translation_warnings(cpp_code)

    # Collect structured rate metrics
    structured_rate: float | None = None
    try:
        from uasset_read.kismet.jump_analyzer import JumpAnalyzer
        rate_analyzer = JumpAnalyzer(expressions)
        rate_report = rate_analyzer.analyze_structured_rate()
        structured_rate = rate_report.rate
    except (ImportError, AttributeError, TypeError, ValueError):
        structured_rate = None

    # Extract function reference resolution statistics
    func_ref_stats: dict = {}
    if builder._translator._func_resolver is not None:
        func_ref_stats = builder._translator._func_resolver.get_statistics()
        # Add warning if there are unresolved references
        unresolved_report = builder._translator._func_resolver.get_unresolved_report()
        if unresolved_report:
            warnings.append(unresolved_report)

    # Extract signature from generated code (first line)
    # Format: "void FuncName(...) {" or similar
    signature = cpp_code.split("{")[0].strip() if "{" in cpp_code else f"void {func_name}()"

    # Use native fields to derive structured signature data when available
    native_params: list[dict[str, object]] = []
    native_return_type = "void"
    native_signature_used = False
    if native_fields:
        try:
            from uasset_read.kismet.native_fields import build_native_function_signature
            signature, native_params, native_return_type = build_native_function_signature(
                func_name, native_fields,
            )
            native_signature_used = True
        except (ValueError, KeyError, IndexError):
            pass  # Fall back to graph-derived signature

    # Capture local variables from TypeRegistry snapshot
    local_vars: list[dict[str, str]] = []
    for var_name, cpp_type in type_registry._types.items():
        local_vars.append({"name": var_name, "type": cpp_type})

    # Determine translation_status based on warnings collected above
    translation_status = "complete" if not warnings else "partial"

    return KismetDecompiledResult(
        function_name=func_name,
        signature=signature,
        local_variables=local_vars,
        cpp_code=cpp_code,
        expressions=expressions,
        bytecode_source="function_export",
        bytecode_status="parsed",
        translation_status=translation_status,
        warnings=warnings,
        fallback_reasons=fallback_reasons,
        function_ref_stats=func_ref_stats,
        structured_rate=structured_rate,
        parameters=native_params,
        return_type=native_return_type,
        native_signature=native_signature_used,
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
        list[KismetDecompiledResult] - may be empty if no bytecode found.
        In tolerant mode, includes results with bytecode_status="failed" for
        functions that errored during decompilation.

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

    # Collect Function/UFunction exports only
    results: list[KismetDecompiledResult] = []

    for export in export_map:
        # Check if this is a Function/UFunction export with bytecode
        class_name = resolve_class_name(export.class_index, import_map, export_map)
        if class_name not in FUNCTION_EXPORT_CLASSES:
            continue

        # Attempt decompilation — the native reader determines whether a
        # Function has Script data; export property offsets are unrelated.
        # including no_script and failed
        result = decompile_single_function(
            archive, export, summary, name_map, import_map, export_map, tolerant=tolerant
        )

        if result is not None:
            results.append(result)

    return results


__all__ = ["decompile_uasset", "decompile_single_function"]
