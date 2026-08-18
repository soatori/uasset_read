from __future__ import annotations

"""Post-processing stage — Kismet decompilation, Blueprint graph extraction, dependency analysis."""

import logging
import struct
from typing import TYPE_CHECKING, Optional, List, Union, Sequence
from pathlib import Path

if TYPE_CHECKING:
    from uasset_read.link.linker import PackageLinker
    from uasset_read.archive import FArchive
    from uasset_read.memory_safety import MemoryPolicy
    from uasset_read.link.result import LinkerParseResult
    from uasset_read.models.result import ParseResult

from uasset_read.exceptions import ParseError
from uasset_read.core.error_handling import tolerant_parse
from uasset_read.serializers.object_resources import (
    find_main_blueprint_generated_class, detect_blueprint,
    build_imports_list, read_soft_object_paths,
)

logger = logging.getLogger(__name__)


def _extract_kismet_decompiled(
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
                archive, export, summary, name_map, import_map, export_map,
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
                        if failure else None
                    ),
                    script_metrics=(
                        {
                            "bytecode_buffer_size": failure.bytecode_buffer_size,
                            "serialized_script_size": failure.serialized_script_size,
                            "serialized_bytes_consumed": 0,
                            "bytecode_bytes_consumed": failure.bytecode_index or 0,
                        }
                        if failure else None
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
                        script_result.serialized_script, name_map, summary,
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
            from uasset_read.kismet.translator import TypeRegistry

            type_registry = TypeRegistry()
            builder = FunctionBodyBuilder(type_registry, linker=linker)
            cpp_code = builder.to_function_body_structured(
                expressions, func_name=export.object_name,
            )
            warnings = _collect_pipeline_translation_warnings(cpp_code)

            # Extract structured rate metrics
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
                        export.object_name, script_result.native_fields,
                    )
                    signature = sig_str
                    native_signature_used = True
                except (ValueError, KeyError, IndexError):
                    signature = cpp_code.split("{")[0].strip() if "{" in cpp_code else f"void {export.object_name}()"
            else:
                signature = cpp_code.split("{")[0].strip() if "{" in cpp_code else f"void {export.object_name}()"

            # Capture local variables from TypeRegistry snapshot
            local_vars: list[dict[str, str]] = []
            for var_name, cpp_type in type_registry._types.items():
                local_vars.append({"name": var_name, "type": cpp_type})

            result = KismetDecompiledResult(
                function_name=export.object_name,
                signature=signature,
                local_variables=local_vars,
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
            results.append(KismetDecompiledResult(
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
            ))
    return results


def _collect_pipeline_translation_warnings(cpp_code: str) -> list[str]:
    """Report low-confidence bytecode translations."""
    warnings: list[str] = []
    if "/* unknown:" in cpp_code:
        warnings.append("Kismet translation contains unsupported expression tokens")
    if "Function_" in cpp_code or "LocalFunction_" in cpp_code:
        warnings.append("Kismet translation contains unresolved function references")
    return warnings


def _extract_blueprint_graphs_and_metadata(
    archive: "FArchive",
    summary,
    name_map: List[str],
    import_map,
    export_map,
    result: "Union[ParseResult, LinkerParseResult]",
    linker: Optional["PackageLinker"] = None,
    archive_factory=None,
):
    """Extract Blueprint graphs and metadata (BPGC priority + UBlueprint fallback).

    Returns:
        Extracted BlueprintMetadata, or None if not found.
    """
    # Lazy import of extras module (per #117 core/extras layering)
    from uasset_read.blueprint import extract_blueprint_metadata

    # --- Blueprint Graph extraction (before metadata extraction to pass graphs parameter) ---
    graphs_list = None
    try:
        from uasset_read.graph import extract_blueprint_graphs
        if hasattr(result, 'graphs'):
            with tolerant_parse(result, "graph extraction"):
                result.graphs = extract_blueprint_graphs(
                    archive, summary, name_map, import_map, export_map,
                    linker=linker,
                )
                graphs_list = result.graphs
    except ImportError:
        logger.debug("graph module not found, skipping Blueprint graph extraction")

    # --- Blueprint metadata extraction (BPGC priority) ---
    blueprint_metadata = None
    asset_name = name_map[0] if name_map else None

    if asset_name:
        main_bpgc = find_main_blueprint_generated_class(
            export_map, import_map, asset_name
        )
        if main_bpgc:
            owned_archive = archive_factory is not None
            temp_archive = archive_factory() if archive_factory else archive
            temp_archive.set_byte_swapping(archive._byte_swapping)
            try:
                with tolerant_parse(result, "blueprint extraction (BPGC)"):
                    meta, warn = extract_blueprint_metadata(
                        main_bpgc, temp_archive, import_map,
                        export_map, name_map, summary,
                        linker=linker,
                        graphs=graphs_list,
                    )
                    if meta:
                        blueprint_metadata = meta
                        if hasattr(result, 'errors') and warn:
                            result.errors.append(f"blueprint parent warning: {warn}")
            finally:
                if owned_archive:
                    temp_archive.close()

    # --- UBlueprint fallback ---
    if not blueprint_metadata:
        for export in export_map:
            if linker is not None:
                from uasset_read.serializers.object_resources import detect_blueprint_with_linker
                is_bp = detect_blueprint_with_linker(export, linker)
            else:
                is_bp = detect_blueprint(export, import_map, export_map)
            if is_bp:
                owned_archive = archive_factory is not None
                temp_archive = archive_factory() if archive_factory else archive
                temp_archive.set_byte_swapping(archive._byte_swapping)
                try:
                    with tolerant_parse(result, "blueprint extraction"):
                        meta, warn = extract_blueprint_metadata(
                            export, temp_archive, import_map,
                            export_map, name_map, summary,
                            linker=linker,
                            graphs=graphs_list,
                        )
                        if meta:
                            blueprint_metadata = meta
                            if hasattr(result, 'errors') and warn:
                                result.errors.append(f"blueprint parent warning: {warn}")
                finally:
                    if owned_archive:
                        temp_archive.close()
                break

    # Only assign when blueprint_metadata is not None, to avoid overwriting existing Blueprint data
    if blueprint_metadata is not None and hasattr(result, 'blueprint'):
        result.blueprint = blueprint_metadata

    return blueprint_metadata


def _run_kismet_and_dependency_analysis(
    path: str,
    archive: "FArchive",
    summary,
    name_map: List[str],
    import_map,
    export_map,
    result: "Union[ParseResult, LinkerParseResult]",
    tolerant: bool = True,
    linker: Optional["PackageLinker"] = None,
    blueprint_metadata=None,
) -> None:
    """Kismet decompilation + component extraction + dependency analysis."""
    # Kismet decompilation (per D-02, D-10)
    try:
        from uasset_read.kismet.pipeline import decompile_single_function  # noqa: F401 — module existence check
        if hasattr(result, 'decompiled_functions'):
            decompiled = _extract_kismet_decompiled(
                path, archive, summary, name_map,
                import_map, export_map, tolerant, linker=linker,
            )
            result.decompiled_functions = decompiled
            if decompiled and getattr(result, "graphs", None):
                from uasset_read.kismet.semantic import enrich_decompiled_functions
                enrich_decompiled_functions(decompiled, result.graphs)
            if blueprint_metadata and not decompiled and hasattr(result, 'warnings'):
                result.warnings.append("Kismet decompilation: no functions decompiled (may have no bytecode)")
    except ImportError:
        logger.debug("kismet module not found, skipping bytecode decompilation")
    except (OSError, struct.error, ValueError, KeyError) as e:
        if hasattr(result, 'warnings'):
            result.warnings.append(f"Kismet decompilation error: {e}")

    # Component property extraction
    try:
        from uasset_read.blueprint.component_extractor import extract_components
        if hasattr(result, 'components'):
            result.components = extract_components(export_map, import_map)
    except ImportError:
        logger.debug("component_extractor module not found, skipping component property extraction")
    except (KeyError, TypeError, ValueError) as e:
        if hasattr(result, 'errors'):
            result.errors.append(f"component extraction error: {e}")

    # Dependency analysis
    with tolerant_parse(result, "dependency analysis"):
        if hasattr(result, 'imports'):
            result.imports = build_imports_list(import_map)
        if hasattr(result, 'soft_references'):
            result.soft_references = read_soft_object_paths(
                archive, summary, name_map,
            )


def _post_process(
    path: str,
    archive: "FArchive",
    summary,
    name_map: List[str],
    import_map,
    export_map,
    result: "Union[ParseResult, LinkerParseResult]",
    tolerant: bool = True,
    linker: Optional["PackageLinker"] = None,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    archive_factory=None,
    memory_policy: Optional["MemoryPolicy"] = None,
) -> None:
    """Shared post-processing: Blueprint metadata, graph extraction, dependency analysis.

    Writes fields via hasattr guards, supporting both ParseResult and LinkerParseResult.
    """
    blueprint_metadata = _extract_blueprint_graphs_and_metadata(
        archive, summary, name_map, import_map, export_map,
        result, linker=linker, archive_factory=archive_factory,
    )

    _run_kismet_and_dependency_analysis(
        path, archive, summary, name_map, import_map, export_map,
        result, tolerant=tolerant, linker=linker,
        blueprint_metadata=blueprint_metadata,
    )

    if include_parent_assets:
        _resolve_parent_assets(
            path, result, tolerant, asset_roots,
            memory_policy=memory_policy,
        )

    # name_map consistency check
    if hasattr(result, 'name_map') and not result.name_map:
        if summary is not None and getattr(summary, 'name_count', 0) > 0:
            if hasattr(result, 'errors'):
                result.errors.append(
                    f"name_map is empty (summary.name_count={summary.name_count}), "
                    f"name table read failed"
                )

    result.is_success = not result.errors


def _find_parent_asset_file(parent_class: str, roots: Sequence[Path]) -> Optional[Path]:
    target_name = f"{parent_class}.uasset"
    seen: set[Path] = set()
    for root in roots:
        try:
            root = root.resolve()
        except OSError:
            continue
        if root in seen or not root.exists():
            continue
        seen.add(root)
        direct = root / target_name
        if direct.is_file():
            return direct
        if root.is_dir():
            try:
                match = next(root.rglob(target_name), None)
            except OSError:
                match = None
            if match is not None and match.is_file():
                return match
    return None


def _resolve_parent_assets(
    path: str,
    result: "Union[ParseResult, LinkerParseResult]",
    tolerant: bool,
    asset_roots: Optional[Sequence[str]],
    memory_policy: Optional["MemoryPolicy"] = None,
) -> None:
    """Best-effort parent Blueprint lookup used by cross-asset parsing."""
    if not getattr(result, "blueprint", None):
        return
    parent_class = getattr(result.blueprint, "parent_class", None)
    if not parent_class:
        return

    result.logic_sources.append({
        "source": "current_asset",
        "asset": path,
        "blueprint": result.summary.package_name if result.summary else None,
    })

    roots = [Path(root) for root in (asset_roots or [])]
    roots.append(Path(path).resolve().parent)
    parent_file = _find_parent_asset_file(parent_class, roots)
    if parent_file is None:
        result.logic_sources.append({
            "source": "native_parent",
            "class": parent_class,
            "status": "asset_not_found",
        })
        result.warnings.append(
            f"Parent asset '{parent_class}.uasset' not found in asset roots"
        )
        return

    # Lazy import to avoid circular dependencies
    from uasset_read.pipeline.core import parse_uasset_with_linker

    try:
        parent_result = parse_uasset_with_linker(
            str(parent_file),
            tolerant=tolerant,
            include_parent_assets=False,
            memory_policy=memory_policy,
        )
    except (OSError, ParseError, struct.error, ValueError) as exc:
        result.logic_sources.append({
            "source": "parent_asset",
            "class": parent_class,
            "asset": str(parent_file),
            "status": "parse_error",
            "error": str(exc),
        })
        result.warnings.append(f"Parent asset '{parent_file}' parse failed: {exc}")
        return

    result.resolved_parent_assets.append({
        "class": parent_class,
        "path": str(parent_file),
        "status": "success" if parent_result.is_success else "failed",
        "warnings": parent_result.warnings,
        "errors": parent_result.errors,
    })
    result.logic_sources.append({
        "source": "parent_asset",
        "class": parent_class,
        "asset": str(parent_file),
        "status": "success" if parent_result.is_success else "failed",
    })
    if parent_result.graphs:
        from uasset_read.graph import format_graphs_json
        result.inherited_blueprint_graphs.extend(format_graphs_json(parent_result.graphs))
