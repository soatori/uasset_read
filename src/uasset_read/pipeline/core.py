"""Core parse pipeline -- parse_package(), parse_uasset_with_linker(), parse_package_lazy().

This module is the canonical location for the uasset parse lifecycle.
Extracted from ``uasset_read.parse_uasset`` as part of the pipeline
consolidation (task #458).
"""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING, Sequence, Callable
from pathlib import Path

if TYPE_CHECKING:
    from uasset_read.memory_safety import MemoryPolicy
    from uasset_read.config import ParseConfig

from uasset_read.memory_safety import ResourceBudget, MemoryLimitExceeded
from uasset_read.archive import FArchive
from uasset_read.exceptions import VersionError, ParseError
from uasset_read.package import PackageProvider
from uasset_read.models.result import ParseResult
from uasset_read.config import LogConfig
from uasset_read.project_logging import scoped_project_logging, configure_project_logging
from uasset_read.pipeline.stages import (
    _record_parse_stage_error,
    _init_parse_env,
    _read_core_tables,
    _read_secondary_tables,
    _parse_export_properties,
    _create_linker,
    _read_package_headers,
)
from uasset_read.pipeline.post_process import _post_process
from uasset_read.pipeline.config import (
    _apply_lightweight_parse,
    _resolve_parse_params,
)

logger = logging.getLogger(__name__)


def _cleanup_parse_memory(result) -> None:
    """Unified memory cleanup: break circular references, reset global caches.

    Called in the finally block of parse_package / parse_package_lazy to prevent
    memory leaks from UObjectInstance <-> linker circular references during batch parsing,
    and unbounded growth of global caches (ClassHandlerRegistry).
    """
    # Break UObjectInstance <-> linker circular references
    if result is not None and result.linker:
        try:
            if hasattr(result.linker, "_export_objects"):
                for obj in result.linker._export_objects:
                    obj.linker = None
            if hasattr(result.linker, "_import_objects"):
                for obj in result.linker._import_objects:
                    obj.linker = None
            result.linker._export_objects.clear()
            result.linker._import_objects.clear()
            result.linker._root_objects.clear()
            result.linker._preload_cache.clear()
            result.linker._archive = None
            logger.debug("linker circular references broken, export/import objects cleared")
        except Exception as e:
            logger.debug("linker circular reference cleanup exception, ignored: %s", e)

    # Reset global class_registry cache
    try:
        from uasset_read.parsers.class_registry import get_class_registry

        get_class_registry().reset_cache()
        logger.debug("class_registry.reset_cache() called")
    except Exception as e:
        logger.debug("class_registry.reset_cache() exception, ignored: %s", e)


def _cleanup_archive_diagnostics(result, archive) -> None:
    """Collect linker/FArchive diagnostics and close archive at the end."""
    if result.linker and getattr(result.linker, "diagnostics", None):
        result.diagnostics.extend(result.linker.diagnostics)
        # Aggregate linker BoundedEventBuffer truncation counts
        linker_diag_buf = getattr(result.linker, "_diagnostics", None)
        if linker_diag_buf is not None:
            result.diagnostics_dropped_count += getattr(linker_diag_buf, "dropped_count", 0)
    if archive:
        archive_diagnostics = archive.get_diagnostics()
        if archive_diagnostics:
            result.diagnostics = archive_diagnostics + result.diagnostics
        # Collect structured diagnostics
        structured_diags = archive.get_structured_diagnostics()
        if structured_diags:
            result.structured_diagnostics = structured_diags + result.structured_diagnostics
        # Propagate archive BoundedEventBuffer truncation counts
        result.diagnostics_dropped_count += archive.diagnostics_dropped_count
        result.hex_view_dropped_count += archive.hex_view_dropped_count
        if archive.is_hex_view_enabled():
            result.hex_view_entries = archive.get_hex_view_entries()
        archive.close()


def _run_linker_post_load(linker, result, tolerant: bool) -> None:
    """Execute linker.post_load() and handle exceptions."""
    if linker is None:
        return
    try:
        linker.post_load()
    except (OSError, struct.error, ValueError, AttributeError) as e:
        if not tolerant:
            raise ParseError(f"Linker post_load failed: {e}") from e
        result.errors.append(f"Linker post_load failed: {e}")
    # Propagate import verification errors from linker to result
    if hasattr(linker, "_import_verification_errors") and linker._import_verification_errors:
        result.errors.extend(linker._import_verification_errors)


