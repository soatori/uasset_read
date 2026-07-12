"""
序列化模型 — UE 蓝图引脚、节点、图容器、成员引用。

本模块定义的类是 UE 二进制格式的直接映射（序列化模型），用于
serializers 层从 archive 读取数据时构建实例。它们与 ir.py 中的
呈现模型（GraphIR / NodeIR / PinIR）形成清晰的分层：

- core.py 类：序列化层，保留 UE 原始类型（int 方向、FEdGraphPinType 嵌套对象等）
- ir.py 类：呈现层，面向渲染器的简化表示（str 方向、str 类型等）

IR Builder 负责从序列化模型转换为呈现模型。

Per D-01: 保持 UE 源码命名。
Per D-10: Python 3.10+ 严格类型提示。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.link.object_instance import UObjectInstance


@dataclass
class FEdGraphPinType:
    """蓝图引脚类型结构。"""
    pin_category: str = ""
    pin_subcategory: str = ""
    pin_subcategory_object: Optional[int] = None  # FPackageIndex (int32)
    pin_subcategory_object_name: Optional[str] = None
    pin_subcategory_object_ref: Optional["UObjectInstance"] = None
    container_type: int = 0
    is_map_key: bool = False
    is_map_value: bool = False
    is_reference: bool = False
    is_weak_pointer: bool = False
    is_const: bool = False
    is_uobject_wrapper: bool = False
    b_serialize_as_single_precision_float: bool = False
    # Map terminal 类型（container_type == 3 时，key 的 terminal 信息）
    map_key_terminal_category: str = ""
    map_key_terminal_sub_category: str = ""
    map_key_terminal_sub_category_object: Optional[int] = None  # FPackageIndex (int32)
    map_key_terminal_sub_category_object_name: Optional[str] = None


@dataclass
class UEdGraphPin:
    """UEdGraphPin 蓝图引脚完整结构。"""
    # PIN-01: 基础信息
    pin_id: str
    pin_name: str
    pin_friendly_name: Optional[str] = None
    pin_tooltip: str = ""
    direction: int = 0
    # PIN-02: PinType
    pin_type: Optional[FEdGraphPinType] = None
    # PIN-03: 默认值
    default_value: Optional[str] = None
    auto_default_value: Optional[str] = None
    default_object: Optional[int] = None
    default_object_ref: Optional["UObjectInstance"] = None  # D-04: linker 解析后的对象引用
    default_text_value: Optional[str] = None
    # PIN-04: 连接引用 — 原始 dict（保留兼容）
    linked_to_raw: List[dict] = field(default_factory=list)
    sub_pins: List[dict] = field(default_factory=list)
    parent_pin: Optional[dict] = None
    ref_pass_through: Optional[dict] = None
    # PIN-04+: 连接引用 — 解析后的 UObjectInstance（新增，linker 模式）
    linked_to_objects: List[Optional["UObjectInstance"]] = field(default_factory=list)
    sub_pins_objects: List[Optional["UObjectInstance"]] = field(default_factory=list)
    parent_pin_object: Optional["UObjectInstance"] = None
    ref_pass_through_object: Optional["UObjectInstance"] = None
    # PIN-05: 显示属性
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
    """UEdGraphNode 蓝图节点基类。"""
    node_guid: str
    node_pos_x: int = 0
    node_pos_y: int = 0
    node_comment: str = ""
    pins: List["UEdGraphPin"] = field(default_factory=list)
    class_name: str = ""
    node_data: Optional[Any] = None


@dataclass
class UEdGraph:
    """UEdGraph 蓝图图容器。"""
    graph_name: str
    graph_class: str
    schema: Optional[str] = None
    nodes: List["UEdGraphNode"] = field(default_factory=list)
    graph_guid: Optional[str] = None
    b_editable: bool = True
    subgraphs: List["UEdGraph"] = field(default_factory=list)


@dataclass
class FMemberReference:
    """FMemberReference 成员引用结构。"""
    member_parent: Optional[str] = None
    member_name: str = ""
    member_guid: Optional[str] = None
    b_self_context: bool = False
