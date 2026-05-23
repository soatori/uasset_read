"""Fallback 处理器 — 处理未知类型的默认回退。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition

logger = logging.getLogger(__name__)


class FallbackProcessor(N2CNodeProcessor):
    """默认回退处理器，处理所有未注册类型。

    通过 set_fallback() 注册，不通过 register() 注册。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return []  # 空列表 — 通过 set_fallback() 注册

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        logger.warning(
            "Fallback processing for unknown type: %s", node.class_name
        )
        definition.extra_data["fallback"] = True
        definition.extra_data["original_class_name"] = node.class_name
