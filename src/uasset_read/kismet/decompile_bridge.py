"""Kismet decompile bridge, reached from v2 asset/decode depth.

Permanent v2 internal (#642). Produces expression trees and structured
diagnostics for Function/UFunction exports. C++ pseudocode generation was
retired 2026-09-10 (Gate K); the public function-logic representation is
``semantic.functions[]`` expressions (K0 contract).
"""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)


def extract_kismet_decompiled(
    archive: "FArchive",
    summary,
    name_map: list[str],
    import_map,
    export_map,
    tolerant: bool = True,
) -> List:
    """Extract Kismet bytecode from Blueprint UStruct Function/UFunction exports.

    Tolerant mode: failures return a result for that function, never crash.
    Per D-10: Kismet decompilation failure does NOT block the main pipeline.
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
                results.append(
                    KismetDecompiledResult(
                        function_name=export.object_name,
                        signature=f"void {export.object_name}()",
                        bytecode_source="unknown",
                        bytecode_status="no_script",
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
                )
                continue

            if script_result.status == "failed":
                failure = script_result.failure
                reason = failure.error_message if failure else "unknown"
                results.append(
                    KismetDecompiledResult(
                        function_name=export.object_name,
                        signature=f"void {export.object_name}()",
                        bytecode_source="unknown",
                        bytecode_status="failed",
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
                        fallback_reasons=[f"UFunction script read failed: {reason}"],
                    )
                )
                continue

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
                results.append(
                    KismetDecompiledResult(
                        function_name=export.object_name,
                        signature=f"void {export.object_name}()",
                        bytecode_source="function_export",
                        bytecode_status="failed",
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
                        fallback_reasons=[f"bytecode extraction error: {reason}"],
                    )
                )
                continue

            native_params: list[dict[str, object]] = []
            native_return_type = "void"
            native_signature_used = False
            signature = f"void {export.object_name}()"
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
                    signature = f"void {export.object_name}()"

            results.append(
                KismetDecompiledResult(
                    function_name=export.object_name,
                    signature=signature,
                    expressions=expressions,
                    bytecode_source="function_export",
                    bytecode_status="parsed",
                    parameters=native_params,
                    return_type=native_return_type,
                    native_signature=native_signature_used,
                    function_ref_stats={},
                )
            )

        except (ParseError, OSError, struct.error, ValueError, KeyError, AttributeError) as e:
            logger.debug("Kismet decompile failed for export '%s': %s", export.object_name, e)
            results.append(
                KismetDecompiledResult(
                    function_name=export.object_name,
                    signature=f"void {export.object_name}()",
                    bytecode_source="unknown",
                    bytecode_status="failed",
                    error_code="function_processing_error",
                    error_message=str(e),
                    error_context={
                        "function_name": export.object_name,
                        "export_index": export_idx,
                        "class_name": class_name,
                        "package_offset": export.serial_offset,
                        "export_offset": export.serial_offset,
                    },
                    fallback_reasons=[f"function processing error: {e}"],
                )
            )
    return results
