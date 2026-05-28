"""EdGraphNode_Comment 处理器 — 提取注释框信息。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class CommentProcessor(N2CNodeProcessor):
    """处理 EdGraphNode_Comment 类型节点。

    提取: CommentText, NodeWidth, NodeHeight, CommentColor, FontSize, CommentDepth。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.Comment]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if node.node_data is None:
            return

        data = node.node_data
        if not isinstance(data, dict):
            return

        # 提取注释文本
        comment_text = data.get("NodeComment", data.get("comment_text", ""))
        if comment_text:
            definition.extra_data["comment_text"] = comment_text

        # 提取尺寸
        for key in ("NodeWidth", "NodeHeight"):
            if key in data:
                definition.extra_data[key.lower()] = data[key]

        # 提取颜色、字体、深度
        for pascal_key, snake_key in (
            ("CommentColor", "comment_color"),
            ("FontSize", "font_size"),
            ("CommentDepth", "comment_depth"),
        ):
            if pascal_key in data:
                definition.extra_data[snake_key] = data[pascal_key]
            elif snake_key in data:
                definition.extra_data[snake_key] = data[snake_key]
