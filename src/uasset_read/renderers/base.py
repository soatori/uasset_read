"""渲染器基础 — IRenderer ABC + RenderOptions。

渲染器只接收 PackageIR，不访问 ParseResult。
渲染器不做数据转换（GUID 格式化等在 IR 构建时完成）。
渲染器不拼接业务逻辑，只负责格式排版。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def is_blueprint_export(export: ExportIR) -> bool:
    """判断是否为蓝图相关 export。

    蓝图 export 定义：
    - 类名以 _C 结尾（如 BP_Character_C）
    - 或有 graphs 数据
    """
    if export.object_name.endswith("_C"):
        return True
    if export.graphs:
        return True
    return False


@dataclass
class RenderOptions:
    """渲染选项（渲染器只读，不修改）。"""
    verbose: bool = False
    indent: int = 2
    include_schema: bool = False
    include_function_graphs: bool = False
    linker_result: Any = None  # LinkerParseResult，供需要 linker 数据的格式使用
    output_level: str = "standard"  # "standard"（默认，过滤 UI/空字段）或 "debug"（完整输出）
    hex_view: bool = False  # 输出 HexView 解析轨迹数据


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