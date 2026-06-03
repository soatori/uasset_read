"""渲染器基础 — IRenderer ABC + RenderOptions。

渲染器只接收 PackageIR，不访问 ParseResult。
渲染器不做数据转换（GUID 格式化等在 IR 构建时完成）。
渲染器不拼接业务逻辑，只负责格式排版。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


@dataclass
class RenderOptions:
    """渲染选项（渲染器只读，不修改）。"""
    verbose: bool = False
    indent: int = 2
    include_schema: bool = False
    include_function_graphs: bool = False
    linker_result: Any = None  # LinkerParseResult，供需要 linker 数据的格式使用


class IRenderer(ABC):
    """渲染器抽象基类。"""

    @abstractmethod
    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        """将 IR 渲染为字符串。

        Args:
            ir: PackageIR 实例
            options: 渲染选项

        Returns:
            渲染后的字符串
        """
        ...

    @property
    @abstractmethod
    def format_name(self) -> str:
        """此渲染器处理的格式名称。"""
        ...