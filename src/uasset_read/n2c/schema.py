"""N2CStruct 数据模型 — N2C 中间格式的 core dataclass。

N2CPin / N2CNode / N2CGraph / N2CStruct 四层结构，
用于表示完整的 Blueprint graph 数据，支持 to_dict() JSON 序列化。

与 P69 N2CNodeDefinition.extra_data 键名对齐：
  member_name, member_parent, event_name, b_override, branch_type 等。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class N2CPin:
    """扁平化 Pin 信息，去除冗余字段。"""
    pin_name: str
    pin_category: str
    pin_subcategory: str = ""
    direction: str = "input"  # "input" 或 "output"
    default_value: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pin_name": self.pin_name,
            "pin_category": self.pin_category,
            "pin_subcategory": self.pin_subcategory,
            "direction": self.direction,
            "default_value": self.default_value,
        }


@dataclass
class N2CNode:
    """紧凑节点表示。

    extra_data 与 P69 N2CNodeDefinition.extra_data 键名对齐。
    """
    id: str
    type: str
    name: str
    comment: str = ""
    pure: bool = False
    latent: bool = False
    input_pins: List[N2CPin] = field(default_factory=list)
    output_pins: List[N2CPin] = field(default_factory=list)
    extra_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "comment": self.comment,
            "pure": self.pure,
            "latent": self.latent,
            "input_pins": [p.to_dict() for p in self.input_pins],
            "output_pins": [p.to_dict() for p in self.output_pins],
            "extra_data": dict(self.extra_data),
        }


@dataclass
class N2CGraph:
    """单图表示。

    graph_type 语义化类型对齐 GRAPH_TYPE_MAP（"event", "uber", "function", "macro" 等）。
    """
    name: str
    graph_type: str
    nodes: List[N2CNode] = field(default_factory=list)
    flows: Dict[str, Any] = field(default_factory=lambda: {
        "execution": [],
        "data": {},
    })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "graph_type": self.graph_type,
            "nodes": [n.to_dict() for n in self.nodes],
            "flows": dict(self.flows),
        }


@dataclass
class N2CStruct:
    """顶层输出容器。

    version: Schema 版本，初始 1.0.0
    metadata: Blueprint 元数据（Name, BlueprintType, BlueprintClass）
    graphs: 图列表
    structs: 结构体定义占位
    enums: 枚举定义占位
    """
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    graphs: List[N2CGraph] = field(default_factory=list)
    structs: List[Dict[str, Any]] = field(default_factory=list)
    enums: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "metadata": dict(self.metadata),
            "graphs": [g.to_dict() for g in self.graphs],
            "structs": list(self.structs),
            "enums": list(self.enums),
        }
