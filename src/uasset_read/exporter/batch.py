"""批量导出 — 将多个 .uasset/.umap 文件导出到结构化目录。

等价于 的 TryWriteToDir 模式。
目录结构：
    output_dir/
      BP_MyBlueprint/
        blueprint.json
      BP_Another/
        blueprint.json
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.exporter.base import ExportOptions


@dataclass
class BatchExportResult:
    """批量导出结果。"""
    success: list[str] = field(default_factory=list)          # 成功导出的文件路径
    failed: list[tuple[str, str]] = field(default_factory=list)  # (file_path, error_message)
    skipped: list[tuple[str, str]] = field(default_factory=list) # (file_path, reason)

    @property
    def total(self) -> int:
        return len(self.success) + len(self.failed) + len(self.skipped)

    @property
    def has_failures(self) -> bool:
        return bool(self.failed)


class BatchExporter:
    """批量导出器。

    将多个 .uasset/.umap 文件解析并导出到指定目录结构。
    """

    def __init__(self, output_dir: str, options: "ExportOptions"):
        self.output_dir = Path(output_dir)
        self.options = options

    def export_files(self, file_paths: list[str]) -> BatchExportResult:
        """导出多个 .uasset/.umap 文件。

        Args:
            file_paths: .uasset 文件路径列表

        Returns:
            BatchExportResult 包含成功/失败/跳过信息
        """
        result = BatchExportResult()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        for file_path in file_paths:
            try:
                self._export_single(file_path, result)
            except Exception as e:
                result.failed.append((file_path, str(e)))

        return result

    def _export_single(self, file_path: str, batch_result: BatchExportResult) -> None:
        """导出单个文件。"""
        from uasset_read.parse_uasset import parse_package, parse_uasset_with_linker
        from uasset_read.exporter.base import IExporter

        # 解析
        try:
            # cpp_skeleton 需要 linker
            if self.options.format in ("cpp_skeleton", "cpp_json_ir"):
                parse_result = parse_uasset_with_linker(
                    file_path,
                    tolerant=self.options.tolerant,
                    include_parent_assets=self.options.include_parent_assets,
                    asset_roots=self.options.asset_roots,
                )
            else:
                parse_result = parse_package(
                    file_path,
                    tolerant=self.options.tolerant,
                    include_parent_assets=self.options.include_parent_assets,
                    asset_roots=self.options.asset_roots,
                )
        except Exception as e:
            batch_result.failed.append((file_path, f"parse error: {e}"))
            return

        if not parse_result.is_success:
            batch_result.skipped.append((file_path, "parse failed"))
            return

        # 确定输出目录和文件名
        asset_name = self._derive_asset_name(parse_result)
        out_dir = self.output_dir / asset_name
        out_dir.mkdir(parents=True, exist_ok=True)

        # 构建输出路径
        ext = self._file_extension()
        out_path = out_dir / f"blueprint{ext}"

        # 导出
        from uasset_read.exporter.registry import ExporterRegistry
        try:
            exporter = ExporterRegistry.get(self.options.format)
        except ValueError as e:
            batch_result.failed.append((file_path, str(e)))
            return

        try:
            file_options = self._options
            file_options.output_path = str(out_path)
            exporter.export_to_file(parse_result, file_options)
            batch_result.success.append(str(out_path))
        except Exception as e:
            batch_result.failed.append((file_path, f"export error: {e}"))

    def _derive_asset_name(self, parse_result) -> str:
        """从解析结果派生资产名称作为目录名。"""
        # 优先使用 blueprint 名称
        if hasattr(parse_result, 'blueprint') and parse_result.blueprint:
            bp = parse_result.blueprint
            if hasattr(bp, 'blueprint_name') and bp.blueprint_name:
                return bp.blueprint_name

        # 使用包名
        if hasattr(parse_result, 'summary') and parse_result.summary:
            summary = parse_result.summary
            if hasattr(summary, 'package_name') and summary.package_name:
                return summary.package_name

        # 回退到文件名
        return Path(str(parse_result)).stem if hasattr(parse_result, '__str__') else "unknown"

    def _file_extension(self) -> str:
        """根据格式返回文件扩展名。"""
        ext_map = {
            "json": ".json",
            "json_summary": ".json",
            "text": ".txt",
            "text_summary": ".txt",
            "markdown": ".md",
            "blueprint_text": ".txt",
            "n2c": ".n2c.json",
            "cpp_skeleton": ".h",
            "cpp_json_ir": ".cpp.json",
        }
        return ext_map.get(self.options.format, ".txt")

    @property
    def _options(self):
        """返回可替换的 ExportOptions 副本。"""
        import dataclasses
        return dataclasses.replace(self.options)