def _parse_package_core(
    path: str,
    result,
    tolerant: bool | None = None,
    provider: PackageProvider | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    include_parent_assets: bool | None = None,
    asset_roots: Sequence[str] | None = None,
    extra_linker_setup: Callable | None = None,
    check_aes_key: bytes | None = None,
    lightweight_threshold: int | None = None,
    force_full_parse: bool | None = None,
    hex_view: bool | None = None,
    memory_policy: MemoryPolicy | None = None,
) -> None:
    """Shared core parse logic — read package and populate result.

    Args:
        path: File path
        result: ParseResult or ParseResult instance (modified in place)
        tolerant: Tolerant mode (None means use default True)
        provider: package provider
        mappings_path: Type mappings file path
        game: Game identifier
        include_parent_assets: Whether to parse parent assets (None means use default False)
        asset_roots: Asset root directory list
        extra_linker_setup: Extra callback after linker creation (linker, result) -> None
        check_aes_key: If provided, raises ParseError (parse_package compatibility)
        force_full_parse: Force full parse for large blueprints (None means use default False)
        hex_view: Enable HexView byte offset tracking (None means use default False)
    """
    # Resolve None to internal defaults
    if tolerant is None:
        tolerant = True
    if include_parent_assets is None:
        include_parent_assets = False
    if force_full_parse is None:
        force_full_parse = False
    if hex_view is None:
        hex_view = False

    from uasset_read.memory_safety import (
        MemoryMonitor,
        MemoryPolicy,
        ResourceBudget,
    )

    archive = None
    bundle = None

    file_path = Path(path)
    file_size = file_path.stat().st_size if file_path.is_file() else 0
    policy = memory_policy or MemoryPolicy()
    memory_monitor = MemoryMonitor(
        asset_path=path,
        limits=policy.limits_for_size(file_size),
    )
    budget = ResourceBudget()

    with memory_monitor:
        try:
            # Initialize environment
            init_result = _init_parse_env(
                path,
                result,
                tolerant,
                provider,
                mappings_path,
                game,
                check_aes_key,
                hex_view,
                budget=budget,
            )
            if init_result is None:
                return
            archive, bundle, mappings_provider = init_result

            # Read core tables (summary/name/import/export)
            if not _read_core_tables(
                archive,
                result,
                path,
                tolerant,
                memory_monitor,
                mappings_provider,
                budget=budget,
            ):
                return

            # Read secondary tables + create linker
            _read_secondary_tables(
                archive,
                result,
                tolerant,
                linker=None,
                mappings_provider=mappings_provider,
                path=path,
                memory_monitor=memory_monitor,
                budget=budget,
            )
            linker = _create_linker(
                archive,
                result.summary,
                result.name_map,
                result.import_map,
                result.export_map or [],
                result,
                tolerant=tolerant,
                version_container=result.version_container,
                extra_linker_setup=extra_linker_setup,
            )

            # Lightweight parse path (early return)
            if _apply_lightweight_parse(result, tolerant, lightweight_threshold, force_full_parse):
                return

            # Full parse: preload -> post_load -> post_process
            _parse_export_properties(
                archive,
                result,
                linker,
                tolerant,
                mappings_provider,
                game or "",
                memory_monitor,
                budget=budget,
            )
            memory_monitor.checkpoint("post_load")
            _run_linker_post_load(linker, result, tolerant)
            memory_monitor.checkpoint("post_process")

            _post_process(
                path,
                archive,
                result.summary,
                result.name_map,
                result.import_map,
                result.export_map or [],
                result,
                tolerant,
                linker=linker,
                include_parent_assets=include_parent_assets,
                asset_roots=asset_roots,
                archive_factory=lambda: (
                    bundle.open_archive(tolerant=tolerant) if bundle else FArchive(path, tolerant=tolerant)
                ),
                memory_policy=policy,
            )

            # Assign result.graphs to blueprint exports (IR builder reads from export.graphs)
            if result.graphs and result.export_map:
                for export in result.export_map:
                    name = str(getattr(export, "object_name", "") or "")
                    if name.endswith("_C") and not name.startswith("Default__"):
                        export.graphs = result.graphs
                        break  # Only assign to main blueprint export

            result.is_success = not result.errors

        except Exception as e:
            if isinstance(e, MemoryLimitExceeded):
                raise
            if isinstance(e, VersionError):
                _record_parse_stage_error(result, archive, path, "version", "legacy_file_version", e)
                result.is_success = False
            elif isinstance(e, ParseError):
                _record_parse_stage_error(result, archive, path, "parse", "parse_error", e)
                result.is_success = False
            elif isinstance(e, MemoryError):
                error_msg = f"MemoryError: {e}"
                if error_msg not in result.errors:
                    result.errors.append(error_msg)
                result.is_success = False
            else:
                _record_parse_stage_error(result, archive, path, "parse", "unexpected", e)
                result.is_success = False
            if not tolerant:
                raise

        finally:
            _cleanup_archive_diagnostics(result, archive)


