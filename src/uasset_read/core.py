"""核心解析 API — 纯函数，无 argparse、无 sys.exit、无 print。

CLI、独立脚本、未来 Skill 共享此 API。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
import warnings

from uasset_read.batch_worker import BatchWorkerRequest, run_isolated_asset
from uasset_read.ir_builder import build_package_ir
from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker
from uasset_read.renderers import get_renderer, list_formats as _list_renderer_formats
from uasset_read.renderers.base import RenderOptions
from uasset_read.exceptions import ParseError as ParseError  # Re-export for backward compatibility

if TYPE_CHECKING:
    from uasset_read.memory_safety import MemoryPolicy


@dataclass
class BatchResult:
    """批量导出结果。"""
    total: int = 0
    success: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


def parse_single(
    file_path: str,
    format: str = "json",
    tolerant: bool = True,
    verbose: bool = False,
    include_schema: bool = False,
    include_function_graphs: bool = False,
    include_parent_assets: bool = False,
    asset_roots: list[str] | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    force_full_parse: bool = False,
    hex_view: bool = False,
    memory_policy: "MemoryPolicy | None" = None,
    output_level: str = "standard",
) -> str:
    """解析单个 .uasset/.umap，返回格式化字符串。

    纯函数，无 argparse、无 sys.exit、无 print。
    需要 linker 的格式内部自动选择 parse_uasset_with_linker。
    解析阶段使用集中式 MemoryPolicy 检查点。

    Args:
        file_path: .uasset/.umap 文件路径
        format: 输出格式（json, markdown）
        tolerant: 容错模式，遇到错误继续解析
        verbose: 详细输出
        include_schema: 包含 JSON Schema
        include_function_graphs: 包含函数图
        include_parent_assets: 解析父资产
        asset_roots: 资产根目录列表
        mappings_path: .usmap 映射文件路径
        game: 游戏名称
        force_full_parse: 强制完整解析大蓝图（忽略轻量模式阈值）
        hex_view: 启用 HexView 字节偏移追踪
        memory_policy: 可选内存策略
        output_level: 输出级别（standard/debug），standard 过滤 UI 属性和空字段

    Returns:
        格式化后的字符串

    Raises:
        ParseError: 解析失败
        ValueError: 渲染格式不存在
    """
    # 需要 linker 的格式
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
        )

    if not result.is_success and not _can_render_tolerant_json(result, format, tolerant):
        raise ParseError(f"Parse failed: {'; '.join(result.errors)}")

    if hex_view and result.hex_view_entries:
        from uasset_read.debug.hex_view import format_hex_view
        return format_hex_view(
            result.hex_view_entries,
            file_size=result.summary.uncompressed_size if result.summary else 0,
        )

    ir = build_package_ir(result)
    renderer = get_renderer(format)
    options = RenderOptions(
        verbose=verbose,
        include_schema=include_schema,
        include_function_graphs=include_function_graphs,
        linker_result=None,
        output_level=output_level,
    )
    return renderer.render(ir, options)


def _can_render_tolerant_json(result, format: str, tolerant: bool) -> bool:
    if not tolerant or format not in {"json"}:
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


def parse_batch(
    input_dir: str,
    format: str = "json",
    output_dir: str | None = None,
    tolerant: bool = True,
    verbose: bool = False,
    include_schema: bool = False,
    include_function_graphs: bool = False,
    include_parent_assets: bool = False,
    asset_roots: list[str] | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
    force_full_parse: bool = False,
    hex_view: bool = False,
    max_memory_usage: float = 0.85,  # 内存使用上限（85%）
    skip_large_files: bool | None = None,
    isolate_assets: bool = True,
    memory_policy: "MemoryPolicy | None" = None,
    output_level: str = "standard",
) -> BatchResult:
    """批量解析目录下所有 .uasset/.umap。

    Args:
        input_dir: 输入目录
        format: 输出格式
        output_dir: 输出目录（默认为 input_dir/output）
        tolerant: 容错模式
        verbose: 详细输出
        include_schema: 包含 JSON Schema
        include_function_graphs: 包含函数图
        include_parent_assets: 解析父资产
        asset_roots: 资产根目录列表
        mappings_path: .usmap 映射文件路径
        game: 游戏名称
        force_full_parse: 强制完整解析大蓝图（忽略轻量模式阈值）
        hex_view: 启用 HexView 字节偏移追踪
        max_memory_usage: 系统内存使用上限（0.0-1.0），超过时停止启动 worker
        skip_large_files: 已弃用；文件大小仅用于选择资源档位
        isolate_assets: 是否为每个资产启动独立子进程
        memory_policy: 可选内存策略
        output_level: 输出级别（standard/debug），standard 过滤 UI 属性和空字段

    Returns:
        BatchResult 包含成功、跳过、失败的文件列表

    Raises:
        ValueError: 目录不存在或没有资产文件
    """
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

    package_files = sorted([*input_path.glob("*.uasset"), *input_path.glob("*.umap")])
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

        out_file = output_path / f"{pf.stem}{extension}"
        try:
            if isolate_assets:
                request = BatchWorkerRequest(
                    file_path=str(pf),
                    output_path=str(out_file),
                    parse_options=parse_options,
                )
                outcome = run_isolated_asset(
                    request,
                    policy.limits_for_path(pf),
                    policy.poll_interval_seconds,
                )
                if outcome.succeeded:
                    result.success.append(outcome.output_path)
                else:
                    result.failed.append((str(pf), outcome.error))
                continue

            output_str = parse_single(str(pf), **parse_options)
            out_file.write_text(output_str, encoding="utf-8")
            result.success.append(str(out_file))
        except Exception as exc:
            result.failed.append((str(pf), f"{type(exc).__name__}: {exc}"))

    return result


def list_formats() -> list[str]:
    """返回所有支持的格式名列表。"""
    return _list_renderer_formats()
