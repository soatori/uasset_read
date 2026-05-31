"""导出接口抽象与配置 — ExportOptions dataclass + IExporter ABC。

ExporterOptions 统一管理所有导出选项（格式、schema、输出路径等）。
IExporter 定义导出器的标准契约。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult


@dataclass
class ExportOptions:
    """统一导出配置。

    受 ExporterOptions 启发，但针对蓝图解析场景简化。
    """
    # 输出格式：json / json_summary / text / text_summary / markdown /
    #           blueprint_text / n2c / cpp_skeleton / cpp_json_ir
    format: str = "json"

    # 通用选项
    include_schema: bool = False
    include_function_graphs: bool = False
    verbose: bool = False

    # 输出目标
    output_path: str | None = None   # None = stdout, 文件路径 = 写入文件
    output_dir: str | None = None    # 批量模式：输出目录

    # 验证
    validate_output: bool = False


class ExportValidationError(Exception):
    """输出验证失败。"""
    pass


class IExporter(ABC):
    """导出器抽象基类。

    每个具体导出器实现此接口，内部调用现有 formatter 函数。
    """

    @abstractmethod
    def export(self, result: ParseResult | LinkerParseResult, options: ExportOptions) -> str:
        """将解析结果导出为字符串。

        Args:
            result: ParseResult 或 LinkerParseResult
            options: 导出配置

        Returns:
            导出内容的字符串形式
        """
        ...

    def export_to_file(self, result: ParseResult | LinkerParseResult, options: ExportOptions) -> str:
        """导出并写入文件。

        Args:
            result: ParseResult 或 LinkerParseResult
            options: 导出配置（必须设置 output_path）

        Returns:
            写入的文件路径

        Raises:
            ValueError: output_path 未设置
            ExportValidationError: 验证失败
            IOError: 写入失败
        """
        content = self.export(result, options)

        # 验证
        if options.validate_output and self.validates_against_schema:
            errors = self.validate(result, options)
            if errors:
                raise ExportValidationError(f"{self.format_name} validation failed: {'; '.join(errors)}")

        # 写入
        path = options.output_path
        if not path:
            raise ValueError("output_path must be set for export_to_file")

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def validate(self, result: ParseResult | LinkerParseResult, options: ExportOptions) -> list[str]:
        """验证导出内容。默认返回空列表（不支持验证的导出器）。

        子类可重写以实现具体验证逻辑（如 N2CExporter）。
        """
        return []

    @property
    @abstractmethod
    def format_name(self) -> str:
        """此导出器处理的格式名称。"""
        ...

    @property
    def validates_against_schema(self) -> bool:
        """此导出器是否支持 schema 验证。"""
        return False