@scoped_project_logging
def parse_package(
    path: str,
    tolerant: bool | None = None,
    include_parent_assets: bool | None = None,
    asset_roots: Sequence[str] | None = None,
    provider: PackageProvider | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    lightweight_threshold: int | None = None,
    force_full_parse: bool | None = None,
    hex_view: bool | None = None,
    memory_policy: MemoryPolicy | None = None,
    config: ParseConfig | None = None,
    log_config: LogConfig | None = None,
) -> ParseResult:
    """
    Main entry point: parse Unreal package (.uasset or .umap).

    Args:
        path: .uasset/.umap file path
        tolerant: Whether to enable tolerant mode (default enabled)
        provider: Optional package provider (filesystem/pak/iostore)
        force_full_parse: Force full parse for large blueprints (ignore lightweight threshold)
        hex_view: Enable HexView byte offset tracking
        config: Optional ParseConfig instance for centralized parameter management.
            When config is passed, legacy-style individual parameters can still override
            config values (but mixing is not recommended).

    Returns:
        ParseResult instance (containing parse data and error messages)
    """
    result = ParseResult()

    # Merge config and legacy parameters
    core_kwargs = _resolve_parse_params(
        config,
        {
            "tolerant": tolerant,
            "include_parent_assets": include_parent_assets,
            "asset_roots": asset_roots,
            "mappings_path": mappings_path,
            "game": game,
            "force_full_parse": force_full_parse,
            "hex_view": hex_view,
            "lightweight_threshold": lightweight_threshold,
            "memory_policy": memory_policy,
        },
    )

    _parse_package_core(
        path,
        result,
        provider=provider,
        **core_kwargs,
    )
    _cleanup_parse_memory(result)
    return result


def parse_uasset(
    path: str,
    tolerant: bool | None = None,
    include_parent_assets: bool | None = None,
    asset_roots: Sequence[str] | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    force_full_parse: bool | None = None,
    memory_policy: MemoryPolicy | None = None,
    config: ParseConfig | None = None,
) -> ParseResult:
    """
    Compatibility entry point: parse .uasset files.

    Internally delegates to parse_package(), so sidecar payload discovery is
    shared with .umap/package parsing.
    """
    return parse_package(
        path,
        tolerant=tolerant,
        include_parent_assets=include_parent_assets,
        asset_roots=asset_roots,
        mappings_path=mappings_path,
        game=game,
        force_full_parse=force_full_parse,
        memory_policy=memory_policy,
        config=config,
    )


@scoped_project_logging
def parse_uasset_with_linker(
    path: str,
    tolerant: bool | None = None,
    preload_all: bool = False,
    include_parent_assets: bool | None = None,
    asset_roots: Sequence[str] | None = None,
    provider: PackageProvider | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    lightweight_threshold: int | None = None,
    force_full_parse: bool | None = None,
    hex_view: bool | None = None,
    memory_policy: MemoryPolicy | None = None,
    config: ParseConfig | None = None,
    log_config: LogConfig | None = None,
) -> "ParseResult":
    """Parse entry point using PackageLinker (D-01, D-04).

    Args:
        path: .uasset file path
        tolerant: Whether to enable tolerant mode (default enabled)
        preload_all: Whether to preload all exports (default False, lazy loading)
        provider: Optional package provider (filesystem/pak/iostore)
        force_full_parse: Force full parse for large blueprints (ignore lightweight threshold)
        hex_view: Enable HexView byte offset tracking
        config: Optional ParseConfig instance for centralized parameter management.

    Returns:
        ParseResult instance (containing object graph and post-processed data)
    """
    # Lazy import of extras module (per #117 core/extras layering)
    # Only configure logging when caller explicitly provides log_config;
    # the library itself must not create log sessions.
    if log_config:
        configure_project_logging(**log_config.to_configure_kwargs())

    result = ParseResult()

    def extra_linker_setup(linker, res):
        res.all_objects = linker._import_objects + linker._export_objects
        res.root_objects = linker._root_objects

    # Merge config and legacy parameters
    core_kwargs = _resolve_parse_params(
        config,
        {
            "tolerant": tolerant,
            "include_parent_assets": include_parent_assets,
            "asset_roots": asset_roots,
            "mappings_path": mappings_path,
            "game": game,
            "force_full_parse": force_full_parse,
            "hex_view": hex_view,
            "lightweight_threshold": lightweight_threshold,
            "memory_policy": memory_policy,
        },
    )

    _parse_package_core(
        path,
        result,
        provider=provider,
        extra_linker_setup=extra_linker_setup,
        **core_kwargs,
    )

    if preload_all and result.linker:
        for i in range(len(result.linker._export_objects)):
            try:
                result.linker.preload(i)
            except ParseError as e:
                logger.warning("Failed to preload export %d, skipping: %s", i, e)
            except Exception as e:
                logger.exception("Unexpected error preloading export %d: %s", i, e)

    return result


