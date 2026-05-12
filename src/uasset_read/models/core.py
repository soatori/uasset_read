"""
核心 UE 蓝图数据模型 — 引脚、节点、图容器、成员引用。

等价覆盖 uasset_read.py 中第 1878-1971 行的数据类定义。
Per D-01: 保持 UE 源码命名。
Per D-06: 数据和序列化解耦，from_archive 为 stub。
Per D-10: Python 3.10+ 严格类型提示。
Per D-12: 静态 from_archive 方法（Phase 31 实现）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict, Self, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectImport, ObjectExport


@dataclass
class FEdGraphPinType:
    """蓝图引脚类型结构。"""
    pin_category: str = ""
    pin_subcategory: str = ""
    pin_subcategory_object: Optional[str] = None
    container_type: int = 0
    is_map_key: bool = False
    is_map_value: bool = False

    @classmethod
    def from_archive(
        cls,
        archive: FArchive,
        name_map: List[str],
        summary: PackageFileSummary
    ) -> Self:
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_ed_graph_pin_type
        return read_ed_graph_pin_type(archive, name_map, summary)


@dataclass
class UEdGraphPin:
    """UEdGraphPin 蓝图引脚完整结构。"""
    # PIN-01: 基础信息
    pin_id: str
    pin_name: str
    pin_tooltip: str = ""
    direction: int = 0
    # PIN-02: PinType
    pin_type: Optional[FEdGraphPinType] = None
    # PIN-03: 默认值
    default_value: Optional[str] = None
    auto_default_value: Optional[str] = None
    default_object: Optional[int] = None
    default_text_value: Optional[str] = None
    # PIN-04: 连接引用
    linked_to_raw: List[dict] = field(default_factory=list)
    sub_pins: List[dict] = field(default_factory=list)
    parent_pin: Optional[dict] = None
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

    @classmethod
    def from_archive(
        cls,
        archive: FArchive,
        name_map: List[str],
        summary: PackageFileSummary,
        export_map: List[ObjectExport],
        import_map: List[ObjectImport]
    ) -> Self:
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_ue_graph_pin
        return read_ue_graph_pin(archive, name_map, summary, export_map, import_map)


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

    @classmethod
    def from_archive(
        cls,
        archive: FArchive,
        name_map: List[str],
        summary: PackageFileSummary,
        export_map: List[ObjectExport],
        import_map: List[ObjectImport],
        node_export: ObjectExport
    ) -> Self:
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_ue_graph_node
        return read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export)


@dataclass
class UEdGraph:
    """UEdGraph 蓝图图容器。"""
    graph_name: str
    graph_class: str
    schema: Optional[str] = None
    nodes: List["UEdGraphNode"] = field(default_factory=list)
    graph_guid: Optional[str] = None
    b_editable: bool = True

    @classmethod
    def from_archive(
        cls,
        archive: FArchive,
        name_map: List[str],
        summary: PackageFileSummary,
        export_map: List[ObjectExport],
        import_map: List[ObjectImport],
        graph_export: ObjectExport,
        graph_class: str,
        graph_export_idx: int = 0
    ) -> Self:
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_ue_graph
        return read_ue_graph(archive, name_map, summary, export_map, import_map, graph_export, graph_class, graph_export_idx)


@dataclass
class FMemberReference:
    """FMemberReference 成员引用结构。"""
    member_parent: Optional[str] = None
    member_name: str = ""
    member_guid: Optional[str] = None
    b_self_context: bool = False

    @classmethod
    def from_archive(
        cls,
        archive: FArchive,
        name_map: List[str],
        import_map: List[ObjectImport],
        export_map: List[ObjectExport]
    ) -> Self:
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_fmember_reference
        return read_fmember_reference(archive, name_map, import_map, export_map)
