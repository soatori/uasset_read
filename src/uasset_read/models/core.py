"""
Serialization models — UE Blueprint pins, nodes, and graph containers.

The classes defined here are direct mappings of the UE binary format (serialization
models), used by the serializers layer to construct instances when reading data from
the archive. They preserve UE native types (int direction, nested FEdGraphPinType
objects, etc.).

The former presentation/IR layer (`models/ir.py` — GraphIR / NodeIR / PinIR — plus the
IR Builder and the renderer system) was removed together with the v1 pipeline; v2
consumes these serialization models directly from `src/uasset_read/models/`. Per D-01: Keep UE source naming.
Per D-10: Python 3.10+ strict type hints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FEdGraphPinType:
    """Blueprint pin type structure."""

    pin_category: str = ""
    container_type: int = 0
    is_reference: bool = False
    # FEdGraphTerminalType trailing bools (EdGraphNode.cpp operator<<;
    # map-key terminal only — value terminal category reads stay cursor-only)
    map_key_terminal_is_const: bool = False
    map_key_terminal_is_weak_pointer: bool = False
    map_key_terminal_is_uobject_wrapper: bool = False


@dataclass
class UEdGraphPin:
    """UEdGraphPin complete blueprint pin structure."""

    pin_id: str
    pin_name: str
    direction: int = 0
    pin_type: FEdGraphPinType | None = None
    linked_to_raw: list[dict] = field(default_factory=list)


@dataclass
class UEdGraphNode:
    """UEdGraphNode base class for blueprint nodes."""

    node_pos_x: int = 0
    node_pos_y: int = 0
    node_comment: str = ""
    pins: list["UEdGraphPin"] = field(default_factory=list)
    class_name: str = ""
    node_data: Any | None = None
    # Internal bookkeeping set during graph reading (1-based export index)
    _export_index: int | None = None


@dataclass
class UEdGraph:
    """UEdGraph blueprint graph container."""

    graph_name: str
    nodes: list["UEdGraphNode"] = field(default_factory=list)
    subgraphs: list["UEdGraph"] = field(default_factory=list)
