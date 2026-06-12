"""
核心 UE 蓝图数据模型 — 引脚、节点、图容器、成员引用。

等价覆盖 uasset_read.py 中第 1878-1971 行的数据类定义。
Per D-01: 保持 UE 源码命名。
Per D-06: 数据和序列化解耦，from_archive 为 stub。
Per D-10: Python 3.10+ 严格类型提示。
Per D-12: 静态 from_archive 方法。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.archive import FArchive
    from uasset_read.serializers.package_summary import PackageFileSummary
    from uasset_read.serializers.object_resources import ObjectImport, ObjectExport
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

    @classmethod
    def from_archive(
        cls,
        archive: FArchive,
        name_map: List[str],
        summary: PackageFileSummary
    ) -> "FEdGraphPinType":
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_ed_graph_pin_type
        return read_ed_graph_pin_type(archive, name_map, summary)


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

    @classmethod
    def from_archive(
        cls,
        archive: FArchive,
        name_map: List[str],
        summary: PackageFileSummary,
        export_map: List[ObjectExport],
        import_map: List[ObjectImport]
    ) -> "UEdGraphPin":
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_ue_graph_pin
        return read_ue_graph_pin(archive, name_map, summary, export_map, import_map)

    @classmethod
    def from_archive_with_linker(
        cls,
        archive: FArchive,
        name_map: List[str],
        summary: PackageFileSummary,
        export_map: List[ObjectExport],
        import_map: List[ObjectImport],
        linker: Optional["PackageLinker"] = None,
    ) -> "UEdGraphPin":
        """带 linker 的读取入口，支持 PackageIndex → UObjectInstance 解析（D-09）。"""
        from uasset_read.serializers.graph import read_ue_graph_pin
        from uasset_read.serializers.object_resources import PackageIndex
        pin = read_ue_graph_pin(archive, name_map, summary, export_map, import_map, linker)
        # D-04: 解析 default_object 为 UObjectInstance
        if linker is not None and pin.default_object is not None and pin.default_object != 0:
            try:
                pin.default_object_ref = linker.resolve_package_index(PackageIndex(pin.default_object))
            except Exception:
                pin.default_object_ref = None  # D-06: 解析失败存 None
        return pin


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
    ) -> "UEdGraphNode":
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_ue_graph_node
        return read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export)

    @classmethod
    def from_archive_with_linker(
        cls,
        archive: FArchive,
        name_map: List[str],
        summary: PackageFileSummary,
        export_map: List[ObjectExport],
        import_map: List[ObjectImport],
        node_export: ObjectExport,
        linker: Optional["PackageLinker"] = None,
    ) -> "UEdGraphNode":
        """带 linker 的读取入口（D-09）。"""
        from uasset_read.serializers.graph import read_ue_graph_node
        return read_ue_graph_node(archive, name_map, summary, export_map, import_map, node_export, linker)


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
    ) -> "UEdGraph":
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_ue_graph
        return read_ue_graph(archive, name_map, summary, export_map, import_map, graph_export, graph_class, graph_export_idx)

    @classmethod
    def from_archive_with_linker(
        cls,
        archive: FArchive,
        name_map: List[str],
        summary: PackageFileSummary,
        export_map: List[ObjectExport],
        import_map: List[ObjectImport],
        graph_export: ObjectExport,
        graph_class: str,
        graph_export_idx: int = 0,
        linker: Optional["PackageLinker"] = None,
    ) -> "UEdGraph":
        """带 linker 的读取入口（D-09）。"""
        from uasset_read.serializers.graph import read_ue_graph
        return read_ue_graph(archive, name_map, summary, export_map, import_map, graph_export, graph_class, graph_export_idx, linker)


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
    ) -> "FMemberReference":
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_fmember_reference
        return read_fmember_reference(archive, name_map, import_map, export_map)
