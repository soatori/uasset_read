"""Kismet decompile bridge, reached from v2 asset/decode depth.

Permanent v2 internal (#642). Produces expression trees and structured
diagnostics for Function/UFunction exports. C++ pseudocode generation was
retired 2026-09-10 (Gate K); the public function-logic representation is
``semantic.functions[]`` expressions (K0 contract).

Identity (export_index / object_id / class_name) is populated from the
export table before parsing. Read-phase status (extracted|no_script|failed)
maps explicitly onto the analysis vocabulary (parsed|partial|unavailable).
"""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.exceptions import ParseError, StreamPoisonedError

logger = logging.getLogger(__name__)


def _unavailable(
    export,
    idx: int,
    class_name: str | None,
    code: str,
    message: str,
    *,
    source_range=None,
    context: bool = True,
    metrics: dict | None = None,
    fallback: str | None = None,
):
    """One structured unavailable result for a failed Function export."""
    from uasset_read.kismet.result import KismetDecompiledResult

    return KismetDecompiledResult(
        function_name=export.object_name,
        signature=f"void {export.object_name}()",
        bytecode_status="unavailable",
        export_index=idx,
        object_id=f"export:{idx}",
        class_name=class_name or "Unknown",
        script_source_range=source_range,
        error_code=code,
        error_message=message,
        error_context=(
            {
                "function_name": export.object_name,
                "export_index": idx,
                "class_name": class_name,
                "package_offset": export.serial_offset,
                "export_offset": export.serial_offset,
            }
            if context
            else None
        ),
        script_metrics=metrics,
        fallback_reasons=[fallback] if fallback else [],
    )


def extract_kismet_decompiled(
    archive: "FArchive",
    summary,
    name_map: list[str],
    import_map,
    export_map,
) -> list:
    """Extract Kismet bytecode from Blueprint UStruct Function/UFunction exports.

    Tolerant mode: failures return a result for that function, never crash.
    Per D-10: Kismet decompilation failure does NOT block the main pipeline.
    StreamPoisonedError is re-raised: a poisoned cursor cannot become a
    valid partial decode.
    """
    from uasset_read.kismet.bytecode_extractor import FUNCTION_EXPORT_CLASSES
    from uasset_read.kismet.ufunction_reader import read_ufunction_script
    from uasset_read.kismet.bytecode_extractor import parse_bytecode_stream
    from uasset_read.kismet.result import KismetDecompiledResult
    from uasset_read.kismet.expressions import OpaqueExpression
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
                    _unavailable(
                        export,
                        export_idx,
                        class_name,
                        "confirmed_no_script",
                        "UFunction Script header declares no bytecode",
                        source_range=script_result.script_source_range,
                        metrics={
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
                    _unavailable(
                        export,
                        export_idx,
                        class_name,
                        failure.error_code if failure else "ufunction_script_read_error",
                        reason,
                        context=failure is not None,
                        metrics=(
                            {
                                "bytecode_buffer_size": failure.bytecode_buffer_size,
                                "serialized_script_size": failure.serialized_script_size,
                                "serialized_bytes_consumed": 0,
                                "bytecode_bytes_consumed": 0,
                            }
                            if failure
                            else None
                        ),
                        fallback=f"UFunction script read failed: {reason}",
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
                        tolerant=True,
                    )
                except StreamPoisonedError:
                    raise
                except (ParseError, ValueError) as exc:
                    parse_error = exc

            if parse_error or not expressions:
                reason = str(parse_error) if parse_error else "no bytecode expressions extracted"
                results.append(
                    _unavailable(
                        export,
                        export_idx,
                        class_name,
                        "bytecode_decode_error",
                        reason,
                        source_range=script_result.script_source_range,
                        metrics={
                            "bytecode_buffer_size": script_result.bytecode_buffer_size,
                            "serialized_script_size": script_result.serialized_script_size,
                            "serialized_bytes_consumed": len(script_result.serialized_script),
                            "bytecode_bytes_consumed": 0,
                        },
                        fallback=f"bytecode extraction error: {reason}",
                    )
                )
                continue

            signature = f"void {export.object_name}()"
            if script_result.native_fields:
                try:
                    from uasset_read.kismet.native_fields import build_native_function_signature

                    signature = build_native_function_signature(
                        export.object_name,
                        script_result.native_fields,
                    )
                except (ValueError, KeyError, IndexError):
                    signature = f"void {export.object_name}()"

            has_opaque = any(isinstance(e, OpaqueExpression) for e in expressions)
            bytecode_status = "partial" if has_opaque else "parsed"

            # Normalize into instruction IR + CFG for the projected functions dict.
            from uasset_read.parsers.blueprint.bytecode import (
                normalize_instructions,
                project_instruction,
            )
            from uasset_read.parsers.blueprint.control_flow import build_cfg, project_cfg

            instructions = normalize_instructions(expressions)
            cfg = build_cfg(instructions)

            results.append(
                KismetDecompiledResult(
                    function_name=export.object_name,
                    signature=signature,
                    export_index=export_idx,
                    object_id=f"export:{export_idx}",
                    class_name=class_name or "Unknown",
                    script_source_range=script_result.script_source_range,
                    expressions=expressions,
                    bytecode_status=bytecode_status,
                    instructions=[project_instruction(i) for i in instructions],
                    cfg=project_cfg(cfg),
                )
            )

        except StreamPoisonedError as e:
            # A poisoned cursor cannot become a valid partial decode for this
            # function; surface it as unavailable and keep sibling exports.
            logger.debug("Kismet stream poisoned for export '%s': %s", export.object_name, e)
            results.append(
                _unavailable(
                    export,
                    export_idx,
                    class_name,
                    "stream_poisoned",
                    str(e),
                    context=False,
                    fallback=f"stream poisoned: {e}",
                )
            )
        except (ParseError, OSError, struct.error, ValueError, KeyError, AttributeError) as e:
            logger.debug("Kismet decompile failed for export '%s': %s", export.object_name, e)
            results.append(
                _unavailable(
                    export,
                    export_idx,
                    class_name,
                    "function_processing_error",
                    str(e),
                    fallback=f"function processing error: {e}",
                )
            )
    return results