def parse_package_lazy(
    path: str,
    export_indices: list[int] | None = None,
    store_raw_bytes: bool = False,
    tolerant: bool = True,
    provider: PackageProvider | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    memory_policy: MemoryPolicy | None = None,
) -> ParseResult:
    """Lazy-loading mode package parsing — parse export bodies on demand.

    Always parses: Header, NameMap, ImportMap, ExportMap (metadata).
    Only parses body for specified export_indices; when not specified, all exports are marked as not loaded.

    When provider offers open_file(), it is preferred for obtaining the archive (supports mmap
    range reads) to avoid loading the entire file into memory; otherwise falls back to read_file() path.

    Args:
        path: .uasset/.umap file path
        export_indices: List of export indices whose bodies need parsing, None means skip all
        store_raw_bytes: Whether to store export body raw bytes in lazy_load_archive
            (default False — lazy loading scenario does not cache raw bytes to save memory)
        tolerant: Tolerant mode
        provider: Optional package provider
        mappings_path: Type mappings file path
        game: Game identifier
        memory_policy: Memory policy

    Returns:
        ParseResult instance (export bodies parsed on demand)
    """
    result = ParseResult()
    archive = None
    linker = None
    budget = ResourceBudget()

    # When provider offers open_file(), use it directly to obtain archive,
    # to avoid loading the entire file into memory via open_package_bundle().
    # open_file() supports mmap range reads, suitable for lazy loading scenarios.
    use_direct_archive = (
        provider is not None and hasattr(provider, "open_file") and callable(getattr(provider, "open_file", None))
    )

    try:
        mappings_provider = None
        if mappings_path:
            from uasset_read.mappings import TypeMappingsProvider

            mappings_provider = TypeMappingsProvider.from_file(mappings_path, budget=budget)
            result.metadata["mappings_path"] = mappings_path
        if game:
            result.metadata["game"] = game

        if use_direct_archive and provider is not None:
            # Fast path: obtain archive via open_file(), do not read entire file
            archive = provider.open_file(path)
            if archive is None:
                raise FileNotFoundError(f"Package not found: {path}")

            # Read core tables
            if not _read_core_tables(
                archive,
                result,
                path,
                tolerant,
                validate_range=True,
                budget=budget,
            ):
                if result.summary is None:
                    return result

            # Read secondary tables
            _read_secondary_tables(
                archive,
                result,
                tolerant,
                linker=None,
                mappings_provider=mappings_provider,
                path=path,
                memory_monitor=None,
                budget=budget,
            )
        else:
            # Fallback path: read via bundle (read_file)
            bundle_obj, archive, linker, mappings_provider = _read_package_headers(
                path,
                result,
                tolerant=tolerant,
                provider=provider,
                mappings_path=mappings_path,
                game=game,
                budget=budget,
            )
            if result.summary is None:
                return result

        # Parse specified export bodies on demand -- delegate to shared implementation
        parse_indices = set(export_indices) if export_indices else set()

        _parse_export_properties(
            archive,
            result,
            linker,
            tolerant,
            mappings_provider,
            game or "",
            memory_monitor=None,  # No memory monitor in lazy path (diagnostic only)
            budget=budget,
            export_indices=parse_indices,
            store_raw_bytes=store_raw_bytes,
        )

        # post_load
        if linker is not None:
            try:
                linker.post_load()
            except (OSError, struct.error, ValueError, AttributeError) as e:
                if not tolerant:
                    raise ParseError(f"Linker post_load failed: {e}") from e
                result.errors.append(f"Linker post_load failed: {e}")
            # Propagate import verification errors from linker to result
            if hasattr(linker, "_import_verification_errors") and linker._import_verification_errors:
                result.errors.extend(linker._import_verification_errors)

        result.is_success = not result.errors
        result.metadata["lazy_loading"] = True
        result.metadata["loaded_exports"] = sorted(parse_indices)
        result.metadata["total_exports"] = len(result.export_map or [])

    except VersionError as e:
        _record_parse_stage_error(result, archive, path, "version", "legacy_file_version", e)
        result.is_success = False
        if not tolerant:
            raise
    except ParseError as e:
        _record_parse_stage_error(result, archive, path, "parse", "parse_error", e)
        result.is_success = False
        if not tolerant:
            raise
    except Exception as e:
        _record_parse_stage_error(result, archive, path, "parse", "unexpected", e)
        result.is_success = False
        if not tolerant:
            raise
    finally:
        if archive:
            archive.close()
        _cleanup_parse_memory(result)

    return result
