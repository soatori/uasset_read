"""N2C 节点处理器抽象基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class N2CNodeProcessor(ABC):
    """节点处理器抽象基类。

    每种语义类型对应一个具体处理器子类，负责将 UEdGraphNode
    转换为 N2CNodeDefinition。
    """

    @property
    @abstractmethod
    def node_types(self) -> List[N2CNodeType]:
        """此处理器可处理的节点语义类型列表。"""
        ...

    @abstractmethod
    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        """处理节点，填充 definition 的 extra_data。

        Args:
            node: 原始 UEdGraphNode
            definition: 已创建的基本 N2CNodeDefinition，处理器应填充 extra_data
        """
        ...

    def can_process(self, node_type: N2CNodeType) -> bool:
        """检查此处理器是否可以处理给定节点类型。"""
        return node_type in self.node_types
