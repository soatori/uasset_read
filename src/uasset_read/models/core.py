"""
Serialization models — UE Blueprint pins, nodes, graph containers, member references.

The classes defined here are direct mappings of the UE binary format (serialization
models), used by the serializers layer to construct instances when reading data from
the archive. They form a clear layer separation from the presentation models in
ir.py (GraphIR / NodeIR / PinIR):

- core.py classes: serialization layer, preserving UE native types (int direction,
  FEdGraphPinType nested objects, etc.)
- ir.py classes: presentation layer, simplified representation for renderers
  (str direction, str type, etc.)

The IR Builder is responsible for converting serialization models to presentation models.

Per D-01: Keep UE source naming.
Per D-10: Python 3.10+ strict type hints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Any


@dataclass
class FEdGraphPinType:
    """Blueprint pin type structure."""

    pin_category: str = ""
    pin_subcategory: str = ""
    pin_subcategory_object: Optional[int] = None  # FPackageIndex (int32)
    pin_subcategory_object_name: Optional[str] = None
    pin_subcategory_object_ref: Optional[Any] = None
    container_type: int = 0
    is_map_key: bool = False
    is_map_value: bool = False
    is_reference: bool = False
    is_weak_pointer: bool = False
    is_const: bool = False
    is_uobject_wrapper: bool = False
    b_serialize_as_single_precision_float: bool = False
    # Map terminal type (when container_type == 3, key terminal info)
    map_key_terminal_category: str = ""
    map_key_terminal_sub_category: str = ""
    map_key_terminal_sub_category_object: Optional[int] = None  # FPackageIndex (int32)
    map_key_terminal_sub_category_object_name: Optional[str] = None
    # FEdGraphTerminalType trailing bools (EdGraphNode.cpp operator<<)
    map_key_terminal_is_const: bool = False
    map_key_terminal_is_weak_pointer: bool = False
    map_key_terminal_is_uobject_wrapper: bool = False


@dataclass
class UEdGraphPin:
    """UEdGraphPin complete blueprint pin structure."""

    # PIN-01: Basic information
    pin_id: str
    pin_name: str
    pin_friendly_name: Optional[str] = None
    pin_tooltip: str = ""
    direction: int = 0
    # PIN-02: PinType
    pin_type: Optional[FEdGraphPinType] = None
    # PIN-03: Default values
    default_value: Optional[str] = None
    auto_default_value: Optional[str] = None
    default_object: Optional[int] = None
    default_object_ref: Optional[Any] = None  # D-04: reserved for object-reference resolution (unused on the single-package path)
    default_text_value: Optional[str] = None
    # PIN-04: Link references — raw dict (backward compat)
    linked_to_raw: List[dict] = field(default_factory=list)
    sub_pins: List[dict] = field(default_factory=list)
    parent_pin: Optional[dict] = None
    ref_pass_through: Optional[dict] = None
    # PIN-04+: Link references — resolved object references
    linked_to_objects: List[Optional[Any]] = field(default_factory=list)
    sub_pins_objects: List[Optional[Any]] = field(default_factory=list)
    parent_pin_object: Optional[Any] = None
    ref_pass_through_object: Optional[Any] = None
    # PIN-05: Display attributes
    hidden: bool = False
    not_connectable: bool = False
    advanced_view: bool = False
    orphaned_pin: bool = False
    # EditorOnly
    owning_node_index: int = 0
    source_index: Optional[int] = None
    persistent_guid: Optional[str] = None
    # Legacy
    flags: int = 0


@dataclass
class UEdGraphNode:
    """UEdGraphNode base class for blueprint nodes."""

    node_guid: str
    node_pos_x: int = 0
    node_pos_y: int = 0
    node_comment: str = ""
    pins: List["UEdGraphPin"] = field(default_factory=list)
    class_name: str = ""
    node_data: Optional[Any] = None
    # Internal bookkeeping set during graph reading (1-based export index)
    _export_index: Optional[int] = None
    _export_object_name: Optional[str] = None


@dataclass
class UEdGraph:
    """UEdGraph blueprint graph container."""

    graph_name: str
    graph_class: str
    schema: Optional[str] = None
    nodes: List["UEdGraphNode"] = field(default_factory=list)
    graph_guid: Optional[str] = None
    b_editable: bool = True
    subgraphs: List["UEdGraph"] = field(default_factory=list)


@dataclass
class FMemberReference:
    """FMemberReference member reference structure."""

    member_parent: Optional[str] = None
    member_name: str = ""
    member_guid: Optional[str] = None
    b_self_context: bool = False
