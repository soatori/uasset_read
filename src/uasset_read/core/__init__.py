"""核心解析 API — 纯函数，无 argparse、无 sys.exit、无 print。

CLI、独立脚本、未来 Skill 共享此 API。
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
    new_log_run_id,
    scoped_project_logging,
)
from uasset_read.renderers import get_renderer, list_formats as _list_renderer_formats
from uasset_read.renderers.base import RenderOptions
from uasset_read.exceptions import ParseError as ParseError, SemanticContractError  # Re-export for backward compatibility

if TYPE_CHECKING:
    from uasset_read.memory_safety import MemoryPolicy
    from uasset_read.config import ParseConfig
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """批量导出结果。"""
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
    """配置项目日志。

    优先使用 log_config（LogConfig 实例），旧风格参数保留兼容。
    """
    if log_config is not None:
        # 检测是否有旧参数也显式传入
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
                "同时传入 log_config 和旧风格日志参数，旧参数将被忽略。"
                "请统一使用 LogConfig。",
                DeprecationWarning,
                stacklevel=2,
            )
        return configure_project_logging(**log_config.to_configure_kwargs())

    # 旧风格路径
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
    """解析单个 .uasset/.umap，返回格式化字符串。

    纯函数，无 argparse、无 sys.exit、无 print。
    需要 linker 的格式内部自动选择 parse_uasset_with_linker。
    解析阶段使用集中式 MemoryPolicy 检查点。

    Args:
        file_path: .uasset/.umap 文件路径
        format: 输出格式（json, markdown）
        tolerant: 容错模式，遇到错误继续解析。None 表示使用 ParseConfig 或默认值 True
        verbose: 详细输出
        include_schema: 包含 JSON Schema
        include_parent_assets: 解析父资产。None 表示使用 ParseConfig 或默认值 False
        asset_roots: 资产根目录列表
        mappings_path: .usmap 映射文件路径
        game: 游戏名称
        force_full_parse: 强制完整解析大蓝图（忽略轻量模式阈值）。None 表示使用 ParseConfig 或默认值 False
        hex_view: 启用 HexView 字节偏移追踪。None 表示使用 ParseConfig 或默认值 False
        memory_policy: 可选内存策略
        output_level: 输出级别（standard/debug），standard 过滤 UI 属性和空字段
        log_config: 可选 LogConfig 实例，集中管理日志参数。
        parse_config: 可选 ParseConfig 实例，集中管理解析参数。

    Returns:
        格式化后的字符串

    Raises:
        ParseError: 解析失败
        ValueError: 渲染格式不存在
    """
    _VALID_OUTPUT_LEVELS = {"standard", "debug"}
    if output_level not in _VALID_OUTPUT_LEVELS:
        raise ValueError(
            f"Invalid output_level: {output_level!r}. "
            f"Expected one of ['standard', 'debug']"
        )

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
    """解析并渲染，返回 (output_str, parse_result)。

    parse_single 和 parse_batch 共用的核心逻辑。
    """
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

    if not result.is_success and not _can_render_tolerant_json(result, format, tolerant):
        raise ParseError(f"Parse failed: {'; '.join(result.errors)}")

    ir = build_package_ir(result)

    # 释放临时大对象，防止批量解析时内存累积
    try:
        for export in getattr(result, "export_map", []) or []:
            if hasattr(export, "_asset_type_data"):
                delattr(export, "_asset_type_data")
            if hasattr(export, "_uclass_native_fields"):
                delattr(export, "_uclass_native_fields")
    except Exception:
        logger.debug("批量清理临时大对象失败", exc_info=True)

    # JSON format: route through semantic pipeline
    if format == "json":
        from uasset_read.semantic.builder import build_semantic_ir
        from uasset_read.semantic.projection import project_semantic
        from uasset_read.semantic.validator import validate_semantic_document
        from uasset_read.semantic.render import render_semantic_json

        semantic_ir = build_semantic_ir(ir, source_path=file_path)
        semantic_ir = project_semantic(semantic_ir, output_level)
        validation_errors = validate_semantic_document(semantic_ir)
        if validation_errors:
            raise SemanticContractError(
                "Semantic contract violated: " + "; ".join(validation_errors)
            )
        return render_semantic_json(semantic_ir, include_schema=include_schema), result

    # Other formats: use renderer registry
    renderer = get_renderer(format)
    options = RenderOptions(
        verbose=verbose,
        include_schema=include_schema,
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
    include_parent_assets: bool | None = None,
    asset_roots: list[str] | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    force_full_parse: bool | None = None,
    hex_view: bool | None = None,
    max_memory_usage: float = 0.85,  # 内存使用上限（85%）
    skip_large_files: bool | None = None,
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
    """批量解析目录下所有 .uasset/.umap。

    Args:
        input_dir: 输入目录
        format: 输出格式
        output_dir: 输出目录（默认为 input_dir/output）
        tolerant: 容错模式
        verbose: 详细输出
        include_schema: 包含 JSON Schema
        include_parent_assets: 解析父资产
        asset_roots: 资产根目录列表
        mappings_path: .usmap 映射文件路径
        game: 游戏名称
        force_full_parse: 强制完整解析大蓝图（忽略轻量模式阈值）
        hex_view: 启用 HexView 字节偏移追踪
        max_memory_usage: 系统内存使用上限（0.0-1.0），超过时停止启动 worker
        skip_large_files: 已弃用；文件大小仅用于选择资源档位
        isolate_assets: 是否为每个资产启动独立子进程。True/False/\"auto\"（auto 根据文件大小自动选择）
        memory_policy: 可选内存策略
        output_level: 输出级别（standard/debug），standard 过滤 UI 属性和空字段

    Returns:
        BatchResult 包含成功、跳过、失败的文件列表

    Raises:
        ValueError: 目录不存在或没有资产文件
    """
    # 验证 isolate_assets 参数
    if not isinstance(isolate_assets, bool) and isolate_assets != "auto":
        raise ValueError(
            f"isolate_assets must be bool or 'auto', got {isolate_assets!r}"
        )

    _VALID_OUTPUT_LEVELS = {"standard", "debug"}
    if output_level not in _VALID_OUTPUT_LEVELS:
        raise ValueError(
            f"Invalid output_level: {output_level!r}. "
            f"Expected one of ['standard', 'debug']"
        )

    active_run_id = log_run_id or current_log_run_id() or new_log_run_id()
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

    if skip_large_files is not None:
        warnings.warn(
            "skip_large_files is deprecated; file size now selects an isolated "
            "worker resource tier",
            DeprecationWarning,
            stacklevel=2,
        )
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
    output_path.mkdir(parents=True, exist_ok=True)

    result = BatchResult(total=len(package_files))
    policy = memory_policy or MemoryPolicy()
    system_usage_limit = min(max_memory_usage, policy.system_usage_limit)

    if format.startswith("json"):
        extension = ".json"
    elif format == "markdown":
        extension = ".md"
    else:
        extension = f".{format}"

    parse_options = {
        "format": format,
        "tolerant": tolerant,
        "verbose": verbose,
        "include_schema": include_schema,
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

    # #346: 智能混合模式 — 将导入移到循环外部
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

        out_file = output_path / f"{pf.name}{extension}"
        try:
            # #346: 智能混合模式
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
                continue

            output_str, parse_result = _parse_and_render(
                str(pf),
                format=format,
                tolerant=tolerant,
                verbose=verbose,
                include_schema=include_schema,
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

            # 检查 partial 状态并追踪原因
            from uasset_read.models.status import _result_status, PARTIAL_STATUSES
            status = _result_status(parse_result)
            if status == "partial":
                result.partial.append(str(pf))
                for exp in (getattr(parse_result, "export_map", None) or []):
                    exp_status = getattr(exp, "parse_status", None)
                    if exp_status and exp_status in PARTIAL_STATUSES:
                        result.partial_reasons.setdefault(exp_status, []).append(str(pf))

            # 原子写入：先写临时文件再 replace，避免中断产生不完整输出（#434）
            tmp_fd = -1
            tmp_path = ""
            try:
                tmp_fd, tmp_path = tempfile.mkstemp(
                    dir=str(output_path.parent), suffix=".tmp"
                )
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp_f:
                    tmp_f.write(output_str)
                tmp_fd = -1  # fdopen 已接管 fd，无需再 close
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
            logging.getLogger(__name__).error("parse_batch asset failed: %s — %s", pf, error_msg)

    elapsed = time.monotonic() - start_time
    _log_batch_summary(result, elapsed_seconds=elapsed)
    return result


def list_formats() -> list[str]:
    """返回所有支持的格式名列表。"""
    formats = set(_list_renderer_formats())
    formats.add("json")  # json goes through semantic pipeline, not renderer registry
    return sorted(formats)


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
    """对比两个 .uasset 文件的文本摘要差异，返回 unified diff 输出。

    解析失败不会抛出异常，而是在 diff 输出中标注解析错误信息。
    当提供 writer 时，diff 写入流而不是返回字符串（流式输出）。

    Args:
        file_path1: 第一个 .uasset 文件路径
        file_path2: 第二个 .uasset 文件路径
        tolerant: 容错模式
        context_lines: diff 上下文行数
        mappings_path: 可选 .usmap/.jmap 类型映射
        game: 可选游戏名（启用游戏特定属性解析）
        force_full_parse: 是否强制完整蓝图解析
        writer: 可选输出流，提供时 diff 写入该流
        log_config: 可选 LogConfig 实例，集中管理日志参数。

    Returns:
        writer 为 None 时返回 unified diff 文本；否则返回空字符串
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
    """将 unified diff 流式写入 writer。

    逐行写入，不累积完整 diff 字符串。
    """
    import difflib

    # 解析文件 1
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
        text1 = f"[解析错误] {Path(file_path1).name}: {e}"

    # 解析文件 2
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
        text2 = f"[解析错误] {Path(file_path2).name}: {e}"

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
        writer.write(f"--- a/{name1}\n+++ b/{name2}\n（无差异）\n")
