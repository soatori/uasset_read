"""Parse pipeline stage functions — each stage handles one phase of parsing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, List, Sequence, Callable

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.link.linker import PackageLinker
    from uasset_read.package import PackageBundle, PackageProvider

from uasset_read.exceptions import ParseError
from uasset_read.serializers.package_summary import (
    read_package_summary, read_name_table, read_depends_map,
    read_preload_dependencies, validate_export_data_range,
    read_soft_package_references,
)
from uasset_read.serializers.object_resources import (
    read_import_map, read_export_map, read_soft_object_paths,
)
from uasset_read.versioning import build_version_container
from uasset_read.parsers.property_parser import parse_properties_from_export
from uasset_read.blueprint import extract_component_transforms

from ._helpers import (
    _run_required_stage,
    _should_use_lightweight_tolerant_parse,
    _build_lightweight_function_graphs,
    _package_metadata,
    _record_parse_stage_error,
)

import logging
logger = logging.getLogger(__name__)


@dataclass
class _ParseContext:
    """Parsing pipeline context — state passed between stages."""
    path: str
    result: Any
    tolerant: bool = True
    provider: Any = None
    mappings_path: Optional[str] = None
    game: Optional[str] = None
    include_parent_assets: bool = False
    asset_roots: Optional[Sequence[str]] = None
    extra_linker_setup: Optional[Callable] = None
    lightweight_threshold: Optional[int] = None
    bundle: Any = None
    archive: Any = None
    mappings_provider: Any = None
    linker: Any = None
    aborted: bool = False

    def abort(self) -> None:
        self.aborted = True


def _stage_open_bundle_and_archive(ctx: _ParseContext) -> None:
    """Stage 1: Open mappings, bundle, archive; extract mmap info."""
    if ctx.mappings_path:
        from uasset_read.mappings import TypeMappingsProvider
        ctx.mappings_provider = TypeMappingsProvider.from_file(ctx.mappings_path)
        ctx.result.metadata["mappings_path"] = ctx.mappings_path
    if ctx.game:
        ctx.result.metadata["game"] = ctx.game

    from uasset_read.package import open_package_bundle
    ctx.bundle = open_package_bundle(ctx.path, provider=ctx.provider, tolerant=ctx.tolerant)
    ctx.archive = ctx.bundle.open_archive(tolerant=ctx.tolerant)
    ctx.result.metadata.update(_package_metadata(ctx.bundle))

    # Extract mmap info
    mmap_info = ctx.archive.get_mmap_info()
    ctx.result.mmap_used = mmap_info["used"]
    ctx.result.mmap_warning = mmap_info["warning"]


def _stage_build_parse_context(ctx: _ParseContext) -> None:
    """Stage 2: Set engine family, version config, validate export data range."""
    # Set engine family and version config (UE4/UE5 compatibility)
    file_version_ue5 = getattr(ctx.result.summary, 'file_version_ue5', 0)
    legacy_file_version = getattr(ctx.result.summary, 'legacy_file_version', -9)
    file_version_ue4 = getattr(ctx.result.summary, 'file_version_ue4', 0)

    if file_version_ue5 == 0 and legacy_file_version > -6:
        ctx.result.engine_family = "ue4"
        ctx.result.compatibility_mode = "compatibility"
    else:
        ctx.result.engine_family = "ue5"
        ctx.result.compatibility_mode = "native"

    # Build version config
    from uasset_read.package_version_profile import build_version_profile
    ctx.result.version_profile = build_version_profile(
        legacy_file_version=legacy_file_version,
        file_version_ue4=file_version_ue4,
        file_version_ue5=file_version_ue5,
    )

    ctx.result.version_container = build_version_container(ctx.result.summary)

    # Truncated file detection: validate export data range
    try:
        validate_export_data_range(ctx.archive, ctx.result.summary)
    except Exception as e:
        if not ctx.tolerant:
            raise
        _record_parse_stage_error(
            ctx.result, ctx.archive, ctx.path, "package_summary", "export_data_range", e
        )
        ctx.abort()


def _stage_read_core_tables(ctx: _ParseContext) -> None:
    """Stage 3: Read name_map, import_map, export_map, depends, soft refs."""
    # Read name table
    ctx.result.name_map = _run_required_stage(
        result=ctx.result, archive=ctx.archive, path=ctx.path, tolerant=ctx.tolerant,
        stage="name_table", field="name_map",
        reader=lambda: read_name_table(ctx.archive, ctx.result.summary),
    )
    if ctx.result.name_map is None:
        ctx.result.name_map = []
        ctx.abort()
        return

    # Read import table
    ctx.result.import_map = _run_required_stage(
        result=ctx.result, archive=ctx.archive, path=ctx.path, tolerant=ctx.tolerant,
        stage="import_map", field="import_map",
        reader=lambda: read_import_map(ctx.archive, ctx.result.summary, ctx.result.name_map),
    )
    if ctx.result.import_map is None:
        ctx.result.import_map = []
        ctx.abort()
        return

    # Read export table
    ctx.result.export_map = _run_required_stage(
        result=ctx.result, archive=ctx.archive, path=ctx.path, tolerant=ctx.tolerant,
        stage="export_map", field="export_map",
        reader=lambda: read_export_map(ctx.archive, ctx.result.summary, ctx.result.name_map),
    )
    if ctx.result.export_map is None:
        ctx.result.export_map = []
        ctx.abort()
        return

    # Read DependsMap (dependency table) and PreloadDependencies (preload dependencies)
    if hasattr(ctx.result.summary, 'depends_offset'):
        ctx.result.summary.depends_map = read_depends_map(ctx.archive, ctx.result.summary)
    if hasattr(ctx.result.summary, 'preload_dependency_count'):
        ctx.result.summary.preload_dependencies = read_preload_dependencies(ctx.archive, ctx.result.summary)

    # Read SoftPackageReferences (soft package reference table)
    if hasattr(ctx.result.summary, 'soft_package_references_count') and ctx.result.summary.soft_package_references_count > 0:
        ctx.result.soft_package_references = read_soft_package_references(ctx.archive, ctx.result.summary, ctx.result.name_map)

    # Read SoftObjectPathList (UE5.7+ for indexed SoftObjectProperty parsing)
    if hasattr(ctx.result.summary, 'soft_object_paths_count') and ctx.result.summary.soft_object_paths_count > 0:
        ctx.result.soft_object_path_list = read_soft_object_paths(
            ctx.archive, ctx.result.summary, ctx.result.name_map
        )
    else:
        ctx.result.soft_object_path_list = []

    # Store soft_object_path_list on summary for property parser access
    setattr(ctx.result.summary, '_soft_object_path_list', ctx.result.soft_object_path_list)


def _stage_create_and_link_linker(ctx: _ParseContext) -> None:
    """Stage 4: Create PackageLinker, execute link() and extra_linker_setup."""
    try:
        from uasset_read.link.linker import PackageLinker
        ctx.linker = PackageLinker(
            ctx.archive, ctx.result.summary, ctx.result.name_map,
            ctx.result.import_map, ctx.result.export_map or [],
            version_container=ctx.result.version_container,
        )
        ctx.linker.link()
        ctx.result.linker = ctx.linker

        if ctx.extra_linker_setup is not None:
            ctx.extra_linker_setup(ctx.linker, ctx.result)

        # NOTE: post_load() is deferred until after export preloading (link → preload → post_load)
    except Exception as e:
        if not ctx.tolerant:
            raise ParseError(f"Linker creation failed: {e}") from e
        ctx.result.errors.append(f"Linker creation failed: {e}")


def _stage_preload_exports(ctx: _ParseContext) -> None:
    """Stage 5: Preload export properties (linker.preload or parse_properties_from_export)."""
    if _should_use_lightweight_tolerant_parse(ctx.result, ctx.tolerant, ctx.lightweight_threshold):
        ctx.result.warnings.append(
            "Lightweight tolerant parse used due to export complexity "
            f"(exports={getattr(ctx.result.summary, 'export_count', 0)})"
        )
        ctx.result.metadata["lightweight_tolerant_parse"] = True
        ctx.result.metadata["function_graphs_fallback"] = _build_lightweight_function_graphs(ctx.result.export_map)
        ctx.result.is_success = len(ctx.result.errors) == 0
        ctx.abort()
        return

    # Parse ExportMap properties — unified dispatch via linker.preload() (link → preload → post_load)
    _mappings = ctx.mappings_provider.mappings if ctx.mappings_provider else None
    for _exp_idx, export in enumerate(ctx.result.export_map or []):
        if export.serial_size > 0:
            try:
                if ctx.linker is not None:
                    ctx.linker.preload(
                        _exp_idx,
                        mappings=_mappings,
                        game=ctx.game,
                        tolerant=ctx.tolerant,
                    )
                    # Backward compatibility: copy linker instance properties back to export.properties
                    inst = ctx.linker._export_objects[_exp_idx]
                    export.properties = inst.serialized_properties
                else:
                    export.properties = parse_properties_from_export(
                        export, ctx.archive, ctx.result.summary, ctx.result.name_map,
                        ctx.result.export_map or [], ctx.result.import_map,
                        linker=ctx.linker,
                        mappings=_mappings,
                        game=ctx.game,
                        tolerant=ctx.tolerant,
                    )
                if not getattr(export, "parse_status", None):
                    setattr(export, "parse_status", "success")
                elif getattr(export, "parse_status", None) in ("opaque", "partial_metadata"):
                    # Maintain status set by asset type handler, don't override as success
                    pass
            except Exception as e:
                if not ctx.tolerant:
                    raise ParseError(f"Property parse error in {export.object_name}: {e}") from e
                ctx.result.errors.append(f"Property parse error in {export.object_name}: {e}")
                export.properties = []
                setattr(export, "parse_status", "failed")
                setattr(export, "fallback_reason", "parse_error")
                setattr(export, "error_message", str(e))

            # Extract component transform properties
            if export.properties:
                export.transforms = extract_component_transforms(export.properties)


def _stage_run_post_load_and_post_process(ctx: _ParseContext) -> None:
    """Stage 6: Execute post_load and _post_process."""
    # post_load — executed after all export preloading (link → preload → post_load)
    if ctx.linker is not None:
        try:
            ctx.linker.post_load()
        except Exception as e:
            if not ctx.tolerant:
                raise ParseError(f"Linker post_load failed: {e}") from e
            ctx.result.errors.append(f"Linker post_load failed: {e}")

    # Shared post-processing
    from ._helpers import _post_process
    _post_process(
        ctx.path, ctx.archive, ctx.result.summary, ctx.result.name_map,
        ctx.result.import_map, ctx.result.export_map or [], ctx.result, ctx.tolerant,
        linker=ctx.linker,
        include_parent_assets=ctx.include_parent_assets,
        asset_roots=ctx.asset_roots,
        archive_factory=lambda: ctx.bundle.open_archive(tolerant=ctx.tolerant) if ctx.bundle else FArchive(ctx.path, tolerant=ctx.tolerant),
    )


def _stage_finalize_result(ctx: _ParseContext) -> None:
    """Stage 7: Set is_success flag."""
    ctx.result.is_success = len(ctx.result.errors) == 0


def _stage_cleanup(ctx: _ParseContext) -> None:
    """Cleanup: collect diagnostics, close archive, release linker reference, reset caches."""
    # Collect linker diagnostics (PackageIndex out of bounds, serial_offset/size anomalies, etc.)
    if ctx.result.linker and getattr(ctx.result.linker, 'diagnostics', None):
        ctx.result.diagnostics.extend(ctx.result.linker.diagnostics)
    if ctx.archive:
        # Collect FArchive diagnostics (truncation detection, offset overflow, etc.)
        archive_diagnostics = ctx.archive.get_diagnostics()
        if archive_diagnostics:
            ctx.result.diagnostics = archive_diagnostics + ctx.result.diagnostics
        ctx.archive.close()

    # Task 8: Release linker reference to archive, allow GC to reclaim (#107-6)
    if ctx.result.linker is not None:
        ctx.result.linker._archive = None

    # Task 9: Reset Kismet class-level caches to prevent unbounded growth during batch parsing (#107-7)
    from uasset_read.kismet.archive import FKismetArchive
    FKismetArchive.reset_warned_offsets()

    # Task 10: Reset BPGC bytecode cache (#107-9)
    from uasset_read.kismet.bytecode_extractor import reset_bpgc_cache
    reset_bpgc_cache()

    # Task 11: Clear ClassHandlerRegistry caches (#108)
    from uasset_read.parsers.class_registry import reset_default_registry_cache
    reset_default_registry_cache()
