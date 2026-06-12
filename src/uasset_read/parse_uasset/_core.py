"""Core parsing functions — parse_package, parse_uasset, parse_uasset_with_linker."""
from __future__ import annotations

from typing import Any, Optional, Sequence, Callable

from uasset_read.package import PackageProvider
from uasset_read.models.result import ParseResult
from uasset_read.link.result import LinkerParseResult

from ._stages import (
    _ParseContext,
    _stage_open_bundle_and_archive,
    _stage_build_parse_context,
    _stage_read_core_tables,
    _stage_create_and_link_linker,
    _stage_preload_exports,
    _stage_run_post_load_and_post_process,
    _stage_finalize_result,
    _stage_cleanup,
)
from ._helpers import (
    _run_required_stage,
    _record_parse_stage_error,
)

import logging
logger = logging.getLogger(__name__)


def _parse_package_core(
    path: str,
    result: Any,
    tolerant: bool = True,
    provider: Optional["PackageProvider"] = None,
    mappings_path: Optional[str] = None,
    game: Optional[str] = None,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    extra_linker_setup: Optional[Callable] = None,
    lightweight_threshold: Optional[int] = None,
) -> None:
    """Shared core parsing logic — orchestrates 7-stage parsing pipeline.

    Args:
        path: File path
        result: ParseResult or LinkerParseResult instance (modified in place)
        tolerant: Tolerant mode
        provider: Package provider
        mappings_path: Type mapping file path
        game: Game identifier
        include_parent_assets: Whether to parse parent assets
        asset_roots: Asset root directory list
        extra_linker_setup: Callback after linker creation (linker, result) -> None
    """
    from uasset_read.serializers.package_summary import read_package_summary
    from uasset_read.exceptions import VersionError, ParseError

    ctx = _ParseContext(
        path=path, result=result, tolerant=tolerant, provider=provider,
        mappings_path=mappings_path, game=game, include_parent_assets=include_parent_assets,
        asset_roots=asset_roots, extra_linker_setup=extra_linker_setup,
        lightweight_threshold=lightweight_threshold,
    )
    try:
        _stage_open_bundle_and_archive(ctx)
        if ctx.aborted: return

        # Summary is read immediately after open (part of stage 2), then rest of tables in stage 3
        ctx.result.summary = _run_required_stage(
            result=ctx.result, archive=ctx.archive, path=ctx.path, tolerant=ctx.tolerant,
            stage="package_summary", field="summary",
            reader=lambda: read_package_summary(ctx.archive),
        )
        if ctx.result.summary is None:
            return

        _stage_build_parse_context(ctx)
        if ctx.aborted: return
        _stage_read_core_tables(ctx)
        if ctx.aborted: return
        _stage_create_and_link_linker(ctx)
        _stage_preload_exports(ctx)
        if ctx.aborted: return
        _stage_run_post_load_and_post_process(ctx)
        _stage_finalize_result(ctx)
    except VersionError as e:
        _record_parse_stage_error(ctx.result, ctx.archive, ctx.path, "version", "legacy_file_version", e)
        ctx.result.errors.append(str(e))
        ctx.result.is_success = False
        if not tolerant: raise
    except ParseError as e:
        _record_parse_stage_error(ctx.result, ctx.archive, ctx.path, "parse", "parse_error", e)
        ctx.result.errors.append(str(e))
        if e.partial_result:
            for key, value in e.partial_result.items():
                if hasattr(ctx.result, key):
                    setattr(ctx.result, key, value)
        ctx.result.is_success = False
        if not tolerant: raise
    except Exception as e:
        _record_parse_stage_error(ctx.result, ctx.archive, ctx.path, "parse", "unexpected", e)
        ctx.result.errors.append(f"Unexpected error: {str(e)}")
        ctx.result.is_success = False
        if not tolerant: raise
    finally:
        _stage_cleanup(ctx)


def parse_package(
    path: str,
    tolerant: bool = True,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    provider: Optional[PackageProvider] = None,
    mappings_path: Optional[str] = None,
    game: Optional[str] = None,
    lightweight_threshold: Optional[int] = None,
) -> ParseResult:
    """
    Main entry: parse Unreal package (.uasset or .umap).

    Args:
        path: .uasset/.umap file path
        tolerant: Whether to enable tolerant mode (default on)
        provider: Optional package provider (filesystem/pak/iostore)
        mappings_path: Type mapping file path
        game: Game identifier
        lightweight_threshold: Lightweight parse threshold

    Returns:
        ParseResult instance (with parsed data and error info)
    """
    result = ParseResult()

    _parse_package_core(
        path, result,
        tolerant=tolerant, provider=provider,
        mappings_path=mappings_path, game=game,
        include_parent_assets=include_parent_assets,
        asset_roots=asset_roots,
        lightweight_threshold=lightweight_threshold,
    )
    return result


def parse_uasset(
    path: str,
    tolerant: bool = True,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    mappings_path: Optional[str] = None,
    game: Optional[str] = None,
) -> ParseResult:
    """
    Compatibility entry: parse .uasset file.

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
    )


def parse_uasset_with_linker(
    path: str,
    tolerant: bool = True,
    preload_all: bool = False,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    provider: Optional[PackageProvider] = None,
    mappings_path: Optional[str] = None,
    game: Optional[str] = None,
    lightweight_threshold: Optional[int] = None,
) -> "LinkerParseResult":
    """Parallel parsing entry using PackageLinker (D-01, D-04).

    Args:
        path: .uasset file path
        tolerant: Whether to enable tolerant mode (default on)
        preload_all: Whether to preload all exports (default False, lazy loading)
        provider: Optional package provider (filesystem/pak/iostore)

    Returns:
        LinkerParseResult instance (with object graph and post-processing data)
    """
    result = LinkerParseResult()

    def extra_linker_setup(linker, res):
        res.all_objects = linker._import_objects + linker._export_objects
        res.root_objects = linker._root_objects

    _parse_package_core(
        path, result,
        tolerant=tolerant, provider=provider,
        mappings_path=mappings_path, game=game,
        include_parent_assets=include_parent_assets,
        asset_roots=asset_roots,
        extra_linker_setup=extra_linker_setup,
        lightweight_threshold=lightweight_threshold,
    )

    if preload_all and result.linker:
        for i in range(len(result.linker._export_objects)):
            try:
                result.linker.preload(i)
            except Exception as e:
                logger.warning("Failed to preload export %d, skipping: %s", i, e)

    return result
