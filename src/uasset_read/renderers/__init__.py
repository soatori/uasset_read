"""渲染器注册表 — 格式名到渲染器的映射与分发。

取代旧的 ExporterRegistry + FORMAT_REGISTRY。
"""
from __future__ import annotations

from typing import Type

from uasset_read.renderers.base import IRenderer

# 渲染器注册表（由具体渲染器模块 import 时自动注册）
RENDERER_REGISTRY: dict[str, Type[IRenderer]] = {}


def register_renderer(format_name: str, renderer_class: Type[IRenderer]) -> None:
    """注册一个格式名到渲染器类的映射。"""
    if format_name in RENDERER_REGISTRY:
        raise ValueError(f"Render format '{format_name}' is already registered")
    RENDERER_REGISTRY[format_name] = renderer_class


def get_renderer(format_name: str) -> IRenderer:
    """获取指定格式的渲染器实例。"""
    renderer_class = RENDERER_REGISTRY.get(format_name)
    if renderer_class is None:
        available = ", ".join(sorted(RENDERER_REGISTRY.keys()))
        raise ValueError(f"Unknown render format: '{format_name}'. Available: {available}")
    return renderer_class()


def list_formats() -> list[str]:
    """返回所有已注册的格式名。"""
    return sorted(RENDERER_REGISTRY.keys())


# 导入具体渲染器模块以触发注册
from uasset_read.renderers import json_renderer  # noqa: F401, E402
from uasset_read.renderers import markdown_renderer  # noqa: F401, E402
