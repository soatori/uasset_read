"""Core parse API — pure functions, no argparse, no sys.exit, no print.

CLI, standalone scripts, and future Skills share this API.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, TYPE_CHECKING
import logging
import os
import tempfile
import warnings

from uasset_read.batch_worker import BatchWorkerRequest, run_isolated_asset
from uasset_read.config import LogConfig
from uasset_read.ir_builder import build_package_ir
from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker
from uasset_read.project_logging import (
    configure_project_logging,
    current_log_run_id,
    log_context,
    new_log_run_id,
    scoped_project_logging,
    set_last_parse_result,
)
from uasset_read.renderers import get_renderer, list_formats as _list_renderer_formats
from uasset_read.renderers.base import RenderOptions, validate_output_level
from uasset_read.exceptions import ParseError as ParseError  # Re-export for backward compatibility

if TYPE_CHECKING:
    from uasset_read.memory_safety import MemoryPolicy
    from uasset_read.config import ParseConfig
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """Batch export result."""
    total: int = 0
    success: list[str] = field(default_factory=list)
    partial: list[str] = field(default_factory=list)
    partial_reasons: dict[str, list[str]] = field(default_factory=dict)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    failed: list[tuple[str, str, str]] = field(default_factory=list)  # (path, error, details)


def _log_batch_summary(result: BatchResult, elapsed_seconds: float = 0) -> None:
    logging.getLogger(__name__).info(
        "batch_summary total=%d success=%d partial=%d skipped=%d failed=%d elapsed=%.1fs",
        result.total,
        len(result.success),
        len(result.partial),
        len(result.skipped),
        len(result.failed),
        elapsed_seconds,
    )


def _log_asset_summary(
    name: str, result: object, *, duration_ms: float = 0.0,
) -> None:
    """Emit per-asset summary line within a batch loop."""
    from uasset_read.project_logging import _count_export_categories

    parse_status = getattr(result, "status", "unknown")
    export_count = len(getattr(result, "export_map", None) or [])
    diagnostics_count = (
        len(getattr(result, "diagnostics", None) or [])
        + getattr(result, "diagnostics_dropped_count", 0)
    )
    error_count = len(getattr(result, "errors", None) or [])
    warning_count = len(getattr(result, "warnings", None) or [])
    cats = _count_export_categories(result)
    with log_context(asset=name):
        logging.getLogger(__name__).info(
            "asset_summary input=%s parse_status=%s duration_ms=%.1f "
            "exports=%d diagnostics=%d fallback=%d opaque=%d "
            "recovery=%d errors=%d warnings=%d",
            name, parse_status, duration_ms,
            export_count, diagnostics_count,
            cats["fallback"], cats["opaque"], cats["recovery"],
            error_count, warning_count,
        )


def _configure_logging(
    *,
    log_config: LogConfig | None = None,
    log_level: str | None = None,
    log_dir: str | None = None,
    log_enabled: bool = True,
    log_run_id: str | None = None,
    log_keep_latest: int | None = None,
    log_max_total_bytes: int | None = None,
    log_cleanup: bool = False,
    log_max_bytes: int = 10_000_000,
    log_backup_count: int = 5,
):
    """Configure project logging.

    Prefer log_config (LogConfig instance); legacy parameters kept for compatibility.
    """
    if log_config is not None:
        # Check if legacy parameters were also explicitly passed
        has_legacy = any(v is not None and v != {
            "log_level": None, "log_dir": None, "log_run_id": None,
            "log_keep_latest": None, "log_max_total_bytes": None,
        }.get(k) for k, v in {
            "log_level": log_level, "log_dir": log_dir,
            "log_run_id": log_run_id, "log_keep_latest": log_keep_latest,
            "log_max_total_bytes": log_max_total_bytes,
        }.items())
        if has_legacy:
            warnings.warn(
                "Both log_config and legacy log parameters provided; "
                "legacy parameters will be ignored. "
                "Use LogConfig instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        return configure_project_logging(**log_config.to_configure_kwargs())

    # Legacy-style path
    effective_enabled = log_enabled and log_level != "off"
    if (
        log_level is None
        and log_dir is None
        and log_enabled is True
        and log_run_id is None
        and log_keep_latest is None
        and log_max_total_bytes is None
        and log_cleanup is False
        and log_max_bytes == 10_000_000
        and log_backup_count == 5
    ):
        return None
    kwargs = {
        "level": log_level or "DEBUG",
        "log_dir": log_dir,
        "enabled": effective_enabled,
        "max_bytes": log_max_bytes,
        "backup_count": log_backup_count,
    }
    if log_run_id is not None:
        kwargs["run_id"] = log_run_id
    if log_keep_latest is not None:
        kwargs["keep_latest"] = log_keep_latest
    if log_max_total_bytes is not None:
        kwargs["max_total_bytes"] = log_max_total_bytes
    if log_cleanup:
        kwargs["cleanup"] = True
    return configure_project_logging(**kwargs)


@scoped_project_logging
def parse_single(
    file_path: str,
    format: str = "json",
    tolerant: bool | None = None,
    verbose: bool = False,
    include_schema: bool = False,
    include_function_graphs: bool = False,
    include_parent_assets: bool | None = None,
    asset_roots: list[str] | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    force_full_parse: bool | None = None,
    hex_view: bool | None = None,
    memory_policy: "MemoryPolicy | None" = None,
    output_level: str = "standard",
    log_level: str | None = None,
    log_dir: str | None = None,
    log_enabled: bool = True,
    log_run_id: str | None = None,
    log_keep_latest: int | None = None,
    log_max_total_bytes: int | None = None,
    log_cleanup: bool = False,
    log_max_bytes: int = 10_000_000,
    log_backup_count: int = 5,
    log_config: LogConfig | None = None,
    parse_config: "ParseConfig | None" = None,
) -> str:
    """Parse a single .uasset/.umap, return formatted string.

    Pure function, no argparse, no sys.exit, no print.
    Formats requiring a linker internally select parse_uasset_with_linker.
    Parse phase uses centralized MemoryPolicy checkpoints.

    Args:
        file_path: .uasset/.umap file path
        format: Output format (json, markdown)
        tolerant: Fault-tolerant mode, continue parsing on error. None means use ParseConfig or default True
        verbose: Verbose output
        include_schema: Include JSON Schema
        include_function_graphs: Include function graphs
        include_parent_assets: Parse parent assets. None means use ParseConfig or default False
        asset_roots: Asset root directory list
        mappings_path: .usmap mapping file path
        game: Game name
        force_full_parse: Force full parse of large blueprints (ignore lightweight mode threshold). None means use ParseConfig or default False
        hex_view: Enable HexView byte offset tracking. None means use ParseConfig or default False
        memory_policy: Optional memory policy
        output_level: Output level (standard/debug), standard filters UI properties and empty fields
        log_config: Optional LogConfig instance for centralized log parameter management.
        parse_config: Optional ParseConfig instance for centralized parse parameter management.

    Returns:
        Formatted string

    Raises:
        ParseError: Parse failed
        ValueError: Render format does not exist
    """
    validate_output_level(output_level)
    # #423: Skip reconfiguration when scoped_project_logging already owns the session.
    # A set _configured_run_id means the scoped wrapper already configured logging,
    # regardless of whether log_config is None or not.
    already_configured = current_log_run_id() is not None
    if not already_configured:
        _configure_logging(
            log_config=log_config,
            log_level=log_level,
            log_dir=log_dir,
            log_enabled=log_enabled,
            log_run_id=log_run_id,
            log_keep_latest=log_keep_latest,
            log_max_total_bytes=log_max_total_bytes,
            log_cleanup=log_cleanup,
            log_max_bytes=log_max_bytes,
            log_backup_count=log_backup_count,
        )

    output_str, _ = _parse_and_render(
        file_path,
        format=format,
        tolerant=tolerant,
        verbose=verbose,
        include_schema=include_schema,
        include_function_graphs=include_function_graphs,
        include_parent_assets=include_parent_assets,
        asset_roots=asset_roots,
        mappings_path=mappings_path,
        game=game,
        force_full_parse=force_full_parse,
        hex_view=hex_view,
        memory_policy=memory_policy,
        output_level=output_level,
        parse_config=parse_config,
    )
    return output_str


def _parse_and_render(
    file_path: str,
    *,
    format: str = "json",
    tolerant: bool | None = None,
    verbose: bool = False,
    include_schema: bool = False,
    include_function_graphs: bool = False,
    include_parent_assets: bool | None = None,
    asset_roots: list[str] | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    force_full_parse: bool | None = None,
    hex_view: bool | None = None,
    memory_policy: "MemoryPolicy | None" = None,
    output_level: str = "standard",
    parse_config: "ParseConfig | None" = None,
) -> tuple[str, "ParseResult | LinkerParseResult"]:
    """Parse and render, return (output_str, parse_result).

    Core logic shared by parse_single and parse_batch.
    """
    set_last_parse_result(None)

    linker_formats = {"json"}

    if format in linker_formats:
        result = parse_uasset_with_linker(
            file_path,
            tolerant=tolerant,
            include_parent_assets=include_parent_assets,
            asset_roots=asset_roots,
            mappings_path=mappings_path,
            game=game,
            force_full_parse=force_full_parse,
            hex_view=hex_view,
            memory_policy=memory_policy,
            config=parse_config,
        )
    else:
        result = parse_package(
            file_path,
            tolerant=tolerant,
            include_parent_assets=include_parent_assets,
            asset_roots=asset_roots,
            mappings_path=mappings_path,
            game=game,
            force_full_parse=force_full_parse,
            hex_view=hex_view,
            memory_policy=memory_policy,
            config=parse_config,
        )

    set_last_parse_result(result)

    if not result.is_success and not _can_render_tolerant_json(result, format, tolerant):
        raise ParseError(f"Parse failed: {'; '.join(result.errors)}")

    ir = build_package_ir(result)

    # Release temporary large objects to prevent memory accumulation during batch parsing
    try:
        for export in getattr(result, "export_map", []) or []:
            if hasattr(export, "_asset_type_data"):
                delattr(export, "_asset_type_data")
            if hasattr(export, "_uclass_native_fields"):
                delattr(export, "_uclass_native_fields")
    except Exception:
        logger.debug("Failed to clean up temporary large objects in batch", exc_info=True)

    renderer = get_renderer(format)
    options = RenderOptions(
        verbose=verbose,
        include_schema=include_schema,
        include_function_graphs=include_function_graphs,
        output_level=output_level,
        hex_view=hex_view,
    )
    return renderer.render(ir, options), result


def _can_render_tolerant_json(result, format: str, tolerant: bool | None) -> bool:
    if (tolerant is not None and not tolerant) or format not in {"json"}:
        return False
    from uasset_read.link.result import LinkerParseResult
    from uasset_read.models.result import ParseResult

    if not isinstance(result, (ParseResult, LinkerParseResult)):
        return False
    if getattr(result, "diagnostics", None):
        return True
    if getattr(result, "metadata", None):
        return True
    if getattr(result, "summary", None) is not None:
        return True
    if getattr(result, "name_map", None):
        return True
    if getattr(result, "import_map", None) or getattr(result, "export_map", None):
        return True
    return False


@scoped_project_logging
def parse_batch(
    input_dir: str,
    format: str = "json",
    output_dir: str | None = None,
    tolerant: bool | None = None,
    verbose: bool = False,
    include_schema: bool = False,
    include_function_graphs: bool = False,
    include_parent_assets: bool | None = None,
    asset_roots: list[str] | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    force_full_parse: bool | None = None,
    hex_view: bool | None = None,
    max_memory_usage: float = 0.85,  # Memory usage limit (85%)
    isolate_assets: bool | str = True,  # True/False/"auto"
    memory_policy: "MemoryPolicy | None" = None,
    output_level: str = "standard",
    log_level: str | None = None,
    log_dir: str | None = None,
    log_enabled: bool = True,
    log_run_id: str | None = None,
    log_keep_latest: int | None = None,
    log_max_total_bytes: int | None = None,
    log_cleanup: bool = False,
    log_max_bytes: int = 10_000_000,
    log_backup_count: int = 5,
    log_config: LogConfig | None = None,
    parse_config: "ParseConfig | None" = None,
) -> BatchResult:
    """Batch parse all .uasset/.umap in a directory.

    Args:
        input_dir: Input directory
        format: Output format
        output_dir: Output directory (defaults to input_dir/output)
        tolerant: Fault-tolerant mode
        verbose: Verbose output
        include_schema: Include JSON Schema
        include_function_graphs: Include function graphs
        include_parent_assets: Parse parent assets
        asset_roots: Asset root directory list
        mappings_path: .usmap mapping file path
        game: Game name
        force_full_parse: Force full parse of large blueprints (ignore lightweight mode threshold)
        hex_view: Enable HexView byte offset tracking
        max_memory_usage: System memory usage limit (0.0-1.0), stops spawning workers when exceeded
        skip_large_files: Deprecated; file size is only used for tier selection
        isolate_assets: Whether to spawn a separate subprocess per asset. True/False/\"auto\" (auto selects based on file size)
        memory_policy: Optional memory policy
        output_level: Output level (standard/debug), standard filters UI properties and empty fields

    Returns:
        BatchResult containing lists of succeeded, skipped, and failed files

    Raises:
        ValueError: Directory does not exist or contains no asset files
    """
    validate_output_level(output_level)
    # Validate isolate_assets parameter
    if not isinstance(isolate_assets, bool) and isolate_assets != "auto":
        raise ValueError(
            f"isolate_assets must be bool or 'auto', got {isolate_assets!r}"
        )

    active_run_id = log_run_id or current_log_run_id() or new_log_run_id()
    # #423: Skip reconfiguration when scoped_project_logging already owns the session.
    # A set _configured_run_id means the scoped wrapper already configured logging,
    # regardless of whether log_config is None or not.
    already_configured = current_log_run_id() is not None
    if not already_configured:
        _configure_logging(
            log_config=log_config,
            log_level=log_level,
            log_dir=log_dir,
            log_enabled=log_enabled,
            log_run_id=active_run_id,
            log_keep_latest=log_keep_latest,
            log_max_total_bytes=log_max_total_bytes,
            log_cleanup=log_cleanup,
            log_max_bytes=log_max_bytes,
            log_backup_count=log_backup_count,
        )

    from uasset_read.memory_safety import MemoryPolicy, get_memory_stats

    if not 0.0 < max_memory_usage <= 1.0:
        raise ValueError("max_memory_usage must be in (0.0, 1.0]")

    input_path = Path(input_dir)
    if not input_path.is_dir():
        raise ValueError(f"Not a directory: {input_dir}")

    package_files = sorted([*input_path.rglob("*.uasset"), *input_path.rglob("*.umap")])
    if not package_files:
        raise ValueError(f"No .uasset/.umap files found in {input_dir}")

    if output_dir is None:
        output_dir = str(input_path / "output")
    output_path = Path(output_dir)

    result = BatchResult(total=len(package_files))
    policy = memory_policy or MemoryPolicy()
    system_usage_limit = min(max_memory_usage, policy.system_usage_limit)

    if format.startswith("json"):
        extension = ".json"
    elif format == "markdown":
        extension = ".md"
    else:
        extension = f".{format}"

    output_files = {pf: output_path / f"{pf.stem}{extension}" for pf in package_files}
    output_collisions: dict[Path, list[Path]] = {}
    for pf, out_file in output_files.items():
        output_collisions.setdefault(out_file, []).append(pf)
    colliding_outputs = {
        out_file: inputs
        for out_file, inputs in output_collisions.items()
        if len(inputs) > 1
    }
    if colliding_outputs:
        details = "; ".join(
            f"{out_file}: {', '.join(str(pf) for pf in inputs)}"
            for out_file, inputs in colliding_outputs.items()
        )
        raise ValueError(f"Multiple input files resolve to the same output path: {details}")

    output_path.mkdir(parents=True, exist_ok=True)

    parse_options = {
        "format": format,
        "tolerant": tolerant,
        "verbose": verbose,
        "include_schema": include_schema,
        "include_function_graphs": include_function_graphs,
        "include_parent_assets": include_parent_assets,
        "asset_roots": asset_roots,
        "mappings_path": mappings_path,
        "game": game,
        "force_full_parse": force_full_parse,
        "hex_view": hex_view,
        "memory_policy": policy,
        "output_level": output_level,
    }
    if parse_config is not None:
        parse_options["parse_config"] = parse_config

    # #346: Smart hybrid mode — move imports outside the loop
    if isolate_assets == "auto":
        from uasset_read.memory_safety import should_isolate, check_file_size, FileSizeTier

    import time
    start_time = time.monotonic()

    for idx, pf in enumerate(package_files):
        stats = get_memory_stats()
        if stats.usage_percent > system_usage_limit:
            reason = (
                f"System memory usage {stats.usage_percent * 100:.1f}% exceeds "
                f"{system_usage_limit * 100:.1f}%"
            )
            for remaining in package_files[idx:]:
                result.skipped.append((str(remaining), reason))
            break

        out_file = output_files[pf]
        try:
            # #346: Smart hybrid mode
            if isolate_assets == "auto":
                file_size = check_file_size(pf)
                tier = FileSizeTier.from_size(file_size)
                actual_isolate = should_isolate(file_size, tier)
            else:
                actual_isolate = bool(isolate_assets)

            if actual_isolate:
                request = BatchWorkerRequest(
                    file_path=str(pf),
                    output_path=str(out_file),
                    parse_options=parse_options,
                    logging_options={
                        "enabled": log_enabled if log_config is None else log_config.enabled,
                        "level": (log_level or "DEBUG") if log_config is None else (log_config.level or "DEBUG"),
                        "log_dir": log_dir if log_config is None else log_config.dir,
                        "run_id": active_run_id,
                    },
                )
                outcome = run_isolated_asset(
                    request,
                    policy.limits_for_path(pf),
                    policy.poll_interval_seconds,
                )
                if outcome.succeeded:
                    result.success.append(outcome.output_path)
                else:
                    result.failed.append((str(pf), outcome.error, outcome.error_details))
                    # #423: Log worker error details inside the session so they
                    # appear in the caller-specified log file, not just stderr.
                    logging.getLogger(__name__).error(
                        "parse_batch worker failed: %s\n%s",
                        outcome.error,
                        outcome.error_details,
                    )
                continue

            asset_start = time.monotonic()
            output_str, parse_result = _parse_and_render(
                str(pf),
                format=format,
                tolerant=tolerant,
                verbose=verbose,
                include_schema=include_schema,
                include_function_graphs=include_function_graphs,
                include_parent_assets=include_parent_assets,
                asset_roots=asset_roots,
                mappings_path=mappings_path,
                game=game,
                force_full_parse=force_full_parse,
                hex_view=hex_view,
                memory_policy=policy,
                output_level=output_level,
                parse_config=parse_config,
            )
            asset_duration_ms = (time.monotonic() - asset_start) * 1000

            # Per-asset summary for non-isolated batch assets
            _log_asset_summary(pf.name, parse_result, duration_ms=asset_duration_ms)

            # Check partial status and track reasons
            from uasset_read.models.status import _result_status, PARTIAL_STATUSES
            status = _result_status(parse_result)
            if status == "partial":
                result.partial.append(str(pf))
                for exp in (getattr(parse_result, "export_map", None) or []):
                    exp_status = getattr(exp, "parse_status", None)
                    if exp_status and exp_status in PARTIAL_STATUSES:
                        result.partial_reasons.setdefault(exp_status, []).append(str(pf))

            # Atomic write: write to temp file then replace, prevents incomplete output on interruption (#434)
            tmp_fd = -1
            tmp_path = ""
            try:
                tmp_fd, tmp_path = tempfile.mkstemp(
                    dir=str(output_path.parent), suffix=".tmp"
                )
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp_f:
                    tmp_f.write(output_str)
                tmp_fd = -1  # fdopen has taken ownership of fd, no need to close
                os.replace(tmp_path, str(out_file))
            except BaseException:
                if tmp_fd >= 0:
                    os.close(tmp_fd)
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
            result.success.append(str(out_file))
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            error_msg = f"{type(exc).__name__}: {exc}"
            result.failed.append((str(pf), error_msg, tb))
            # #423: Log full traceback inside the session so it appears in the
            # caller-specified log file, not just in BatchResult.failed.
            logging.getLogger(__name__).error(
                "parse_batch asset failed: %s — %s\n%s",
                pf, error_msg, tb,
            )

    elapsed = time.monotonic() - start_time
    _log_batch_summary(result, elapsed_seconds=elapsed)
    return result


def list_formats() -> list[str]:
    """Return list of all supported format names."""
    return _list_renderer_formats()


@scoped_project_logging
def diff_single(
    file_path1: str,
    file_path2: str,
    *,
    tolerant: bool | None = None,
    context_lines: int = 3,
    mappings_path: str | None = None,
    game: str | None = None,
    force_full_parse: bool | None = None,
    writer: IO[str] | None = None,
    log_level: str | None = None,
    log_dir: str | None = None,
    log_enabled: bool = True,
    log_run_id: str | None = None,
    log_keep_latest: int | None = None,
    log_max_total_bytes: int | None = None,
    log_cleanup: bool = False,
    log_max_bytes: int = 10_000_000,
    log_backup_count: int = 5,
    log_config: LogConfig | None = None,
) -> str:
    """Compare text summary differences of two .uasset files, return unified diff output.

    Parse failures do not raise exceptions; instead, parse error messages are annotated in the diff output.
    When a writer is provided, the diff is written to the stream instead of returning a string (streaming output).

    Args:
        file_path1: First .uasset file path
        file_path2: Second .uasset file path
        tolerant: Fault-tolerant mode
        context_lines: Number of diff context lines
        mappings_path: Optional .usmap/.jmap type mapping
        game: Optional game name (enables game-specific property parsing)
        force_full_parse: Whether to force full blueprint parsing
        writer: Optional output stream; when provided, diff is written to this stream
        log_config: Optional LogConfig instance for centralized log parameter management.

    Returns:
        Unified diff text when writer is None; empty string otherwise
    """
    _configure_logging(
        log_config=log_config,
        log_level=log_level,
        log_dir=log_dir,
        log_enabled=log_enabled,
        log_run_id=log_run_id,
        log_keep_latest=log_keep_latest,
        log_max_total_bytes=log_max_total_bytes,
        log_cleanup=log_cleanup,
        log_max_bytes=log_max_bytes,
        log_backup_count=log_backup_count,
    )

    if writer is None:
        from io import StringIO
        buf = StringIO()
        _diff_to(
            file_path1, file_path2, buf,
            tolerant=tolerant,
            context_lines=context_lines,
            mappings_path=mappings_path,
            game=game,
            force_full_parse=force_full_parse,
        )
        return buf.getvalue()
    _diff_to(
        file_path1, file_path2, writer,
        tolerant=tolerant,
        context_lines=context_lines,
        mappings_path=mappings_path,
        game=game,
        force_full_parse=force_full_parse,
    )
    return ""


def _diff_to(
    file_path1: str,
    file_path2: str,
    writer: IO[str],
    *,
    tolerant: bool | None = None,
    context_lines: int = 3,
    mappings_path: str | None = None,
    game: str | None = None,
    force_full_parse: bool | None = None,
) -> None:
    """Stream unified diff to writer.

    Writes line by line without accumulating the full diff string.
    """
    import difflib

    # Parse file 1
    try:
        text1 = parse_single(
            file_path1,
            format="json",
            tolerant=tolerant,
            verbose=False,
            mappings_path=mappings_path,
            game=game,
            force_full_parse=force_full_parse,
        )
    except Exception as e:
        text1 = f"[Parse error] {Path(file_path1).name}: {e}"

    # Parse file 2
    try:
        text2 = parse_single(
            file_path2,
            format="json",
            tolerant=tolerant,
            verbose=False,
            mappings_path=mappings_path,
            game=game,
            force_full_parse=force_full_parse,
        )
    except Exception as e:
        text2 = f"[Parse error] {Path(file_path2).name}: {e}"

    name1 = Path(file_path1).name
    name2 = Path(file_path2).name

    lines1 = text1.splitlines(keepends=True)
    lines2 = text2.splitlines(keepends=True)

    diff = difflib.unified_diff(
        lines1,
        lines2,
        fromfile=f"a/{name1}",
        tofile=f"b/{name2}",
        n=context_lines,
    )

    wrote_any = False
    for line in diff:
        writer.write(line)
        wrote_any = True

    if not wrote_any:
        writer.write(f"--- a/{name1}\n+++ b/{name2}\n(no differences)\n")
