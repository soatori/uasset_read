"""渲染器基础 — IRenderer ABC + RenderOptions。

渲染器只接收 PackageIR，不访问 ParseResult。
渲染器不做数据转换（GUID 格式化等在 IR 构建时完成）。
渲染器不拼接业务逻辑，只负责格式排版。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


# ── 渲染器共享常量 ──
# 以下是各渲染器共用的过滤列表，统一定义于此。

# 编辑器布局属性（不影响运行时和 C++ 翻译）
EDITOR_PROPERTY_NAMES = frozenset({
    # 节点布局
    "NodePosX", "NodePosY", "NodeWidth", "NodeHeight",
    "NodeGuid", "NodeComment", "bIsCommentBubbleVisible",
    # 注释相关
    "CommentColor", "FontSize",
    "bCommentBubbleVisible_InDetailsPanel",
    "bCommentBubblePinned", "bCommentBubbleVisible",
    # 图相关
    "Schema", "GraphGuid", "ErrorType",
    "AdvancedPinDisplay", "MoveMode",
    # 事件/函数引用（已提取到其他字段）
    "EventReference", "bOverrideFunction",
})

# 编辑器内部变量（不影响运行时和 C++ 翻译）
EDITOR_VARIABLE_NAMES = frozenset({
    "UbergraphPages",  # 图页面索引列表
    "FunctionGraphs",  # 函数图索引列表
    "CategorySorting",  # 编辑器分类排序
    "ImplementedInterfaces",  # 已实现接口（已在 blueprint.interfaces 中）
    "LastEditedDocuments",  # 最后编辑文档
    "ThumbnailInfo",  # 缩略图信息
    "bLegacyNeedToPurgeSkelRefs",  # 骨骼引用清理标记
})

# 编辑器内部节点类（不影响运行时，UE 编译时移除）
EDITOR_NODE_CLASSES = frozenset({
    "K2Node_Knot",  # 重定向节点，仅编辑器布局用途
})


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
