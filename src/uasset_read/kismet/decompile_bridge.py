from __future__ import annotations

"""Deprecated v1-derived Kismet decompile bridge, retained only for v2 decode depth.

Copied verbatim from ``uasset_read.pipeline.post_process`` (v1 pipeline, deleted in
the v0.6.0 refactor) so ``uasset_read.v2.package.legacy`` can keep decompiling
Kismet bytecode without the v1 pipeline package. The underlying
``uasset_read.kismet`` package is itself deprecated; this bridge is a thin
retention shim, not a supported public API.
"""

import logging
import struct
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from uasset_read.link.linker import PackageLinker
    from uasset_read.archive import FArchive

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)


def extract_kismet_decompiled(
    path: str,
    archive: "FArchive",
    summary,
    name_map: List[str],
    import_map,
    export_map,
    tolerant: bool = True,
    linker: Optional["PackageLinker"] = None,
) -> List:
    """Extract and decompile Kismet bytecode from Blueprint UStruct exports.

    Tolerant mode: failures return empty list for that function, never crash.
    Per D-10: Kismet decompilation failure does NOT block the main pipeline.

    Uses read_ufunction_script for native Function/UFunction exports to correctly
    handle the UStruct prefix (SuperStruct, Children, NativePropertyCount, native
    fields) before the bytecode header.
    """
    from uasset_read.kismet.bytecode_extractor import FUNCTION_EXPORT_CLASSES
    from uasset_read.kismet.ufunction_reader import read_ufunction_script
    from uasset_read.kismet.bytecode_extractor import parse_bytecode_stream
    from uasset_read.kismet.result import KismetDecompiledResult
    from uasset_read.serializers.object_resources import resolve_class_name

    results = []
    for export_idx, export in enumerate(export_map):
        class_name = resolve_class_name(export.class_index, import_map, export_map)
        if class_name not in FUNCTION_EXPORT_CLASSES:
            continue
        try:
            # Use the native UFunction reader to extract script bytes and native fields
            script_result = read_ufunction_script(
                archive,
                export,
                summary,
                name_map,
                import_map,
                export_map,
                export_index=export_idx,
            )

            if script_result.status == "no_script":
                # No bytecode - create a result with no_script status
                result = KismetDecompiledResult(
                    function_name=export.object_name,
                    signature=f"void {export.object_name}()",
                    local_variables=[],
                    cpp_code="",
                    bytecode_source="unknown",
                    bytecode_status="no_script",
                    translation_status="not_applicable",
                    error_code="confirmed_no_script",
                    error_message="UFunction Script header declares no bytecode",
                    error_context={
                        "function_name": export.object_name,
                        "export_index": export_idx,
                        "class_name": class_name,
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
                results.append(result)
                continue

            if script_result.status == "failed":
                failure = script_result.failure
                reason = failure.error_message if failure else "unknown"
                result = KismetDecompiledResult(
                    function_name=export.object_name,
                    signature=f"void {export.object_name}()",
                    local_variables=[],
                    cpp_code="",
                    bytecode_source="unknown",
                    bytecode_status="failed",
                    translation_status="not_applicable",
                    error_code=failure.error_code if failure else "ufunction_script_read_error",
                    error_message=reason,
                    error_context=(
                        {
                            "function_name": failure.function_name,
                            "export_index": failure.export_index,
                            "class_name": failure.class_name,
                            "package_offset": failure.package_offset,
                            "export_offset": failure.export_offset,
                        }
                        if failure
                        else None
                    ),
                    script_metrics=(
                        {
                            "bytecode_buffer_size": failure.bytecode_buffer_size,
                            "serialized_script_size": failure.serialized_script_size,
                            "serialized_bytes_consumed": 0,
                            "bytecode_bytes_consumed": 0,
                        }
                        if failure
                        else None
                    ),
                    warnings=[],
                    fallback_reasons=[f"UFunction script read failed: {reason}"],
                )
                results.append(result)
                continue

            # script_result.status == "extracted"
            # Parse the bytecode from the serialized script
            expressions: list = []
            parse_error: Exception | None = None
            if script_result.serialized_script:
                try:
                    expressions = parse_bytecode_stream(
                        script_result.serialized_script,
                        name_map,
                        summary,
                        bytecode_buffer_size=script_result.bytecode_buffer_size,
                        tolerant=tolerant,
                    )
                except (ParseError, ValueError) as exc:
                    parse_error = exc

            if parse_error or not expressions:
                reason = str(parse_error) if parse_error else "no bytecode expressions extracted"
                result = KismetDecompiledResult(
                    function_name=export.object_name,
                    signature=f"void {export.object_name}()",
                    local_variables=[],
                    cpp_code="",
                    bytecode_source="function_export",
                    bytecode_status="failed",
                    translation_status="not_applicable",
                    error_code="bytecode_decode_error",
                    error_message=reason,
                    error_context={
                        "function_name": export.object_name,
                        "export_index": export_idx,
                        "class_name": class_name,
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
                    fallback_reasons=[f"bytecode extraction error: {reason}"],
                )
                results.append(result)
                continue

            # Build C++ pseudocode from the parsed expressions
            from uasset_read.kismet.body_builder import FunctionBodyBuilder

            builder = FunctionBodyBuilder(linker=linker)
            cpp_code = builder.to_function_body(
                expressions,
                func_name=export.object_name,
            )
            warnings = _collect_pipeline_translation_warnings(cpp_code)

            # Extract structured rate metrics
            structured_rate: float | None = None
            try:
                from uasset_read.kismet.jump_analyzer import JumpAnalyzer

                rate_analyzer = JumpAnalyzer(expressions)
                structured_rate = rate_analyzer.analyze_structured_rate()
            except (ImportError, AttributeError, TypeError, ValueError):
                structured_rate = None

            # Extract function reference resolution statistics
            func_ref_stats: dict = {}
            if builder._translator._func_resolver is not None:
                func_ref_stats = builder._translator._func_resolver.get_statistics()
                unresolved_report = builder._translator._func_resolver.get_unresolved_report()
                if unresolved_report:
                    warnings.append(unresolved_report)

            # Use native fields to derive structured signature data
            native_params: list[dict[str, object]] = []
            native_return_type = "void"
            native_signature_used = False
            if script_result.native_fields:
                try:
                    from uasset_read.kismet.native_fields import build_native_function_signature

                    sig_str, native_params, native_return_type = build_native_function_signature(
                        export.object_name,
                        script_result.native_fields,
                    )
                    signature = sig_str
                    native_signature_used = True
                except (ValueError, KeyError, IndexError):
                    signature = cpp_code.split("{")[0].strip() if "{" in cpp_code else f"void {export.object_name}()"
            else:
                signature = cpp_code.split("{")[0].strip() if "{" in cpp_code else f"void {export.object_name}()"

            result = KismetDecompiledResult(
                function_name=export.object_name,
                signature=signature,
                local_variables=[],
                cpp_code=cpp_code,
                expressions=expressions,
                bytecode_source="function_export",
                bytecode_status="parsed",
                translation_status="complete",
                warnings=warnings,
                function_ref_stats=func_ref_stats,
                structured_rate=structured_rate,
                parameters=native_params,
                return_type=native_return_type,
                native_signature=native_signature_used,
            )
            results.append(result)

        except (ParseError, OSError, struct.error, ValueError, KeyError, AttributeError) as e:
            # Per D-10: a per-function failure does not block the package, but
            # it must remain visible in the public result list.
            logger.debug("Kismet decompile failed for export '%s': %s", export.object_name, e)
            results.append(
                KismetDecompiledResult(
                    function_name=export.object_name,
                    signature=f"void {export.object_name}()",
                    local_variables=[],
                    cpp_code="",
                    bytecode_source="unknown",
                    bytecode_status="failed",
                    translation_status="not_applicable",
                    error_code="function_processing_error",
                    error_message=str(e),
                    error_context={
                        "function_name": export.object_name,
                        "export_index": export_idx,
                        "class_name": class_name,
                        "package_offset": export.serial_offset,
                        "export_offset": export.serial_offset,
                    },
                    warnings=[],
                    fallback_reasons=[f"function processing error: {e}"],
                )
            )
    return results


def _collect_pipeline_translation_warnings(cpp_code: str) -> list[str]:
    """Report low-confidence bytecode translations."""
    warnings: list[str] = []
    if "/* unknown:" in cpp_code:
        warnings.append("Kismet translation contains unsupported expression tokens")
    if "Function_" in cpp_code or "LocalFunction_" in cpp_code:
        warnings.append("Kismet translation contains unresolved function references")
    return warnings
