"""核心解析 API — 纯函数，无 argparse、无 sys.exit、无 print。

CLI、独立脚本、未来 Skill 共享此 API。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

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
    # 需要 linker 的格式
    linker_formats = {"json", "json_summary", "cpp_skeleton"}

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
        linker_result=result if format == "cpp_skeleton" else None,
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

    Returns:
        BatchResult 包含成功、跳过、失败的文件列表

    Raises:
        ValueError: 目录不存在或没有资产文件
    """
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

    for pf in package_files:
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

            out_file = output_path / f"{pf.stem}{ext}"
            out_file.write_text(output_str, encoding="utf-8")
            result.success.append(str(out_file))
        except Exception as e:
            result.failed.append((str(pf), str(e)))

    return result


def list_formats() -> list[str]:
    """返回所有支持的格式名列表。"""
    return _list_renderer_formats()
