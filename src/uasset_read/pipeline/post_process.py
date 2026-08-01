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
    """
    from uasset_read.kismet.bytecode_extractor import FUNCTION_EXPORT_CLASSES
    from uasset_read.serializers.object_resources import resolve_class_name
    from uasset_read.kismet.pipeline import decompile_single_function

    results = []
    for export in export_map:
        class_name = resolve_class_name(export.class_index, import_map, export_map)
        if class_name not in FUNCTION_EXPORT_CLASSES:
            continue
        try:
            result = decompile_single_function(
                archive, export, summary, name_map, import_map, export_map,
                tolerant=tolerant, linker=linker,
            )
            if result is not None:
                results.append(result)
        except (ParseError, OSError, struct.error, ValueError, KeyError, AttributeError) as e:
            # Per D-10: failure does NOT block pipeline
            # Log warning so caller can diagnose if needed
            logger.debug("Kismet decompile failed for export '%s': %s", export.object_name, e)
    return results


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
    from uasset_read.parse_uasset import parse_uasset_with_linker

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
