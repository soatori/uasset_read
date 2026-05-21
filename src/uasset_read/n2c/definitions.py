"""N2C 节点定义 — 语义化节点数据结构。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from uasset_read.n2c.node_types import N2CNodeType


@dataclass
class N2CNodeDefinition:
    """语义化节点定义。

    从 UEdGraphNode 转换而来的中间格式表示，包含节点的语义类型、
    引脚信息和附加数据。
    """
    node_id: str
    node_type: N2CNodeType
    position: Tuple[int, int]
    comment: str = ""
    input_pins: List[Dict] = field(default_factory=list)
    output_pins: List[Dict] = field(default_factory=list)
    extra_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于 JSON 序列化。

        extra_data 中的键会合并到输出字典中。
        """
        result: Dict[str, Any] = {
            "node_name": self.node_id,
            "node_type": self.node_type.value if isinstance(self.node_type, N2CNodeType) else self.node_type,
            "position": {"x": self.position[0], "y": self.position[1]},
            "node_comment": self.comment,
            "pins": self.input_pins + self.output_pins,
        }
        result.update(self.extra_data)
        return result
