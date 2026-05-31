"""导出器注册表 — 格式名到导出器的映射与分发。

等价于 的 Exporter 工厂模式。
使用类方法注册表，支持自动注册和手动注册。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Type

if TYPE_CHECKING:
    from uasset_read.exporter.base import IExporter
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult


class ExporterRegistry:
    """导出器注册表。

    单例模式的类方法注册表，支持：
    - 自动注册（导出器模块 import 时调用）
    - 手动注册（ExporterRegistry.register(name, class)）
    - 格式分发（ExporterRegistry.get(name)）
    - 格式列表（ExporterRegistry.list_formats()）
    """

    _exporters: Dict[str, Type["IExporter"]] = {}

    @classmethod
    def register(cls, format_name: str, exporter_class: Type["IExporter"]) -> None:
        """注册一个格式名到导出器类的映射。

        Args:
            format_name: 格式名称（如 "json", "markdown"）
            exporter_class: 实现 IExporter 的类

        Raises:
            ValueError: 格式名已注册
        """
        if format_name in cls._exporters:
            raise ValueError(f"Export format '{format_name}' is already registered")
        cls._exporters[format_name] = exporter_class

    @classmethod
    def get(cls, format_name: str) -> "IExporter":
        """获取指定格式的导出器实例。

        Args:
            format_name: 格式名称

        Returns:
            IExporter 实例

        Raises:
            ValueError: 未知格式
        """
        exporter_class = cls._exporters.get(format_name)
        if exporter_class is None:
            available = ", ".join(sorted(cls._exporters.keys()))
            raise ValueError(f"Unknown export format: '{format_name}'. Available: {available}")
        return exporter_class()

    @classmethod
    def list_formats(cls) -> list[str]:
        """返回所有已注册的格式名。"""
        return sorted(cls._exporters.keys())

    @classmethod
    def clear(cls) -> None:
        """清空注册表（主要用于测试）。"""
        cls._exporters.clear()


def export(result: ParseResult | LinkerParseResult, format: str = "json", **kwargs) -> str:
    """便捷函数：一步完成格式分发和导出。

    Args:
        result: ParseResult 或 LinkerParseResult
        format: 格式名称
        **kwargs: 传递给 ExportOptions 的其他参数

    Returns:
        导出内容的字符串

    Raises:
        ValueError: 未知格式
    """
    from uasset_read.exporter.base import ExportOptions

    options = ExportOptions(format=format, **kwargs)
    exporter = ExporterRegistry.get(format)
    return exporter.export(result, options)
