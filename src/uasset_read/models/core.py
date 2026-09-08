"""
Serialization models — UE Blueprint pins, nodes, graph containers, member references.

The classes defined here are direct mappings of the UE binary format (serialization
models), used by the serializers layer to construct instances when reading data from
the archive. They preserve UE native types (int direction, nested FEdGraphPinType
objects, etc.).

The former presentation/IR layer (`models/ir.py` — GraphIR / NodeIR / PinIR — plus the
IR Builder and the renderer system) was removed together with the v1 pipeline; v2
consumes these serialization models directly from `src/uasset_read/models/`. Animation IR
is the one surviving IR-style layer and lives in `models/ir_anim.py`.

Per D-01: Keep UE source naming.
Per D-10: Python 3.10+ strict type hints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

@dataclass
class FEdGraphPinType:
    """Blueprint pin type structure."""

    pin_category: str = ""
    pin_subcategory: str = ""
    pin_subcategory_object: int | None = None  # FPackageIndex (int32)
    pin_subcategory_object_name: str | None = None
    pin_subcategory_object_ref: Any | None = None
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
    map_key_terminal_sub_category_object: int | None = None  # FPackageIndex (int32)
    map_key_terminal_sub_category_object_name: str | None = None
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
    pin_friendly_name: str | None = None
    pin_tooltip: str = ""
    direction: int = 0
    # PIN-02: PinType
    pin_type: FEdGraphPinType | None = None
    # PIN-03: Default values
    default_value: str | None = None
    auto_default_value: str | None = None
    default_object: int | None = None
    default_object_ref: Any | None = (
        None  # D-04: reserved for object-reference resolution (unused on the single-package path)
    )
    default_text_value: str | None = None
    # PIN-04: Link references — raw dict (backward compat)
    linked_to_raw: list[dict] = field(default_factory=list)
    sub_pins: list[dict] = field(default_factory=list)
    parent_pin: dict | None = None
    ref_pass_through: dict | None = None
    # PIN-04+: Link references — resolved object references
    linked_to_objects: list[Any | None] = field(default_factory=list)
    sub_pins_objects: list[Any | None] = field(default_factory=list)
    parent_pin_object: Any | None = None
    ref_pass_through_object: Any | None = None
    # PIN-05: Display attributes
    hidden: bool = False
    not_connectable: bool = False
    advanced_view: bool = False
    orphaned_pin: bool = False
    # EditorOnly
    owning_node_index: int = 0
    source_index: int | None = None
    persistent_guid: str | None = None
    # Legacy
    flags: int = 0


@dataclass
class UEdGraphNode:
    """UEdGraphNode base class for blueprint nodes."""

    node_guid: str
    node_pos_x: int = 0
    node_pos_y: int = 0
    node_comment: str = ""
    pins: list["UEdGraphPin"] = field(default_factory=list)
    class_name: str = ""
    node_data: Any | None = None
    # Internal bookkeeping set during graph reading (1-based export index)
    _export_index: int | None = None
    _export_object_name: str | None = None


@dataclass
class UEdGraph:
    """UEdGraph blueprint graph container."""

    graph_name: str
    graph_class: str
    schema: str | None = None
    nodes: list["UEdGraphNode"] = field(default_factory=list)
    graph_guid: str | None = None
    b_editable: bool = True
    subgraphs: list["UEdGraph"] = field(default_factory=list)


@dataclass
class FMemberReference:
    """FMemberReference member reference structure."""

    member_parent: str | None = None
    member_name: str = ""
    member_guid: str | None = None
    b_self_context: bool = False
