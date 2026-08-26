"""渲染器基础 — 共享常量、工具函数、RenderOptions。

渲染器只接收 PackageIR，不访问 ParseResult。
渲染器不做数据转换（GUID 格式化等在 IR 构建时完成）。
渲染器不拼接业务逻辑，只负责格式排版。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import ExportIR


# ── 渲染器共享常量 ──
# 以下是各渲染器共用的过滤列表，统一定义于此。

# 编辑器布局属性（不影响运行时和 C++ 翻译）
EDITOR_PROPERTY_NAMES = frozenset(
    {
        # 节点布局
        "NodePosX",
        "NodePosY",
        "NodeWidth",
        "NodeHeight",
        "NodeGuid",
        "NodeComment",
        "bIsCommentBubbleVisible",
        # 注释相关
        "CommentColor",
        "FontSize",
        "bCommentBubbleVisible_InDetailsPanel",
        "bCommentBubblePinned",
        "bCommentBubbleVisible",
        # 图相关
        "Schema",
        "GraphGuid",
        "ErrorType",
        "AdvancedPinDisplay",
        "MoveMode",
        # 事件/函数引用（已提取到其他字段）
        "EventReference",
        "bOverrideFunction",
    }
)

# 编辑器内部变量（不影响运行时和 C++ 翻译）
EDITOR_VARIABLE_NAMES = frozenset(
    {
        "UbergraphPages",  # 图页面索引列表
        "FunctionGraphs",  # 函数图索引列表
        "CategorySorting",  # 编辑器分类排序
        "ImplementedInterfaces",  # 已实现接口（已在 blueprint.interfaces 中）
        "LastEditedDocuments",  # 最后编辑文档
        "ThumbnailInfo",  # 缩略图信息
        "bLegacyNeedToPurgeSkelRefs",  # 骨骼引用清理标记
    }
)

# 编辑器内部节点类（不影响运行时，UE 编译时移除）
EDITOR_NODE_CLASSES = frozenset(
    {
        "K2Node_Knot",  # 重定向节点，仅编辑器布局用途
    }
)


def filter_editor_items(
    items: list,
    class_field: str = "object_class",
    exclude_classes: frozenset = EDITOR_NODE_CLASSES,
) -> list:
    """过滤编辑器专用项（供渲染器共用）。"""
    return [item for item in items if getattr(item, class_field, None) not in exclude_classes]


def filter_variables(
    variables: list,
    exclude_names: frozenset = EDITOR_VARIABLE_NAMES,
) -> list:
    """过滤编辑器内部变量（供渲染器共用）。"""
    return [v for v in variables if v.name not in exclude_names]


def is_blueprint_export(export: ExportIR) -> bool:
    """判断是否为蓝图相关 export。

    蓝图 export 定义：
    - 类名以 _C 结尾（如 BP_Character_C）
    - 或有 graphs 数据
    """
    if getattr(export, "object_name", None) is not None and export.object_name.endswith("_C"):
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
    output_level: str = "standard"  # "standard"（默认，过滤 UI/空字段）或 "debug"（完整输出）
    hex_view: bool = False  # 输出 HexView 解析轨迹数据

    def __post_init__(self) -> None:
        _valid = {"standard", "debug"}
        if self.output_level not in _valid:
            raise ValueError(f"Invalid output_level: {self.output_level!r}. Expected one of ['standard', 'debug']")
