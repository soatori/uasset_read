"""核心解析 API — 纯函数，无 argparse、无 sys.exit、无 print。

CLI、独立脚本、未来 Skill 共享此 API。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
import logging
_logger = logging.getLogger(__name__)

from uasset_read.ir_builder import build_package_ir
from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker
from uasset_read.renderers import get_renderer, list_formats as _list_renderer_formats
from uasset_read.renderers.base import RenderOptions
from uasset_read.exceptions import ParseError as ParseError  # Re-export for backward compatibility

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


@dataclass
class BatchResult:
    """批量导出结果。"""
    total: int = 0
    success: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    skipped_large: list[tuple[str, str]] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


def _sanitize_filename_component(value: object, fallback: str) -> str:
    """Return a single safe filename component."""
    safe = "".join(
        ch if ch.isalnum() or ch in {".", "_", "-"} else "_"
        for ch in str(value)
    )
    safe = safe.replace("..", "_").strip("._-")
    return safe or fallback


def _safe_output_path(output_path: Path, stem: object, ext: str) -> Path:
    safe_stem = _sanitize_filename_component(stem, "asset")
    safe_ext = _sanitize_filename_component(ext.lstrip("."), "out")
    candidate = (output_path / f"{safe_stem}.{safe_ext}").resolve()
    output_root = output_path.resolve()
    try:
        candidate.relative_to(output_root)
    except ValueError as exc:
        raise ValueError(f"Unsafe output path escaped output directory: {candidate}") from exc
    return candidate


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
    *,
    max_file_size_mb: float | None = None,
) -> str:
    """解析单个 .uasset/.umap，返回格式化字符串。

    纯函数，无 argparse、无 sys.exit、无 print。
    需要 linker 的格式内部自动选择 parse_uasset_with_linker。

    Args:
        file_path: .uasset/.umap 文件路径
        format: 输出格式（json, json_summary, text, markdown 等）
        tolerant: 容错模式，遇到错误继续解析
        verbose: 详细输出
        include_schema: 包含 JSON Schema
        include_function_graphs: 包含函数图
        include_parent_assets: 解析父资产
        asset_roots: 资产根目录列表
        mappings_path: .usmap 映射文件路径
        game: 游戏名称

    Returns:
        格式化后的字符串

    Raises:
        ParseError: 解析失败
        ValueError: 渲染格式不存在
    """
    from uasset_read.constants import DEFAULT_MAX_PARSE_SIZE_MB, WARN_FILE_SIZE_MB
    from uasset_read.memory import get_file_size_mb

    # --- 文件大小保护 ---
    # 解析有效限制值：None → 默认值，0/inf → 禁用
    effective_limit = (
        DEFAULT_MAX_PARSE_SIZE_MB if max_file_size_mb is None else max_file_size_mb
    )
    check_enabled = effective_limit not in (0, float("inf"))

    if check_enabled:
        file_size_mb = get_file_size_mb(file_path)
        if file_size_mb > effective_limit:
            raise ParseError(
                f"File too large: {file_size_mb:.1f} MB exceeds "
                f"max_file_size_mb={effective_limit:.0f} MB. "
                f"Increase max_file_size_mb or pass max_file_size_mb=0 to disable this check."
            )
        if file_size_mb >= WARN_FILE_SIZE_MB:
            _logger.warning(
                "Parsing large file: %s (%.1f MB). "
                "Memory usage will be high. Consider using parse_batch() with memory guards.",
                Path(file_path).name,
                file_size_mb,
            )

    # cpp_skeleton 走独立管线（不经过标准渲染器注册表）
    if format == "cpp_skeleton":
        from uasset_read.renderers.cpp_skeleton_renderer import CppSkeletonRenderer
        result = parse_uasset_with_linker(
            file_path,
            tolerant=tolerant,
            include_parent_assets=include_parent_assets,
            asset_roots=asset_roots,
            mappings_path=mappings_path,
            game=game,
        )
        if not result.is_success and not tolerant:
            raise ParseError(f"Parse failed: {'; '.join(result.errors)}")
        pipeline = CppSkeletonRenderer()
        return pipeline.generate(result)

    # 需要 linker 的格式
    linker_formats = {"json", "json_summary"}

    if format in linker_formats:
        result = parse_uasset_with_linker(
            file_path,
            tolerant=tolerant,
            include_parent_assets=include_parent_assets,
            asset_roots=asset_roots,
            mappings_path=mappings_path,
            game=game,
        )
    else:
        result = parse_package(
            file_path,
            tolerant=tolerant,
            include_parent_assets=include_parent_assets,
            asset_roots=asset_roots,
            mappings_path=mappings_path,
            game=game,
        )

    if not result.is_success and not _can_render_tolerant_json(result, format, tolerant):
        raise ParseError(f"Parse failed: {'; '.join(result.errors)}")

    # 构建 IR
    ir = build_package_ir(result)

    # 渲染
    renderer = get_renderer(format)
    options = RenderOptions(
        verbose=verbose,
        include_schema=include_schema,
        include_function_graphs=include_function_graphs,
    )
    return renderer.render(ir, options)


def _can_render_tolerant_json(result, format: str, tolerant: bool) -> bool:
    if not tolerant or format not in {"json", "json_summary"}:
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
    *,
    max_file_size_mb: float | None = None,
    batch_size: int = 50,
    max_memory_percent: float = 70.0,
    memory_check: Callable[[], Any] | None = None,
) -> BatchResult:
    """批量解析目录下所有 .uasset/.umap。

    内存安全参数:
        max_file_size_mb: 单文件最大 MB，超过则跳过。
            None → 使用 batch 默认值 500 MB（比单文件的 1000 MB 更保守）。
            设为 0 或 float('inf') 禁用检查。
        batch_size: 每批处理文件数，批间执行 GC（默认 50）
        max_memory_percent: 系统内存已用百分比上限（默认 70%）
        memory_check: 自定义内存检查回调，返回 MemoryCheckResult。
            为 None 时使用内置 MemoryMonitor。设为 lambda: None 跳过检查。

    Returns:
        BatchResult 包含成功、跳过、跳过（超大）、失败的文件列表
    """
    from uasset_read.memory import MemoryMonitor, MemoryStatus, force_gc, get_file_size_mb

    # None → batch 保守默认值（比 parse_single 的 1000 MB 更保守）
    effective_max_file_size = 500.0 if max_file_size_mb is None else max_file_size_mb

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

    # 内存监控初始化
    if memory_check is None:
        monitor = MemoryMonitor(max_memory_percent=max_memory_percent)
        memory_check = monitor.check

    processed_in_batch = 0

    for pf in package_files:
        # 1. 大文件检查（effective_max_file_size <= 0 或 inf 时禁用）
        file_size_mb = get_file_size_mb(pf)
        check_size = effective_max_file_size not in (0, float("inf"))
        if check_size and file_size_mb > effective_max_file_size:
            reason = f"file too large: {file_size_mb:.1f} MB > {effective_max_file_size:.0f} MB limit"
            result.skipped_large.append((str(pf), reason))
            continue

        # 2. 内存检查
        check_result = memory_check()
        if check_result is not None and hasattr(check_result, "state"):
            if check_result.state == MemoryStatus.CRITICAL:
                reason = f"memory critical: {check_result.used_percent:.0f}% used"
                result.skipped.append((str(pf), reason))
                continue

        # 3. 解析文件
        try:
            output_str = parse_single(
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
                max_file_size_mb=effective_max_file_size,
            )
            # 确定输出文件扩展名
            if format.startswith("json"):
                ext = ".json"
            elif format == "markdown":
                ext = ".md"
            elif format == "text":
                ext = ".txt"
            else:
                ext = f".{format}"

            out_file = _safe_output_path(output_path, pf.stem, ext)
            out_file.write_text(output_str, encoding="utf-8")
            result.success.append(str(out_file))
        except Exception as e:
            result.failed.append((str(pf), str(e)))

        # 4. 分批 GC
        processed_in_batch += 1
        if processed_in_batch >= batch_size:
            force_gc()
            processed_in_batch = 0

    # 最终 GC
    force_gc()

    return result


def list_formats() -> list[str]:
    """返回所有支持的格式名列表。"""
    return _list_renderer_formats()
